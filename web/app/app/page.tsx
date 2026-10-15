import Link from "next/link";
import { getInsights, getItems } from "@/lib/data";
import { currentUser } from "@/lib/supabase/server";
import { loadCabinet } from "@/lib/cabinet";
import { cleanTitle, daysLeft, deadlineStatus, fmtDate, isTenderCategory, type FullItem } from "@/lib/types";
import { ActMini, DeadlinePill, MiniCard } from "@/components/item-bits";
import { SeenButton } from "./seen-button";

export const dynamic = "force-dynamic";

const IMP = { высокая: 0, средняя: 1, низкая: 2 } as const;

function since(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    timeZone: "Asia/Tashkent", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit",
  });
}

export default async function TodayPage() {
  const me = await currentUser();
  const cab = await loadCabinet(me?.id ?? null);
  const items = getItems();
  const state = new Map(cab.mine.map((s) => [s.tenderId, s]));
  const isNew = (it: FullItem) => !state.get(it.id)?.status && it.firstSeen > cab.seenUntil;
  const alive = (it: FullItem) => deadlineStatus(it.deadline).status !== "expired";
  const ours = (it: FullItem) => it.direction !== "нет";
  const byScore = (a: FullItem, b: FullItem) => (b.score ?? 0) - (a.score ?? 0) || b.firstSeen.localeCompare(a.firstSeen);

  const tenders = items.filter((it) => isTenderCategory(it.category) && alive(it) && ours(it));
  const company = tenders.filter((it) => it.track === "company" || it.track === "both");
  const expert = tenders.filter((it) => it.track === "expert" || it.track === "both");
  const newCompany = company.filter(isNew).sort(byScore);
  const newExpert = expert.filter(isNew).sort(byScore);
  const acts = items.filter((it) => it.category === "legislation" && it.act);
  const newActs = acts.filter(isNew);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();
  const actsShown = (newActs.length ? newActs : acts.filter((a) => a.firstSeen > weekAgo))
    .filter((a) => a.act!.importance !== "низкая")
    .sort((a, b) => IMP[a.act!.importance] - IMP[b.act!.importance] || b.firstSeen.localeCompare(a.firstSeen))
    .slice(0, 4);

  const mineWatched = items.filter((it) => {
    const s = state.get(it.id);
    return s && (s.saved || ["working", "submitted"].includes(s.status ?? ""));
  });
  const hot = mineWatched
    .filter((it) => { const d = daysLeft(it.deadline); return d !== null && d >= 0 && d <= 10; })
    .sort((a, b) => (daysLeft(a.deadline) ?? 99) - (daysLeft(b.deadline) ?? 99));
  const weekly = getInsights().find((i) => i.format === "weekly-v2") ?? getInsights()[0];
  const totalNew = newCompany.length + newExpert.length + newActs.length;

  return (
    <div className="page">
      <div className="today-head">
        <div>
          <h1>Сегодня</h1>
          <p className="muted">
            Новое с вашего прошлого просмотра — <b>{since(cab.seenUntil)}</b>.
          </p>
        </div>
        <SeenButton count={totalNew} scope="Сегодня" />
      </div>

      <div className="kpis">
        <Link href="/app/tenders?f=new" className="kpi">
          <b>{newCompany.length}</b><span>новых тендеров для компаний</span>
        </Link>
        <Link href="/app/experts?f=new" className="kpi">
          <b>{newExpert.length}</b><span>новых позиций для эксперта</span>
        </Link>
        <Link href="/app/law" className="kpi">
          <b>{newActs.filter((a) => a.act!.importance === "высокая").length}</b><span>важных актов</span>
        </Link>
        <Link href="/app/my" className={`kpi${hot.length ? " kpi-hot" : ""}`}>
          <b>{hot.length}</b><span>сроков в ближайшие 10 дней в «Моих»</span>
        </Link>
      </div>

      {hot.length > 0 && (
        <section className="block">
          <h2>Горящие сроки по вашим тендерам</h2>
          <div className="hot-list">
            {hot.slice(0, 6).map((it) => (
              <Link key={it.id} href={`/app/${it.track === "expert" ? "experts" : "tenders"}?id=${it.id}`} className="hot-row">
                <DeadlinePill deadline={it.deadline} />
                <span>{cleanTitle(it)}</span>
                <span className="muted small">{state.get(it.id)?.status === "working" ? "в работе" : state.get(it.id)?.status === "submitted" ? "подан" : "сохранён"}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <div className="two-col">
        <section className="block">
          <div className="block-head">
            <h2>Для компаний</h2>
            <Link href="/app/tenders?f=new" className="small">все новые ({newCompany.length}) →</Link>
          </div>
          {newCompany.length === 0 && <p className="empty-s">Новых тендеров по профилю нет.</p>}
          <div className="mini-grid">
            {newCompany.slice(0, 6).map((it) => (
              <MiniCard key={it.id} it={it} href={`/app/tenders?id=${it.id}`} isNew />
            ))}
          </div>
        </section>
        <section className="block">
          <div className="block-head">
            <h2>Для эксперта</h2>
            <Link href="/app/experts?f=new" className="small">все новые ({newExpert.length}) →</Link>
          </div>
          {newExpert.length === 0 && <p className="empty-s">Новых позиций для индивидуального консультанта нет.</p>}
          <div className="mini-grid">
            {newExpert.slice(0, 6).map((it) => (
              <MiniCard key={it.id} it={it} href={`/app/experts?id=${it.id}`} isNew />
            ))}
          </div>
        </section>
      </div>

      <section className="block">
        <div className="block-head">
          <h2>Законодательство: {newActs.length ? "новое" : "за неделю"} — что важно и что это даёт</h2>
          <Link href="/app/law" className="small">все акты →</Link>
        </div>
        {actsShown.length === 0 && <p className="empty-s">Разобранных актов пока нет.</p>}
        <div className="mini-grid">
          {actsShown.map((it) => <ActMini key={it.id} it={it} isNew={isNew(it)} />)}
        </div>
      </section>

      {weekly && (
        <section className="block weekly-teaser">
          <div className="block-head">
            <h2>Обзор недели</h2>
            <Link href={`/app/analytics/${weekly.id}`} className="small">читать полностью →</Link>
          </div>
          <h3>{weekly.title}</h3>
          <p>{weekly.lead}</p>
          {weekly.topActs && weekly.topActs.length > 0 && (
            <ul className="tight">
              {weekly.topActs.slice(0, 3).map((t) => (
                <li key={t.act + t.title}><b>{t.act}</b> — {t.title}: {t.action}</li>
              ))}
            </ul>
          )}
          <p className="muted small">Период: {weekly.period} · подготовлен {fmtDate(weekly.created)}</p>
        </section>
      )}
      <p className="muted small foot-note">
        Всего в кабинете: {company.length} актуальных тендеров для компаний, {expert.length} позиций для
        эксперта, {acts.length} разобранных актов.
      </p>
    </div>
  );
}
