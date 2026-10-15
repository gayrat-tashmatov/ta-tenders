import Link from "next/link";
import { notFound } from "next/navigation";
import { getItem, getNpa } from "@/lib/data";
import { fmtDate, stripRawTitle } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const it = getItem(id);
  const t = it?.act?.title_ru || (it ? stripRawTitle(it.titleRu || it.title) : "Акт");
  return { title: `${t.slice(0, 80)} — TA Tenders` };
}

const FOR_LABEL: Record<string, string> = {
  TopAdvisor: "TopAdvisor", UNISON: "UNISON", Гайрат: "Гайрат (эксперт)", бизнес: "Бизнесу",
};

export default async function ActPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const it = getItem(id);
  if (!it || it.category !== "legislation") notFound();
  const a = it.act;
  const mentions = getNpa().filter((n) => n.itemId === id).flatMap((n) => n.mentions);
  return (
    <div className="page page-narrow">
      <Link href="/app/law" className="back">← Законодательство</Link>
      {!a && (
        <>
          <h1>{stripRawTitle(it.titleRu || it.title)}</h1>
          <p className="muted">Разбора пока нет: акт узкий или ещё в очереди.</p>
          <a className="btn" href={it.url} target="_blank" rel="noopener noreferrer">Текст на lex.uz ↗</a>
        </>
      )}
      {a && (
        <article className="act-page">
          <div className="act-top">
            <span className={`imp imp-${a.importance}`}>{a.importance === "высокая" ? "важно для бизнеса" : a.importance === "средняя" ? "отраслевое" : "узкое"}</span>
            {a.spheres.map((s) => <span key={s} className="tag">{s}</span>)}
          </div>
          <h1>{a.title_ru}</h1>
          <dl className="facts facts-inline">
            <dt>Акт</dt><dd>{[a.act_type, a.number && `№ ${a.number}`].filter(Boolean).join(" ")}</dd>
            {a.adopted && (<><dt>Принят</dt><dd>{fmtDate(a.adopted)}</dd></>)}
            {a.effective && (<><dt>Вступает в силу</dt><dd>{fmtDate(a.effective)}</dd></>)}
            <dt>Разбор по</dt><dd>{a.source_kind === "pdf" ? "скану акта" : a.source_kind === "text" ? "полному тексту" : "реквизитам (текста нет)"}</dd>
          </dl>
          <section className="lead-box"><h2>Суть</h2><p>{a.essence}</p></section>
          {a.key_changes.length > 0 && (
            <section className="d-sec"><h2>Что меняется</h2><ul>{a.key_changes.map((c) => <li key={c}>{c}</li>)}</ul></section>
          )}
          {a.business_impact && <section className="d-sec"><h2>Что это значит для бизнеса</h2><p>{a.business_impact}</p></section>}
          {a.who_affected.length > 0 && (
            <section className="d-sec"><h2>Кого касается</h2><div className="tags">{a.who_affected.map((w) => <span key={w} className="tag">{w}</span>)}</div></section>
          )}
          {a.opportunities.length > 0 && (
            <section className="d-sec opp-box">
              <h2>Возможности</h2>
              <ul>{a.opportunities.map((o) => <li key={o.for + o.what}><b>{FOR_LABEL[o.for] ?? o.for}:</b> {o.what}</li>)}</ul>
            </section>
          )}
          {a.expected_procurements.length > 0 && (
            <section className="d-sec proc-box">
              <h2>Поручено разработать или закупить</h2>
              <p className="muted small">Это будущие тендеры и проекты — стоит следить за заказчиками.</p>
              <ul>{a.expected_procurements.map((p) => <li key={p}>{p}</li>)}</ul>
            </section>
          )}
          {a.obligations.length > 0 && (
            <section className="d-sec">
              <h2>Поручения и сроки</h2>
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th>Кто</th><th>Что</th><th>Срок</th></tr></thead>
                  <tbody>{a.obligations.map((o, i) => <tr key={i}><td>{o.who}</td><td>{o.what}</td><td>{o.deadline || "—"}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          )}
          {a.risks.length > 0 && (
            <section className="d-sec"><h2>Риски и на что обратить внимание</h2><ul>{a.risks.map((r) => <li key={r}>{r}</li>)}</ul></section>
          )}
          {mentions.length > 0 && (
            <section className="d-sec"><h2>Упоминания в СМИ</h2>
              <ul>{mentions.map((m) => <li key={m.url}><a href={m.url} target="_blank" rel="noopener noreferrer">{m.title}</a> <span className="muted small">{fmtDate(m.added)}</span></li>)}</ul>
            </section>
          )}
          <div className="d-links">
            <a className="btn" href={it.url} target="_blank" rel="noopener noreferrer">Текст акта на lex.uz ↗</a>
          </div>
          <p className="muted small">Разбор подготовлен автоматически по тексту акта. Перед советом клиенту сверяйтесь с первоисточником.</p>
        </article>
      )}
    </div>
  );
}
