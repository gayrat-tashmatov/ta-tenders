"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS: { href: string; label: string; exact?: boolean }[] = [
  { href: "/app", label: "Сегодня", exact: true },
  { href: "/app/tenders", label: "Тендеры" },
  { href: "/app/experts", label: "Для эксперта" },
  { href: "/app/law", label: "Законодательство" },
  { href: "/app/analytics", label: "Аналитика" },
  { href: "/app/my", label: "Мои" },
];

export function CabNav() {
  const path = usePathname() ?? "";
  return (
    <nav className="cab-nav" aria-label="Разделы кабинета">
      {LINKS.map((l) => {
        const active = l.exact ? path === l.href : path.startsWith(l.href);
        return (
          <Link key={l.href} href={l.href} className={active ? "active" : undefined}>
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
