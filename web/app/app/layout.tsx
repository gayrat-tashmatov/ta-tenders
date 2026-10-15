import Link from "next/link";
import { currentUser, isDemo } from "@/lib/supabase/server";
import { getMeta } from "@/lib/data";
import { CabNav } from "@/components/cab-nav";
import { signOut } from "../login/actions";

export const metadata = { title: "TA Tenders — кабинет" };

function freshness(iso: string): string {
  if (!iso) return "нет данных";
  const d = new Date(iso);
  const t = d.toLocaleString("ru-RU", {
    timeZone: "Asia/Tashkent", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
  return `обновлено ${t}`;
}

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const me = await currentUser();
  const meta = getMeta();
  return (
    <div className="cab">
      <header className="cab-top">
        <div className="cab-top-in">
          <Link href="/app" className="cab-brand">
            Tenders
          </Link>
          <CabNav />
          <div className="cab-me">
            <span className="cab-fresh" title="Когда пайплайн последний раз обновил данные">
              {freshness(meta.updatedAt)}
            </span>
            {isDemo() && <span className="pill pill-warn">демо</span>}
            <details className="cab-menu">
              <summary>{me?.name ?? "Профиль"}</summary>
              <div className="cab-menu-pop">
                <Link href="/app/health">Источники данных</Link>
                <Link href="/app/my#history">История команды</Link>
                <form action={signOut}>
                  <button>Выйти</button>
                </form>
              </div>
            </details>
          </div>
        </div>
      </header>
      <main className="cab-main">{children}</main>
    </div>
  );
}
