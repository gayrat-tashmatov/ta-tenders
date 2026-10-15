import Link from "next/link";
import { getItems } from "@/lib/data";
import { currentUser, isDemo, supabaseServer } from "@/lib/supabase/server";
import { loadCabinet } from "@/lib/cabinet";
import { cleanTitle, fmtDate, type FullItem } from "@/lib/types";
import { DeadlinePill, DirectionChip, originLine } from "@/components/item-bits";

export const dynamic = "force-dynamic";
export const metadata = { title: "Мои — TA Tenders" };

const GROUPS = [
  { key: "working", label: "В работе" },
  { key: "submitted", label: "Поданные — ждём результат" },
  { key: "saved", label: "Сохранённые" },
  { key: "won", label: "Выигранные" },
  { key: "lost", label: "Проигранные" },
] as const;
const ACTION_LABEL: Record<string, string> = {
  status: "статус", saved: "сохранил(а)", unsaved: "убрал(а) из сохранённых",
  note: "заметка", mark_all_viewed: "отметил(а) всё просмотренным",
};
const STATUS_LABEL: Record<string, string> = {
  viewed: "просмотрен", working: "в работе", submitted: "подан", won: "выигран", lost: "проигран", skipped: "не наше",
};

export default async function MyPage() {
  const me = await currentUser();
  const cab = await loadCabinet(me?.id ?? null);
  const items = new Map(getItems().map((it) => [it.id, it]));
  const mine = cab.mine.filter((s) => items.has(s.tenderId));
  const grouped: Record<string, { s: (typeof mine)[number]; it: FullItem }[]> = {};
  for (const s of mine) {
    const it = items.get(s.tenderId)!;
    const keys = [s.status ?? "", s.saved ? "saved" : ""];
    for (const k of keys) if (GROUPS.some((g) => g.key === k)) (grouped[k] ??= []).push({ s, it });
  }
  for (const k of Object.keys(grouped))
    grouped[k].sort((a, b) => (a.it.deadline ?? "9999").localeCompare(b.it.deadline ?? "9999"));

  let log: { user_id: string | null; tender_id: string; tender_title: string | null; action: string; value: string | null; created_at: string }[] = [];
  if (!isDemo()) {
    const sb = await supabaseServer();
    const { data } = await sb.from("activity_log").select("user_id, tender_id, tender_title, action, value, created_at")
      .neq("action", "status").order("created_at", { ascending: false }).limit(60);
    const { data: st } = await sb.from("activity_log").select("user_id, tender_id, tender_title, action, value, created_at")
      .eq("action", "status").neq("value", "viewed").order("created_at", { ascending: false }).limit(60);
    log = [...(data ?? []), ...(st ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 80);
  }
  const hrefFor = (it: FullItem) => (it.category === "legislation" ? `/app/law/${it.id}` : `/app/${it.track === "expert" ? "experts" : "tenders"}?id=${it.id}`);

  return (
    <div className="page">
      <div className="page-head">
        <h1>Мои</h1>
        <p className="muted">Ваша воронка: что сохранено, что в работе, что подано и чем закончилось. Сортировка по сроку.</p>
      </div>
      {GROUPS.map((g) => (
        <section key={g.key} className="block">
          <h2>{g.label} <span className="muted">({grouped[g.key]?.length ?? 0})</span></h2>
          {!grouped[g.key]?.length && <p className="empty-s">Пусто.</p>}
          <div className="my-list">
            {(grouped[g.key] ?? []).map(({ s, it }) => (
              <Link key={g.key + it.id} href={hrefFor(it)} className="my-row">
                <DeadlinePill deadline={it.deadline} />
                <span className="my-t">{cleanTitle(it)}</span>
                <DirectionChip d={it.direction} />
                <span className="muted small">{originLine(it)}</span>
                {s.note && <span className="my-note">📝 {s.note.slice(0, 120)}</span>}
              </Link>
            ))}
          </div>
        </section>
      ))}
      <section className="block" id="history">
        <h2>История команды</h2>
        {isDemo() && <p className="empty-s">В демо-режиме история недоступна.</p>}
        <ul className="hist">
          {log.map((r, i) => (
            <li key={i}>
              <span className="muted small">{fmtDate(r.created_at)} {r.created_at.slice(11, 16)}</span>{" "}
              <b>{cab.names[r.user_id ?? ""] ?? "коллега"}</b>{" "}
              {ACTION_LABEL[r.action] ?? r.action}
              {r.action === "status" && r.value ? `: ${STATUS_LABEL[r.value] ?? r.value}` : ""}
              {r.tender_id !== "*" && r.tender_title ? <> — {items.has(r.tender_id) ? <Link href={hrefFor(items.get(r.tender_id)!)}>{r.tender_title}</Link> : r.tender_title}</> : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
