"""
Хранилище (SQLite, коммитится в репозиторий — «репо как база» для serverless-схемы).

Таблицы:
  items        — все записи с анализом (источник данных для экспорта на сайт)
  seen         — вечный дедуп-реестр (uid / URL-хеш / контент-хеш);
                 для новостей чистится через SEEN_NEWS_PRUNE_DAYS, тендеры/НПА — вечные
  npa_registry — реестр актов по реквизиту: один акт = одна карточка
  npa_mentions — упоминания акта (новости/разборы), прикрепляются к карточке
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

import config
import dedupe

log = logging.getLogger("store")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path=config.DB_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            uid TEXT, category TEXT, source TEXT, origin TEXT,
            title TEXT, url TEXT, published TEXT,
            summary TEXT, full_text TEXT, meta TEXT,
            score INTEGER, analysis TEXT, npa_refs TEXT,
            notified INTEGER DEFAULT 0,
            first_seen TEXT, toks TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_items_cat ON items(category);
        CREATE INDEX IF NOT EXISTS idx_items_first ON items(first_seen);

        CREATE TABLE IF NOT EXISTS seen (
            key TEXT PRIMARY KEY,          -- 'uid:..' | 'url:..' | 'content:..'
            category TEXT,
            first_seen TEXT
        );

        CREATE TABLE IF NOT EXISTS npa_registry (
            npa_key TEXT PRIMARY KEY,      -- 'ZRU-1137' | 'PP-394' | 'LEX-123456'
            item_id TEXT,                  -- карточка акта (items.id)
            title TEXT,
            first_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS npa_mentions (
            npa_key TEXT, item_id TEXT, kind TEXT, title TEXT, url TEXT, added TEXT,
            PRIMARY KEY (npa_key, item_id)
        );

        CREATE TABLE IF NOT EXISTS source_health (
            origin TEXT PRIMARY KEY,
            last_run TEXT,                 -- когда источник опрашивали в последний раз
            last_count INTEGER,            -- сколько отдал в последний прогон
            last_nonzero TEXT,             -- когда в последний раз отдал > 0
            total_items INTEGER DEFAULT 0  -- всего записей в items от этого источника
        );

        CREATE TABLE IF NOT EXISTS insights (
            id TEXT PRIMARY KEY,           -- 'law-2026-08-11'
            kind TEXT,                     -- 'law' (дальше: 'tenders', 'market')
            title TEXT, lead TEXT,
            body TEXT,                     -- JSON: sections, business_impact, how_to_prepare
            sources TEXT,                  -- JSON: [{keys, title, url, itemId}]
            period TEXT, created TEXT
        );
        """)
        self.db.commit()

    # ─────────────── Дедуп-ключи ───────────────
    def _keys(self, item: dict) -> list:
        """Ключи «просмотрено». Если у записи есть стабильный ID источника (uid) —
        дедупим ТОЛЬКО по нему: у извещений одного проекта (WB) и лотов с типовыми
        названиями (UZEX/TenderWeek) URL и текст совпадают, а лоты — разные.
        URL/контент-хеши остаются для записей без uid (новости из RSS)."""
        if item.get("uid"):
            return ["uid:" + item["uid"]]
        keys = []
        if item.get("url"):
            keys.append("url:" + dedupe.url_hash(item["url"]))
        keys.append("content:" + dedupe.content_hash(item.get("title", ""),
                                                     item.get("full_text", "")))
        return keys

    def is_seen(self, item: dict) -> bool:
        keys = self._keys(item)
        q = ",".join("?" * len(keys))
        return self.db.execute(
            f"SELECT 1 FROM seen WHERE key IN ({q}) LIMIT 1", keys).fetchone() is not None

    def mark_seen(self, item: dict):
        now = _now()
        self.db.executemany(
            "INSERT OR IGNORE INTO seen(key, category, first_seen) VALUES (?,?,?)",
            [(k, item.get("category"), now) for k in self._keys(item)])
        self.db.commit()

    # ─────────────── Реестр НПА ───────────────
    def npa_lookup(self, npa_keys: list) -> str | None:
        """Есть ли уже карточка для любого из реквизитов? → item_id."""
        for k in npa_keys:
            row = self.db.execute(
                "SELECT item_id FROM npa_registry WHERE npa_key=?", (k,)).fetchone()
            if row:
                return row["item_id"]
        return None

    def npa_register(self, npa_keys: list, item: dict):
        now = _now()
        for k in npa_keys:
            self.db.execute(
                "INSERT OR IGNORE INTO npa_registry(npa_key, item_id, title, first_seen) "
                "VALUES (?,?,?,?)", (k, dedupe.item_slug(item), item.get("title", ""), now))
        self.db.commit()

    def npa_add_mention(self, npa_keys: list, item: dict):
        """Новость/разбор про известный акт → упоминание, не новая карточка.
        Карточка акта не может быть упоминанием самой себя."""
        now = _now()
        slug = dedupe.item_slug(item)
        for k in npa_keys:
            row = self.db.execute(
                "SELECT item_id FROM npa_registry WHERE npa_key=?", (k,)).fetchone()
            if not row or row["item_id"] == slug:
                continue
            self.db.execute(
                "INSERT OR IGNORE INTO npa_mentions(npa_key, item_id, kind, title, url, added) "
                "VALUES (?,?,?,?,?,?)",
                (k, slug, item.get("category", ""),
                 item.get("title", "")[:200], item.get("url", ""), now))
        self.db.commit()

    # ─────────────── История для семантического дедупа ───────────────
    def recent_tokens(self, days: int = config.NEAR_DUP_DAYS) -> list:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return [(r["category"], r["toks"] or "") for r in self.db.execute(
            "SELECT category, toks FROM items WHERE first_seen >= ?", (cutoff,))]

    # ─────────────── Записи ───────────────
    def save_item(self, item: dict, score: int, analysis: dict | None,
                  npa_refs: list, notified: bool):
        self.db.execute(
            """INSERT OR REPLACE INTO items
               (id, uid, category, source, origin, title, url, published,
                summary, full_text, meta, score, analysis, npa_refs,
                notified, first_seen, toks)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                       COALESCE((SELECT first_seen FROM items WHERE id=?), ?), ?)""",
            (dedupe.item_slug(item), item.get("uid"), item.get("category"),
             item.get("source"), item.get("origin"), item.get("title"),
             item.get("url"), str(item.get("published") or ""),
             item.get("summary"), item.get("full_text"),
             json.dumps(item.get("meta") or {}, ensure_ascii=False, default=str),
             score,
             json.dumps(analysis, ensure_ascii=False) if analysis else None,
             json.dumps(npa_refs, ensure_ascii=False),
             int(notified), dedupe.item_slug(item), _now(), dedupe.tokens_str(item)))
        self.db.commit()

    def set_notified(self, item_id: str):
        self.db.execute("UPDATE items SET notified=1 WHERE id=?", (item_id,))
        self.db.commit()

    # ─────────────── Обслуживание ───────────────
    def prune(self):
        """Чистим только новостные хеши; тендеры и НПА в seen — вечные."""
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=config.SEEN_NEWS_PRUNE_DAYS)).isoformat()
        self.db.execute("DELETE FROM seen WHERE category=? AND first_seen < ?",
                        (config.CAT_NEWS, cutoff))
        self.db.commit()

    def record_health(self, collect_stats: dict):
        """Записать статистику последнего сбора по источникам."""
        now = _now()
        for origin, n in collect_stats.items():
            total = self.db.execute(
                "SELECT COUNT(*) FROM items WHERE origin=?", (origin,)).fetchone()[0]
            prev = self.db.execute(
                "SELECT last_nonzero FROM source_health WHERE origin=?", (origin,)).fetchone()
            last_nz = now if n > 0 else (prev["last_nonzero"] if prev else None)
            self.db.execute(
                "INSERT OR REPLACE INTO source_health"
                "(origin, last_run, last_count, last_nonzero, total_items) VALUES (?,?,?,?,?)",
                (origin, now, int(n), last_nz, total))
        self.db.commit()

    def stats(self) -> dict:
        c = self.db.execute
        return {
            "items": c("SELECT COUNT(*) FROM items").fetchone()[0],
            "seen": c("SELECT COUNT(*) FROM seen").fetchone()[0],
            "npa": c("SELECT COUNT(*) FROM npa_registry").fetchone()[0],
            "mentions": c("SELECT COUNT(*) FROM npa_mentions").fetchone()[0],
            "notified": c("SELECT COUNT(*) FROM items WHERE notified=1").fetchone()[0],
        }

    def close(self):
        self.db.close()
