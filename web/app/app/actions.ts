"use server";

import { revalidatePath } from "next/cache";
import { isDemo, supabaseServer } from "@/lib/supabase/server";

async function upsertState(tenderId: string, patch: Record<string, unknown>) {
  if (isDemo()) return; // демо: состояние не сохраняется
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return;
  await supabase.from("tender_state").upsert(
    {
      user_id: user.id,
      tender_id: tenderId,
      updated_at: new Date().toISOString(),
      ...patch,
    },
    { onConflict: "user_id,tender_id" },
  );
  revalidatePath("/app");
}

export async function setStatus(tenderId: string, status: string) {
  await upsertState(tenderId, { status });
}

export async function toggleSaved(tenderId: string, saved: boolean) {
  await upsertState(tenderId, { saved });
}

export async function saveNote(tenderId: string, note: string) {
  await upsertState(tenderId, { note });
}
