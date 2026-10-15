import "server-only";
import { isDemo, supabaseServer } from "@/lib/supabase/server";

/** Отметка «всё до этого момента просмотрено» хранится одной служебной строкой
 *  tender_state (tender_id = SEEN_KEY, note = ISO-время). До 15.10.2026 «Всё прочитано»
 *  писало строку на каждый тендер (у Гайрата 955 строк), а чтение упиралось в лимит
 *  1000 строк PostgREST — отметки терялись, прочитанное снова висело как новое. */
export const SEEN_KEY = "__seen_until__";

export interface UserState {
  tenderId: string;
  status: string | null;
  saved: boolean;
  note: string | null;
  updatedAt: string | null;
  userId: string;
}

type Row = {
  user_id: string;
  tender_id: string;
  status: string | null;
  saved: boolean | null;
  note: string | null;
  updated_at: string | null;
};

async function fetchAll(
  page: (from: number, to: number) => PromiseLike<{ data: Row[] | null; error: unknown }>,
): Promise<Row[]> {
  const out: Row[] = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await page(from, from + 999);
    if (error || !data) break;
    out.push(...data);
    if (data.length < 1000) break;
  }
  return out;
}

const toState = (r: Row): UserState => ({
  tenderId: r.tender_id,
  status: r.status,
  saved: !!r.saved,
  note: r.note,
  updatedAt: r.updated_at,
  userId: r.user_id,
});

export interface CabinetData {
  mine: UserState[];
  team: UserState[];
  seenUntil: string; // ISO
  names: Record<string, string>;
}

/** Свои статусы (постранично), «кто что ведёт» у коллег и отметка просмотра. */
export async function loadCabinet(meId: string | null): Promise<CabinetData> {
  const fallbackSeen = new Date(Date.now() - 3 * 86400000).toISOString();
  if (isDemo() || !meId) return { mine: [], team: [], seenUntil: fallbackSeen, names: {} };
  const sb = await supabaseServer();
  const cols = "user_id, tender_id, status, saved, note, updated_at";
  const [mine, team, prof] = await Promise.all([
    fetchAll((a, b) => sb.from("tender_state").select(cols).eq("user_id", meId).order("tender_id").range(a, b)),
    fetchAll((a, b) =>
      sb.from("tender_state").select(cols).neq("user_id", meId)
        .in("status", ["working", "submitted", "won"]).order("tender_id").range(a, b)),
    sb.from("profiles").select("id, full_name"),
  ]);
  const seenRow = mine.find((r) => r.tender_id === SEEN_KEY);
  // нет отметки — берём последнее действие пользователя (тот, кто жал «Всё прочитано»)
  const lastAction = mine
    .filter((r) => r.tender_id !== SEEN_KEY && r.updated_at)
    .map((r) => r.updated_at!)
    .sort()
    .at(-1);
  const names: Record<string, string> = {};
  for (const p of prof.data ?? []) names[p.id] = p.full_name ?? "коллега";
  return {
    mine: mine.filter((r) => r.tender_id !== SEEN_KEY).map(toState),
    team: team.map(toState),
    seenUntil: seenRow?.note || lastAction || fallbackSeen,
    names,
  };
}
