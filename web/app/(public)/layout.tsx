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
          <Link href="/" style={{ textDecoration: "none" }}>
            <span className="wordmark">
              TopAdvisor <span>· Tenders</span>
            </span>
          </Link>
          <nav className="site-nav">
            <Link href="/">Лента</Link>
            <Link href="/npa">НПА</Link>
            <Link href="/analytics">Аналитика</Link>
            <Link href="/app" className="nav-cta">
              Кабинет →
            </Link>
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
