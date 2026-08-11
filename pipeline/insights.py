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


def _call_model(prompt: str):
    """MODEL_INSIGHT → при любой ошибке MODEL_ANALYZE."""
    client = llm._anthropic()
    for model in (config.MODEL_INSIGHT, config.MODEL_ANALYZE):
        try:
            resp = client.messages.create(
                model=model, max_tokens=8096,
                messages=[{"role": "user", "content": prompt}])
            data = llm._extract_json(llm._resp_text(resp))
            if isinstance(data, dict) and data.get("title") and data.get("sections"):
                log.info("Инсайт сгенерирован моделью %s", model)
                return data
            log.warning("Инсайт: модель %s вернула неожиданный формат", model)
        except Exception as e:
            log.warning("Инсайт: модель %s FAIL: %s", model, e)
    return None


def generate_law_insight(store: Store, force: bool = False) -> dict | None:
    """Возвращает созданный инсайт (или None)."""
    if not config.ANTHROPIC_KEY:
        log.info("Инсайт: нет ANTHROPIC_API_KEY — пропуск")
        return None
    if not force and not should_generate(store):
        log.info("Инсайт: условия не выполнены (рано или мало актов) — пропуск")
        return None

    items = _law_items(store, config.INSIGHT_LOOKBACK_DAYS)
    if not items:
        log.info("Инсайт: нет актов за период")
        return None

    acts_blob = []
    for it in items[:40]:
        refs = json.loads(it["npa_refs"] or "[]")
        refs_h = ", ".join(r for r in refs if not r.startswith("LEX")) or \
            ", ".join(refs) or "реквизит не распознан"
        acts_blob.append(f"- [{refs_h}] {it['title']}\n  Текст: {(it['full_text'] or '')[:500]}\n"
                         f"  Ссылка: {it['url']}")
    period = _fmt_period(config.INSIGHT_LOOKBACK_DAYS)
    prompt = config.INSIGHT_PROMPT.format(period=period, acts="\n".join(acts_blob))

    data = _call_model(prompt)
    if not data:
        return None

    # Ссылки на первоисточники для блока «Источники» на странице дайджеста
    sources = []
    for it in items[:40]:
        refs = [r for r in json.loads(it["npa_refs"] or "[]") if not r.startswith("LEX")]
        sources.append({"keys": refs, "title": it["title"][:180],
                        "url": it["url"], "itemId": it["id"]})

    now = datetime.now(timezone.utc)
    insight_id = f"law-{now.strftime('%Y-%m-%d')}"
    store.db.execute(
        "INSERT OR REPLACE INTO insights(id, kind, title, lead, body, sources, period, created) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (insight_id, "law", data.get("title", ""), data.get("lead", ""),
         json.dumps({"sections": data.get("sections", []),
                     "business_impact": data.get("business_impact", []),
                     "how_to_prepare": data.get("how_to_prepare", [])},
                    ensure_ascii=False),
         json.dumps(sources, ensure_ascii=False),
         period, now.isoformat(timespec="seconds")))
    store.db.commit()
    log.info("Инсайт сохранён: %s — %s", insight_id, data.get("title", "")[:80])
    return {"id": insight_id, **data}
