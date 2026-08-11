"use server";

import { redirect } from "next/navigation";
import { isDemo, supabaseServer } from "@/lib/supabase/server";

export async function signIn(_prev: { error: string } | null, formData: FormData) {
  const rawNext = String(formData.get("next") ?? "/app");
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/app";
  if (isDemo()) redirect(next);
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL)
    return { error: "Кабинет ещё не подключён — добавьте ключи Supabase" };
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const supabase = await supabaseServer();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    const m = error.message.toLowerCase();
    if (m.includes("not confirmed"))
      return {
        error:
          "E-mail не подтверждён. В Supabase (Authentication → Users) удалите " +
          "пользователя и создайте заново с галочкой «Auto Confirm User».",
      };
    if (m.includes("invalid login"))
      return { error: "Неверный e-mail или пароль" };
    return { error: `Ошибка входа: ${error.message}` };
  }
  redirect(next);
}

export async function signOut() {
  if (!isDemo()) {
    const supabase = await supabaseServer();
    await supabase.auth.signOut();
  }
  redirect("/login");
}
