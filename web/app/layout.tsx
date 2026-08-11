import type { Metadata } from "next";
import { Inter } from "next/font/google";
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
  return (
    <html lang="ru" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
