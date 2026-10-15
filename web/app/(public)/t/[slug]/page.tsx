import { redirect } from "next/navigation";
// Ссылки из Telegram (SITE_BASE_URL/t/<slug>) ведут в кабинет
export default async function LegacyItem({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  redirect(`/app/item/${slug}`);
}
