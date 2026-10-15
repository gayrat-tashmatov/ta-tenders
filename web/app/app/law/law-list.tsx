"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { fmtDate, stripRawTitle, type ActReview } from "@/lib/types";

export interface LawRow {
  id: string; title: string; titleRu: string | null; firstSeen: string; published: string | null;
  url: string; act: ActReview | null;
}

const IMP: Record<string, number> = { высокая: 0, средняя: 1, низкая: 2 };
const FOR_LABEL: Record<string, string> = { TopAdvisor: "TopAdvisor", UNISON: "UNISON", Гайрат: "Эксперт", бизнес: "Бизнесу" };

export function LawList({ rows, seenUntil }: { rows: LawRow[]; seenUntil: string }) {
  const [imp, setImp] = useState<"important" | "all">("important");
  const [sphere, setSphere] = useState("all");
  const [q, setQ] = useState("");
  const spheres = useMemo(
    () => [...new Set(rows.flatMap((r) => r.act?.spheres ?? []))].sort(),
    [rows],
  );
  const reviewed = rows.filter((r) => r.act);
  const shown = useMemo(() => {
    const n = q.trim().toLowerCase();
    return reviewed
      .filter((r) => (imp === "all" ? true : r.act!.importance !== "низкая"))
      .filter((r) => (sphere === "all" ? true : r.act!.spheres.includes(sphere)))
      .filter((r) => !n || `${r.act!.title_ru} ${r.act!.essence} ${r.act!.number} ${r.title}`.toLowerCase().includes(n))
      .sort((a, b) => b.firstSeen.slice(0, 10).localeCompare(a.firstSeen.slice(0, 10)) || IMP[a.act!.importance] - IMP[b.act!.importance]);
  }, [reviewed, imp, sphere, q]);
  const unreviewed = rows.filter((r) => !r.act).slice(0, 40);

  let lastDay = "";
  return (
    <div className="page">
      <div className="page-head">
        <h1>Законодательство</h1>
        <p className="muted">
          Новые акты с lex.uz с разбором по полному тексту: суть, что меняется, кого касается, что это даёт
          бизнесу, какие работы и закупки поручены. Разобрано {reviewed.length} из {rows.length}.
        </p>
      </div>
      <div className="filters-bar">
        <div className="seg">
          <button className={imp === "important" ? "on" : ""} onClick={() => setImp("important")}>Важные и отраслевые</button>
          <button className={imp === "all" ? "on" : ""} onClick={() => setImp("all")}>Все разобранные</button>
        </div>
        <select className="select" value={sphere} onChange={(e) => setSphere(e.target.value)} aria-label="Сфера">
          <option value="all">Все сферы</option>
          {spheres.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input className="search" placeholder="Поиск: номер, тема…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {shown.length === 0 && <div className="empty">Ничего не найдено.</div>}
      <div className="acts">
        {shown.map((r) => {
          const a = r.act!;
          const day = r.firstSeen.slice(0, 10);
          const head = day !== lastDay ? (lastDay = day, <div className="day-h" key={`d-${day}`}>{fmtDate(day)}</div>) : null;
          const opps = a.opportunities.filter((o) => o.for !== "бизнес").slice(0, 2);
          return (
            <div key={r.id}>
              {head}
              <Link href={`/app/law/${r.id}`} className={`act-card imp-b-${a.importance}`}>
                <div className="act-top">
                  {r.firstSeen > seenUntil && <span className="dot-new" />}
                  <span className={`imp imp-${a.importance}`}>{a.importance === "высокая" ? "важно" : a.importance === "средняя" ? "отраслевое" : "узкое"}</span>
                  <span className="muted small">{[a.act_type, a.number && `№ ${a.number}`].filter(Boolean).join(" ")}</span>
                  {a.effective && <span className="muted small">· в силу {fmtDate(a.effective)}</span>}
                  <span className="act-spheres">{a.spheres.slice(0, 3).map((s) => <span key={s} className="tag">{s}</span>)}</span>
                </div>
                <h3>{a.title_ru || stripRawTitle(r.title)}</h3>
                <p>{a.essence}</p>
                {opps.length > 0 && (
                  <div className="act-opps">
                    {opps.map((o) => <span key={o.what}><b>{FOR_LABEL[o.for] ?? o.for}:</b> {o.what}</span>)}
                  </div>
                )}
                {a.expected_procurements.length > 0 && (
                  <div className="act-proc">Ожидаемые работы и закупки: {a.expected_procurements.length}</div>
                )}
              </Link>
            </div>
          );
        })}
      </div>
      {unreviewed.length > 0 && (
        <details className="block unrev">
          <summary>Акты без разбора ({rows.length - reviewed.length}) — узкие ведомственные или ещё в очереди</summary>
          <ul>
            {unreviewed.map((r) => (
              <li key={r.id}>
                <span className="muted small">{fmtDate(r.firstSeen)}</span>{" "}
                <a href={r.url} target="_blank" rel="noopener noreferrer">{stripRawTitle(r.titleRu || r.title).slice(0, 160)}</a>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
