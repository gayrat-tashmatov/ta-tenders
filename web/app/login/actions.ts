"use server";

import { redirect } from "next/navigation";
import { isDemo, supabaseServer } from "@/lib/supabase/server";

export async function signIn(_prev: { error: string } | null, formData: FormData) {
  if (isDemo()) redirect("/app");
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL)
    return { error: "Кабинет ещё не подключён — добавьте ключи Supabase" };
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const supabase = await supabaseServer();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { error: "Неверный e-mail или пароль" };
  redirect("/app");
}

export async function signOut() {
  if (!isDemo()) {
    const supabase = await supabaseServer();
    await supabase.auth.signOut();
  }
  redirect("/login");
}
