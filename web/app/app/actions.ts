"use server";

import { revalidatePath } from "next/cache";
import { isDemo, supabaseServer } from "@/lib/supabase/server";

export type ActionResult = { ok: boolean; error?: string };

async function upsertState(
  tenderId: string,
  patch: Record<string, unknown>,
  log: { action: string; value?: string | null; title?: string },
): Promise<ActionResult> {
  if (isDemo()) return { ok: true }; // демо: состояние не сохраняется
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Сессия истекла — войдите заново" };

  const { error } = await supabase.from("tender_state").upsert(
    {
      user_id: user.id,
      tender_id: tenderId,
      updated_at: new Date().toISOString(),
      ...patch,
    },
    { onConflict: "user_id,tender_id" },
  );
  if (error) {
    console.error("tender_state upsert failed:", error.message);
    return { ok: false, error: `Не сохранилось: ${error.message}` };
  }

  // История действий — не блокирует основное сохранение, если таблицы ещё нет
  const { error: logErr } = await supabase.from("activity_log").insert({
    user_id: user.id,
    tender_id: tenderId,
    tender_title: log.title ?? null,
    action: log.action,
    value: log.value ?? null,
  });
  if (logErr) console.warn("activity_log insert failed:", logErr.message);

  revalidatePath("/app");
  return { ok: true };
}

export async function setStatus(tenderId: string, status: string, title?: string) {
  return upsertState(tenderId, { status }, { action: "status", value: status, title });
}

export async function toggleSaved(tenderId: string, saved: boolean, title?: string) {
  return upsertState(tenderId, { saved }, { action: saved ? "saved" : "unsaved", title });
}

export async function saveNote(tenderId: string, note: string, title?: string) {
  return upsertState(tenderId, { note }, { action: "note", value: note, title });
}

/** «Всё прочитано»: пачкой перевести новые тендеры в «Просмотрен». Одна запись в историю. */
export async function markAllViewed(
  tenderIds: string[],
  scope: string,
): Promise<ActionResult & { count?: number }> {
  if (isDemo()) return { ok: true, count: tenderIds.length };
  if (tenderIds.length === 0) return { ok: true, count: 0 };
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Сессия истекла — войдите заново" };

  const now = new Date().toISOString();
  const { error } = await supabase.from("tender_state").upsert(
    tenderIds.map((id) => ({
      user_id: user.id,
      tender_id: id,
      status: "viewed",
      updated_at: now,
    })),
    { onConflict: "user_id,tender_id", ignoreDuplicates: false },
  );
  if (error) return { ok: false, error: `Не сохранилось: ${error.message}` };

  await supabase.from("activity_log").insert({
    user_id: user.id,
    tender_id: "*",
    tender_title: scope,
    action: "mark_all_viewed",
    value: String(tenderIds.length),
  });
  revalidatePath("/app");
  return { ok: true, count: tenderIds.length };
}
