"""
Общий headless-движок для JS-источников (etender.uzex.uz, EBRD ECEPP, UNGM, ADB CSRN).

Эти сайты не отдают данные без браузера. Устойчивое решение:
  1) headless Chromium (Playwright) открывает страницу и даёт SPA вызвать свой API;
  2) перехватываем ВСЕ JSON-ответы её запросов (+ ссылки в DOM как запасной вариант);
  3) обобщённо достаём тендер-подобные записи (по набору ключей). Для международных
     источников — фильтр по региону (Узбекистан/ЦА).

Не завязано ни на CSS-селекторы, ни на адрес эндпоинта. Сырой перехват каждого источника
пишется в logs/<key>_capture.json ({urls, dom, captured}) — по нему фиксируются поля.

Требует один раз:  pip install playwright && playwright install chromium
Включается флагом HEADLESS_ENABLED=1; набор — HEADLESS_ON.
"""

import re
import json
import logging

import config

log = logging.getLogger("headless")

TITLE_KEYS = ("name", "title", "subject", "lot_name", "lotname", "purchase_name",
              "tender_name", "product_name", "description", "notice_title",
              "name_ru", "name_uz", "nameru", "nameuz", "goods_name")
ID_KEYS = ("id", "lot_id", "lotid", "tender_id", "tenderid", "notice_id", "display_no",
           "number", "guid", "code", "reg_number", "regnumber")
DEADLINE_KEYS = ("end_date", "enddate", "deadline", "date_end", "dateend", "clarific_date",
                 "finish_date", "finishdate", "trade_end", "date_finish", "closing_date",
                 "close_at", "closing_at", "close_date")
# «Признак» настоящего тендера — чтобы не путать со справочником категорий (id+name).
SIGNAL_KEYS = DEADLINE_KEYS + ("start_date", "startdate", "display_no", "cost", "amount",
                               "price", "start_price", "seller_name", "buyer_name", "buyer",
                               "publication-date", "noticedate", "publicated_at", "totalcost")
BUYER_KEYS = ("seller_name", "buyer_name", "buyer", "organization", "customer_name",
              "contact_organization", "purchaser", "org_name")
COST_KEYS = ("cost", "amount", "price", "budget", "start_price", "sum", "start_cost",
             "totalcost", "total_cost")
REGION_KEYS = ("region_name", "district_name", "location", "place", "region")
CURR_KEYS = ("currency_codeabc", "currency_code", "currency_name", "currency")


def _first(d: dict, keys):
    low = {k.lower(): k for k in d.keys()}
    for want in keys:
        k = low.get(want.lower())
        if k is not None and d[k] not in (None, "", [], {}):
            return d[k]
    return None


def _looks_like_tender(d, require_signal=True) -> bool:
    if not (isinstance(d, dict) and _first(d, TITLE_KEYS) is not None
            and _first(d, ID_KEYS) is not None):
        return False
    # для тендеров требуем «признак» (дедлайн/цена/заказчик), чтобы не путать со справочником;
    # для проектов/драфтов (pppda, regulation) — не требуем.
    return _first(d, SIGNAL_KEYS) is not None if require_signal else True


def _walk(obj, out, require_signal):
    if isinstance(obj, list):
        out.extend(x for x in obj if _looks_like_tender(x, require_signal))
        for x in obj:
            _walk(x, out, require_signal)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk(v, out, require_signal)


def extract_records(captured: list, require_signal: bool = True) -> list:
    """Достаём уникальные тендер-подобные записи. Понимает и «сырые» тела, и {url, body}."""
    out = []
    for blob in captured:
        target = blob["body"] if isinstance(blob, dict) and set(blob.keys()) >= {"url", "body"} \
            else blob
        _walk(target, out, require_signal)
    seen, uniq = set(), []
    for d in out:
        key = str(_first(d, ID_KEYS))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    return uniq


def _render(page, url, captured):
    """Перехватываем ВСЕ JSON-ответы (по content-type), без фильтра по ключевым словам."""
    def on_resp(resp):
        try:
            if "json" in resp.headers.get("content-type", "").lower():
                captured.append({"url": resp.url, "body": resp.json()})
        except Exception:
            pass
    page.on("response", on_resp)
    # domcontentloaded, а не networkidle: на etender висит чат-виджет (jivosite),
    # из-за которого networkidle не наступает и goto падает по таймауту.
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)   # даём XHR-запросам отработать (их ловит on_resp)
    try:
        return page.eval_on_selector_all(
            "a[href*='tender'],a[href*='lot'],a[href*='view'],a[href*='detail'],"
            "a[href*='notice'],a[href*='csrn'],a[href*='Notice'],a[href*='procedure']",
            "els=>els.map(e=>({href:e.href,text:(e.innerText||'').trim()})).filter(x=>x.text)")
    except Exception:
        return []


def _enrich(d: dict) -> dict:
    """Доп. поля для карточки, если они есть в записи."""
    m = {"deadline": _first(d, DEADLINE_KEYS), "buyer": _first(d, BUYER_KEYS),
         "cost": _first(d, COST_KEYS), "region": _first(d, REGION_KEYS),
         "currency": _first(d, CURR_KEYS), "number": str(_first(d, ID_KEYS))}
    return {k: v for k, v in m.items() if v not in (None, "")}


def _summary(title, meta) -> str:
    bits = [title]
    if meta.get("buyer"):
        bits.append(f"Заказчик: {meta['buyer']}")
    if meta.get("cost"):
        bits.append(f"Сумма: {meta['cost']} {meta.get('currency','')}".strip())
    if meta.get("region"):
        bits.append(f"Регион: {meta['region']}")
    return ". ".join(str(b) for b in bits)


def _kw_match(text, keywords) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


def _norm_txt(s: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", (s or "").lower())


def _build(src, records, dom, mk, region_match, max_items):
    intl = src["cat"] == config.CAT_INTL
    consulting = src.get("consulting_only", False)
    pk = src.get("prefer_key")
    if pk and any(pk in d for d in records):
        records = [d for d in records if pk in d]
    dom_by_num, dom_by_text = {}, []
    for l in dom:
        m = re.search(r"(\d{5,})", l["href"])
        if m:
            dom_by_num[m.group(1)] = l["href"]
        t = _norm_txt(l["text"])
        if len(t) >= 15:                      # осмысленный текст ссылки → матч по названию
            dom_by_text.append((t, l["href"]))

    items = []
    for d in records:
        title = str(_first(d, TITLE_KEYS))[:280]
        blob = json.dumps(d, ensure_ascii=False)
        if intl and not region_match(blob):                       # регион: по всему телу
            continue
        if consulting and not _kw_match(title, config.CONSULTING_KEYWORDS):  # консалтинг: по названию
            continue
        meta = _enrich(d)
        if consulting:
            meta["kw_match"] = True   # прошёл словарь консалтинга/ИТ → floor в run.py
        num = meta.get("number", "")
        url = (src["detail_url"].format(id=num) if src.get("detail_url") and num
               else dom_by_num.get(num))
        if not url:                            # матч по названию (xt-xarid: /procedure/{id}/core)
            tn = _norm_txt(title)
            for dt, href in dom_by_text:
                if tn[:40] and (tn[:40] in dt or dt[:40] in tn):
                    url = href
                    break
        if not url:
            url = src["url"]
            meta["portal_only"] = True         # прямой ссылки нет — ведём на портал, покажем №
        items.append(mk(src["source"], src["cat"], src["origin"],
                        f"[{src['key']}] {title}", url, None,
                        summary=_summary(title, meta)[:600], full_text=blob[:2500], meta=meta,
                        uid=f"{src['key']}:{num}" if num else None))
        if len(items) >= max_items:
            break

    # Запасной вариант — ссылки из DOM. Только если API вообще не дал записей
    # (иначе для etender налипнут бесполезные ссылки «Batafsil»).
    if not items and not records and dom:
        for l in dom[:max_items]:
            text = f"{l['text']} {l['href']}"
            if intl and not region_match(text):
                continue
            if consulting and not _kw_match(l["text"], config.CONSULTING_KEYWORDS):
                continue
            items.append(mk(src["source"], src["cat"], src["origin"],
                            f"[{src['key']}] {l['text'][:200]}", l["href"], None,
                            summary=l["text"], full_text=l["text"]))
    return items


_UN_AGENCIES = ("UNDP", "UNICEF", "UNOPS", "UNFPA", "UNHCR", "UNESCO", "UNIDO",
                "UN WOMEN", "UNWOMEN", "WFP", "FAO", "ILO", "IOM", "WHO", "WIPO",
                "ITC", "IFAD", "UNAIDS", "UNU", "UN ", "МОТ", "ПРООН")


def _ungm_rows(page) -> list:
    return page.evaluate("""() => {
      const seen = new Set(); const out = [];
      document.querySelectorAll("a[href*='/Public/Notice/']").forEach(a => {
        const href = a.getAttribute('href');
        if (!/\\/Public\\/Notice\\/\\d+/.test(href) || seen.has(href)) return;
        seen.add(href);
        let el = a;
        for (let i = 0; i < 8 && el.parentElement; i++) {
          el = el.parentElement;
          if (el.innerText && el.innerText.trim().length > 120) break;
        }
        out.push({href, text: (el.innerText || '').trim().slice(0, 700)});
      });
      return out;
    }""")


def _collect_ungm(ctx, mk, region_match, max_items) -> list:
    """UNGM (вся система ООН: ПРООН, МОТ, IOM, FAO, ЮНИСЕФ, WFP…):
    для каждой страны из UNGM_COUNTRIES — выбрать её в фильтре, нажать Search,
    разобрать строки результатов (title/deadline/agency/reference)."""
    items, seen_ids = [], set()
    for country in config.UNGM_COUNTRIES:
        page = ctx.new_page()
        try:
            page.goto("https://www.ungm.org/Public/Notice",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            # всплывающий диалог перекрывает страницу — закрываем
            try:
                page.keyboard.press("Escape")
                page.evaluate("document.querySelectorAll('.ui-widget-overlay, .ui-dialog')"
                              ".forEach(e => e.remove())")
            except Exception:
                pass
            # фильтр страны: автокомплит → первый пункт; до 3 попыток, проверяем,
            # что страна реально выбрана (иначе UNGM отдаёт ГЛОБАЛЬНУЮ ленту —
            # так утекали Африка/ЛатАм под тегом [UN·KAZ]).
            selected = False
            for attempt in range(3):
                try:
                    page.fill("#selNoticeCountry-input", country)
                    # ждём именно появления пункта, а не фиксированную паузу
                    page.wait_for_selector(f"li.ui-menu-item >> text={country}",
                                           timeout=4000 + attempt * 2000)
                    page.click(f"li.ui-menu-item >> text={country}", timeout=2500)
                except Exception:
                    page.keyboard.press("ArrowDown")
                    page.keyboard.press("Enter")
                page.wait_for_timeout(700)
                chk = page.evaluate(
                    "() => ({sel: (document.querySelector('#isCountrySelected')||{}).value || '',"
                    "        id: (document.querySelector('#selNoticeCountry')||{}).value || '',"
                    "        inp: (document.querySelector('#selNoticeCountry-input')||{}).value || ''})")
                if str(chk.get("sel")) == "1" or (chk.get("id") and country.lower() in str(chk.get("inp")).lower()):
                    selected = True
                    break
                # сброс перед новой попыткой
                try:
                    page.fill("#selNoticeCountry-input", "")
                    page.wait_for_timeout(600)
                except Exception:
                    pass
            if not selected:
                log.warning("headless ungm [%s]: страна не выбралась — пропуск, чтобы не тянуть глобальную ленту", country)
                continue
            page.click("button:has-text('Search')", timeout=8000, force=True)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(2500)
            rows = _ungm_rows(page)
            # страховка: строки, где явно названа чужая страна и нет нашей — выкидываем
            _cn = country.lower()
            rows = [r for r in rows
                    if _cn in r["text"].lower() or region_match(r["text"])
                    or not any(k in r["text"].lower() for k in config.OFFREGION_KEYWORDS)]
            n = 0
            for r in rows:
                m_id = re.search(r"/Public/Notice/(\d+)", r["href"])
                nid = m_id.group(1) if m_id else None
                if not nid or nid in seen_ids:
                    continue
                seen_ids.add(nid)
                lines = [l.strip() for l in r["text"].split("\n") if l.strip()]
                title = next(
                    (l for l in lines
                     if len(l) >= 15 and "GMT" not in l and "Expires" not in l
                     and not re.search(r"\d{1,2}-[A-Za-z]{3}-\d{4}", l)),
                    lines[0] if lines else "UN notice")
                agency = next((a for a in _UN_AGENCIES
                               if any(a.lower() in l.lower() for l in lines)),
                              "").strip() or "UN"
                m_dl = re.search(r"\b(\d{1,2}[-–][A-Za-z]{3}[-–]\d{4})\b", r["text"])
                items.append(mk(
                    f"UNGM · {agency}", config.CAT_INTL, "ungm.org",
                    f"[UN·{country[:3].upper()}] {title[:230]}",
                    f"https://www.ungm.org{r['href']}", None,
                    summary=" · ".join(lines[:6])[:700], full_text=r["text"][:2500],
                    uid=f"ungm:{nid}",
                    meta={"deadline": m_dl.group(1) if m_dl else None,
                          "agency": agency, "country": country}))
                n += 1
                if len(items) >= max_items:
                    break
            log.info("headless ungm [%s]: строк=%d → %d", country, len(rows), n)
        except Exception as e:
            log.warning("headless ungm [%s] FAIL: %s", country, e)
        finally:
            page.close()
        if len(items) >= max_items:
            break
    return items


def run_headless(keys=None, force=False) -> list:
    """Собрать headless-источники. keys=None → все из HEADLESS_ON. force=True → игнор флага."""
    from sources import _mk, _region_match
    if not (config.HEADLESS_ENABLED or force):
        return []
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        log.warning("headless: нет playwright — pip install playwright && playwright install chromium")
        return []

    want = set(keys) if keys else set(config.HEADLESS_ON)
    srcs = [s for s in config.HEADLESS_SOURCES if s["key"] in want]
    if not srcs:
        return []

    items = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True,
                                        args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = browser.new_context(user_agent=config.HTTP_HEADERS["User-Agent"],
                                      locale="ru-RU")
            for s in srcs:
                try:
                    if s.get("custom") == "ungm":
                        items += _collect_ungm(ctx, _mk, _region_match, config.HEADLESS_MAX)
                        continue
                    captured = []
                    page = ctx.new_page()
                    dom = _render(page, s["url"], captured)
                    page.close()
                    _dump(s["key"], captured, dom)
                    records = extract_records(captured, s.get("require_signal", True))
                    built = _build(s, records, dom, _mk, _region_match, config.HEADLESS_MAX)
                    log.info("headless %s: JSON=%d dom=%d → %d",
                             s["key"], len(records), len(dom), len(built))
                    items += built
                except Exception as e:
                    log.warning("headless %s FAIL: %s", s["key"], e)
            browser.close()
    except Exception as e:
        log.warning("headless движок FAIL: %s", e)
    return items


def _dump(key, captured, dom):
    """Диагностический дамп: адреса JSON-ответов + ссылки DOM + сами тела (усечённо)."""
    try:
        payload = {
            "urls": [c["url"] for c in captured if isinstance(c, dict) and "url" in c],
            "dom": dom[:60],
            "captured": captured[:60],          # ограничиваем число, но JSON остаётся ВАЛИДНЫМ
        }
        (config.LOG_FILE.parent / f"{key}_capture.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def collect_all_headless() -> list:
    return run_headless()
