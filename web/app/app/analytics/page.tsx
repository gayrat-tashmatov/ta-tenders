import AnalyticsContent from "@/app/(public)/analytics/page";

export const metadata = { title: "Аналитика | Кабинет TA Tenders" };

export default function CabinetAnalyticsPage() {
  return (
    <main className="container cab-section">
      <AnalyticsContent />
    </main>
  );
}
