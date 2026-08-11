"use client";

import { useMemo, useState, useTransition } from "react";
import {
  CATEGORY_ICON,
  CATEGORY_LABEL,
  deadlineStatus,
  fmtDate,
  stripRawTitle,
  type Category,
} from "@/lib/types";
import { saveNote, setStatus, toggleSaved } from "./actions";

export interface CabTender {
  id: string;
  category: Category;
  source: string;
  title: string;
  titleRu: string | null;
  url: string;
  buyer: string | null;
  budget: string | null;
  deadline: string | null;
  score: number | null;
  summaryRu: string | null;
  siteBrief: string | null;
  recommendation: string | null;
  eligibility: string | null;
  docsChecklist: string[];
  firstSeen: string;
}
export interface CabState {
  userId: string;
  tenderId: string;
  status: string;
  saved: boolean;
  note: string | null;
}
export interface CabProfile {
  id: string;
  fullName: string;
}

const STATUS_LABEL: Record<string, string> = {
  new: "Новый",
  viewed: "Просмотрен",
  working: "В работе",
  submitted: "Подан",
  won: "Выигран",
  lost: "Проигран",
  skipped: "Пропущен",
};
const STATUS_ORDER = ["viewed", "working", "submitted", "won", "lost", "skipped"];

const FOLDERS = [
  { key: "all", label: "Все тендеры" },
  { key: "hot", label: "🔥 Горящие" },
  { key: "new", label: "Новые" },
  { key: "saved", label: "⭐ Сохранённые" },
  { key: "working", label: "В работе" },
  { key: "submitted", label: "Поданные" },
  { key: "done", label: "Выигран / проигран" },
  { key: "expired", label: "Завершённые" },
] as const;

function title(t: CabTender): string {
  if (t.titleRu && t.titleRu.trim().length >= 6) return t.titleRu;
  return stripRawTitle(t.title);
}

export function Workspace({
  tenders,
  states,
  profiles,
  meId,
  demo,
}: {
  tenders: CabTender[];
  states: CabState[];
  profiles: CabProfile[];
  meId: string;
  demo: boolean;
}) {
  const [folder, setFolder] = useState<string>("all");
  const [cat, setCat] = useState<Category | "all">("all");
  const [src, setSrc] = useState<string>("all");
  const [period, setPeriod] = useState<"all" | "today" | "week">("all");
  const [q, setQ] = useState("");
  const [selId, setSelId] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  // локальный оверлей поверх серверного состояния — мгновенный отклик UI
  const [local, setLocal] = useState<Record<string, Partial<CabState>>>({});

  const nameOf = useMemo(
    () => new Map(profiles.map((p) => [p.id, p.fullName || "коллега"])),
    [profiles],
  );
  const myState = useMemo(() => {
    const m = new Map<string, CabState>();
    for (const s of states) if (s.userId === meId) m.set(s.tenderId, s);
    return m;
  }, [states, meId]);
  const teamWork = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const s of states)
      if (s.userId !== meId && ["working", "submitted", "won"].includes(s.status))
        m.set(s.tenderId, [...(m.get(s.tenderId) ?? []), nameOf.get(s.userId) ?? ""]);
    return m;
  }, [states, meId, nameOf]);

  const my = (id: string): Partial<CabState> => ({
    status: "new",
    saved: false,
    note: "",
    ...myState.get(id),
    ...local[id],
  });

  const enriched = useMemo(
    () =>
      tenders.map((t) => {
        const ds = deadlineStatus(t.deadline);
        return { ...t, _dl: ds.status, _days: ds.days };
      }),
    [tenders],
  );

  const sources = useMemo(
    () => [...new Set(tenders.map((t) => t.source))].sort(),
    [tenders],
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: enriched.length };
    for (const t of enriched) {
      const s = my(t.id);
      if (t._dl === "expiring") c.hot = (c.hot ?? 0) + 1;
      if (t._dl === "expired") c.expired = (c.expired ?? 0) + 1;
      if ((s.status ?? "new") === "new" && t._dl !== "expired")
        c.new = (c.new ?? 0) + 1;
      if (s.saved) c.saved = (c.saved ?? 0) + 1;
      if (s.status === "working") c.working = (c.working ?? 0) + 1;
      if (s.status === "submitted") c.submitted = (c.submitted ?? 0) + 1;
      if (s.status === "won" || s.status === "lost") c.done = (c.done ?? 0) + 1;
    }
    return c;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enriched, states, local]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return enriched
      .filter((t) => {
        const s = my(t.id);
        switch (folder) {
          case "hot":
            if (t._dl !== "expiring") return false;
            break;
          case "new":
            if ((s.status ?? "new") !== "new" || t._dl === "expired") return false;
            break;
          case "saved":
            if (!s.saved) return false;
            break;
          case "working":
            if (s.status !== "working") return false;
            break;
          case "submitted":
            if (s.status !== "submitted") return false;
            break;
          case "done":
            if (s.status !== "won" && s.status !== "lost") return false;
            break;
          case "expired":
            if (t._dl !== "expired") return false;
            break;
          default:
            if (t._dl === "expired") return false; // «Все» = актуальные
        }
        if (cat !== "all" && t.category !== cat) return false;
        if (src !== "all" && t.source !== src) return false;
        if (period !== "all") {
          const days = period === "today" ? 1 : 7;
          if (+new Date(t.firstSeen) < Date.now() - days * 86400000) return false;
        }
        if (!needle) return true;
        return `${t.title} ${t.titleRu ?? ""} ${t.buyer ?? ""} ${t.source}`
          .toLowerCase()
          .includes(needle);
      })
      .sort((a, b) => {
        const rank = { expiring: 0, active: 1, none: 2, expired: 3 } as const;
        const r = rank[a._dl] - rank[b._dl];
        if (r !== 0) return r;
        if (a._dl === "expiring" || a._dl === "active")
          return (a._days ?? 999) - (b._days ?? 999);
        return (
          (b.score ?? 0) - (a.score ?? 0) ||
          b.firstSeen.localeCompare(a.firstSeen)
        );
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enriched, folder, cat, src, period, q, states, local]);

  const sel = shown.find((t) => t.id === selId) ?? shown[0] ?? null;
  const selState = sel ? my(sel.id) : null;

  function patch(id: string, p: Partial<CabState>) {
    setLocal((prev) => ({ ...prev, [id]: { ...prev[id], ...p } }));
  }
  function select(t: (typeof enriched)[number]) {
    setSelId(t.id);
    const s = my(t.id);
    if ((s.status ?? "new") === "new") {
      patch(t.id, { status: "viewed" });
      startTransition(() => void setStatus(t.id, "viewed"));
    }
  }
  function onStatus(id: string, status: string) {
    patch(id, { status });
    startTransition(() => void setStatus(id, status));
  }
  function onStar(id: string, saved: boolean) {
    patch(id, { saved });
    startTransition(() => void toggleSaved(id, saved));
  }

  return (
    <div className="ws">
      {/* ── левая колонка: папки и фильтры ── */}
      <aside className="ws-side">
        <div className="ws-side-title">Папки</div>
        {FOLDERS.map((f) => (
          <button
            key={f.key}
            className={`ws-folder${folder === f.key ? " active" : ""}`}
            onClick={() => setFolder(f.key)}
          >
            <span>{f.label}</span>
            <b>{counts[f.key] ?? 0}</b>
          </button>
        ))}
        <div className="ws-side-title">Категории</div>
        {(["all", "international_tender", "uz_tender", "job", "legislation", "news"] as const).map(
          (c) => (
            <button
              key={c}
              className={`ws-folder${cat === c ? " active" : ""}`}
              onClick={() => setCat(c)}
            >
              <span>
                {c === "all"
                  ? "Все категории"
                  : `${CATEGORY_ICON[c]} ${CATEGORY_LABEL[c]}`}
              </span>
            </button>
          ),
        )}
      </aside>

      {/* ── центр: список ── */}
      <section className="ws-list">
        <div className="ws-toolbar">
          <input
            className="search"
            placeholder="Поиск по названию, заказчику, источнику…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select
            className="ws-select"
            value={src}
            onChange={(e) => setSrc(e.target.value)}
          >
            <option value="all">Все источники</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {(
            [
              ["all", "За всё время"],
              ["week", "7 дней"],
              ["today", "Сегодня"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              className={`tab small${period === k ? " active" : ""}`}
              onClick={() => setPeriod(k)}
            >
              {label}
            </button>
          ))}
        </div>
        {demo && (
          <div className="ws-demo-note">
            Демо-режим: статусы и звёздочки не сохраняются, пока не подключён
            Supabase.
          </div>
        )}
        {shown.length === 0 && <div className="empty">В этой папке пусто.</div>}
        {shown.map((t) => {
          const s = my(t.id);
          const dlText = fmtDate(t.deadline);
          const team = teamWork.get(t.id);
          return (
            <div
              key={t.id}
              className={`ws-row${sel?.id === t.id ? " active" : ""}${
                t._dl === "expired" ? " dim" : ""
              }`}
              onClick={() => select(t)}
            >
              <button
                className={`star${s.saved ? " on" : ""}`}
                title={s.saved ? "Убрать из сохранённых" : "Сохранить"}
                onClick={(e) => {
                  e.stopPropagation();
                  onStar(t.id, !s.saved);
                }}
              >
                ★
              </button>
              <div className="ws-row-main">
                <div className="ws-row-title">{title(t)}</div>
                <div className="ws-row-meta">
                  <span>
                    {CATEGORY_ICON[t.category]} {t.source}
                  </span>
                  {t.buyer && <span>· {t.buyer.slice(0, 45)}</span>}
                  {team && team.length > 0 && (
                    <span className="who">ведёт: {team.join(", ")}</span>
                  )}
                </div>
              </div>
              <div className="ws-row-side">
                {t._dl === "expiring" && (
                  <span className="badge st-expiring">
                    🔥 {t._days === 0 ? "сегодня" : `${t._days} дн.`}
                  </span>
                )}
                {t._dl === "active" && (
                  <span className="badge st-active">до {dlText}</span>
                )}
                {t._dl === "expired" && (
                  <span className="badge st-expired">завершён</span>
                )}
                <span className={`chip status-${s.status ?? "new"}`}>
                  {STATUS_LABEL[s.status ?? "new"]}
                </span>
              </div>
            </div>
          );
        })}
      </section>

      {/* ── правая панель: детали ── */}
      <aside className="ws-detail">
        {!sel && <div className="empty">Выберите тендер из списка</div>}
        {sel && selState && (
          <>
            <div className="ws-detail-head">
              <span className="badge">
                {CATEGORY_ICON[sel.category]} {CATEGORY_LABEL[sel.category]}
              </span>
              {typeof sel.score === "number" && (
                <span className="badge">оценка {sel.score}/10</span>
              )}
            </div>
            <h2>{title(sel)}</h2>
            <div className="ws-facts">
              {sel.buyer && (
                <div>
                  <b>Заказчик:</b> {sel.buyer}
                </div>
              )}
              {sel.budget && (
                <div>
                  <b>Бюджет:</b> {sel.budget}
                </div>
              )}
              {sel.deadline && (
                <div>
                  <b>Дедлайн:</b> {fmtDate(sel.deadline)}
                  {sel.deadline && deadlineStatus(sel.deadline).days !== null &&
                    deadlineStatus(sel.deadline).days! >= 0 &&
                    ` (${deadlineStatus(sel.deadline).days} дн.)`}
                </div>
              )}
            </div>

            <div className="ws-actions">
              <button
                className={`btn small${selState.saved ? "" : " ghost"}`}
                onClick={() => onStar(sel.id, !selState.saved)}
              >
                {selState.saved ? "★ Сохранён" : "☆ Сохранить"}
              </button>
              {STATUS_ORDER.map((st) => (
                <button
                  key={st}
                  className={`btn small${selState.status === st ? "" : " ghost"}`}
                  onClick={() => onStatus(sel.id, st)}
                >
                  {STATUS_LABEL[st]}
                </button>
              ))}
            </div>

            {sel.summaryRu && (
              <div className="ws-block">
                <h3>Суть</h3>
                <p>{sel.summaryRu}</p>
              </div>
            )}
            {sel.siteBrief && (
              <div className="ws-block">
                <h3>Разбор</h3>
                <p>{sel.siteBrief}</p>
              </div>
            )}
            {sel.eligibility && (
              <div className="ws-block">
                <h3>Требования</h3>
                <p>{sel.eligibility}</p>
              </div>
            )}
            {sel.docsChecklist.length > 0 && (
              <div className="ws-block">
                <h3>Документы</h3>
                <ul>
                  {sel.docsChecklist.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </div>
            )}
            {sel.recommendation && (
              <div className="ws-block reco">
                <h3>🎯 Рекомендация</h3>
                <p>{sel.recommendation}</p>
              </div>
            )}

            <NoteBox
              key={sel.id}
              tenderId={sel.id}
              initial={selState.note ?? ""}
              demo={demo}
              onSaved={(v) => patch(sel.id, { note: v })}
            />

            <div className="ws-links">
              <a href={sel.url} target="_blank" rel="noopener noreferrer" className="btn">
                Первоисточник ↗
              </a>
              <a href={`/t/${sel.id}`} target="_blank" className="btn ghost">
                Публичная карточка
              </a>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function NoteBox({
  tenderId,
  initial,
  demo,
  onSaved,
}: {
  tenderId: string;
  initial: string;
  demo: boolean;
  onSaved: (v: string) => void;
}) {
  const [val, setVal] = useState(initial);
  const [saving, setSaving] = useState(false);
  const dirty = val !== initial;
  return (
    <div className="ws-block">
      <h3>Заметка</h3>
      <textarea
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder={demo ? "В демо-режиме не сохраняется" : "Ваша заметка по тендеру…"}
        rows={3}
      />
      <button
        className="btn small ghost"
        disabled={!dirty || saving}
        onClick={async () => {
          setSaving(true);
          await saveNote(tenderId, val);
          onSaved(val);
          setSaving(false);
        }}
      >
        {saving ? "Сохраняем…" : dirty ? "Сохранить заметку" : "Сохранено"}
      </button>
    </div>
  );
}
