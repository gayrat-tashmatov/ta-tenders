import { getItems } from "@/lib/data";
import { currentUser, isDemo, supabaseServer } from "@/lib/supabase/server";
import { Workspace, type CabTender, type CabState, type CabProfile } from "./workspace";

export const dynamic = "force-dynamic";

async function loadData(): Promise<{
  tenders: CabTender[];
  states: CabState[];
  profiles: CabProfile[];
}> {
  if (isDemo()) {
    // Демо: те же данные, что на публичном сайте; личное состояние не сохраняется
    const tenders = getItems().map((it) => ({
      id: it.id,
      category: it.category,
      source: it.source,
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
      firstSeen: it.firstSeen,
    }));
    return { tenders, states: [], profiles: [{ id: "demo", fullName: "Демо" }] };
  }

  const supabase = await supabaseServer();
  const [t, s, p] = await Promise.all([
    supabase
      .from("tenders")
      .select(
        "id, category, source, title, title_ru, url, buyer, budget, deadline, score, summary_ru, site_brief, recommendation, eligibility, docs_checklist, first_seen",
      )
      .order("first_seen", { ascending: false })
      .limit(600),
    supabase.from("tender_state").select("*"),
    supabase.from("profiles").select("id, full_name"),
  ]);

  const tenders: CabTender[] = (t.data ?? []).map((r) => ({
    id: r.id,
    category: r.category,
    source: r.source,
    title: r.title ?? "",
    titleRu: r.title_ru,
    url: r.url ?? "",
    buyer: r.buyer,
    budget: r.budget,
    deadline: r.deadline,
    score: r.score,
    summaryRu: r.summary_ru,
    siteBrief: r.site_brief,
    recommendation: r.recommendation,
    eligibility: r.eligibility,
    docsChecklist: (r.docs_checklist as string[]) ?? [],
    firstSeen: r.first_seen ?? "",
  }));
  const states: CabState[] = (s.data ?? []).map((r) => ({
    userId: r.user_id,
    tenderId: r.tender_id,
    status: r.status,
    saved: r.saved,
    note: r.note,
  }));
  const profiles: CabProfile[] = (p.data ?? []).map((r) => ({
    id: r.id,
    fullName: r.full_name ?? "",
  }));
  return { tenders, states, profiles };
}

export default async function AppPage() {
  const me = await currentUser();
  const { tenders, states, profiles } = await loadData();
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
