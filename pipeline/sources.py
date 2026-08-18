"""
Сборщики источников. Каждый возвращает список нормализованных элементов (dict):
  source, category, origin, title, url, published(datetime|None),
  summary, full_text, meta(dict), uid(str|None — стабильный ID у первоисточника)

uid — основа вечного дедупа: "wb:OP00461411", "tw:36300", "lexuz:123456".
Каждый источник изолирован (try/except + лог числа собранных элементов).
"""

import re
import logging
from datetime import datetime, timezone

import requests
import feedparser
from bs4 import BeautifulSoup

import config

log = logging.getLogger("sources")


# ─────────────────────────── helpers ───────────────────────────
def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(config.HTTP_HEADERS)
    return s


def strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(text, "lxml").get_text(" ")).strip()


def _mk(source, category, origin, title, url, published=None,
        summary="", full_text="", meta=None, uid=None) -> dict:
    return {
        "source": source, "category": category, "origin": origin,
        "title": (title or "").strip()[:300], "url": url,
        "published": published, "summary": (summary or "")[:1500],
        "full_text": (full_text or summary or "")[:6000],
        "meta": meta or {}, "uid": uid,
    }


def _parse_rss_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _region_match(*texts) -> bool:
    blob = " ".join(t for t in texts if t).lower()
    return any(k in blob for k in config.REGION_KEYWORDS)


# ─────────────────────────── 1. World Bank Procurement API ───────────────────────────
def fetch_worldbank(rows: int = 60) -> list:
    items = []
    try:
        r = requests.get(
            config.WB_API_URL,
            params={"format": "json", "rows": rows, "fl": config.WB_API_FIELDS,
                    "project_ctry_name_exact": "Uzbekistan",
                    "srt": "noticedate", "order": "desc"},
            headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        for n in r.json().get("procnotices", []):
            ntype = n.get("notice_type", "")
            if config.WB_NOTICE_TYPES_KEEP and ntype not in config.WB_NOTICE_TYPES_KEEP:
                continue
            pid = n.get("project_id", "")
            nid = n.get("id", "")
            # прямая страница ИЗВЕЩЕНИЯ (не проекта) — проверено вживую
            url = (f"https://projects.worldbank.org/en/projects-operations/"
                   f"procurement-detail/{nid}" if nid else
                   f"https://projects.worldbank.org/en/projects-operations/"
                   f"project-detail/{pid}")
            published = None
            try:
                published = datetime.strptime(n.get("noticedate", ""), "%d-%b-%Y")\
                    .replace(tzinfo=timezone.utc)
            except Exception:
                pass
            title = f"[WB] {ntype}: {n.get('project_name', '')}".strip()
            body = strip_html(n.get("notice_text", "")) or n.get("bid_description", "")
            items.append(_mk(
                "World Bank", config.CAT_INTL, "World Bank", title, url, published,
                summary=n.get("bid_description", ""), full_text=body,
                uid=f"wb:{nid}" if nid else None,
                meta={"deadline": n.get("submission_deadline_date"),
                      "reference": n.get("bid_reference_no"),
                      "notice_type": ntype, "project_id": pid,
                      "country": n.get("project_ctry_name")}))
        log.info("World Bank API: %d", len(items))
    except Exception as e:
        log.warning("World Bank API FAIL: %s", e)
    return items


# ─────────────────────────── 2. EU TED API ───────────────────────────
def _ted_text(v):
    if not v:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return _ted_text(v[0]) if v else ""
    if isinstance(v, dict):
        for k in ("eng", "en", "ENG", "EN"):
            if k in v:
                return _ted_text(v[k])
        for vv in v.values():
            t = _ted_text(vv)
            if t:
                return t
    return str(v)


def _ted_link(links):
    if isinstance(links, dict):
        for key in ("html", "pdf", "xml"):
            u = _ted_text(links.get(key))
            if u.startswith("http"):
                return u
        for v in links.values():
            u = _ted_text(v)
            if u.startswith("http"):
                return u
    u = _ted_text(links)
    return u if u.startswith("http") else ""


def fetch_ted(limit: int = 30) -> list:
    if not config.TED_ENABLED:
        return []
    items = []
    try:
        r = requests.post(
            config.TED_API_URL,
            json={"query": config.TED_QUERY, "fields": config.TED_FIELDS,
                  "limit": limit, "page": 1, "scope": "ACTIVE"},
            headers={**config.HTTP_HEADERS, "Content-Type": "application/json"},
            timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        for n in r.json().get("notices", []):
            title = _ted_text(n.get("notice-title"))
            if not title:
                continue
            pubno = str(n.get("publication-number", ""))
            url = _ted_link(n.get("links")) or \
                f"https://ted.europa.eu/en/notice/-/detail/{pubno}"
            published = None
            pd = n.get("publication-date")
            if pd:
                try:
                    published = datetime.fromisoformat(str(pd).replace("Z", "+00:00"))
                except Exception:
                    pass
            items.append(_mk(
                "EU TED", config.CAT_INTL, "EU TED", f"[TED] {title}", url, published,
                summary=title, full_text=title,
                uid=f"ted:{pubno}" if pubno else None,
                meta={"deadline": n.get("deadline-receipt-request"),
                      "buyer": _ted_text(n.get("buyer-name")), "reference": pubno}))
        log.info("EU TED: %d", len(items))
    except Exception as e:
        log.warning("EU TED FAIL: %s", e)
    return items


# ─────────────────────────── 3. UNDP Procurement ───────────────────────────
def fetch_undp(max_items: int = 40) -> list:
    items = []
    try:
        r = requests.get(config.UNDP_URL, headers=config.HTTP_HEADERS,
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        seen = set()
        for a in soup.find_all("a", href=True):
            if "notice" not in a["href"].lower():
                continue
            ctx = a
            for _ in range(3):
                if ctx.parent:
                    ctx = ctx.parent
            ctx_text = ctx.get_text(" ", strip=True)[:800]
            if not re.search(r"uzbekistan|UNDP-UZB", ctx_text, re.I):
                continue
            href = a["href"]
            url = href if href.startswith("http") else \
                config.UNDP_URL.rstrip("/") + "/" + href.lstrip("/")
            if url in seen:
                continue
            seen.add(url)
            m = re.search(r"notice_id=(\d+)", url)
            title = a.get_text(" ", strip=True) or "UNDP notice"
            items.append(_mk(
                "UNDP", config.CAT_INTL, "UNDP", f"[UNDP] {title}", url,
                summary=ctx_text[:600], full_text=ctx_text[:2000],
                uid=f"undp:{m.group(1)}" if m else None,
                meta={"country": "Uzbekistan"}))
            if len(items) >= max_items:
                break
        log.info("UNDP: %d (по Узбекистану)", len(items))
    except Exception as e:
        log.warning("UNDP FAIL: %s", e)
    return items


# ─────────────────────────── 4. МФО-RSS (AIIB) ───────────────────────────
def fetch_mfi_rss() -> list:
    items, s = [], _session()
    for feed in config.MFI_RSS_FEEDS:
        try:
            r = s.get(feed["url"], timeout=config.HTTP_TIMEOUT)
            parsed = feedparser.parse(r.content)
            n = 0
            for e in parsed.entries[:60]:
                title = e.get("title", "")
                summary = strip_html(e.get("summary", ""))
                if not _region_match(title, summary):
                    continue
                link = e.get("link", "")
                items.append(_mk(
                    feed["name"], config.CAT_INTL, feed["name"],
                    f"[{feed['name'].split()[0]}] {title}", link,
                    _parse_rss_date(e), summary=summary, full_text=summary))
                n += 1
            log.info("MFI RSS %s: %d (после фильтра региона)", feed["name"], n)
        except Exception as e:
            log.warning("MFI RSS %s FAIL: %s", feed["name"], e)
    return items


# ─────────────────────────── 5. lex.uz — новые НПА ───────────────────────────
def fetch_lexuz_telegram(limit: int = 25) -> list:
    """Парсим https://t.me/s/lexuzofficial — каждый акт со ссылкой lex.uz/docs/<id>."""
    items = []
    try:
        r = requests.get("https://t.me/s/lexuzofficial",
                         headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
        soup = BeautifulSoup(r.text, "lxml")
        msgs = soup.select("div.tgme_widget_message")[-limit:]
        for m in msgs:
            body_el = m.select_one("div.tgme_widget_message_text")
            if not body_el:
                continue
            text = body_el.get_text(" ", strip=True)
            if not text:
                continue
            doc_url, doc_id = "", None
            for a in body_el.select("a[href]"):
                if "lex.uz" in a["href"]:
                    doc_url = a["href"]
                    dm = re.search(r"docs?/(-?\d+)", doc_url)
                    if dm:
                        doc_id = dm.group(1)
                    break
            msg_link = m.select_one("a.tgme_widget_message_date")
            url = doc_url or (msg_link["href"] if msg_link else "https://t.me/lexuzofficial")
            published = None
            t = m.select_one("time[datetime]")
            if t and t.get("datetime"):
                try:
                    published = datetime.fromisoformat(t["datetime"])
                except Exception:
                    pass
            title = "[НПА] " + text.split("\n")[0][:160]
            items.append(_mk(
                "lex.uz", config.CAT_LAW, "lex.uz", title, url, published,
                summary=text, full_text=text,
                uid=f"lexuz:{doc_id}" if doc_id else None))
        log.info("lex.uz Telegram: %d", len(items))
    except Exception as e:
        log.warning("lex.uz Telegram FAIL: %s", e)
    return items


# ─────────────────────────── 6. TenderWeek — ПУБЛИЧНЫЙ листинг ───────────────────────────
def _tw_parse_row(a, base="https://www.tenderweek.com") -> dict | None:
    """Строка листинга: заказчик | №ID | название | описание… | категория | дата."""
    href = a.get("href", "")
    m = re.search(r"/tender-(\d+)", href)
    if not m:
        return None
    tid = m.group(1)
    url = href if href.startswith("http") else base + href

    row = a
    for _ in range(4):
        if row.parent is None:
            break
        row = row.parent
        txt = row.get_text(" | ", strip=True)
        if f"№{tid}" in txt or ("Опубликован" in txt and len(txt) > 60):
            break
    txt = row.get_text(" | ", strip=True)
    parts = [p.strip() for p in txt.split("|") if p.strip()]

    buyer, title, desc, categ, published = "", "", "", "", None
    idx_num = next((i for i, p in enumerate(parts) if p == f"№{tid}"), None)
    if idx_num is not None:
        buyer = parts[idx_num - 1] if idx_num >= 1 else ""
        title = parts[idx_num + 1] if idx_num + 1 < len(parts) else ""
        desc = parts[idx_num + 2] if idx_num + 2 < len(parts) else ""
        categ = parts[idx_num + 3] if idx_num + 3 < len(parts) else ""
    else:
        title = a.get_text(strip=True)

    dm = re.search(r"Опубликован[оа]?:?\s*(\d{2})[./](\d{2})[./](\d{4})", txt)
    if dm:
        try:
            published = datetime(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)),
                                 tzinfo=timezone.utc)
        except Exception:
            pass
    ddm = re.search(r"Истекает:?\s*(\d{2}[./]\d{2}[./]\d{4})", txt)

    if not title or len(title) < 8:
        return None
    summary_bits = [b for b in (buyer and f"Заказчик: {buyer}",
                                categ and f"Категория: {categ}",
                                desc) if b]
    return _mk("TenderWeek", config.CAT_UZTEND, "TenderWeek",
               f"[TW] {title[:240]}", url, published,
               summary=". ".join(summary_bits)[:800],
               full_text=f"{title}. {'. '.join(summary_bits)}",
               uid=f"tw:{tid}",
               meta={"buyer": buyer, "tw_category": categ,
                     "deadline": ddm.group(1) if ddm else None})


def fetch_tenderweek_public(pages: int | None = None) -> list:
    """TenderWeek.com — бесплатный агрегатор тендеров УЗ (5 нацоператоров).
    Листинг публичный; вход (полные тексты) закрыт reCAPTCHA — не автоматизируем."""
    pages = pages or config.TENDERWEEK_PAGES
    items, seen = [], set()
    s = _session()
    try:
        for p in range(1, pages + 1):
            url = config.TENDERWEEK_URL if p == 1 else f"{config.TENDERWEEK_URL}?page={p}"
            r = s.get(url, timeout=config.HTTP_TIMEOUT)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "lxml")
            added = 0
            for a in soup.find_all("a", href=re.compile(r"/tender-\d+")):
                it = _tw_parse_row(a)
                if not it or it["uid"] in seen:
                    continue
                seen.add(it["uid"])
                items.append(it)
                added += 1
            if added == 0:
                break
        log.info("TenderWeek (публичный листинг): %d", len(items))
    except Exception as e:
        log.warning("TenderWeek FAIL: %s", e)
    return items


# ─────────────────────────── 7. uzjobs.uz — вакансии консультантов (RSS) ───────────────────────────
def fetch_uzjobs(limit: int = 40) -> list:
    """RSS uzjobs.uz; оставляем консультантские/экспертные позиции (JOB_KEYWORDS)."""
    items = []
    try:
        r = requests.get(config.UZJOBS_RSS, headers=config.HTTP_HEADERS,
                         timeout=config.HTTP_TIMEOUT)
        parsed = feedparser.parse(r.content)
        for e in parsed.entries[:limit]:
            title = e.get("title", "")
            link = e.get("link", "")
            if not title or not link:
                continue
            blob = f"{title} {e.get('summary', '')}".lower()
            if not any(k in blob for k in config.JOB_KEYWORDS):
                continue
            m = re.search(r"vakansy_view-(\d+)", link)
            summary = strip_html(e.get("summary", ""))
            items.append(_mk(
                "UzJobs", config.CAT_JOB, "uzjobs.uz",
                f"[UzJobs] {re.sub(r'^(Вакансия|Vacancy):\s*', '', title).strip()[:240]}",
                link, _parse_rss_date(e), summary=summary, full_text=summary,
                uid=f"uzjobs:{m.group(1)}" if m else None))
        log.info("UzJobs: %d (консультанты/эксперты)", len(items))
    except Exception as e:
        log.warning("UzJobs FAIL: %s", e)
    return items


# ─────────────────────────── Полный текст страницы (для глубокого анализа) ───────────────────────────
_FULLTEXT_SKIP = ("tenderweek.com", "etender.uzex.uz", "xarid.uzex.uz",
                  "xt-xarid.uz", "t.me")   # SPA или стены логина — там нечего забирать


def fetch_full_page_text(url: str) -> str:
    """Основной текст страницы (как в v4): для новостей и server-rendered извещений
    (UNGM, UNDP, uzjobs). Возвращает '' при любых проблемах."""
    if not url or any(d in url for d in _FULLTEXT_SKIP):
        return ""
    try:
        r = requests.get(url, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()
        for sel in ("article", ".article-body", ".post-content", ".news-content",
                    "[itemprop='articleBody']", "main"):
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 150:
                return el.get_text("\n", strip=True)[:4500]
        body = soup.find("body")
        return body.get_text("\n", strip=True)[:4500] if body else ""
    except Exception:
        return ""


# ─────────────────────────── 8. Новостные RSS ───────────────────────────
def fetch_news_rss() -> list:
    items, s = [], _session()
    for feed in config.RSS_FEEDS:
        try:
            r = s.get(feed["url"], timeout=config.HTTP_TIMEOUT)
            parsed = feedparser.parse(r.content)
            n = 0
            for e in parsed.entries[:40]:
                title = e.get("title", "")
                link = e.get("link", "")
                if not title or not link:
                    continue
                summary = strip_html(e.get("summary", ""))
                items.append(_mk(
                    feed["name"], config.CAT_NEWS, feed["name"], title, link,
                    _parse_rss_date(e), summary=summary, full_text=summary,
                    meta={"dir": feed["dir"]}))
                n += 1
            log.info("RSS %s: %d", feed["name"], n)
        except Exception as e:
            log.warning("RSS %s FAIL: %s", feed["name"], e)
    return items


# ─────────────────────────── Оркестратор сбора ───────────────────────────
# Статистика последнего сбора: origin → сколько элементов отдал источник в ЭТОМ прогоне.
# Ноль там, где обычно есть данные, — сигнал тихой поломки (показывается в кабинете).
LAST_COLLECT_STATS: dict = {}


def _tally(items: list) -> list:
    for it in items:
        LAST_COLLECT_STATS[it["origin"]] = LAST_COLLECT_STATS.get(it["origin"], 0) + 1
    return items


def collect_all() -> list:
    LAST_COLLECT_STATS.clear()
    # источники, которые обязаны что-то отдать: заводим нули, чтобы поломка была видна
    for o in ("World Bank", "TenderWeek", "lex.uz", "ungm.org", "etender.uzex.uz",
              "xt-xarid.uz", "uzjobs.uz", "Gazeta.uz", "Spot.uz", "Kun.uz"):
        LAST_COLLECT_STATS.setdefault(o, 0)
    items = []
    items += _tally(fetch_worldbank())
    items += _tally(fetch_ted())
    items += _tally(fetch_undp())
    items += _tally(fetch_mfi_rss())
    items += _tally(fetch_uzjobs())
    items += _tally(fetch_tenderweek_public())
    try:
        from headless import collect_all_headless    # playwright опционален
        items += _tally(collect_all_headless())
    except Exception as e:
        log.warning("headless источники недоступны: %s", e)
    items += _tally(fetch_lexuz_telegram())
    items += _tally(fetch_news_rss())
    log.info("ИТОГО собрано: %d элементов", len(items))
    return items
