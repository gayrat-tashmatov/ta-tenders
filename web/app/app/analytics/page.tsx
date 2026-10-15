import Link from "next/link";
import { getInsights, getItems } from "@/lib/data";
import { DIRECTION_LABEL, deadlineStatus, fmtDate, isTenderCategory } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "Аналитика — TA Tenders" };

function Bars({ data }: { data: [string, number][] }) {
  const max = Math.max(1, ...data.map(([, n]) => n));
  return (
    <div className="bars">
      {data.map(([k, n]) => (
        <div key={k} className="bar-row">
          <span className="bar-k">{k}</span>
          <span className="bar-track"><span className="bar-fill" style={{ width: `${(n / max) * 100}%` }} /></span>
          <b className="bar-n">{n}</b>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const insights = getInsights();
  const weekly = insights.filter((i) => i.format === "weekly-v2");
  const legacy = insights.filter((i) => i.format !== "weekly-v2");
  const items = getItems();
  const open = items.filter((it) => isTenderCategory(it.category) && deadlineStatus(it.deadline).status !== "expired" && it.direction !== "нет");
  const count = (key: (x: (typeof open)[number]) => string | null | undefined) => {
    const m = new Map<string, number>();
    for (const it of open) { const k = key(it); if (k) m.set(k, (m.get(k) ?? 0) + 1); }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  };
  const byDir = count((it) => (it.direction ? DIRECTION_LABEL[it.direction] : "не размечено"));
  const byDonor = count((it) => it.donor || it.source.replace(/\s*\(.*\)$/, "")).slice(0, 10);
  const weeks: [string, number][] = [];
  for (let w = 5; w >= 0; w--) {
    const from = new Date(Date.now() - (w + 1) * 7 * 86400000).toISOString();
    const to = new Date(Date.now() - w * 7 * 86400000).toISOString();
    const n = items.filter((it) => isTenderCategory(it.category) && it.firstSeen >= from && it.firstSeen < to && it.direction !== "нет" && (it.score ?? 0) >= 7).length;
    weeks.push([`${fmtDate(from)?.slice(0, 5)}–${fmtDate(to)?.slice(0, 5)}`, n]);
  }
  const latest = weekly[0];
  return (
    <div className="page">
      <div className="page-head">
        <h1>Аналитика</h1>
        <p className="muted">Недельный регуляторный обзор и срез рынка тендеров по профилю компаний.</p>
      </div>
      {latest ? (
        <Link href={`/app/analytics/${latest.id}`} className="weekly-hero">
          <span className="pill">Обзор недели · {latest.period}</span>
          <h2>{latest.title}</h2>
          <p>{latest.lead}</p>
          <span className="small">Читать: главное, что сделать, возможности, ожидаемые закупки, календарь →</span>
        </Link>
      ) : (
        <div className="note">Первый недельный обзор появится после ближайшего прогона с разобранными актами.</div>
      )}
      <div className="three-col">
        <section className="block"><h2>Открытые тендеры по направлениям</h2><Bars data={byDir} /></section>
        <section className="block"><h2>Кто финансирует</h2><Bars data={byDonor} /></section>
        <section className="block"><h2>Релевантных тендеров по неделям</h2><Bars data={weeks} /></section>
      </div>
      {weekly.length > 1 && (
        <section className="block">
          <h2>Архив обзоров</h2>
          <ul className="arch">
            {weekly.slice(1).map((i) => <li key={i.id}><Link href={`/app/analytics/${i.id}`}>{i.title}</Link> <span className="muted small">{i.period}</span></li>)}
          </ul>
        </section>
      )}
      {legacy.length > 0 && (
        <details className="block">
          <summary>Старые ежедневные дайджесты ({legacy.length})</summary>
          <ul className="arch">
            {legacy.map((i) => <li key={i.id}><Link href={`/app/analytics/${i.id}`}>{i.title}</Link> <span className="muted small">{fmtDate(i.created)}</span></li>)}
          </ul>
        </details>
      )}
    </div>
  );
}
