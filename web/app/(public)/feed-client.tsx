"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  CATEGORY_ICON,
  CATEGORY_LABEL,
  cleanTitle,
  deadlineStatus,
  fmtDate,
  npaTypeTitle,
  type Category,
  type DlStatus,
  type FeedItem,
} from "@/lib/types";

const TABS: Array<{ key: Category | "all"; label: string }> = [
  { key: "all", label: "Все" },
  { key: "international_tender", label: "🌍 Международные" },
  { key: "uz_tender", label: "🇺🇿 Узбекистан" },
  { key: "job", label: "🧑‍💼 Позиции" },
  { key: "legislation", label: "⚖️ НПА" },
  { key: "news", label: "📰 Новости" },
];

const STATUS_TABS: Array<{ key: string; label: string }> = [
  { key: "actual", label: "Актуальные" },
  { key: "expiring", label: "🔥 Горящие" },
  { key: "expired", label: "Завершённые" },
  { key: "all", label: "Все" },
];

const STATUS_RANK: Record<DlStatus, number> = {
  expiring: 0,
  active: 1,
  none: 2,
  expired: 3,
};

function statusBadge(status: DlStatus, days: number | null, dlText: string | null) {
  if (status === "expiring")
    return (
      <span className="badge st-expiring">
        🔥 {days === 0 ? "последний день" : `осталось ${days} дн.`}
        {dlText ? ` · до ${dlText}` : ""}
      </span>
    );
  if (status === "active")
    return (
      <span className="badge st-active">
        открыт · до {dlText} ({days} дн.)
      </span>
    );
  if (status === "expired")
    return <span className="badge st-expired">завершён · {dlText}</span>;
  return null;
}

export function FeedClient({
  items,
  actIdx = {},
}: {
  items: FeedItem[];
  actIdx?: Record<string, string>;
}) {
  const [tab, setTab] = useState<Category | "all">("all");
  const [statusTab, setStatusTab] = useState("actual");
  const [q, setQ] = useState("");

  const enriched = useMemo(
    () =>
      items.map((it) => {
        const ds = deadlineStatus(it.deadline);
        return { ...it, _status: ds.status, _days: ds.days };
      }),
    [items],
  );

  const stats = useMemo(() => {
    const weekAgo = Date.now() - 7 * 86400000;
    return {
      expiring: enriched.filter((it) => it._status === "expiring").length,
      open: enriched.filter(
        (it) => it._status === "active" || it._status === "expiring",
      ).length,
      npa7: enriched.filter(
        (it) =>
          it.category === "legislation" && +new Date(it.firstSeen) >= weekAgo,
      ).length,
      total: enriched.length,
    };
  }, [enriched]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = enriched.filter((it) => {
      if (tab !== "all" && it.category !== tab) return false;
      if (statusTab === "actual" && it._status === "expired") return false;
      if (statusTab === "expiring" && it._status !== "expiring") return false;
      if (statusTab === "expired" && it._status !== "expired") return false;
      if (!needle) return true;
      const blob = `${it.title} ${it.titleRu ?? ""} ${it.summaryRu ?? ""} ${
        it.buyer ?? ""
      } ${it.source} ${it.npaRefs.join(" ")}`.toLowerCase();
      return blob.includes(needle);
    });
    return filtered.sort((a, b) => {
      const r = STATUS_RANK[a._status] - STATUS_RANK[b._status];
      if (r !== 0) return r;
      if (a._status === "expiring" || a._status === "active")
        return (a._days ?? 999) - (b._days ?? 999);       // ближе дедлайн — выше
      if (a._status === "expired")
        return (b._days ?? -999) - (a._days ?? -999);      // недавно завершённые выше
      return (
        (b.score ?? 0) - (a.score ?? 0) ||
        b.firstSeen.localeCompare(a.firstSeen)
      );
    });
  }, [enriched, tab, statusTab, q]);

  return (
    <>
      <div className="stats">
        <div className="stat">
          <div className="n">{stats.expiring}</div>
          <div className="l">🔥 горящих дедлайнов</div>
        </div>
        <div className="stat">
          <div className="n">{stats.open}</div>
          <div className="l">открытых тендеров</div>
        </div>
        <div className="stat">
          <div className="n">{stats.npa7}</div>
          <div className="l">НПА за 7 дней</div>
        </div>
        <div className="stat">
          <div className="n">{stats.total}</div>
          <div className="l">записей в ленте</div>
        </div>
      </div>

      <div className="filters">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab${tab === t.key ? " active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="filters">
        {STATUS_TABS.map((t) => (
          <button
            key={t.key}
            className={`tab small${statusTab === t.key ? " active" : ""}`}
            onClick={() => setStatusTab(t.key)}
          >
            {t.label}
          </button>
        ))}
        <input
          className="search"
          placeholder="Поиск: заказчик, тема, реквизит НПА…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {shown.length === 0 && (
        <div className="empty">Ничего не найдено — измените фильтр или запрос.</div>
      )}

      {shown.map((it) => {
        const dlText = fmtDate(it.deadline);
        return (
          <div
            key={it.id}
            className={`card${it._status === "expired" ? " expired" : ""}${
              it._status === "expiring" ? " urgent" : ""
            }`}
          >
            <div className="card-meta">
              <span className="badge">
                {CATEGORY_ICON[it.category]} {CATEGORY_LABEL[it.category]}
              </span>
              <span>{it.source}</span>
              {it.buyer && <span>· {it.buyer.slice(0, 60)}</span>}
              {statusBadge(it._status, it._days, dlText)}
              {it.budget && <span className="badge">💰 {it.budget.slice(0, 40)}</span>}
            </div>
            <Link href={`/t/${it.id}`} className="card-link">
              <h3 className="card-title">{cleanTitle(it)}</h3>
              {it.summaryRu && <p className="card-sum">{it.summaryRu}</p>}
            </Link>
            <div className="card-foot">
              {it.npaRefs
                .filter((r) => !r.startsWith("LEX"))
                .slice(0, 3)
                .map((r) =>
                  actIdx[r] && actIdx[r] !== it.id ? (
                    <Link className="chip" href={`/t/${actIdx[r]}`} key={r}>
                      {npaTypeTitle(r)} {r}
                    </Link>
                  ) : (
                    <span className="chip" key={r}>
                      {npaTypeTitle(r)} {r}
                    </span>
                  ),
                )}
              <span className="spacer" />
              <Link href={`/t/${it.id}`}>Разбор →</Link>
              <a href={it.url} target="_blank" rel="noopener noreferrer">
                Источник ↗
              </a>
            </div>
          </div>
        );
      })}
    </>
  );
}
