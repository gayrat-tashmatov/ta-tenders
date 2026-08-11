import NpaContent from "@/app/(public)/npa/page";

export const metadata = { title: "НПА | Кабинет TA Tenders" };

export default function CabinetNpaPage() {
  return (
    <main className="container cab-section">
      <NpaContent />
    </main>
  );
}
