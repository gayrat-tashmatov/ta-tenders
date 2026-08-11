import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Диагностика подключения кабинета: /api/health */
export function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
  let host: string | null = null;
  try {
    host = url ? new URL(url).hostname : null;
  } catch {
    host = "НЕКОРРЕКТНЫЙ URL";
  }
  return NextResponse.json({
    supabaseUrl: host,
    anonKeyType: !anon
      ? null
      : anon.startsWith("sb_publishable_")
        ? "publishable"
        : anon.startsWith("sb_secret_")
          ? "ОШИБКА: вставлен СЕКРЕТНЫЙ ключ вместо публичного"
          : anon.startsWith("eyJ")
            ? "legacy (anon или service?)"
            : "неизвестный формат",
    env: process.env.VERCEL_ENV ?? "local",
  });
}
