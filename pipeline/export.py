"""
Экспорт данных для сайта → web/data/*.json (коммитятся, сайт читает их при сборке).

  feed.json  — лёгкий список карточек для ленты (фильтры на клиенте)
  items.json — полные записи с анализом (страницы /t/[slug])
  npa.json   — реестр НПА: карточка акта + прикреплённые упоминания (/npa/[slug])
  meta.json  — время обновления, счётчики
"""

import re
import json
import logging
from datetime import datetime, timezone

import config
from store import Store

log = logging.getLogger("export")

FEED_LIMIT = 500          # свежих карточек в ленте
ITEMS_LIMIT = 800         # полных записей (страницы)

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _norm_deadline(v) -> str | None:
    """Приводим дедлайн к YYYY-MM-DD, если формат распознан; иначе исходная строка."""
    if not v:
        return None
    s = str(v).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\b(\d{1,2})-([A-Za-z]{3})[a-z]*-(\d{4})\b", s)     # 28-Aug-2026
    if m and m.group(2).lower() in _MONTHS:
        return f"{m.group(3)}-{_MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(\d{2})[./](\d{2})[./](\d{4})\b", s)             # 28.08.2026 | 28/08/2026
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return s


def _row_to_item(r) -> dict:
    analysis = json.loads(r["analysis"]) if r["analysis"] else {}
    meta = json.loads(r["meta"]) if r["meta"] else {}
    npa_refs = json.loads(r["npa_refs"]) if r["npa_refs"] else []
    return {
        "id": r["id"], "category": r["category"], "source": r["source"],
        "origin": r["origin"], "title": r["title"], "url": r["url"],
        "published": r["published"] or None, "firstSeen": r["first_seen"],
        "score": r["score"], "npaRefs": npa_refs,
        "buyer": meta.get("buyer") or analysis.get("target_entity"),
        "deadline": _norm_deadline(analysis.get("deadline_info") or meta.get("deadline")),
        "titleRu": analysis.get("title_ru"),
        "summaryRu": analysis.get("summary_ru"),
        "siteBrief": analysis.get("site_brief"),
        "opportunityType": analysis.get("opportunity_type"),
        "budget": analysis.get("budget_info") or meta.get("cost"),
        "eligibility": analysis.get("eligibility"),
        "docsChecklist": analysis.get("docs_checklist") or [],
        "recommendation": analysis.get("consulting_recommendation"),
        "urgency": analysis.get("urgency"),
        "summary": r["summary"],
    }


def export_all(store: Store) -> list:
    """Пишет web/data/*.json; возвращает items (их же зеркалим в Supabase)."""
    config.WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = store.db.execute(
        "SELECT * FROM items ORDER BY first_seen DESC LIMIT ?", (ITEMS_LIMIT,)).fetchall()
    items = []
    for r in rows:
        it = _row_to_item(r)
        # новости на сайт — только релевантные; тендеры/НПА/позиции — все
        if it["category"] == config.CAT_NEWS and (it["score"] or 0) < config.SITE_MIN_NEWS_SCORE:
            continue
        items.append(it)

    feed = [{k: it.get(k) for k in
             ("id", "category", "source", "origin", "titleRu", "title", "summaryRu",
              "buyer", "deadline", "budget", "score", "urgency", "published",
              "firstSeen", "npaRefs", "url")}
            for it in items[:FEED_LIMIT]]

    # НПА: реестр + упоминания
    npa = []
    for reg in store.db.execute(
            "SELECT * FROM npa_registry ORDER BY first_seen DESC").fetchall():
        mentions = [dict(m) for m in store.db.execute(
            "SELECT item_id, kind, title, url, added FROM npa_mentions "
            "WHERE npa_key=? ORDER BY added", (reg["npa_key"],))]
        npa.append({"key": reg["npa_key"], "itemId": reg["item_id"],
                    "title": reg["title"], "firstSeen": reg["first_seen"],
                    "mentions": mentions})

    # Аналитика
    ins = []
    for r in store.db.execute(
            "SELECT * FROM insights ORDER BY created DESC LIMIT 50").fetchall():
        body = json.loads(r["body"] or "{}")
        ins.append({"id": r["id"], "kind": r["kind"], "title": r["title"],
                    "lead": r["lead"], "period": r["period"], "created": r["created"],
                    "sections": body.get("sections", []),
                    "businessImpact": body.get("business_impact", []),
                    "howToPrepare": body.get("how_to_prepare", []),
                    "sources": json.loads(r["sources"] or "[]")})

    stats = store.stats()
    meta = {"updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "counts": {"feed": len(feed), "items": len(items), "npa": len(npa),
                       "insights": len(ins)},
            "stats": stats}

    for name, data in (("feed.json", feed), ("items.json", items),
                       ("npa.json", npa), ("insights.json", ins), ("meta.json", meta)):
        (config.WEB_DATA_DIR / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Экспорт: feed=%d items=%d npa=%d insights=%d → %s",
             len(feed), len(items), len(npa), len(ins), config.WEB_DATA_DIR)
    return items
