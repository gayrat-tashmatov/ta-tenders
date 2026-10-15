// Публичной части больше нет: все старые адреса перенаправляются в кабинет.
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
