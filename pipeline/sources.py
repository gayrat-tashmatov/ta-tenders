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

import json
import os
import config
import dedupe

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
            # Заголовок — суть задания (bid_description), а не название проекта: иначе
            # «верификация ESG-отчёта» выглядела как «Electricity Sector Transformation…» (15.10).
            task = (n.get("bid_description") or "").strip()
            proj = (n.get("project_name") or "").strip()
            short_type = {"Request for Expression of Interest": "REoI",
                          "Invitation for Bids": "IFB"}.get(ntype, ntype)
            title = (f"[WB] {short_type}: {task}" if task and len(task) > 8
                     else f"[WB] {ntype}: {proj}").strip()
            body = strip_html(n.get("notice_text", "")) or n.get("bid_description", "")
            items.append(_mk(
                "World Bank", config.CAT_INTL, "World Bank", title, url, published,
                summary=f"Проект ВБ: {proj}. {task}".strip(), full_text=body,
                uid=f"wb:{nid}" if nid else None,
                meta={"deadline": n.get("submission_deadline_date"),
                      "reference": n.get("bid_reference_no"),
                      "individual": n.get("procurement_method_code") == "INDV",   # индивидуальный консультант
                      "notice_type": ntype, "project_id": pid, "project": proj,
                      "donor": "World Bank",
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
    """UNDP Procurement Notices. Сайт игнорирует фильтр страны и отдаёт мировую
    ленту; внутри — плоский поток текстовых узлов вида
    Title | <название> | Ref No | <ref> | UNDP Office/Country | UNDP-UZB/UZBEKISTAN | …
    Режем поток по «Title» и берём только записи с офисом UZB."""
    items = []
    try:
        r = requests.get(config.UNDP_URL.rstrip("/") + "/search.cfm",
                         params={"search_country": "UZB"},
                         headers=config.HTTP_HEADERS, timeout=60)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        box = soup.select_one(".vacanciesTable") or soup
        # плоский список (текст, ссылка) в порядке документа
        stream = []
        for el in box.descendants:
            if getattr(el, "name", None) == "a" and el.get("href") and "view_notice" in el["href"]:
                stream.append(("A", el.get_text(" ", strip=True), el["href"]))
            elif isinstance(el, str):
                t = el.strip()
                if t:
                    stream.append(("T", t, None))
        # группируем по блокам между «Title»
        blocks, cur = [], None
        for kind, txt, href in stream:
            if kind == "T" and txt == "Title":
                if cur:
                    blocks.append(cur)
                cur = {"texts": [], "href": None, "title": None}
                continue
            if cur is None:
                continue
            if kind == "A":
                if cur["href"] is None:
                    cur["href"] = href
                if cur["title"] is None and len(txt) > 8:
                    cur["title"] = txt
            else:
                if cur["title"] is None and txt not in ("Ref No",) and len(txt) > 8:
                    cur["title"] = txt          # заголовок идёт текстом сразу после «Title»
                else:
                    cur["texts"].append(txt)
        if cur:
            blocks.append(cur)
        for b in blocks:
            tx = b["texts"]
            f = {}
            for i, t in enumerate(tx):
                if t in ("Ref No", "UNDP Office/Country", "Process", "Deadline", "Posted") and i + 1 < len(tx):
                    f[t] = tx[i + 1]
            office = f.get("UNDP Office/Country", "")
            if "UZB" not in office.upper() or not b["title"]:
                continue
            ref = f.get("Ref No", "")
            m = re.search(r"notice_id=(\d+)", b["href"] or "")
            url = (b["href"] if b["href"] and b["href"].startswith("http") else
                   config.UNDP_URL.rstrip("/") + "/" + b["href"].lstrip("/") if b["href"] else
                   config.UNDP_URL.rstrip("/") + f"/search.cfm?search_ref={ref}")
            proc = f.get("Process", "")
            items.append(_mk(
                "UNDP", config.CAT_INTL, "UNDP", f"[UNDP] {b['title'][:230]}", url,
                summary=f"{proc}. Заказчик: ПРООН Узбекистан. Ref: {f.get('Ref No','')}. Дедлайн: {f.get('Deadline','')}",
                full_text=f"{b['title']}. {proc}. {office}. Ref {f.get('Ref No','')}. Deadline {f.get('Deadline','')}. Posted {f.get('Posted','')}",
                uid=f"undp:{m.group(1)}" if m else (f"undp:{ref}" if ref else None),
                meta={"country": "Uzbekistan", "deadline": f.get("Deadline"),
                      "reference": f.get("Ref No"), "process": proc}))
            if len(items) >= max_items:
                break
        log.info("UNDP: %d (по Узбекистану)", len(items))
    except Exception as e:
        log.warning("UNDP FAIL: %s", e)
    return items


def fetch_isdb(max_items: int = 30) -> list:
    """IsDB Project Procurement — фильтр loc=UZ. Карточка: название | статус |
    тип (EOI/GPN/…) | страна | дедлайн. Берём только Active."""
    items = []
    try:
        r = requests.get("https://www.isdb.org/project-procurement/tenders",
                         params={"loc": "UZ", "status": "All"},
                         headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        seen = set()
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "/project-procurement/tenders/" not in h and "/appels-doffres/" not in h:
                continue
            title = a.get_text(" ", strip=True)
            if len(title) < 20 or h in seen:
                continue
            seen.add(h)
            card = a
            for _ in range(4):
                card = card.parent if card.parent else card
            parts = [p.strip() for p in card.get_text("|", strip=True).split("|") if p.strip()]
            status = next((p for p in parts if p in ("Active", "Closed")), "")
            if status == "Closed":
                continue
            ttype = next((p for p in parts if p in ("Expression of Interest", "General Procurement Notice",
                                                     "Request for Proposal", "Invitation for Bids",
                                                     "Contract Award", "Specific Procurement Notice")), "")
            if ttype == "Contract Award":
                continue
            dl = next((p for p in parts if re.match(r"\d{1,2} \w+ \d{4}$", p)), None)
            url = h if h.startswith("http") else "https://www.isdb.org" + h
            items.append(_mk(
                "IsDB", config.CAT_INTL, "isdb.org", f"[IsDB] {title[:230]}", url,
                summary=f"{ttype}. Узбекистан. Дедлайн: {dl or '—'}",
                full_text=f"{title}. {ttype}. Uzbekistan. Deadline {dl or ''}",
                uid=f"isdb:{h.rstrip('/').split('/')[-1][:80]}",
                meta={"country": "Uzbekistan", "deadline": dl, "notice_type": ttype}))
            if len(items) >= max_items:
                break
        log.info("IsDB: %d активных по Узбекистану", len(items))
    except Exception as e:
        log.warning("IsDB FAIL: %s", e)
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


LEXUZ_RSS = (("ru", "https://lex.uz/ru/rss"), ("uz", "https://lex.uz/rss"))


def fetch_lexuz_rss() -> list:
    """Официальный RSS lex.uz («Законодательство: новости»): RU-лента + UZ-лента для актов
    без русской версии. С 22.09.2026 веб-превью t.me/s/lexuzofficial перестало обновляться,
    и поток НПА (а с ним и ежедневная аналитика) встал — обнаружено 13.10.
    В description — тип акта, номер и даты: «Указ Президента … №УП-217. Дата принятия …».
    uid = lexuz:<id документа>; RU и UZ версии одного акта имеют РАЗНЫЕ id — склеиваем по
    реквизиту акта (УП-217 = ПФ-217) внутри выборки и через реестр НПА (run.py, rss_law)."""
    items, s, seen_refs = [], _session(), set()
    for lang, url in LEXUZ_RSS:
        try:
            r = s.get(url, timeout=config.HTTP_TIMEOUT)
            parsed = feedparser.parse(r.content)
            n = 0
            for e in parsed.entries[:120]:
                link = e.get("link", "") or e.get("id", "")
                if link.startswith("/"):
                    link = "https://lex.uz" + link
                dm = re.search(r"docs?/(-?\d+)", link)
                if not dm:
                    continue
                doc_id = dm.group(1).lstrip("-")
                title = strip_html(e.get("title", "")).strip()
                desc = strip_html(e.get("summary", "") or e.get("description", "")).strip()
                refs = set(dedupe.extract_npa_refs(f"{title} {desc}", None)) - {f"LEX-{doc_id}"}
                if refs and refs & seen_refs:
                    continue                      # тот же акт на другом языке
                seen_refs |= refs
                kind = desc.split(".")[0][:120] if desc else ""
                items.append(_mk(
                    "lex.uz", config.CAT_LAW, "lex.uz", f"[НПА] {title[:160]}", link,
                    _parse_rss_date(e),
                    summary=f"{kind}. {title}" if kind else title,
                    full_text=f"{title}. {desc} {link}",   # ссылка → ключ LEX-<id> в реестре
                    uid=f"lexuz:{doc_id}",
                    meta={"lang": lang, "lex_id": doc_id, "act_info": desc[:300], "rss_law": True}))
                n += 1
            log.info("lex.uz RSS %s: %d", lang, n)
        except Exception as e:
            log.warning("lex.uz RSS %s FAIL: %s", lang, e)
    return items


_LEX_NOISE = re.compile(r"(Предложения по документу|Прослушать аудио|Получить ссылку из элемента документа|"
                        r"Ҳужжатга таклиф юбориш|Аудиони тинглаш|Ҳужжат элементидан ҳавола олиш|"
                        r"\[ ОКОЗ:[^\]]*\]|\[ ТСЗ:[^\]]*\]|\[ ОКОЗ[^\]]*\]|\[ ТСЗ[^\]]*\])\s*")


def _lex_page_text(s, url: str):
    r = s.get(url, timeout=config.HTTP_TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    el = soup.select_one("#divCont")
    text = _LEX_NOISE.sub("", re.sub(r"\s+", " ", el.get_text(" ", strip=True))) if el else ""
    orig = None
    if el is not None:
        for a in el.select("a[href]"):
            label = a.get_text(" ", strip=True).lower()
            # «Текст акта приводится на <a>узбекском языке</a>» — ссылка на оригинал
            if re.search(r"/docs?/-?\d+", a["href"]) and any(k in label for k in ("оригинал", "original", "узбекском")):
                orig = a["href"] if a["href"].startswith("http") else "https://lex.uz" + a["href"]
                break
    return text, orig


def fetch_act_text(url: str) -> tuple:
    """Полный текст акта lex.uz для разбора: ('text', str) | ('pdf', bytes) | (None, None).
    Ведомственные акты — текстом в #divCont; указы и постановления — PDF-сканом (/pdffile/<id>),
    их читает модель напрямую. Русская страница часто пуста («текст приводится на узбекском»)
    со ссылкой на оригинал — идём по ней."""
    m = re.search(r"docs?/(-?\d+)", url or "")
    if not m:
        return None, None
    s = _session()
    best = ""
    try:
        text, orig = _lex_page_text(s, url)
        best = text
        short = len(text) < 600 or "приводится на узбекском" in text
        if short and orig:
            t2, _ = _lex_page_text(s, orig)
            if len(t2) > len(best):
                best = t2
        if len(best) >= 600 and "приводится на узбекском" not in best[:600]:
            return "text", best[:40000]
        ids = [m.group(1).lstrip("-")]
        if orig:
            mo = re.search(r"docs?/(-?\d+)", orig)
            if mo:
                ids.append(mo.group(1).lstrip("-"))
        for did in ids:
            r = s.get(f"https://lex.uz/pdffile/{did}", timeout=60)
            if r.ok and r.content[:4] == b"%PDF" and len(r.content) < 15_000_000:
                return "pdf", r.content
    except Exception as e:
        log.warning("lex.uz текст акта FAIL %s: %s", url, e)
    return ("text", best) if best else (None, None)


def fetch_lexuz() -> list:
    """НПА: RSS lex.uz; Telegram-канал — только как резерв, если RSS пуст."""
    items = fetch_lexuz_rss()
    return items if items else fetch_lexuz_telegram()


XTXARID_RPC = "https://api.xt-xarid.uz/rpc"
XTXARID_MAX = int(os.getenv("XTXARID_MAX", "600"))


def fetch_xtxarid_api(max_items: int | None = None) -> list:
    """xt-xarid.uz напрямую через JSON-RPC «ref ref_tender_public» (тот же вызов, что делает
    сайт). Главная страница с 05.10.2026 показывает только 6 процедур, и headless-перехват
    давал 0 — обнаружено 13.10. Страницами по 100 до XTXARID_MAX; уровень процедуры
    (/procedure/{id}/core), фильтр по словарю консалтинга/ИТ, только с живым дедлайном."""
    max_items = max_items or XTXARID_MAX
    items, got = [], []
    hdr = {**config.HTTP_HEADERS, "Content-Type": "application/json",
           "Origin": "https://xt-xarid.uz", "Referer": "https://xt-xarid.uz/"}
    fields = ["id", "name", "status", "publicated_at", "close_at", "totalcost", "currency",
              "lot_count", "good_count", "green", "lang"]
    try:
        offset, page = 0, 100
        while offset < max_items:
            body = {"jsonrpc": "2.0", "id": 1, "method": "ref",
                    "params": {"ref": "ref_tender_public", "op": "read", "limit": page,
                               "offset": offset, "filters": {}, "fields": fields}}
            r = requests.post(XTXARID_RPC, headers=hdr, json=body, timeout=40)
            r.raise_for_status()
            res = r.json().get("result")
            rows = res if isinstance(res, list) else ((res or {}).get("data") or [])
            got += rows
            if len(rows) < page:
                break
            offset += page

        now = datetime.now(timezone.utc)
        seen = set()
        for d in got:
            pid = str(d.get("id") or "")
            title = str(d.get("name") or "").strip()
            if not pid or pid in seen or not title:
                continue
            seen.add(pid)
            if not any(k in title.lower() for k in config.CONSULTING_KEYWORDS):
                continue
            status = str(d.get("status") or "")
            if any(s in status for s in ("cancel", "closed", "draft", "finish", "reject")):
                continue
            close = None
            try:
                close = datetime.fromisoformat(str(d.get("close_at"))[:19]).replace(tzinfo=timezone.utc)
            except Exception:
                pass
            if close and close < now:
                continue
            pub = None
            try:
                pub = datetime.fromisoformat(str(d.get("publicated_at"))[:19]).replace(tzinfo=timezone.utc)
            except Exception:
                pass
            cost = d.get("totalcost")
            meta = {"deadline": str(d.get("close_at") or "")[:19] or None,
                    "published": pub.isoformat() if pub else None,
                    "cost": cost, "currency": d.get("currency") or "UZS",
                    "number": pid, "lot_count": d.get("lot_count"), "status": status,
                    "kw_match": True}
            bits = [title]
            if cost:
                bits.append(f"Сумма: {cost:,.0f} {meta['currency']}".replace(",", " ")
                            if isinstance(cost, (int, float)) else f"Сумма: {cost} {meta['currency']}")
            if d.get("lot_count"):
                bits.append(f"Лотов: {d['lot_count']}")
            items.append(_mk("XT-Xarid (госзакупки)", config.CAT_UZTEND, "xt-xarid.uz",
                             f"[xt-xarid] {title[:280]}",
                             f"https://xt-xarid.uz/procedure/{pid}/core", pub,
                             summary=". ".join(bits)[:800],
                             full_text=json.dumps(d, ensure_ascii=False)[:2500],
                             uid=f"xtxarid:{pid}", meta=meta))
        log.info("xt-xarid API: лента=%d → консалтинг/ИТ с живым дедлайном %d", len(got), len(items))
    except Exception as e:
        log.warning("xt-xarid API FAIL: %s", e)
    return items


# ─────────────────────────── MangoFetch — агрегатор доноров (публичные страницы стран) ───────────────────────────
MANGOFETCH_BASE = "https://www.mangofetch.com"
MANGOFETCH_COUNTRIES = {"Uzbekistan": "UZB", "Kazakhstan": "KAZ", "Kyrgyzstan": "KGZ",
                        "Tajikistan": "TJK", "Turkmenistan": "TKM"}   # ISO3: «TUR» модель читала как Турцию
_MF_DONOR_SHORT = {
    "Asian Development Bank": "ADB", "World Bank": "WB", "Islamic Development Bank": "IsDB",
    "Asian Infrastructure Investment Bank": "AIIB", "EBRD": "EBRD", "European Union": "EU",
    "Agence Française de Développement": "AFD", "U.S. Department of State": "US DoS",
    "UNDP": "UNDP", "UNOPS": "UNOPS", "FAO": "FAO", "ILO": "ILO", "OSCE": "OSCE", "IOM": "IOM",
    "UNICEF": "UNICEF", "UN-Women": "UNWomen", "UNESCO": "UNESCO", "IAEA": "IAEA",
    "UN Secretariat": "UN", "UNIDO": "UNIDO", "WHO": "WHO", "WFP": "WFP", "KfW": "KfW", "GIZ": "GIZ"}
_MF_DATE_FMT = ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d")


def _mf_date(text: str):
    text = (text or "").strip()
    for fmt in _MF_DATE_FMT:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def fetch_mangofetch(countries: dict | None = None) -> list:
    """MangoFetch.com — открытый агрегатор закупок доноров (ВБ, ООН, АБР, ЕБРР, AFD, ЕС…).
    Главная ценность — АБР: adb.org закрыт для ботов (403), а консалтинг АБР по ЦА —
    ровно профиль компании (сверка 15.10.2026: 7 открытых извещений АБР по Узбекистану,
    42 по ЦА, у нас — 0). robots.txt разрешает индексацию страниц, /api/ — нет, его не трогаем.
    Берём страницы стран (ItemList: до 40 извещений), детали — только по новым (JSON-LD
    страницы тендера: донор, отрасль, даты, ссылка на оригинал у донора).
    Дубли с прямыми источниками (UNGM, ВБ, UNDP, IsDB) снимает run.py по похожести названий."""
    countries = countries or MANGOFETCH_COUNTRIES
    s = _session()
    now = datetime.now(timezone.utc)
    items = []
    for country, iso in countries.items():
        try:
            r = s.get(f"{MANGOFETCH_BASE}/country/{country}", timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            cards = {}
            for a in soup.select("a[href^='/tenders/']"):
                href = a.get("href", "")
                m = re.fullmatch(r"/tenders/([0-9a-f-]{36})", href)
                if not m or m.group(1) in cards:
                    continue
                card = a
                for _ in range(4):
                    if card.parent is not None and len(card.parent.get_text(" ", strip=True)) < 600:
                        card = card.parent
                txt = re.sub(r"\s+", " ", card.get_text(" | ", strip=True))
                cm = re.match(r"(.*?) \| — (.*?) · (.*?) \| · deadline (.*)", txt)
                if not cm:
                    continue
                title, donor, ctry, dl = (x.strip() for x in cm.groups())
                cards[m.group(1)] = (title, donor, ctry, dl)
            n = 0
            for mid, (title, donor, ctry, dl) in cards.items():
                deadline = _mf_date(dl)
                if deadline and deadline < now:
                    continue                                  # закрытые MangoFetch тоже показывает
                if donor == "World Bank" and country == "Uzbekistan":
                    continue                                  # ВБ по Узбекистану — прямой API
                short = _MF_DONOR_SHORT.get(donor, donor.split()[0][:8])
                items.append(_mk(
                    f"MangoFetch · {donor}", config.CAT_INTL, "mangofetch.com",
                    f"[{short}·{iso}] {title}", f"{MANGOFETCH_BASE}/tenders/{mid}", None,
                    summary=f"Донор: {donor}. Страна: {ctry}. Срок: {dl}.",
                    full_text=f"{title}. Донор (источник финансирования): {donor}. Страна: {ctry}. Срок подачи: {dl}.",
                    uid=f"mf:{mid}",
                    meta={"donor": donor, "country": ctry, "buyer": donor,
                          "deadline": deadline.strftime("%Y-%m-%d") if deadline else dl,
                          "mf_url": f"{MANGOFETCH_BASE}/tenders/{mid}", "cross_source": True,
                          "needs_detail": True}))
                n += 1
            log.info("MangoFetch %s: открытых %d (на странице %d)", country, n, len(cards))
        except Exception as e:
            log.warning("MangoFetch %s FAIL: %s", country, e)
    return items


def enrich_mangofetch(item: dict) -> None:
    """Детали тендера MangoFetch (вызывается только для НОВЫХ записей): JSON-LD страницы —
    дата публикации, отрасль, ссылка на оригинал у донора (её делаем основной ссылкой)."""
    meta = item.setdefault("meta", {})
    if not meta.pop("needs_detail", False):
        return
    try:
        r = _session().get(meta.get("mf_url") or item["url"], timeout=config.HTTP_TIMEOUT)
        soup = BeautifulSoup(r.text, "lxml")
        for ld in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(ld.string or "")
            except Exception:
                continue
            for node in (data if isinstance(data, list) else [data]):
                if isinstance(node, dict) and node.get("@type") == "WebPage":
                    desc = node.get("description") or ""
                    pub = _mf_date((node.get("datePublished") or "")[:10])
                    if pub:
                        item["published"] = pub
                        meta["published"] = pub.isoformat()
                    parts = [x.strip() for x in desc.split("·")]
                    if len(parts) >= 4:
                        meta["sector"] = parts[3]
                    item["summary"] = (item.get("summary") or "") + (f" Отрасль: {meta['sector']}." if meta.get("sector") else "")
                    item["full_text"] = (item.get("full_text") or "") + f" {desc}"
        orig = next((a["href"] for a in soup.select("a[href^='http']")
                     if "mangofetch.com" not in a["href"]
                     and not any(x in a["href"] for x in ("linkedin.", "wikidata.", "twitter.", "x.com/", "facebook."))), None)
        if orig:
            meta["source_url"] = orig
            item["url"] = orig                          # кнопка «Источник» — сразу к донору
    except Exception as e:
        log.warning("MangoFetch детали FAIL %s: %s", item.get("uid"), e)


# ─────────────────────────── Позиции для индивидуальных консультантов (15.10.2026) ───────────────────────────
_CA_ISO = {"UZ": "UZB", "KZ": "KAZ", "KG": "KGZ", "TJ": "TJK", "TM": "TKM"}
_WB_CA_OTHER = "Kazakhstan^Kyrgyz Republic^Tajikistan^Turkmenistan"
_WB_ISO = {"Kazakhstan": "KAZ", "Kyrgyz Republic": "KGZ", "Tajikistan": "TJK", "Turkmenistan": "TKM", "Uzbekistan": "UZB"}


def fetch_worldbank_indv(rows: int = 100) -> list:
    """ВБ: индивидуальные консультанты (метод INDV) в остальных странах ЦА — Узбекистан уже идёт
    основным потоком. Фильтр procurement_method_code=INDV работает только без «_exact»."""
    items = []
    try:
        r = requests.get(config.WB_API_URL, params={
            "format": "json", "rows": rows, "srt": "noticedate", "order": "desc",
            "fl": config.WB_API_FIELDS, "project_ctry_name_exact": _WB_CA_OTHER,
            "notice_type_exact": "Request for Expression of Interest", "procurement_method_code": "INDV"},
            headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        now = datetime.now(timezone.utc)
        for n in r.json().get("procnotices", []):
            nid, task = n.get("id", ""), (n.get("bid_description") or "").strip()
            if not nid or not task:
                continue
            dl = n.get("submission_deadline_date") or ""
            try:
                if dl and datetime.fromisoformat(dl.replace("Z", "+00:00")) < now:
                    continue
            except ValueError:
                pass
            published = None
            try:
                published = datetime.strptime(n.get("noticedate", ""), "%d-%b-%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
            ctry = n.get("project_ctry_name", "")
            items.append(_mk(
                "World Bank", config.CAT_JOB, "World Bank",
                f"[WB·{_WB_ISO.get(ctry, ctry[:3].upper())}] {task}",
                f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{nid}", published,
                summary=f"Индивидуальный консультант. Проект ВБ: {n.get('project_name','')}. Страна: {ctry}.",
                full_text=strip_html(n.get("notice_text", "")) or task, uid=f"wb:{nid}",
                meta={"deadline": dl[:10] or None, "donor": "World Bank", "country": ctry, "individual": True,
                      "reference": n.get("bid_reference_no"), "project": n.get("project_name")}))
        log.info("World Bank INDV (ЦА без УЗ): %d", len(items))
    except Exception as e:
        log.warning("World Bank INDV FAIL: %s", e)
    return items


# Карьерные порталы ООН на Oracle HCM: публичный REST, по которому работает сам сайт вакансий.
UN_HCM_SITES = [
    ("UNDP", "estm.fa.em2.oraclecloud.com", "CX_1"),
    ("UN Women", "estm.fa.em2.oraclecloud.com", "CX_1001"),
    ("IOM", "fa-evlj-saasfaprod1.fa.ocs.oraclecloud.com", "CX_1001"),
]
_HCM_SKIP = re.compile(r"\b(intern|internship|volunteer|driver|cleaner|guard|receptionist|clerk|"
                       r"nurse|doctor|physician|medical|associate,? admin|admin(istrative)? assistant)\b", re.I)


def fetch_un_careers(max_pages: int = 12) -> list:
    """ПРООН, UN Women, МОМ: вакансии и консультации в странах ЦА (проектные позиции, NPSA/IC)."""
    items, s = [], _session()
    for org, host, site in UN_HCM_SITES:
        base = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        n = 0
        try:
            for page in range(max_pages):
                finder = f"findReqs;siteNumber={site},limit=25,offset={page * 25},sortBy=POSTING_DATES_DESC"
                r = s.get(base, params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                                        "finder": finder}, timeout=config.HTTP_TIMEOUT)
                r.raise_for_status()
                data = r.json().get("items") or []
                reqs = data[0].get("requisitionList", []) if data else []
                for q in reqs:
                    iso = _CA_ISO.get(q.get("PrimaryLocationCountry") or "")
                    title = (q.get("Title") or "").strip()
                    if not iso or not title or _HCM_SKIP.search(title):
                        continue
                    pub = None
                    try:
                        pub = datetime.fromisoformat(str(q.get("PostedDate"))[:10]).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                    jid = q.get("Id")
                    items.append(_mk(
                        f"{org} (вакансии)", config.CAT_JOB, f"{org.lower().replace(' ', '')}-careers",
                        f"[{org}·{iso}] {title}",
                        f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{jid}", pub,
                        summary=f"{org}. Страна: {q.get('PrimaryLocationCountry')}. {q.get('PrimaryLocation') or ''}",
                        full_text=title, uid=f"hcm:{org.lower().replace(' ', '')}:{jid}",
                        meta={"deadline": q.get("PostingEndDate"), "donor": org, "agency": org,
                              "country": q.get("PrimaryLocation") or q.get("PrimaryLocationCountry"),
                              "individual": True}))
                    n += 1
                if len(reqs) < 25:
                    break
            log.info("%s вакансии (ЦА): %d", org, n)
        except Exception as e:
            log.warning("%s вакансии FAIL: %s", org, e)
    return items


# ─────────────────────────── 6. TenderWeek — ПУБЛИЧНЫЙ листинг ───────────────────────────
_TW_DATE_RE = re.compile(r"\d{2}[./]\d{2}[./]\d{4}")
# Рубрики TenderWeek, которые по определению услуги/консалтинг: лоты из них всегда идут
# на LLM-разбор и не режутся словарём товарки.
_TW_SERVICE_CATS = ("Консультационные услуги", "Финансовые услуги", "Программное обеспечение",
                    "Образование, наука", "Государственные и социальные услуги",
                    "Юридические", "Маркетинг", "Реклама")


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

    # Карточка (шаблон tenderweek_2026): заказчик | №ID | название | описание… |
    # категория (может быть 2–3) | Опубликовано | дата | [Обновлено | дата] | Истекает | дата
    buyer, title, desc, published, updated, deadline = "", "", "", None, None, None
    categs: list[str] = []
    idx_num = next((i for i, p in enumerate(parts) if p == f"№{tid}"), None)
    if idx_num is not None:
        buyer = parts[idx_num - 1] if idx_num >= 1 else ""
        title = parts[idx_num + 1] if idx_num + 1 < len(parts) else ""
        desc = parts[idx_num + 2] if idx_num + 2 < len(parts) else ""
        for p in parts[idx_num + 3:]:
            if p.startswith(("Опубликован", "Обновлен", "Истекает")) or _TW_DATE_RE.fullmatch(p):
                break
            categs.append(p)
    else:
        title = a.get_text(strip=True)

    def _date_after(label: str):
        # части идут раздельно: «Опубликовано», «14.09.2026» — старый regex по «Опубликовано: dd.mm»
        # не срабатывал, и у всех TW-лотов published/deadline были пустыми (до 14.09.2026)
        for i, p in enumerate(parts):
            if p.startswith(label) and i + 1 < len(parts) and _TW_DATE_RE.fullmatch(parts[i + 1]):
                return parts[i + 1]
        return None

    pub_s, upd_s, dl_s = _date_after("Опубликован"), _date_after("Обновлен"), _date_after("Истекает")
    for src in (pub_s,):
        if src:
            try:
                d, m_, y = src.replace("/", ".").split(".")
                published = datetime(int(y), int(m_), int(d), tzinfo=timezone.utc)
            except Exception:
                pass
    if dl_s:
        d, m_, y = dl_s.replace("/", ".").split(".")
        deadline = f"{y}-{m_}-{d}"

    # «Аудит», «Оценка», «Двери» — короткие названия бывают; раньше порог 8 символов
    # молча выбрасывал их (14.09: пропал REoI на аудит проекта ФАР).
    if not title or len(title) < 3:
        return None
    categ = "; ".join(categs)
    consulting_cat = any(k in categ for k in _TW_SERVICE_CATS)
    summary_bits = [b for b in (buyer and f"Заказчик: {buyer}",
                                categ and f"Категория: {categ}",
                                upd_s and f"Обновлено: {upd_s}",
                                desc) if b]
    return _mk("TenderWeek", config.CAT_UZTEND, "TenderWeek",
               f"[TW] {title[:240]}", url, published,
               summary=". ".join(summary_bits)[:800],
               full_text=f"{title}. {'. '.join(summary_bits)}",
               uid=f"tw:{tid}",
               meta={"buyer": buyer, "tw_category": categ, "deadline": deadline,
                     "updated": upd_s, "kw_match": consulting_cat,
                     "consulting_cat": consulting_cat})


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


# ─────────────────────────── 9. etender.uzex.uz — прямой API (вся лента) ───────────────────────────
def fetch_etender_api(max_items: int | None = None) -> list:
    """Конкурсы UZEX e-Tender через POST TradeList (пагинация From/To).
    Причина: раздел «Активные лоты» отсортирован по ДАТЕ ОКОНЧАНИЯ, headless видел
    первые 20 = закрывающиеся сегодня → 74 из 117 лотов ловились в день дедлайна.
    Здесь — вся активная лента; start_date становится датой публикации."""
    import json as _json
    max_items = max_items or config.ETENDER_API_MAX
    items = []
    hdr = {**config.HTTP_HEADERS, "Content-Type": "application/json; charset=UTF-8",
           "language": "uzb", "Origin": "https://etender.uzex.uz",
           "Referer": "https://etender.uzex.uz/"}
    try:
        got, frm, page = [], 1, 300
        while frm <= max_items:
            r = requests.post(config.ETENDER_API_URL, headers=hdr, timeout=40,
                              json={"TypeId": 1, "From": frm,
                                    "To": min(frm + page - 1, max_items), "System_Id": 0})
            r.raise_for_status()
            data = r.json()
            chunk = data if isinstance(data, list) else []
            got += chunk
            if len(chunk) < page:
                break
            frm += page

        def _dt(v):
            try:
                return datetime.fromisoformat(str(v)[:19]).replace(tzinfo=timezone.utc)
            except Exception:
                return None

        seen = set()
        for d in got:
            lid = str(d.get("id") or d.get("lot_id") or "")
            if not lid or lid in seen:
                continue
            seen.add(lid)
            title = str(d.get("name") or d.get("lot_name") or d.get("title") or "").strip()
            if not title or not any(k in title.lower() for k in config.CONSULTING_KEYWORDS):
                continue
            start = _dt(d.get("start_date"))
            buyer = (d.get("customer_name") or d.get("buyer_name") or d.get("seller_name")
                     or d.get("organization"))
            cost = d.get("cost") or d.get("start_price") or d.get("amount")
            meta = {"deadline": str(d.get("end_date") or "")[:19] or None,
                    "published": start.isoformat() if start else None,
                    "buyer": buyer, "cost": cost,
                    "currency": d.get("currency_name") or "UZS",
                    "region": d.get("region_name"), "number": lid, "kw_match": True}
            bits = [title]
            if buyer:
                bits.append(f"Заказчик: {buyer}")
            if cost:
                bits.append(f"Сумма: {cost} {meta['currency']}")
            if meta.get("region"):
                bits.append(f"Регион: {meta['region']}")
            items.append(_mk("UZEX e-Tender (конкурс)", config.CAT_UZTEND, "etender.uzex.uz",
                             f"[etender] {title[:280]}", f"https://etender.uzex.uz/lot/{lid}",
                             start, summary=". ".join(bits)[:800],
                             full_text=_json.dumps(d, ensure_ascii=False)[:2500],
                             uid=f"etender:{lid}", meta=meta))
        log.info("etender API: лента=%d → консалтинг/ИТ %d", len(got), len(items))
    except Exception as e:
        log.warning("etender API FAIL: %s", e)
    return items


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
    for o in ("World Bank", "TenderWeek", "lex.uz", "ungm.org", "etender.uzex.uz", "UNDP", "isdb.org",
              "xt-xarid.uz", "uzjobs.uz", "Gazeta.uz", "Spot.uz", "Kun.uz"):
        LAST_COLLECT_STATS.setdefault(o, 0)
    items = []
    items += _tally(fetch_worldbank())
    items += _tally(fetch_ted())
    # fetch_undp отключён 15.10.2026: robots.txt procurement-notices.undp.org = Disallow, поток идёт через UNGM
    items += _tally(fetch_isdb())
    items += _tally(fetch_mfi_rss())
    items += _tally(fetch_uzjobs())
    items += _tally(fetch_tenderweek_public())
    items += _tally(fetch_etender_api())
    items += _tally(fetch_xtxarid_api())
    items += _tally(fetch_worldbank_indv())
    items += _tally(fetch_un_careers())
    try:
        from headless import collect_all_headless    # playwright опционален
        items += _tally(collect_all_headless())
    except Exception as e:
        log.warning("headless источники недоступны: %s", e)
    items += _tally(fetch_mangofetch())      # после всех прямых (вкл. UNGM headless): сверка дублей в том же прогоне
    # почтовые рассылки (mail_alerts.py) отключены 15.10.2026: DevelopmentAid больше не нужен
    items += _tally(fetch_lexuz())
    items += _tally(fetch_news_rss())
    log.info("ИТОГО собрано: %d элементов", len(items))
    return items
