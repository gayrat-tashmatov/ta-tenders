import { getItems } from "@/lib/data";
import { currentUser, isDemo } from "@/lib/supabase/server";
import { loadCabinet } from "@/lib/cabinet";
import { isTenderCategory, type FullItem } from "@/lib/types";
import { Workspace, type CabTender } from "./workspace";

const pick = (it: FullItem): CabTender => ({
  id: it.id, category: it.category, source: it.source, origin: it.origin, title: it.title,
  titleRu: it.titleRu, url: it.url, buyer: it.buyer, budget: it.budget, deadline: it.deadline,
  published: it.published, score: it.score, summaryRu: it.summaryRu, siteBrief: it.siteBrief,
  recommendation: it.recommendation, eligibility: it.eligibility, docsChecklist: it.docsChecklist ?? [],
  legalAspects: it.legalAspects ?? [], actionItems: it.actionItems ?? [], firstSeen: it.firstSeen,
  portalOnly: it.portalOnly, lotNumber: it.lotNumber, repeatOf: it.repeatOf ?? null,
  direction: it.direction ?? null, whyUs: it.whyUs ?? null, donor: it.donor ?? null,
  geo: it.geo ?? null, track: it.track,
});

export async function WorkspacePage({
  track, title, subtitle, searchParams,
}: {
  track: "company" | "expert";
  title: string;
  subtitle: string;
  searchParams: Promise<{ id?: string; f?: string }>;
}) {
  const sp = await searchParams;
  const me = await currentUser();
  const cab = await loadCabinet(me?.id ?? null);
  const tenders = getItems()
    .filter((it) => isTenderCategory(it.category) && (it.track === track || it.track === "both"))
    .map(pick);
  return (
    <Workspace
      title={title}
      subtitle={subtitle}
      tenders={tenders}
      mine={cab.mine.map((s) => ({ tenderId: s.tenderId, status: s.status, saved: s.saved, note: s.note }))}
      team={cab.team.map((s) => ({ tenderId: s.tenderId, status: s.status, userId: s.userId }))}
      names={cab.names}
      seenUntil={cab.seenUntil}
      initialId={sp.id}
      initialFolder={sp.f}
      demo={isDemo()}
    />
  );
}
