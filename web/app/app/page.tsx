import { getItems } from "@/lib/data";
import { currentUser, isDemo, supabaseServer } from "@/lib/supabase/server";
import { Workspace, type CabTender, type CabState, type CabProfile } from "./workspace";

export const dynamic = "force-dynamic";

/** Контент кабинета = тот же, что на сайте (web/data, обновляется каждым прогоном).
    Supabase хранит только пользователей и личные статусы/заметки. */
function loadTenders(): CabTender[] {
  return getItems().map((it) => ({
    id: it.id,
    category: it.category,
    source: it.source,
    origin: it.origin,
    portalOnly: it.portalOnly,
    lotNumber: it.lotNumber,
    title: it.title,
    titleRu: it.titleRu,
    url: it.url,
    buyer: it.buyer,
    budget: it.budget,
    deadline: it.deadline,
    score: it.score,
    summaryRu: it.summaryRu,
    siteBrief: it.siteBrief,
    recommendation: it.recommendation,
    eligibility: it.eligibility,
    docsChecklist: it.docsChecklist,
    legalAspects: it.legalAspects,
    actionItems: it.actionItems,
    firstSeen: it.firstSeen,
  }));
}

async function loadUserData(): Promise<{ states: CabState[]; profiles: CabProfile[] }> {
  if (isDemo()) return { states: [], profiles: [{ id: "demo", fullName: "Демо" }] };
  const supabase = await supabaseServer();
  const [s, p] = await Promise.all([
    supabase.from("tender_state").select("*"),
    supabase.from("profiles").select("id, full_name"),
  ]);
  return {
    states: (s.data ?? []).map((r) => ({
      userId: r.user_id,
      tenderId: r.tender_id,
      status: r.status,
      saved: r.saved,
      note: r.note,
    })),
    profiles: (p.data ?? []).map((r) => ({
      id: r.id,
      fullName: r.full_name ?? "",
    })),
  };
}

export default async function AppPage() {
  const me = await currentUser();
  const tenders = loadTenders();
  const { states, profiles } = await loadUserData();
  return (
    <Workspace
      tenders={tenders}
      states={states}
      profiles={profiles}
      meId={me?.id ?? "demo"}
      demo={isDemo()}
    />
  );
}
