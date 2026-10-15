import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getItem } from "@/lib/data";
import { DIRECTION_LABEL, cleanTitle, deadlineLabel, fmtDate, sourceLinkLabel, stripRawTitle } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const it = getItem(id);
  return { title: `${it ? cleanTitle(it).slice(0, 80) : "Позиция"} — Tenders` };
}

export default async function ItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const it = getItem(id);
  if (!it) notFound();
  if (it.category === "legislation") redirect(`/app/law/${id}`);
  const dl = deadlineLabel(it.deadline);
  const back = it.track === "expert" ? "/app/experts" : "/app/tenders";
  return (
    <div className="page page-narrow">
      <Link href={`${back}?id=${it.id}`} className="back">← к списку</Link>
      <div className="d-chips">
        {it.direction && it.direction !== "нет" && <span className={`dir dir-${it.direction}`}>{DIRECTION_LABEL[it.direction]}</span>}
        {typeof it.score === "number" && <span className="pill">релевантность {it.score}/10</span>}
        {it.repeatOf && <span className="pill pill-warn">повтор лота № {it.repeatOf}</span>}
      </div>
      <h1>{cleanTitle(it)}</h1>
      {it.titleRu && stripRawTitle(it.title) !== it.titleRu && <p className="d-orig">{stripRawTitle(it.title)}</p>}
      {it.whyUs && <div className="why"><b>Почему нам:</b> {it.whyUs}</div>}
      <dl className="facts">
        <dt>Финансирование</dt><dd>{it.donor || it.source}</dd>
        {it.buyer && it.buyer !== it.donor && (<><dt>Заказчик</dt><dd>{it.buyer}</dd></>)}
        {it.geo && (<><dt>Страна</dt><dd>{it.geo}</dd></>)}
        {it.budget && (<><dt>Бюджет</dt><dd>{it.budget}</dd></>)}
        {it.published && (<><dt>Опубликовано</dt><dd>{fmtDate(it.published)}</dd></>)}
        <dt>Срок подачи</dt><dd>{fmtDate(it.deadline) ?? "не указан"} {dl.tone !== "none" && <span className={`dl dl-${dl.tone}`}>{dl.text}</span>}</dd>
      </dl>
      {it.summaryRu && <section className="lead-box"><h2>Что нужно</h2><p>{it.summaryRu}</p></section>}
      {it.siteBrief && <section className="d-sec"><h2>Разбор</h2><p>{it.siteBrief}</p></section>}
      {it.recommendation && <section className="d-sec d-reco"><h2>Что предложить</h2><p>{it.recommendation}</p></section>}
      {it.eligibility && <section className="d-sec"><h2>Требования к участнику</h2><p>{it.eligibility}</p></section>}
      {(it.docsChecklist?.length ?? 0) > 0 && <section className="d-sec"><h2>Документы</h2><ul>{it.docsChecklist.map((d) => <li key={d}>{d}</li>)}</ul></section>}
      {(it.actionItems?.length ?? 0) > 0 && <section className="d-sec"><h2>Шаги</h2><ul>{it.actionItems!.map((a) => <li key={a}>{a}</li>)}</ul></section>}
      {(it.legalAspects?.length ?? 0) > 0 && <section className="d-sec"><h2>Юридические аспекты</h2><ul>{it.legalAspects!.map((a) => <li key={a}>{a}</li>)}</ul></section>}
      <div className="d-links">
        <a className="btn" href={it.url} target="_blank" rel="noopener noreferrer">{sourceLinkLabel(it)}</a>
        <Link className="btn ghost" href={`${back}?id=${it.id}`}>Статус и заметка</Link>
      </div>
    </div>
  );
}
