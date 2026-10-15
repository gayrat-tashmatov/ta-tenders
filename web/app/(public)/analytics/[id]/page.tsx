import { redirect } from "next/navigation";
export default async function PublicInsight({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/app/analytics/${id}`);
}
