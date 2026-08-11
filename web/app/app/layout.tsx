import Link from "next/link";
import { currentUser, isDemo } from "@/lib/supabase/server";
import { signOut } from "../login/actions";

export const metadata = { title: "Кабинет | TA Tenders" };

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const me = await currentUser();
  return (
    <div className="cab-root">
      <header className="cab-topbar">
        <Link href="/app" className="cab-logo">
          TopAdvisor <span>· Tenders</span>
        </Link>
        <nav className="cab-topnav">
          <Link href="/app">Тендеры</Link>
          <Link href="/app/npa">НПА</Link>
          <Link href="/app/analytics">Аналитика</Link>
        </nav>
        <div className="cab-user">
          {isDemo() && <span className="badge st-expiring">демо-режим</span>}
          <span className="cab-username">{me?.name}</span>
          <form action={signOut}>
            <button className="cab-signout">Выйти</button>
          </form>
        </div>
      </header>
      {children}
    </div>
  );
}
