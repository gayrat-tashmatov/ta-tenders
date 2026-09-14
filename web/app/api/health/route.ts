import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

/** Время последнего экспорта пайплайна (web/data/meta.json) — свежесть данных на сайте. */
function dataMeta(): { updatedAt: string | null; counts: Record<string, number> | null } {
  try {
    const raw = fs.readFileSync(path.join(process.cwd(), "data", "meta.json"), "utf-8");
    const m = JSON.parse(raw) as { updatedAt?: string; counts?: Record<string, number> };
    return { updatedAt: m.updatedAt ?? null, counts: m.counts ?? null };
  } catch {
    return { updatedAt: null, counts: null };
  }
}

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
    supabaseUrlRaw: url || null,           // URL не секрет; ключи здесь не показываются
    urlLooksClean: /^https:\/\/[a-z0-9]+\.supabase\.co$/.test(url),
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
    commit: process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) ?? null,   // какой коммит собран
    data: dataMeta(),                                                 // когда пайплайн обновил данные
  });
}
