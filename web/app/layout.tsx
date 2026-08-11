import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import { getMeta, fmtDate } from "@/lib/data";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "TA Tenders — тендеры, донорские проекты и НПА Узбекистана",
  description:
    "Агрегатор возможностей для консалтинга: тендеры МФО (Всемирный банк, ЕБРР, АБР, ООН), " +
    "госзакупки Узбекистана, позиции экспертов и мониторинг законодательства — с разбором по каждой позиции.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const meta = getMeta();
  const updated = fmtDate(meta.updatedAt);
  return (
    <html lang="ru" className={inter.variable}>
      <body>
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
      </body>
    </html>
  );
}
