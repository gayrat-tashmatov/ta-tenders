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


def _send(text: str, buttons=None, chat: str | None = None) -> bool:
    """buttons — список (label, url); chat — другой чат (по умолчанию канал)."""
    chat = chat or config.TELEGRAM_CHAT
    if not (config.TELEGRAM_TOKEN and chat):
        log.warning("Telegram: нет токена/чата — пропуск отправки")
        return False
    payload = {
        "chat_id": chat,
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
        path = "law" if item.get("category") == config.CAT_LAW else "item"
        btns.append(("Разбор в кабинете", f"{config.SITE_BASE_URL}/app/{path}/{slug}"))
    meta = item.get("meta") or {}
    if meta.get("portal_only"):
        num = str(meta.get("number") or "")[:25]
        btns.append((f"Портал · лот № {num}" if num else "Портал ↗", item["url"]))
    elif item.get("origin") == "TenderWeek":
        btns.append(("TenderWeek (нужен вход) ↗", item["url"]))
    else:
        btns.append(("Источник ↗", item["url"]))
    return btns


_DIR_TG = {"право": "право", "бизнес": "бизнес-консалтинг", "ИТ_цифровизация": "ИТ и цифровизация",
           "энергетика_климат": "энергетика и климат", "пограничный": "смежное направление"}
# В канал не пишем, КОМУ подходит (имена и компании) — только направления (15.10.2026)
_NAMES_RE = re.compile(r"(TopAdvisor|Top Advisor|UNISON(\s+CONSULT)?|BizAdvisor|Гайрат\w*|Ташматов\w*|Tashmatov|Gayrat)", re.I)


def _no_names(text: str) -> str | None:
    """Текст без упоминаний компаний и людей; если без них фраза теряет смысл — None."""
    if not text:
        return None
    if not _NAMES_RE.search(text):
        return text
    cleaned = _NAMES_RE.sub("", text)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s{2,}", " ", cleaned)).strip(" ,;:—-")
    # «профиль  по бизнес-консалтингу» и т.п. — если осталось меньше половины, не показываем
    return cleaned if len(cleaned) > 0.6 * len(text) else None


def is_expert(item: dict, a: dict) -> bool:
    return item["category"] == config.CAT_JOB or str(a.get("audience") or "").lower() in ("эксперт", "оба")


def act_card(item: dict, a: dict) -> tuple:
    """Карточка закона: суть, что меняется, что это даёт — и кому из нас это работа."""
    r = a["act"]
    imp = {"высокая": "⚖️❗", "средняя": "⚖️"}.get(r.get("importance"), "⚖️")
    head = r.get("title_ru") or _headline(item, a)
    sub = " · ".join(x for x in (r.get("act_type"), r.get("number") and f"№ {r['number']}",
                                  r.get("effective") and f"в силу {_short_date(r['effective'])}") if x)
    lines = [f"{imp} <b>{esc(_trim(head, 160))}</b>", f"<i>{esc(sub)}</i>", ""]
    if r.get("essence"):
        lines.append(esc(_trim(r["essence"], 420)))
    ch = [x for x in r.get("key_changes", []) if x][:3]
    if ch:
        lines.append("\n<b>Что меняется:</b>")
        lines += [f"• {esc(_trim(x, 180))}" for x in ch]
    bi = _no_names(r.get("business_impact") or "")
    if bi:
        lines.append(f"\n<b>Бизнесу:</b> {esc(_trim(bi, 300))}")
    opp = [w for w in (_no_names(o.get("what", "")) for o in r.get("opportunities", []) if o.get("for") != "бизнес") if w][:2]
    if opp:
        lines.append("<b>Возможности:</b> " + "; ".join(esc(_trim(w, 160)) for w in opp))
    proc = [x for x in r.get("expected_procurements", []) if x][:2]
    if proc:
        lines.append("<b>Будут закупать:</b> " + "; ".join(esc(_trim(x, 140)) for x in proc))
    return "\n".join(lines), _buttons(item)


def card(item: dict, a: dict) -> tuple:
    """Структурная карточка: с первого взгляда понятно КТО объявил, ЧТО нужно,
    ЗАЧЕМ это нам, СРОКИ и ЧТО ДЕЛАТЬ. Детали — в кабинете."""
    if item["category"] == config.CAT_LAW and a.get("act"):
        return act_card(item, a)
    head = _headline(item, a)
    cat = item["category"]
    kind = {config.CAT_INTL: "Международный тендер", config.CAT_UZTEND: "Тендер · Узбекистан",
            config.CAT_LAW: "Новый НПА", config.CAT_JOB: "Позиция эксперта"}.get(cat, "Материал")
    if is_expert(item, a):
        kind = "👤 Для эксперта · " + kind
    lines = [f"{_ICON.get(cat, '•')} <b>{esc(head)}</b>",
             f"<i>{esc(kind)} · {esc(item['origin'])}</i>", ""]
    direction = _DIR_TG.get(str(a.get("profile_match") or ""))
    why = _no_names(a.get("profile_reason") or "")
    if direction or why:
        head_dir = f"<b>Подходит по направлению:</b> {esc(direction)}" if direction else "<b>Подходит:</b>"
        lines.append(head_dir + (f" — {esc(_trim(why, 200))}" if why else ""))

    # КТО и ЧТО
    who = a.get("target_entity")
    if who:
        lines.append(f"<b>Кто:</b> {esc(_trim(who, 90))}")
    what = a.get("summary_ru")
    if what:
        lines.append(f"<b>Что нужно:</b> {esc(_trim(what, 420))}")

    # СРОКИ и ДЕНЬГИ — одной строкой
    facts = []
    pub = _short_date(item.get("meta", {}).get("published") or item.get("published"))
    if pub:
        facts.append(f"📅 опубл. {pub}")
    dl = _short_date(a.get("deadline_info") or item.get("meta", {}).get("deadline"))
    if dl:
        facts.append(f"⏳ до {dl}")
    upd = _short_date(item.get("meta", {}).get("updated"))
    if upd:
        facts.append(f"🔄 обновлено {upd}")
    rep = item.get("meta", {}).get("repeat_of")
    if rep:
        facts.append(f"🔁 повтор лота №{esc(str(rep))} от {_short_date(item['meta'].get('repeat_seen')) or '?'}")
    donor = item.get("meta", {}).get("donor") or item.get("meta", {}).get("agency")
    if donor and donor not in ("UN",):
        facts.append(f"🏦 {esc(_trim(str(donor), 40))}")
    if a.get("budget_info"):
        facts.append(f"💰 {esc(_trim(a['budget_info'], 50))}")
    urg = (a.get("urgency") or "").lower()
    if urg in ("критическая", "высокая"):
        facts.append("🔥 срочно")
    if facts:
        lines.append(" · ".join(facts))

    # ЗАЧЕМ НАМ и ЧТО ДЕЛАТЬ
    rec = _no_names(a.get("consulting_recommendation") or "")
    if rec and rec != "Изучить условия":
        lines.append(f"\n<b>Что предложить:</b> {esc(_trim(rec, 260))}")
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
        return 0          # пустые прогоны в канал не пишем (9 прогонов в день = 9 «ничего нет»)

    cat_of = lambda p: p["item"]["category"]
    by_score = lambda p: -(p["analysis"].get("relevance_score") or p.get("score") or 0)
    # позиции экспертов — полноценными карточками (раньше уходили одной строкой в сводке)
    tenders_law = [p for p in processed
                   if cat_of(p) in (config.CAT_INTL, config.CAT_UZTEND, config.CAT_LAW, config.CAT_JOB)]
    jobs = []
    news = sorted([p for p in processed if cat_of(p) == config.CAT_NEWS], key=by_score)

    header = (f"🔔 <b>TA Tenders</b> — {time.strftime('%d.%m.%Y')}\n"
              f"Тендеры/НПА: <b>{len(tenders_law)}</b> · Позиции: <b>{len(jobs)}</b> · "
              f"Новости: <b>{len(news)}</b>")
    hdr_btn = [("Открыть «Сегодня»", f"{config.SITE_BASE_URL}/app")] if config.SITE_BASE_URL else None
    if len(processed) >= 3:
        _send(header, hdr_btn)
        time.sleep(SEND_GAP)

    sent = 0
    order = {config.CAT_INTL: 0, config.CAT_UZTEND: 1, config.CAT_JOB: 2, config.CAT_LAW: 3}
    for p in sorted(tenders_law, key=lambda x: (order.get(cat_of(x), 9), by_score(x))):
        text, buttons = card(p["item"], p["analysis"])
        if _send(text, buttons):
            sent += 1
        if config.TELEGRAM_EXPERT_CHAT and is_expert(p["item"], p["analysis"]):
            _send(text, buttons, chat=config.TELEGRAM_EXPERT_CHAT)
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
    """Анонс недельного регуляторного обзора: лид, 3 главных акта и что делать."""
    lines = [f"📊 <b>Обзор недели: {esc(insight.get('title', 'регуляторные изменения'))}</b>", "",
             esc(_trim(insight.get("lead", ""), 600))]
    top = insight.get("top_acts") or []
    if top:
        lines.append("\n<b>Главное:</b>")
        for t in top[:3]:
            lines.append(f"• <b>{esc(_trim(t.get('title', ''), 120))}</b> — {esc(_trim(t.get('action', ''), 160))}")
    pipe = insight.get("pipeline") or []
    if pipe:
        lines.append(f"\n<b>Ожидаемые закупки:</b> {len(pipe)} — список в обзоре")
    buttons = []
    if config.SITE_BASE_URL and insight.get("id"):
        buttons.append(("Читать обзор", f"{config.SITE_BASE_URL}/app/analytics/{insight['id']}"))
    return _send("\n".join(lines), buttons or None)


def send_test() -> bool:
    return _send("✅ <b>TA Tenders</b> — тест связи. HTML работает: "
                 "&lt;цена&gt; 1.000.000 сум (100%).")


def send_morning(store) -> bool:
    """«Сегодня в кабинете» — один раз в день после MORNING_HOUR_TASHKENT: что нового за сутки
    по трём трекам, лучшее по каждому и ближайшие сроки. Это повод открыть кабинет утром."""
    from datetime import datetime, timedelta, timezone
    now_tk = datetime.now(timezone.utc) + timedelta(hours=5)
    today = now_tk.strftime("%Y-%m-%d")
    if now_tk.hour < config.MORNING_HOUR_TASHKENT or store.kv_get("morning_sent") == today:
        return False
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    rows = store.db.execute(
        "SELECT * FROM items WHERE first_seen >= ? AND category != ? ORDER BY score DESC", (since, config.CAT_NEWS)).fetchall()
    def an(r):
        try:
            return json.loads(r["analysis"] or "{}")
        except Exception:
            return {}
    comp, exp, acts = [], [], []
    for r in rows:
        a = an(r)
        if r["category"] == config.CAT_LAW:
            if (a.get("act") or {}).get("importance") in ("высокая", "средняя"):
                acts.append((r, a))
        elif (r["score"] or 0) >= 7 and str(a.get("profile_match") or "") != "нет":
            (exp if str(a.get("audience") or "") in ("эксперт", "оба") or r["category"] == config.CAT_JOB else comp).append((r, a))
    if not (comp or exp or acts):
        store.kv_set("morning_sent", today)
        return False
    def line(r, a):
        return f"• {esc(_trim(a.get('title_ru') or _strip_tag(r['title']), 110))}"
    out = [f"☀️ <b>Сегодня в кабинете</b> — {now_tk.strftime('%d.%m')}", ""]
    if comp:
        out.append(f"<b>Для компаний:</b> {len(comp)}")
        out += [line(r, a) for r, a in comp[:3]]
    if exp:
        out.append(f"\n<b>👤 Для эксперта:</b> {len(exp)}")
        out += [line(r, a) for r, a in exp[:3]]
    if acts:
        imp = sum(1 for _, a in acts if a["act"].get("importance") == "высокая")
        out.append(f"\n<b>⚖️ Законодательство:</b> {len(acts)} актов с разбором, из них важных {imp}")
        out += [f"• {esc(_trim(a['act'].get('title_ru') or r['title'], 110))}" for r, a in acts[:2]]
    btn = [("Открыть «Сегодня»", f"{config.SITE_BASE_URL}/app")] if config.SITE_BASE_URL else None
    ok = _send("\n".join(out), btn)
    if ok:
        store.kv_set("morning_sent", today)
    return ok


def check_expert_chat(store) -> None:
    """Разово подтверждает личный чат эксперта (секрет TELEGRAM_EXPERT_CHAT_ID) и пишет итог в kv —
    так проверка видна в данных репозитория, без доступа к логам GitHub."""
    import hashlib
    chat = config.TELEGRAM_EXPERT_CHAT
    if not chat:
        store.kv_set("expert_chat", "не задан")
        return
    tag = hashlib.sha1(chat.encode()).hexdigest()[:8]
    if (store.kv_get("expert_chat") or "").startswith(f"ok:{tag}"):
        return
    ok = _send("✅ <b>Личные уведомления эксперта подключены.</b>\n\nСюда будут приходить позиции "
               "для индивидуального консультанта. Общие тендеры и законы — в канале.", chat=chat)
    from datetime import datetime, timezone
    store.kv_set("expert_chat", f"{'ok' if ok else 'ошибка'}:{tag}:{datetime.now(timezone.utc).isoformat(timespec='minutes')}")
