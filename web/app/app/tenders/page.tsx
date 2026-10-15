import { WorkspacePage } from "../ws-page";

export const dynamic = "force-dynamic";
export const metadata = { title: "Тендеры для компаний — TA Tenders" };

export default function TendersPage({ searchParams }: { searchParams: Promise<{ id?: string; f?: string }> }) {
  return (
    <WorkspacePage
      track="company"
      title="Тендеры для компаний"
      subtitle="Отбор фирм, госзакупки услуг, донорские проекты."
      searchParams={searchParams}
    />
  );
}
