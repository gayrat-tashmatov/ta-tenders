import type { Metadata } from "next";
import { IBM_Plex_Mono, Manrope } from "next/font/google";
import "./globals.css";

// Дизайн «Мята»: Manrope — интерфейс, IBM Plex Mono — даты, сроки и числа
const ui = Manrope({ subsets: ["latin", "cyrillic"], weight: ["400", "500", "600", "700", "800"], variable: "--font-ui" });
const mono = IBM_Plex_Mono({ subsets: ["latin", "cyrillic"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Tenders",
  description: "Тендеры, позиции для экспертов и законодательство Узбекистана и Центральной Азии — с разбором по каждой позиции.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${ui.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
