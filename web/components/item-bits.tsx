import Link from "next/link";
import {
  DIRECTION_LABEL,
  cleanTitle,
  deadlineLabel,
  fmtDate,
  type FullItem,
} from "@/lib/types";

export function DirectionChip({ d }: { d?: string | null }) {
  if (!d || d === "нет") return null;
  return <span className={`dir dir-${d}`}>{DIRECTION_LABEL[d] ?? d}</span>;
}

export function DeadlinePill({ deadline }: { deadline: string | null }) {
  const { text, tone } = deadlineLabel(deadline);
  if (tone === "none") return null;
  return <span className={`dl dl-${tone}`}>{text}</span>;
}

export function ImportancePill({ v }: { v?: string | null }) {
  if (!v) return null;
  return <span className={`imp imp-${v}`}>{v === "высокая" ? "важно" : v === "средняя" ? "отраслевое" : "узкое"}</span>;
}

/** Откуда и чьи деньги: донор/агентство, иначе источник. */
export function originLine(it: FullItem): string {
  const parts: string[] = [];
  if (it.donor) parts.push(it.donor);
  else parts.push(it.source.replace(/\s*\(.*\)$/, ""));
  if (it.buyer && it.buyer !== it.donor) parts.push(it.buyer.slice(0, 60));
  return parts.join(" · ");
}

/** Компактная карточка для «Сегодня». */
export function MiniCard({ it, href, isNew }: { it: FullItem; href: string; isNew?: boolean }) {
  return (
    <Link href={href} className="mini">
      <div className="mini-top">
        {isNew && <span className="dot-new" title="Новое с прошлого визита" />}
        <DirectionChip d={it.direction} />
        <DeadlinePill deadline={it.deadline} />
      </div>
      <div className="mini-title">{cleanTitle(it)}</div>
      <div className="mini-meta">{originLine(it)}</div>
      {it.whyUs && <div className="mini-why">{it.whyUs}</div>}
    </Link>
  );
}

export function ActMini({ it, isNew }: { it: FullItem; isNew?: boolean }) {
  const a = it.act;
  const opp = a?.opportunities?.find((o) => o.for !== "бизнес") ?? a?.opportunities?.[0];
  return (
    <Link href={`/app/law/${it.id}`} className="mini mini-act">
      <div className="mini-top">
        {isNew && <span className="dot-new" />}
        <ImportancePill v={a?.importance} />
        <span className="muted small">
          {[a?.act_type, a?.number].filter(Boolean).join(" № ")}
          {a?.effective ? ` · в силу ${fmtDate(a.effective)}` : ""}
        </span>
      </div>
      <div className="mini-title">{a?.title_ru || cleanTitle(it)}</div>
      {a?.essence && <div className="mini-sum">{a.essence}</div>}
      {opp && (
        <div className="mini-why">
          <b>{opp.for}:</b> {opp.what}
        </div>
      )}
    </Link>
  );
}
