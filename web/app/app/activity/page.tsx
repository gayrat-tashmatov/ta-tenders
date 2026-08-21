import Link from "next/link";
import { currentUser, isDemo, supabaseServer } from "@/lib/supabase/server";
import { fmtDate } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "Активность | Кабинет TA Tenders" };

const ACTION_LABEL: Record<string, string> = {
  status: "сменил(а) статус",
  saved: "сохранил(а) ⭐",
  unsaved: "убрал(а) из сохранённых",
  note: "написал(а) заметку",
  mark_all_viewed: "отметил(а) всё прочитанным",
};
const STATUS_LABEL: Record<string, string> = {
  new: "Новый", viewed: "Просмотрен", working: "В работе", submitted: "Подан",
  won: "Выигран", lost: "Проигран", skipped: "Пропущен",
};

interface Row {
  id: number; user_id: string | null; tender_id: string; tender_title: string | null;
  action: string; value: string | null; created_at: string;
}

export default async function ActivityPage() {
  const me = await currentUser();
  let rows: Row[] = [];
  let names = new Map<string, string>();
  let error: string | null = null;

  if (!isDemo()) {
    const supabase = await supabaseServer();
    const [a, p] = await Promise.all([
      supabase.from("activity_log").select("*").order("created_at", { ascending: false }).limit(300),
      supabase.from("profiles").select("id, full_name"),
    ]);
    if (a.error) error = a.error.message;
    rows = (a.data ?? []) as Row[];
    names = new Map((p.data ?? []).map((x) => [x.id, x.full_name || "коллега"]));
  }

  // группировка по дням
  const byDay = new Map<string, Row[]>();
  for (const r of rows) {
    const d = r.created_at.slice(0, 10);
    byDay.set(d, [...(byDay.get(d) ?? []), r]);
  }

  return (
    <main className="container cab-section">
      <h1 className="page-title">Активность команды</h1>
      <p className="page-sub">
        Полная история: кто какой тендер открыл, сохранил, взял в работу, подал, что записал.
        Ничего не теряется — всё остаётся здесь.
      </p>

      {isDemo() && <div className="ws-demo-note">Демо-режим: история доступна после входа.</div>}
      {error && (
        <div className="ws-error-note">
          ⚠ История недоступна: {error}. Выполните миграцию supabase/migration_002_history.sql.
        </div>
      )}
      {!isDemo() && !error && rows.length === 0 && (
        <div className="empty">Пока пусто — действия начнут записываться с первого клика.</div>
      )}

      {[...byDay.entries()].map(([day, list]) => (
        <section key={day} className="section">
          <h2>{fmtDate(day) ?? day}</h2>
          <ul className="activity-list">
            {list.map((r) => {
              const who = r.user_id === me?.id ? "Вы" : names.get(r.user_id ?? "") ?? "коллега";
              const what = ACTION_LABEL[r.action] ?? r.action;
              const val = r.action === "status" ? STATUS_LABEL[r.value ?? ""] ?? r.value
                        : r.action === "note" ? `«${(r.value ?? "").slice(0, 140)}»` : "";
              return (
                <li key={r.id}>
                  <span className="activity-time">{r.created_at.slice(11, 16)}</span>
                  <b>{who}</b> {what}{val ? <> → <b>{val}</b></> : null}:{" "}
                  {r.tender_id === "*" ? (
                    <span>{r.tender_title ?? ""} — {r.value} шт.</span>
                  ) : (
                    <Link href={`/t/${r.tender_id}`}>{r.tender_title ?? r.tender_id}</Link>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </main>
  );
}
