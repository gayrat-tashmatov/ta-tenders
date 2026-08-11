import Link from "next/link";
import { notFound } from "next/navigation";
import { fmtDate, getInsight, getInsights, getNpa, npaTypeTitle } from "@/lib/data";
import { stripRawTitle } from "@/lib/types";
import { buildActIndex, linkifyActs } from "@/lib/acts";

export function generateStaticParams() {
  return getInsights().map((i) => ({ id: i.id }));
}

export const dynamicParams = false;

export default async function InsightPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const ins = getInsight(id);
  if (!ins) notFound();

  const idx = buildActIndex(getNpa());
  const date = fmtDate(ins.created);

  return (
    <>
      <div className="detail-head">
        <span className="badge">📊 Регуляторный дайджест · {ins.period}</span>
        <h1 className="detail-title">{ins.title}</h1>
      </div>

      <p className="insight-lead">{linkifyActs(ins.lead, idx)}</p>

      {ins.sections.map((s) => (
        <div className="section insight-section" key={s.heading}>
          <h2>{s.heading}</h2>
          <p>{linkifyActs(s.body, idx)}</p>
          {(s.act_keys?.length ?? 0) > 0 && (
            <div className="chips">
              {s.act_keys!
                .filter((k) => !k.startsWith("LEX"))
                .map((k) =>
                  idx[k] ? (
                    <Link className="chip" href={`/t/${idx[k]}`} key={k}>
                      {npaTypeTitle(k)} {k}
                    </Link>
                  ) : (
                    <span className="chip" key={k}>
                      {npaTypeTitle(k)} {k}
                    </span>
                  ),
                )}
            </div>
          )}
        </div>
      ))}

      {ins.businessImpact.length > 0 && (
        <div className="section reco">
          <h2>Что это значит для бизнеса</h2>
          <ul>
            {ins.businessImpact.map((b) => (
              <li key={b}>{linkifyActs(b, idx)}</li>
            ))}
          </ul>
        </div>
      )}

      {ins.howToPrepare.length > 0 && (
        <div className="section">
          <h2>Как подготовиться</h2>
          <ol className="num-list">
            {ins.howToPrepare.map((b) => (
              <li key={b}>{linkifyActs(b, idx)}</li>
            ))}
          </ol>
        </div>
      )}

      {ins.sources.length > 0 && (
        <div className="section">
          <h2>Источники ({ins.sources.length})</h2>
          <ul className="src-list">
            {ins.sources.map((s) => (
              <li key={s.itemId}>
                {s.keys.length > 0 && (
                  <b>
                    <Link href={`/t/${s.itemId}`}>{s.keys.join(", ")}</Link>
                    {" — "}
                  </b>
                )}
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {stripRawTitle(s.title)} ↗
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <Link className="btn ghost" href="/analytics">
          ← Вся аналитика
        </Link>
        <Link className="btn ghost" href="/npa">
          Реестр НПА
        </Link>
      </p>

      <p className="back">
        Материал подготовлен автоматически на основе официальных публикаций
        {date ? ` (${date})` : ""}. Реквизиты актов кликабельны — они ведут на
        карточки с первоисточниками. Перед принятием решений сверяйтесь с
        текстами актов.
      </p>
    </>
  );
}
