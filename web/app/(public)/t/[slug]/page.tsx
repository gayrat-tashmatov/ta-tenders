import Link from "next/link";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import {
  CATEGORY_ICON,
  CATEGORY_LABEL,
  cleanTitle,
  deadlineStatus,
  fmtDate,
  getItem,
  getItems,
  getNpa,
  npaTypeTitle,
} from "@/lib/data";
import { buildActIndex, linkifyActs } from "@/lib/acts";
import { sourceLinkLabel } from "@/lib/types";

export function generateStaticParams() {
  return getItems().map((it) => ({ slug: it.id }));
}

export const dynamicParams = false;

export default async function ItemPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const it = getItem(slug);
  if (!it) notFound();

  const idx = buildActIndex(getNpa());
  const { status, days } = deadlineStatus(it.deadline);
  const dlText = fmtDate(it.deadline);
  const pubText = fmtDate(it.published) ?? fmtDate(it.firstSeen);

  const cells: Array<[string, ReactNode]> = [];
  cells.push([
    "Источник",
    <a href={it.url} target="_blank" rel="noopener noreferrer" key="src">
      {it.source} ↗
    </a>,
  ]);
  if (it.buyer) cells.push(["Заказчик", it.buyer]);
  if (it.budget) cells.push(["Бюджет", it.budget]);
  if (dlText)
    cells.push([
      "Дедлайн",
      status === "expired"
        ? `${dlText} — приём закрыт`
        : days !== null
          ? `${dlText} (осталось ${days} дн.)`
          : dlText,
    ]);
  if (pubText) cells.push(["Опубликовано", pubText]);
  if (typeof it.score === "number") cells.push(["Оценка", `${it.score}/10`]);
  if (it.urgency) cells.push(["Срочность", it.urgency]);
  if (it.opportunityType && it.opportunityType !== "нет")
    cells.push(["Тип возможности", it.opportunityType]);

  return (
    <>
      <div className="detail-head">
        <span className="badge">
          {CATEGORY_ICON[it.category]} {CATEGORY_LABEL[it.category]}
        </span>{" "}
        {status === "expiring" && (
          <span className="badge st-expiring">
            🔥 {days === 0 ? "последний день подачи" : `осталось ${days} дн.`}
          </span>
        )}
        {status === "active" && (
          <span className="badge st-active">приём открыт</span>
        )}
        {status === "expired" && (
          <span className="badge st-expired">завершён</span>
        )}
        <h1 className="detail-title">{cleanTitle(it)}</h1>
      </div>

      <div className="meta-grid">
        {cells.map(([k, v]) => (
          <div className="meta-cell" key={k}>
            <div className="k">{k}</div>
            <div className="v">{v}</div>
          </div>
        ))}
      </div>

      {it.summaryRu && (
        <div className="section">
          <h2>Суть</h2>
          <p>{linkifyActs(it.summaryRu, idx, it.id)}</p>
        </div>
      )}

      {it.siteBrief && (
        <div className="section">
          <h2>Разбор</h2>
          <p>{linkifyActs(it.siteBrief, idx, it.id)}</p>
        </div>
      )}

      {it.eligibility && (
        <div className="section">
          <h2>Требования к участникам</h2>
          <p>{linkifyActs(it.eligibility, idx, it.id)}</p>
        </div>
      )}

      {it.docsChecklist.length > 0 && (
        <div className="section">
          <h2>Документы для подачи</h2>
          <ul>
            {it.docsChecklist.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {it.recommendation && (
        <div className="section reco">
          <h2>🎯 Рекомендация</h2>
          <p>{it.recommendation}</p>
        </div>
      )}

      {(it.legalAspects?.length ?? 0) > 0 && (
        <div className="section">
          <h2>⚖️ Юридические аспекты</h2>
          <ul>
            {it.legalAspects!.map((l) => (
              <li key={l}>{linkifyActs(l, idx, it.id)}</li>
            ))}
          </ul>
        </div>
      )}

      {(it.actionItems?.length ?? 0) > 0 && (
        <div className="section">
          <h2>Шаги для участия</h2>
          <ol className="num-list">
            {it.actionItems!.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ol>
          {it.contact && (
            <p style={{ marginTop: 8 }}>
              <b>Контакт:</b> {it.contact}
            </p>
          )}
        </div>
      )}

      {it.npaRefs.length > 0 && (
        <div className="section">
          <h2>Связанные НПА</h2>
          <div className="chips">
            {it.npaRefs.map((r) => {
              const target = idx[r];
              if (target && target !== it.id)
                return (
                  <Link key={r} href={`/t/${target}`} className="chip">
                    {npaTypeTitle(r)} {r}
                  </Link>
                );
              return (
                <a
                  key={r}
                  href={it.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="chip"
                >
                  {npaTypeTitle(r)} {r} · lex.uz ↗
                </a>
              );
            })}
          </div>
        </div>
      )}

      {!it.summaryRu && it.summary && (
        <div className="section">
          <h2>Описание из источника</h2>
          <p>{linkifyActs(it.summary, idx, it.id)}</p>
        </div>
      )}

      <p style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <a className="btn" href={it.url} target="_blank" rel="noopener noreferrer">
          {sourceLinkLabel(it)}
        </a>
        <Link className="btn ghost" href="/app">
          ← В кабинет
        </Link>
      </p>

      <p className="back">
        Запись собрана автоматически из «{it.origin}». Условия участия всегда
        проверяйте в первоисточнике.
      </p>
    </>
  );
}
