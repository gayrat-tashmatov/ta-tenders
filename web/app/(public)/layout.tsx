import Link from "next/link";
import { getMeta, fmtDate } from "@/lib/data";

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const meta = getMeta();
  const updated = fmtDate(meta.updatedAt);
  return (
    <>
      <header className="site-header">
        <div className="container">
          <Link href="/app" style={{ textDecoration: "none" }}>
            <span className="wordmark">
              TopAdvisor <span>· Tenders</span>
            </span>
          </Link>
          <nav className="site-nav">
            <Link href="/app" className="nav-cta">
              ← В кабинет
            </Link>
            <Link href="/app/npa">НПА</Link>
            <Link href="/app/analytics">Аналитика</Link>
          </nav>
        </div>
      </header>
      <main className="container">{children}</main>
      <footer className="site-footer">
        <div className="container">
          TopAdvisor · Tenders — мониторинг тендеров, донорских проектов и
          законодательства Узбекистана.
          {updated ? ` Обновлено: ${updated}.` : ""} Данные собираются из
          открытых официальных источников; проверяйте условия в первоисточнике.
        </div>
      </footer>
    </>
  );
}
