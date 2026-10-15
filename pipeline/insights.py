"""
Аналитика: LLM-дайджест новых НПА → готовый материал для раздела «Аналитика»
(и для переноса на topadvisor.biz).

Генерируется не чаще, чем раз в INSIGHT_EVERY_DAYS, и только если за период
накопилось достаточно актов. Модель: MODEL_INSIGHT (Sonnet), при ошибке —
падение на MODEL_ANALYZE. Строгое заземление: только предоставленные тексты.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import config
import llm
from store import Store

log = logging.getLogger("insights")


def _fmt_period(days: int) -> str:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря"]
    if start.month == end.month:
        return f"{start.day}–{end.day} {months[end.month - 1]} {end.year}"
    return (f"{start.day} {months[start.month - 1]} — "
            f"{end.day} {months[end.month - 1]} {end.year}")


def _law_items(store: Store, days: int) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = store.db.execute(
        "SELECT * FROM items WHERE category=? AND first_seen>=? ORDER BY first_seen",
        (config.CAT_LAW, cutoff)).fetchall()
    return [dict(r) for r in rows]


def should_generate(store: Store) -> bool:
    last = store.db.execute(
        "SELECT MAX(created) FROM insights WHERE kind='law'").fetchone()[0]
    if last:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_dt < timedelta(days=config.INSIGHT_EVERY_DAYS):
            return False
    return len(_law_items(store, config.INSIGHT_LOOKBACK_DAYS)) >= config.INSIGHT_MIN_LAW_ITEMS


def _weekly_model(prompt: str) -> dict | None:
    """Недельный обзор: Opus 5.5, JSON по схеме; отказ классификатора — серверная замена модели."""
    try:
        # длинный ответ → потоковый режим (иначе SDK отказывается: «Streaming is required…»)
        with llm._anthropic().beta.messages.stream(
                model=config.MODEL_INSIGHT, max_tokens=32000,
                output_config={"effort": "high",
                               "format": {"type": "json_schema", "schema": config.WEEKLY_SCHEMA}},
                betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"},
                messages=[{"role": "user", "content": prompt}]) as stream:
            resp = stream.get_final_message()
        if resp.stop_reason == "refusal":
            log.warning("Обзор: отказ модели")
            return None
        return json.loads(next(b.text for b in resp.content if b.type == "text"))
    except Exception as e:
        log.warning("Обзор: модель %s FAIL: %s", config.MODEL_INSIGHT, e)
        return None


def generate_law_insight(store: Store, force: bool = False) -> dict | None:
    """Недельный регуляторный обзор из РАЗБОРОВ актов (analysis.act), а не из сырых заголовков."""
    if not config.ANTHROPIC_KEY:
        log.info("Обзор: нет ANTHROPIC_API_KEY — пропуск")
        return None
    if not force and not should_generate(store):
        log.info("Обзор: рано (раз в %d дн) или мало актов — пропуск", config.INSIGHT_EVERY_DAYS)
        return None
    items = _law_items(store, config.INSIGHT_LOOKBACK_DAYS)
    order = {"высокая": 0, "средняя": 1, "низкая": 2}
    acts = []
    for it in items:
        try:
            a = json.loads(it["analysis"] or "{}").get("act")
        except Exception:
            a = None
        if not a:
            continue
        acts.append({"act": a.get("number") or it["title"][:60], "type": a.get("act_type"),
                     "title": a.get("title_ru"), "importance": a.get("importance"),
                     "effective": a.get("effective"), "spheres": a.get("spheres"),
                     "essence": a.get("essence"), "key_changes": a.get("key_changes"),
                     "business_impact": a.get("business_impact"), "obligations": a.get("obligations"),
                     "opportunities": a.get("opportunities"),
                     "expected_procurements": a.get("expected_procurements"),
                     "_item": it["id"], "_url": it["url"]})
    acts.sort(key=lambda x: order.get(x.get("importance") or "", 3))
    if len(acts) < config.INSIGHT_MIN_LAW_ITEMS:
        log.info("Обзор: разобранных актов за период %d — мало", len(acts))
        return None
    period = _fmt_period(config.INSIGHT_LOOKBACK_DAYS)
    payload = [{k: v for k, v in a.items() if not k.startswith("_")} for a in acts[:45]]
    data = _weekly_model(config.WEEKLY_PROMPT.format(
        period=period, company_profile=config.COMPANY_PROFILE,
        acts=json.dumps(payload, ensure_ascii=False)))
    if not data:
        return None
    sources = [{"keys": [a["act"]], "title": a.get("title") or "", "url": a["_url"], "itemId": a["_item"],
                "importance": a.get("importance")} for a in acts[:45]]
    now = datetime.now(timezone.utc)
    insight_id = f"law-week-{now.strftime('%Y-%m-%d')}"
    body = {k: data.get(k, []) for k in ("top_acts", "sections", "for_business", "opportunities",
                                         "pipeline", "calendar")}
    body["format"] = "weekly-v2"
    store.db.execute(
        "INSERT OR REPLACE INTO insights(id, kind, title, lead, body, sources, period, created) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (insight_id, "law", data.get("title", ""), data.get("lead", ""),
         json.dumps(body, ensure_ascii=False), json.dumps(sources, ensure_ascii=False),
         period, now.isoformat(timespec="seconds")))
    store.db.commit()
    log.info("Обзор сохранён: %s — %s (актов %d)", insight_id, data.get("title", "")[:80], len(acts))
    return {"id": insight_id, **data}
