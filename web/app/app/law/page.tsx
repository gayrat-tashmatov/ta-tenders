import { getItems } from "@/lib/data";
import { currentUser } from "@/lib/supabase/server";
import { loadCabinet } from "@/lib/cabinet";
import { LawList, type LawRow } from "./law-list";

export const dynamic = "force-dynamic";
export const metadata = { title: "Законодательство — TA Tenders" };

export default async function LawPage() {
  const me = await currentUser();
  const cab = await loadCabinet(me?.id ?? null);
  const rows: LawRow[] = getItems()
    .filter((it) => it.category === "legislation")
    .map((it) => ({
      id: it.id, title: it.title, titleRu: it.titleRu, firstSeen: it.firstSeen, published: it.published,
      url: it.url, act: it.act ?? null,
    }));
  return <LawList rows={rows} seenUntil={cab.seenUntil} />;
}
