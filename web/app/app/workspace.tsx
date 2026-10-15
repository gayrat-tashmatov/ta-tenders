"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import {
  DIRECTION_LABEL,
  cleanTitle,
  deadlineLabel,
  deadlineStatus,
  fmtDate,
  sourceLinkLabel,
  stripRawTitle,
  type FullItem,
} from "@/lib/types";
import { markSeenNow, saveNote, setStatus, toggleSaved } from "./actions";

export type CabTender = Pick<
  FullItem,
  | "id" | "category" | "source" | "origin" | "title" | "titleRu" | "url" | "buyer" | "budget"
  | "deadline" | "published" | "score" | "summaryRu" | "siteBrief" | "recommendation"
  | "eligibility" | "docsChecklist" | "legalAspects" | "actionItems" | "firstSeen" | "portalOnly"
  | "lotNumber" | "repeatOf" | "direction" | "whyUs" | "donor" | "geo" | "track"
>;
export interface WsState { tenderId: string; status: string | null; saved: boolean; note: string | null }

const STATUS_LABEL: Record<string, string> = {
  viewed: "Просмотрен", working: "В работе", submitted: "Подан",
  won: "Выигран", lost: "Проигран", skipped: "Не наше",
};
const STATUS_BUTTONS = ["working", "submitted", "won", "lost", "skipped"] as const;
const FOLDERS = [
  { key: "new", label: "Новые" },
  { key: "all", label: "Все актуальные" },
  { key: "hot", label: "Срок ≤ 7 дней" },
  { key: "saved", label: "Сохранённые" },
  { key: "working", label: "В работе" },
  { key: "submitted", label: "Поданные" },
  { key: "done", label: "Итоги" },
  { key: "skipped", label: "Не наше" },
  { key: "expired", label: "Закрытые" },
] as const;
const DIRS = ["право", "бизнес", "ИТ_цифровизация", "энергетика_климат", "пограничный"] as const;

export function Workspace({
  title, subtitle, tenders, mine, team, names, seenUntil, initialId, initialFolder, demo,
}: {
  title: string; subtitle: string; tenders: CabTender[]; mine: WsState[];
  team: { tenderId: string; status: string | null; userId: string }[];
  names: Record<string, string>; seenUntil: string; initialId?: string; initialFolder?: string; demo: boolean;
}) {
  const router = useRouter();
  const [local, setLocal] = useState<Record<string, Partial<WsState>>>({});
  const [seen, setSeen] = useState(seenUntil);
  const [q, setQ] = useState("");
  const [dir, setDir] = useState<string>("all");
  const [src, setSrc] = useState<string>("all");
  const [showOff, setShowOff] = useState(false);
  const [selId, setSelId] = useState<string | null>(initialId ?? null);
  const [mobileDetail, setMobileDetail] = useState(!!initialId);
  const [err, setErr] = useState<string | null>(null);
  const [, start] = useTransition();

  const base = useMemo(() => new Map(mine.map((s) => [s.tenderId, s])), [mine]);
  const my = (id: string): WsState => ({ tenderId: id, status: null, saved: false, note: null, ...base.get(id), ...local[id] });
  const isNew = (t: CabTender) => !my(t.id).status && t.firstSeen > seen;
  const report = (p: Promise<{ ok: boolean; error?: string }>) =>
    p.then((r) => setErr(r.ok ? null : r.error ?? "Не сохранилось")).catch((e) => setErr(String(e)));

  const teamBy = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const s of team) m.set(s.tenderId, [...(m.get(s.tenderId) ?? []), names[s.userId] ?? "коллега"]);
    return m;
  }, [team, names]);

  const rows = useMemo(
    () => tenders.map((t) => ({ ...t, _dl: deadlineStatus(t.deadline) })),
    [tenders],
  );
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of rows) {
      const s = my(t.id);
      const alive = t._dl.status !== "expired";
      const ours = showOff || t.direction !== "нет";
      if (alive && ours && isNew(t)) c.new = (c.new ?? 0) + 1;
      if (alive && ours && s.status !== "skipped") c.all = (c.all ?? 0) + 1;
      if (t._dl.status === "expiring" && ours && s.status !== "skipped") c.hot = (c.hot ?? 0) + 1;
      if (s.saved) c.saved = (c.saved ?? 0) + 1;
      if (s.status === "working") c.working = (c.working ?? 0) + 1;
      if (s.status === "submitted") c.submitted = (c.submitted ?? 0) + 1;
      if (s.status === "won" || s.status === "lost") c.done = (c.done ?? 0) + 1;
      if (s.status === "skipped") c.skipped = (c.skipped ?? 0) + 1;
      if (!alive) c.expired = (c.expired ?? 0) + 1;
    }
    return c;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, local, seen, showOff]);
  const [folder, setFolder] = useState<string>(initialFolder ?? ((counts.new ?? 0) > 0 ? "new" : "all"));

  const sources = useMemo(() => [...new Set(tenders.map((t) => t.donor || t.source))].sort(), [tenders]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows
      .filter((t) => {
        const s = my(t.id);
        const alive = t._dl.status !== "expired";
        const ours = showOff || t.direction !== "нет";
        switch (folder) {
          case "new": if (!(alive && ours && isNew(t))) return false; break;
          case "all": if (!(alive && ours) || s.status === "skipped") return false; break;
          case "hot": if (t._dl.status !== "expiring" || !ours || s.status === "skipped") return false; break;
          case "saved": if (!s.saved) return false; break;
          case "working": if (s.status !== "working") return false; break;
          case "submitted": if (s.status !== "submitted") return false; break;
          case "done": if (s.status !== "won" && s.status !== "lost") return false; break;
          case "skipped": if (s.status !== "skipped") return false; break;
          case "expired": if (alive) return false; break;
        }
        if (dir !== "all" && t.direction !== dir) return false;
        if (src !== "all" && (t.donor || t.source) !== src) return false;
        if (!needle) return true;
        return `${t.title} ${t.titleRu ?? ""} ${t.buyer ?? ""} ${t.source} ${t.donor ?? ""}`.toLowerCase().includes(needle);
      })
      .sort((a, b) => {
        if (folder === "new") return (b.score ?? 0) - (a.score ?? 0) || b.firstSeen.localeCompare(a.firstSeen);
        if (folder === "expired" || folder === "done" || folder === "skipped") return b.firstSeen.localeCompare(a.firstSeen);
        const da = a._dl.days ?? 999, db = b._dl.days ?? 999;
        return da - db || (b.score ?? 0) - (a.score ?? 0);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, folder, dir, src, q, local, seen, showOff]);

  const sel = shown.find((t) => t.id === selId) ?? rows.find((t) => t.id === selId) ?? shown[0] ?? null;
  const selS = sel ? my(sel.id) : null;
  const detailRef = useRef<HTMLElement>(null);
  // новая позиция — карточка справа с начала (раньше оставалась прокрученной от предыдущей)
  useEffect(() => {
    detailRef.current?.scrollTo({ top: 0 });
    if (mobileDetail) window.scrollTo({ top: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel?.id]);

  useEffect(() => {
    if (initialId) document.getElementById(`row-${initialId}`)?.scrollIntoView({ block: "center" });
  }, [initialId]);

  function patch(id: string, p: Partial<WsState>) {
    setLocal((prev) => ({ ...prev, [id]: { ...prev[id], ...p } }));
  }
  function open(t: CabTender) {
    setSelId(t.id);
    setMobileDetail(true);
    if (!my(t.id).status && isNew(t)) {
      patch(t.id, { status: "viewed" });
      start(() => report(setStatus(t.id, "viewed", cleanTitle(t))));
    }
  }
  function onStatus(id: string, status: string) {
    const cur = my(id).status;
    const next = cur === status ? "viewed" : status;
    patch(id, { status: next });
    const t = tenders.find((x) => x.id === id)!;
    start(() => report(setStatus(id, next, cleanTitle(t))));
  }
  function onStar(id: string, saved: boolean) {
    patch(id, { saved });
    const t = tenders.find((x) => x.id === id)!;
    start(() => report(toggleSaved(id, saved, cleanTitle(t))));
  }
  function onSeenAll() {
    const at = new Date().toISOString();
    setSeen(at);
    setFolder("all");
    start(() => report(markSeenNow(title).then((r) => { if (r.ok) router.refresh(); return r; })));
  }

  return (
    <div className={`ws${mobileDetail ? " ws-show-detail" : ""}`}>
      <aside className="ws-side">
        <div className="ws-side-h">{title}</div>
        <p className="ws-side-sub">{subtitle}</p>
        {FOLDERS.map((f) => (
          <button key={f.key} className={`ws-f${folder === f.key ? " on" : ""}${f.key === "new" && (counts.new ?? 0) > 0 ? " has-new" : ""}`}
            onClick={() => setFolder(f.key)}>
            <span>{f.label}</span><b>{counts[f.key] ?? 0}</b>
          </button>
        ))}
        <div className="ws-side-h2">Направление</div>
        <button className={`ws-f${dir === "all" ? " on" : ""}`} onClick={() => setDir("all")}><span>Все направления</span></button>
        {DIRS.map((d) => (
          <button key={d} className={`ws-f${dir === d ? " on" : ""}`} onClick={() => setDir(d)}>
            <span><i className={`swatch dir-${d}`} />{DIRECTION_LABEL[d]}</span>
          </button>
        ))}
        <label className="ws-check">
          <input type="checkbox" checked={showOff} onChange={(e) => setShowOff(e.target.checked)} />
          показывать вне профиля
        </label>
      </aside>

      <section className="ws-list">
        <div className="ws-bar">
          <input className="search" placeholder="Поиск: название, заказчик, донор…" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="select" value={src} onChange={(e) => setSrc(e.target.value)} aria-label="Источник или донор">
            <option value="all">Все доноры и площадки</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {(counts.new ?? 0) > 0 && (
            <button className="btn ghost small" onClick={onSeenAll} title="Всё, что сейчас новое, станет просмотренным">
              ✓ Всё просмотрено ({counts.new})
            </button>
          )}
        </div>
        <div className="ws-mobile-folders">
          <select className="select" value={folder} onChange={(e) => setFolder(e.target.value)}>
            {FOLDERS.map((f) => <option key={f.key} value={f.key}>{f.label} ({counts[f.key] ?? 0})</option>)}
          </select>
        </div>
        {demo && <div className="note">Демо-режим: статусы не сохраняются.</div>}
        {err && <div className="note note-err">⚠ {err}</div>}
        {shown.length === 0 && (
          <div className="empty">{folder === "new" ? "Новых нет — вы всё просмотрели." : "Здесь пусто."}</div>
        )}
        {shown.map((t) => {
          const s = my(t.id);
          const dl = deadlineLabel(t.deadline);
          const who = teamBy.get(t.id);
          return (
            <div id={`row-${t.id}`} key={t.id} className={`row${sel?.id === t.id ? " on" : ""}${t._dl.status === "expired" ? " dim" : ""}`}
              onClick={() => open(t)}>
              <button className={`star${s.saved ? " on" : ""}`} aria-label={s.saved ? "Убрать из сохранённых" : "Сохранить"}
                onClick={(e) => { e.stopPropagation(); onStar(t.id, !s.saved); }}>★</button>
              <div className="row-main">
                <div className="row-title">{isNew(t) && <span className="dot-new" />}{cleanTitle(t)}</div>
                <div className="row-meta">
                  <span>{t.donor || t.source.replace(/\s*\(.*\)$/, "")}</span>
                  {t.buyer && t.buyer !== t.donor && <span>{t.buyer.slice(0, 50)}</span>}
                  {t.published && <span>опубл. {fmtDate(t.published)}</span>}
                  {who && <span className="who">ведёт: {who.join(", ")}</span>}
                </div>
              </div>
              <div className="row-side">
                {dl.tone !== "none" && <span className={`dl dl-${dl.tone}`}>{dl.text}</span>}
                {t.direction && t.direction !== "нет" && <i className={`swatch dir-${t.direction}`} title={DIRECTION_LABEL[t.direction]} />}
                {s.status && s.status !== "viewed" && <span className={`st st-${s.status}`}>{STATUS_LABEL[s.status]}</span>}
              </div>
            </div>
          );
        })}
      </section>

      <aside className="ws-detail" ref={detailRef}>
        {!sel && <div className="empty">Выберите позицию слева</div>}
        {sel && selS && (
          <article>
            <button className="btn ghost small ws-back" onClick={() => setMobileDetail(false)}>← к списку</button>
            <div className="d-chips">
              {sel.direction && sel.direction !== "нет" && <span className={`dir dir-${sel.direction}`}>{DIRECTION_LABEL[sel.direction]}</span>}
              {typeof sel.score === "number" && <span className="pill">релевантность {sel.score}/10</span>}
              {sel.repeatOf && <span className="pill pill-warn">повтор лота № {sel.repeatOf}</span>}
            </div>
            <h2 className="d-title">{cleanTitle(sel)}</h2>
            {sel.titleRu && stripRawTitle(sel.title) !== sel.titleRu && <p className="d-orig">{stripRawTitle(sel.title)}</p>}
            {sel.whyUs && <div className="why"><b>Почему нам:</b> {sel.whyUs}</div>}
            <dl className="facts">
              <dt>Финансирование</dt><dd>{sel.donor || sel.source}</dd>
              {sel.buyer && sel.buyer !== sel.donor && (<><dt>Заказчик</dt><dd>{sel.buyer}</dd></>)}
              {sel.geo && (<><dt>Страна</dt><dd>{sel.geo}</dd></>)}
              {sel.budget && (<><dt>Бюджет</dt><dd>{sel.budget}</dd></>)}
              {sel.published && (<><dt>Опубликовано</dt><dd>{fmtDate(sel.published)}</dd></>)}
              <dt>Срок подачи</dt>
              <dd>{fmtDate(sel.deadline) ?? "не указан"} {deadlineLabel(sel.deadline).tone !== "none" && <span className={`dl dl-${deadlineLabel(sel.deadline).tone}`}>{deadlineLabel(sel.deadline).text}</span>}</dd>
            </dl>
            <div className="d-actions">
              <button className={`btn small${selS.saved ? "" : " ghost"}`} onClick={() => onStar(sel.id, !selS.saved)}>
                {selS.saved ? "★ Сохранено" : "☆ Сохранить"}
              </button>
              {STATUS_BUTTONS.map((st) => (
                <button key={st} className={`btn small${selS.status === st ? " " + "on-" + st : " ghost"}`} onClick={() => onStatus(sel.id, st)}>
                  {st === "working" ? "Беру в работу" : STATUS_LABEL[st]}
                </button>
              ))}
            </div>
            {sel.summaryRu && <section className="d-sec"><h3>Что нужно</h3><p>{sel.summaryRu}</p></section>}
            {sel.siteBrief && <section className="d-sec"><h3>Разбор</h3><p>{sel.siteBrief}</p></section>}
            {sel.recommendation && <section className="d-sec d-reco"><h3>Что предложить</h3><p>{sel.recommendation}</p></section>}
            {sel.eligibility && <section className="d-sec"><h3>Требования к участнику</h3><p>{sel.eligibility}</p></section>}
            {(sel.docsChecklist?.length ?? 0) > 0 && (
              <section className="d-sec"><h3>Документы</h3><ul>{sel.docsChecklist.map((d) => <li key={d}>{d}</li>)}</ul></section>
            )}
            {(sel.actionItems?.length ?? 0) > 0 && (
              <section className="d-sec"><h3>Шаги</h3><ul>{sel.actionItems!.map((a) => <li key={a}>{a}</li>)}</ul></section>
            )}
            {(sel.legalAspects?.length ?? 0) > 0 && (
              <section className="d-sec"><h3>Юридические аспекты</h3><ul>{sel.legalAspects!.map((a) => <li key={a}>{a}</li>)}</ul></section>
            )}
            <NoteBox key={sel.id} id={sel.id} title={cleanTitle(sel)} initial={selS.note ?? ""} demo={demo} onSaved={(v) => patch(sel.id, { note: v })} />
            <div className="d-links">
              <a className="btn" href={sel.url} target="_blank" rel="noopener noreferrer">{sourceLinkLabel(sel)}</a>
              <a className="btn ghost" href={`/app/item/${sel.id}`}>Полная карточка</a>
            </div>
          </article>
        )}
      </aside>
    </div>
  );
}

function NoteBox({ id, title, initial, demo, onSaved }: {
  id: string; title: string; initial: string; demo: boolean; onSaved: (v: string) => void;
}) {
  const [val, setVal] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const dirty = val !== initial;
  return (
    <section className="d-sec">
      <h3>Заметка команды</h3>
      <textarea value={val} rows={3} onChange={(e) => setVal(e.target.value)}
        placeholder={demo ? "В демо-режиме не сохраняется" : "С кем говорили, что решили…"} />
      <button className="btn small ghost" disabled={!dirty || busy} onClick={async () => {
        setBusy(true);
        const r = await saveNote(id, val, title);
        if (r.ok) onSaved(val); else setErr(r.error ?? "Не сохранилось");
        setBusy(false);
      }}>{busy ? "Сохраняю…" : dirty ? "Сохранить заметку" : "Сохранено"}</button>
      {err && <div className="note note-err">⚠ {err}</div>}
    </section>
  );
}
