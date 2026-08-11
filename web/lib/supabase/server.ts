import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** Demo-режим — только локальная разработка без ключей.
    На проде без ключей кабинет закрыт (middleware уводит на /login). */
export const isDemo = () =>
  (!SUPABASE_URL || !SUPABASE_ANON) && process.env.NODE_ENV !== "production";

export async function supabaseServer() {
  const cookieStore = await cookies();
  return createServerClient(SUPABASE_URL, SUPABASE_ANON, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (all) => {
        try {
          for (const { name, value, options } of all)
            cookieStore.set(name, value, options);
        } catch {
          // вызов из Server Component без мутации — обновит middleware
        }
      },
    },
  });
}

export async function currentUser() {
  if (isDemo())
    return { id: "demo", email: "demo@topadvisor.biz", name: "Демо-режим" };
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;
  return {
    id: user.id,
    email: user.email ?? "",
    name:
      (user.user_metadata?.full_name as string) ??
      user.email?.split("@")[0] ??
      "",
  };
}
