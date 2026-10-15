import { WorkspacePage } from "../ws-page";

export const dynamic = "force-dynamic";
export const metadata = { title: "Для эксперта — Tenders" };

export default function ExpertsPage({ searchParams }: { searchParams: Promise<{ id?: string; f?: string }> }) {
  return (
    <WorkspacePage
      track="expert"
      title="Для эксперта"
      subtitle="Индивидуальные консультанты, key experts и позиции в группах реализации проектов."
      searchParams={searchParams}
    />
  );
}
