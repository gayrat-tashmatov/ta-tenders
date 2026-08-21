"""
Telegram-доставка: короткая карточка + кнопки «Разбор на сайте» и «Источник».

Принципы (из uz-monitor-v2): parse_mode=HTML (экранируем только < > &),
превью выключено, паузы под лимит 20 сообщений/мин, обработка 429.
Бот здесь — канал дистрибуции: подробности живут на сайте.
"""

import re
import html
import json
import time
import logging
import requests

import config
import dedupe

log = logging.getLogger("notify")
API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"
SEND_GAP = 3.2


def esc(s) -> str:
    return html.escape(str(s or ""))


def _send(text: str, buttons=None) -> bool:
    """buttons — список (label, url)."""
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT):
        log.warning("Telegram: нет токена/чата — пропуск отправки")
        return False
    payload = {
        "chat_id": config.TELEGRAM_CHAT,
        "text": text[:4096],
        "parse_mode": "HTML",
        "link_preview_options": '{"is_disabled": true}',
    }
    if buttons:
        payload["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": b[0], "url": b[1]} for b in buttons]]})
    for _ in range(2):
        try:
            r = requests.post(f"{API}/sendMessage", data=payload, timeout=20)
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 5)
                log.warning("Telegram 429 — ждём %ss", wait)
                time.sleep(wait + 1)
                continue
            ok = r.json().get("ok", False)
            if not ok:
                log.warning("Telegram error: %s", r.text[:200])
            return ok
        except Exception as e:
            log.warning("Telegram send FAIL: %s", e)
            time.sleep(2)
    return False


def _send_long(text: str, buttons=None) -> bool:
    if len(text) <= 3900:
        return _send(text, buttons)
    parts, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > 3900:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    ok = True
    for i, part in enumerate(parts):
        ok = _send(part, buttons if i == len(parts) - 1 else None) and ok
        time.sleep(1.3)
    return ok


# ─────────────────────────── Оформление ───────────────────────────
_ICON = {config.CAT_INTL: "🌍", config.CAT_UZTEND: "🇺🇿", config.CAT_LAW: "⚖️",
         config.CAT_NEWS: "📰", config.CAT_JOB: "🧑‍💼"}


def _strip_tag(t) -> str:
    return re.sub(r"^\[[^\]]+\]\s*", "", str(t or "")).strip()


def _trim(s, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",.;:—-") + "…"


def _short_date(d):
    if not d:
        return None
    s = str(d)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    m = re.search(r"\b(\d{2})[.\-/](\d{2})[.\-/](\d{4})\b", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return None


def _headline(item: dict, a: dict) -> str:
    t = a.get("title_ru")
    if t and len(str(t).strip()) >= 6:
        return _trim(t, 150)
    raw = _strip_tag(item["title"])
    return _trim(raw, 150)


def _buttons(item: dict) -> list:
    btns = []
    if config.SITE_BASE_URL:
        slug = dedupe.item_slug(item)
        btns.append(("Разбор в кабинете", f"{config.SITE_BASE_URL}/t/{slug}"))
    meta = item.get("meta") or {}
    if meta.get("portal_only"):
        num = str(meta.get("number") or "")[:25]
        btns.append((f"Портал · лот № {num}" if num else "Портал ↗", item["url"]))
    elif item.get("origin") == "TenderWeek":
        btns.append(("TenderWeek (нужен вход) ↗", item["url"]))
    else:
        btns.append(("Источник ↗", item["url"]))
    return btns


def card(item: dict, a: dict) -> tuple:
    """Структурная карточка: с первого взгляда понятно КТО объявил, ЧТО нужно,
    ЗАЧЕМ это нам, СРОКИ и ЧТО ДЕЛАТЬ. Детали — в кабинете."""
    head = _headline(item, a)
    cat = item["category"]
    kind = {config.CAT_INTL: "Международный тендер", config.CAT_UZTEND: "Тендер · Узбекистан",
            config.CAT_LAW: "Новый НПА", config.CAT_JOB: "Позиция эксперта"}.get(cat, "Материал")
    lines = [f"{_ICON.get(cat, '•')} <b>{esc(head)}</b>",
             f"<i>{esc(kind)} · {esc(item['origin'])}</i>", ""]

    # КТО и ЧТО
    who = a.get("target_entity")
    if who:
        lines.append(f"<b>Кто:</b> {esc(_trim(who, 90))}")
    what = a.get("summary_ru")
    if what:
        lines.append(f"<b>Что нужно:</b> {esc(_trim(what, 420))}")

    # СРОКИ и ДЕНЬГИ — одной строкой
    facts = []
    dl = _short_date(a.get("deadline_info") or item.get("meta", {}).get("deadline"))
    if dl:
        facts.append(f"⏳ до {dl}")
    if a.get("budget_info"):
        facts.append(f"💰 {esc(_trim(a['budget_info'], 50))}")
    urg = (a.get("urgency") or "").lower()
    if urg in ("критическая", "высокая"):
        facts.append("🔥 срочно")
    if facts:
        lines.append(" · ".join(facts))

    # ЗАЧЕМ НАМ и ЧТО ДЕЛАТЬ
    rec = a.get("consulting_recommendation")
    if rec and rec != "Изучить условия":
        lines.append(f"\n<b>Зачем нам:</b> {esc(_trim(rec, 260))}")
    elig = a.get("eligibility")
    if elig:
        lines.append(f"<b>Требования:</b> {esc(_trim(elig, 200))}")
    steps = [x for x in (a.get("action_items") or []) if x][:2]
    if steps:
        lines.append("<b>Что делать:</b> " + " → ".join(esc(_trim(x, 110)) for x in steps))

    score = a.get("relevance_score") or item.get("score")
    if score:
        lines.append(f"\n<i>релевантность {esc(score)}/10</i>")
    return "\n".join(lines), _buttons(item)


def digest(rows: list, category: str) -> str:
    lines = [f"{config.CATEGORY_TITLE[category]}  ·  {len(rows)}", ""]
    for row in rows:
        it, a = row["item"], row["analysis"]
        head = a.get("title_ru") or _strip_tag(it["title"])
        lines.append(f"📌 <a href=\"{esc(it['url'])}\"><b>{esc(_trim(head, 200))}</b></a>")
        s = a.get("summary_ru")
        if s and s.strip()[:20].lower() not in head.lower():
            lines.append(esc(_trim(s, 300)))
        lines.append("")
    return "\n".join(lines).rstrip()


# ─────────────────────────── Публичный API ───────────────────────────
def send_report(processed: list) -> int:
    """processed — [{item, score, analysis}]. Возвращает число отправленных сообщений."""
    if not processed:
        _send("🟢 <b>TA Tenders</b>\nНовых релевантных материалов не найдено.")
        return 0

    cat_of = lambda p: p["item"]["category"]
    by_score = lambda p: -(p["analysis"].get("relevance_score") or p.get("score") or 0)
    tenders_law = [p for p in processed
                   if cat_of(p) in (config.CAT_INTL, config.CAT_UZTEND, config.CAT_LAW)]
    jobs = sorted([p for p in processed if cat_of(p) == config.CAT_JOB], key=by_score)
    news = sorted([p for p in processed if cat_of(p) == config.CAT_NEWS], key=by_score)

    header = (f"🔔 <b>TA Tenders</b> — {time.strftime('%d.%m.%Y')}\n"
              f"Тендеры/НПА: <b>{len(tenders_law)}</b> · Позиции: <b>{len(jobs)}</b> · "
              f"Новости: <b>{len(news)}</b>")
    hdr_btn = [("Все тендеры на сайте", config.SITE_BASE_URL)] if config.SITE_BASE_URL else None
    _send(header, hdr_btn)
    time.sleep(SEND_GAP)

    sent = 0
    order = {config.CAT_INTL: 0, config.CAT_UZTEND: 1, config.CAT_LAW: 2}
    for p in sorted(tenders_law, key=lambda x: (order.get(cat_of(x), 9), by_score(x))):
        text, buttons = card(p["item"], p["analysis"])
        if _send(text, buttons):
            sent += 1
        time.sleep(SEND_GAP)

    if jobs:
        if _send_long(digest(jobs, config.CAT_JOB)):
            sent += 1
        time.sleep(SEND_GAP)
    if news:
        if _send_long(digest(news, config.CAT_NEWS)):
            sent += 1
    return sent


def send_insight(insight: dict) -> bool:
    """Анонс нового аналитического дайджеста с кнопкой на сайт."""
    text = (f"📊 <b>{esc(insight.get('title', 'Регуляторный дайджест'))}</b>\n\n"
            f"{esc(_trim(insight.get('lead', ''), 500))}")
    buttons = []
    if config.SITE_BASE_URL and insight.get("id"):
        buttons.append(("Читать разбор", f"{config.SITE_BASE_URL}/analytics/{insight['id']}"))
    return _send(text, buttons or None)


def send_test() -> bool:
    return _send("✅ <b>TA Tenders</b> — тест связи. HTML работает: "
                 "&lt;цена&gt; 1.000.000 сум (100%).")
