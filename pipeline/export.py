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

FEED_LIMIT = 2000         # карточек в ленте (все тендеры/НПА + релевантные новости)
ITEMS_LIMIT = 2000        # тендеры/НПА/позиции (не-новости) за NONNEWS_DAYS
NEWS_LIMIT = 300          # релевантных новостей (score ≥ SITE_MIN_NEWS_SCORE)
NONNEWS_DAYS = 120        # глубина витрины для тендеров/НПА
EXPIRED_KEEP_DAYS = 30    # закрытые тендеры держим ещё месяц («завершён»), потом снимаем

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _budget_str(v, origin: str | None = None) -> str | None:
    """Бюджет на сайт — ВСЕГДА строка. etender/xt-xarid отдают стартовую цену числом
    (meta.cost = 1854000.0); 24.09 сборка Vercel упала на «a.budget.slice is not a function»."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        s = f"{v:,.0f}".replace(",", " ")
        return f"{s} сум" if origin in ("etender.uzex.uz", "xt-xarid.uz") else s
    if isinstance(v, (list, tuple)):
        return "; ".join(str(x) for x in v if x)[:200] or None
    if isinstance(v, dict):
        return "; ".join(f"{k}: {x}" for k, x in v.items() if x)[:200] or None
    return str(v)


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
        "portalOnly": bool(meta.get("portal_only")),
        "lotNumber": meta.get("number"),
        "titleRu": analysis.get("title_ru"),
        "summaryRu": analysis.get("summary_ru"),
        "siteBrief": analysis.get("site_brief"),
        "opportunityType": analysis.get("opportunity_type"),
        "budget": _budget_str(analysis.get("budget_info") or meta.get("cost"), r["origin"]),
        "eligibility": analysis.get("eligibility"),
        "docsChecklist": analysis.get("docs_checklist") or [],
        "recommendation": analysis.get("consulting_recommendation"),
        "legalAspects": analysis.get("legal_aspects") or [],
        "actionItems": analysis.get("action_items") or [],
        "contact": analysis.get("contact_suggestion"),
        "urgency": analysis.get("urgency"),
        "summary": r["summary"],
    }


def export_all(store: Store) -> list:
    """Пишет web/data/*.json; возвращает items (их же зеркалим в Supabase)."""
    config.WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Тендеры/НПА/позиции выбираем ОТДЕЛЬНО от новостей. До 14.09 бралось «последние 800
    # записей любой категории» — новостей копится ~150/день (все хранятся для дедупа),
    # и окно в 800 покрывало ~5 дней: 480 живых тендеров выпали с сайта («нет тендеров»).
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    keep_since = (now - timedelta(days=NONNEWS_DAYS)).isoformat()
    expired_before = (now - timedelta(days=EXPIRED_KEEP_DAYS)).strftime("%Y-%m-%d")
    rows = store.db.execute(
        "SELECT * FROM items WHERE category != ? AND first_seen >= ? "
        "ORDER BY first_seen DESC LIMIT ?",
        (config.CAT_NEWS, keep_since, ITEMS_LIMIT)).fetchall()
    rows += store.db.execute(
        "SELECT * FROM items WHERE category = ? AND score >= ? "
        "ORDER BY first_seen DESC LIMIT ?",
        (config.CAT_NEWS, config.SITE_MIN_NEWS_SCORE, NEWS_LIMIT)).fetchall()
    items = []
    for r in rows:
        it = _row_to_item(r)
        # давно закрытые тендеры (дедлайн прошёл > EXPIRED_KEEP_DAYS дней назад) — с сайта долой
        dl = (it.get("deadline") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dl) and dl < expired_before:
            continue
        items.append(it)
    items.sort(key=lambda x: x.get("firstSeen") or "", reverse=True)

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
    health = []
    try:
        for r in store.db.execute(
                "SELECT origin, last_run, last_count, last_nonzero, total_items "
                "FROM source_health ORDER BY total_items DESC").fetchall():
            health.append({"origin": r["origin"], "lastRun": r["last_run"],
                           "lastCount": r["last_count"], "lastNonzero": r["last_nonzero"],
                           "total": r["total_items"]})
    except Exception:
        pass
    meta = {"updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "counts": {"feed": len(feed), "items": len(items), "npa": len(npa),
                       "insights": len(ins)},
            "stats": stats, "health": health}

    for name, data in (("feed.json", feed), ("items.json", items),
                       ("npa.json", npa), ("insights.json", ins), ("meta.json", meta)):
        (config.WEB_DATA_DIR / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Экспорт: feed=%d items=%d npa=%d insights=%d → %s",
             len(feed), len(items), len(npa), len(ins), config.WEB_DATA_DIR)
    return items
