import Link from "next/link";
import { getInsights } from "@/lib/data";

export const metadata = {
  title: "Аналитика | TA Tenders",
  description:
    "Регуляторные дайджесты и аналитические разборы: что меняется в законодательстве " +
    "Узбекистана и что это значит для бизнеса.",
};

export default function AnalyticsPage() {
  const insights = getInsights();
  return (
    <>
      <h1 className="page-title">Аналитика</h1>
      <p className="page-sub">
        Готовые аналитические материалы на основе мониторинга: регуляторные
        дайджесты по новым НПА — что принято, кого касается и как подготовиться.
      </p>

      {insights.length === 0 && (
        <div className="empty">
          Материалов пока нет — первый дайджест появится после накопления актов.
        </div>
      )}

      {insights.map((ins) => (
        <div className="insight-card" key={ins.id}>
          <div className="card-meta">
            <span className="badge">📊 Регуляторный дайджест</span>
            <span>{ins.period}</span>
            <span>· {ins.sections.length} тем · {ins.sources.length} актов</span>
          </div>
          <h3>
            <Link href={`/analytics/${ins.id}`}>{ins.title}</Link>
          </h3>
          <p className="card-sum">{ins.lead}</p>
          <div className="card-foot">
            <span className="spacer" />
            <Link href={`/analytics/${ins.id}`}>Читать разбор →</Link>
          </div>
        </div>
      ))}
    </>
  );
}
