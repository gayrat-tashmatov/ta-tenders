import Link from "next/link";
import { notFound } from "next/navigation";
import { getInsight, getItems } from "@/lib/data";
import { fmtDate } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: `${getInsight(id)?.title?.slice(0, 80) ?? "Обзор"} — TA Tenders` };
}

const FOR_LABEL: Record<string, string> = { TopAdvisor: "TopAdvisor", UNISON: "UNISON", Гайрат: "Гайрат (эксперт)" };

export default async function InsightPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ins = getInsight(id);
  if (!ins) notFound();
  // реквизит акта → карточка разбора
  const byNumber = new Map<string, string>();
  for (const it of getItems()) if (it.category === "legislation" && it.act?.number) byNumber.set(it.act.number, it.id);
  for (const s of ins.sources ?? []) for (const k of s.keys ?? []) if (!byNumber.has(k)) byNumber.set(k, s.itemId);
  const ActLink = ({ k }: { k: string }) => {
    const target = byNumber.get(k) ?? byNumber.get(k.replace(/^№\s*/, ""));
    return target ? <Link href={`/app/law/${target}`}>{k}</Link> : <>{k}</>;
  };
  const v2 = ins.format === "weekly-v2";
  return (
    <div className="page page-narrow">
      <Link href="/app/analytics" className="back">← Аналитика</Link>
      <span className="pill">{v2 ? "Обзор недели" : "Дайджест"} · {ins.period}</span>
      <h1>{ins.title}</h1>
      <section className="lead-box"><p>{ins.lead}</p></section>

      {v2 && (ins.topActs?.length ?? 0) > 0 && (
        <section className="d-sec">
          <h2>Главное за неделю</h2>
          <div className="top-acts">
            {ins.topActs!.map((t) => (
              <div key={t.act + t.title} className="top-act">
                <div className="muted small"><ActLink k={t.act} /></div>
                <h3>{t.title}</h3>
                <p>{t.why}</p>
                <p className="todo"><b>Что делать:</b> {t.action}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      {(ins.sections ?? []).length > 0 && (
        <section className="d-sec">
          <h2>{v2 ? "По сферам" : "Разделы"}</h2>
          {ins.sections.map((s, i) => (
            <div key={i} className="sphere">
              <h3>{s.sphere || s.heading}</h3>
              <p>{s.body}</p>
              {(s.acts || s.act_keys || []).length > 0 && (
                <p className="muted small">Акты: {(s.acts || s.act_keys || []).map((k, j) => <span key={k}>{j > 0 && ", "}<ActLink k={k} /></span>)}</p>
              )}
            </div>
          ))}
        </section>
      )}
      {v2 && (ins.forBusiness?.length ?? 0) > 0 && (
        <section className="d-sec opp-box"><h2>Что сделать компаниям</h2><ul className="check">{ins.forBusiness!.map((x) => <li key={x}>{x}</li>)}</ul></section>
      )}
      {v2 && (ins.opportunities?.length ?? 0) > 0 && (
        <section className="d-sec">
          <h2>Возможности для нас</h2>
          <ul>{ins.opportunities!.map((o) => <li key={o.what}><b>{FOR_LABEL[o.for] ?? o.for}:</b> {o.what} <span className="muted small">(<ActLink k={o.act} />)</span></li>)}</ul>
        </section>
      )}
      {v2 && (ins.pipeline?.length ?? 0) > 0 && (
        <section className="d-sec proc-box">
          <h2>Ожидаемые закупки и проекты</h2>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Что</th><th>Заказчик</th><th>Когда</th><th>Акт</th></tr></thead>
              <tbody>{ins.pipeline!.map((p, i) => <tr key={i}><td>{p.what}</td><td>{p.who}</td><td>{p.when || "—"}</td><td><ActLink k={p.act} /></td></tr>)}</tbody>
            </table>
          </div>
        </section>
      )}
      {v2 && (ins.calendar?.length ?? 0) > 0 && (
        <section className="d-sec">
          <h2>Календарь</h2>
          <ul className="cal">{ins.calendar!.map((c, i) => <li key={i}><b>{fmtDate(c.date) ?? c.date}</b> {c.what} <span className="muted small">(<ActLink k={c.act} />)</span></li>)}</ul>
        </section>
      )}
      {!v2 && (ins.businessImpact?.length ?? 0) > 0 && (
        <section className="d-sec"><h2>Что это значит для бизнеса</h2><ul>{ins.businessImpact.map((x) => <li key={x}>{x}</li>)}</ul></section>
      )}
      {!v2 && (ins.howToPrepare?.length ?? 0) > 0 && (
        <section className="d-sec"><h2>Как подготовиться</h2><ul>{ins.howToPrepare.map((x) => <li key={x}>{x}</li>)}</ul></section>
      )}
      <p className="muted small">Подготовлен {fmtDate(ins.created)} автоматически по разборам актов. Сверяйтесь с текстами на lex.uz.</p>
    </div>
  );
}
