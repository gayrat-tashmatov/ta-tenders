"""
Дедупликация v3 — главное отличие от uz-monitor-v2.

Три уровня:
  1. Вечный seen по стабильным ключам: uid источника → канонический URL → контент-хеш.
     Для тендеров и НПА записи НЕ протухают (в v2 чистились через 90 дней — отсюда повторы).
  2. Реестр НПА по реквизиту акта (ЗРУ-1137, УП-60, ПП-394, ПКМ-…): один акт = одна
     карточка НАВСЕГДА, независимо от того, каким URL он пришёл (lex.uz, Norma, СМИ).
     Новость про уже известный акт становится «упоминанием» карточки, а не новой записью.
  3. Семантический дедуп против ИСТОРИИ (окно NEAR_DUP_DAYS), а не только внутри
     одного запуска, как было в v2.
"""

import re
import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import config

_TRACKING = re.compile(r"^(utm_|gclid|fbclid|yclid|_ga|mc_|ref$|source$)", re.I)

# ─────────────────────────── Канонизация URL и хеши ───────────────────────────


def canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        s = urlsplit(url.strip())
        host = (s.hostname or "").lower()
        host = host[4:] if host.startswith("www.") else host
        q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=False)
             if not _TRACKING.match(k)]
        q.sort()
        return urlunsplit((s.scheme.lower() or "https", host, s.path.rstrip("/"),
                           urlencode(q), ""))
    except Exception:
        return url.strip()


def url_hash(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:24]


def content_hash(title: str, body: str) -> str:
    norm = re.sub(r"\s+", " ", f"{title} {body}".lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


def item_slug(item: dict) -> str:
    """Стабильный ID записи (он же слаг страницы на сайте)."""
    if item.get("uid"):
        return re.sub(r"[^a-z0-9]+", "-", item["uid"].lower()).strip("-")
    return "u-" + url_hash(item.get("url", "")) [:16]


# ─────────────────────────── Реквизиты НПА ───────────────────────────
# Типы актов Узбекистана. Разные написания (кириллица RU/UZ, латиница) → один ключ.
_NPA_TYPE_MAP = {
    "зру": "ZRU", "zru": "ZRU", "ўрқ": "ZRU", "orq": "ZRU", "o'rq": "ZRU",
    "уп": "UP", "пф": "UP", "pf": "UP", "up": "UP",          # указ президента
    "пп": "PP", "пқ": "PP", "pq": "PP", "pp": "PP",          # постановление президента
    "пкм": "PKM", "вмқ": "PKM", "vmq": "PKM", "pkm": "PKM",  # постановление кабмина
}
_NPA_TYPE_TITLE = {"ZRU": "Закон", "UP": "Указ Президента",
                   "PP": "Постановление Президента", "PKM": "Постановление Кабмина"}

_NPA_RE = re.compile(
    r"\b(ЗРУ|ЎРҚ|ORQ|O['ʻ’‘`´]RQ|ZRU|УП|ПФ|UP|PF|ПП|ПҚ|PP|PQ|ПКМ|ВМҚ|PKM|VMQ)"
    r"\s*[-–—]?\s*№?\s*(\d{1,5})\b", re.I | re.U)
_LEX_RE = re.compile(r"lex\.uz/(?:ru/|uz/|acts?/)?docs?/(-?\d+)", re.I)


def npa_type_title(key: str) -> str:
    return _NPA_TYPE_TITLE.get(key.split("-")[0], "НПА")


def extract_npa_refs(*texts) -> list:
    """Все реквизиты актов из текстов → нормализованные ключи ('ZRU-1137', 'PP-394').
    Ссылки lex.uz дают ключ 'LEX-<id>'."""
    blob = " ".join(t for t in texts if t)
    keys = []
    for typ, num in _NPA_RE.findall(blob):
        norm = typ.lower()
        for ap in ("ʻ", "’", "‘", "`", "´"):
            norm = norm.replace(ap, "'")
        t = _NPA_TYPE_MAP.get(norm)
        if t:
            k = f"{t}-{int(num)}"
            if k not in keys:
                keys.append(k)
    for doc_id in _LEX_RE.findall(blob):
        k = f"LEX-{doc_id.lstrip('-')}"     # в URL id бывает со знаком минус
        if k not in keys:
            keys.append(k)
    return keys


# ─────────────────────────── Семантическая близость ───────────────────────────
_STOP = set("и в во на по за из от до для с со о об к у не что как это же бы или а но the a an of "
            "in on for and to при уз узбекистан узбекистана республике республики года году млн млрд "
            "сум сумов тыс долларов сша".split())


def tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-zа-яё0-9]+", (s or "").lower())
            if len(w) > 3 and w not in _STOP}


def tokens_str(item: dict) -> str:
    return " ".join(sorted(tokens(f"{item.get('title', '')} {item.get('summary', '')[:250]}")))


def overlap(a: set, b: set) -> float:
    """|A∩B| / min(|A|,|B|) — ловит одну тему в разных формулировках."""
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def is_near_dup(item: dict, history: list, thr: float = 0.45) -> bool:
    """history — [(category, toks_str)] за последние NEAR_DUP_DAYS дней.
    Новости сверяем и с новостями, и с НПА (законодательная новость ≈ сам акт)."""
    toks = tokens(f"{item.get('title', '')} {item.get('summary', '')[:250]}")
    if len(toks) < 3:
        return False
    cat = item["category"]
    comparable = {cat}
    if cat == config.CAT_NEWS:
        comparable.add(config.CAT_LAW)
    for h_cat, h_toks in history:
        if h_cat not in comparable:
            continue
        if overlap(toks, set(h_toks.split())) >= thr:
            return True
    return False


def dedup_within_run(items: list, thr: float = 0.45) -> list:
    """Дубли внутри одного запуска (одна тема из разных СМИ) — оставляем лучший score."""
    kept = []
    for it in sorted(items, key=lambda x: -x.get("score", 0)):
        toks = tokens(f"{it.get('title', '')} {it.get('summary', '')[:250]}")
        if len(toks) >= 3 and any(k["category"] == it["category"]
                                  and overlap(toks, k["_toks"]) >= thr for k in kept):
            continue
        it["_toks"] = toks
        kept.append(it)
    for it in kept:
        it.pop("_toks", None)
    return kept


# ─────────────────────────── Товарные закупки — не наш профиль ───────────────────────────
def is_goods_procurement(item: dict) -> bool:
    """True, если это закупка товаров/оборудования без услуговой составляющей."""
    if item.get("category") not in (config.CAT_UZTEND, config.CAT_INTL):
        return False
    title = (item.get("title") or "").lower()
    if any(k in title for k in config.SERVICE_KEYWORDS):
        return False
    return any(k in title for k in config.GOODS_KEYWORDS)


def is_off_region(item: dict) -> bool:
    """Международное извещение про чужую страну (Африка, ЛатАм, ЮВА…) без нашей."""
    if item.get("category") != config.CAT_INTL:
        return False
    blob = f"{item.get('title','')} {item.get('summary','')[:600]}".lower()
    ours = any(k in blob for k in config.REGION_KEYWORDS)
    if ours:
        return False
    return any(k in blob for k in config.OFFREGION_KEYWORDS)
