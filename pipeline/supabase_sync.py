"""
Синхронизация тендеров в Supabase (Postgres) для кабинета.

Пайплайн остаётся источником правды (SQLite в репо); сюда льём зеркало
для авторизованного кабинета. Работает через REST (PostgREST) сервисным
ключом — без дополнительных зависимостей. Нет ключей в env — тихий пропуск.
"""

import os
import json
import logging
from datetime import datetime

import requests

import config
from export import _norm_deadline

log = logging.getLogger("supabase")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def _iso_date(v) -> str | None:
    """deadline в колонку date: только валидная ISO-дата, иначе NULL."""
    s = _norm_deadline(v)
    if not s:
        return None
    try:
        datetime.strptime(s[:10], "%Y-%m-%d")
        return s[:10]
    except ValueError:
        return None


def _row(item: dict) -> dict:
    a = item  # экспортная форма (_row_to_item из export.py)
    return {
        "id": a["id"], "uid": a.get("id"), "category": a["category"],
        "source": a["source"], "origin": a["origin"],
        "title": a["title"], "title_ru": a.get("titleRu"),
        "url": a["url"], "published": a.get("published") or None,
        "deadline": _iso_date(a.get("deadline")),
        "buyer": a.get("buyer"), "budget": a.get("budget"),
        "score": a.get("score"), "urgency": a.get("urgency"),
        "summary_ru": a.get("summaryRu"), "site_brief": a.get("siteBrief"),
        "eligibility": a.get("eligibility"),
        "docs_checklist": a.get("docsChecklist") or [],
        "recommendation": a.get("recommendation"),
        "npa_refs": a.get("npaRefs") or [],
        "first_seen": a.get("firstSeen"),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def sync_items(export_items: list) -> bool:
    """Upsert экспортированных записей в public.tenders. True = успех/пропуск."""
    if not (SUPABASE_URL and SERVICE_KEY):
        log.info("Supabase: ключи не заданы — пропуск синхронизации")
        return True
    rows = [_row(it) for it in export_items
            if it["category"] in (config.CAT_INTL, config.CAT_UZTEND, config.CAT_JOB)]
    if not rows:
        return True
    ok = True
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    for i in range(0, len(rows), 100):
        chunk = rows[i:i + 100]
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/tenders?on_conflict=id",
                headers=headers, data=json.dumps(chunk), timeout=30)
            if r.status_code >= 300:
                log.warning("Supabase upsert FAIL %s: %s", r.status_code, r.text[:200])
                ok = False
        except Exception as e:
            log.warning("Supabase upsert FAIL: %s", e)
            ok = False
    log.info("Supabase: синхронизировано %d тендеров (%s)",
             len(rows), "ok" if ok else "с ошибками")
    return ok
