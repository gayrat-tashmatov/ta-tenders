export type Category =
  | "international_tender"
  | "uz_tender"
  | "job"
  | "legislation"
  | "news";

export interface FeedItem {
  id: string;
  category: Category;
  source: string;
  origin: string;
  titleRu: string | null;
  title: string;
  summaryRu: string | null;
  buyer: string | null;
  deadline: string | null;
  budget: string | null;
  score: number | null;
  urgency: string | null;
  published: string | null;
  firstSeen: string;
  npaRefs: string[];
  url: string;
}

export interface FullItem extends FeedItem {
  siteBrief: string | null;
  opportunityType: string | null;
  eligibility: string | null;
  docsChecklist: string[];
  recommendation: string | null;
  summary: string | null;
  portalOnly?: boolean;
  lotNumber?: string | null;
}

/** Подпись для кнопки первоисточника: честно о том, куда ведёт ссылка. */
export function sourceLinkLabel(it: {
  portalOnly?: boolean;
  lotNumber?: string | null;
  origin: string;
}): string {
  if (it.portalOnly)
    return it.lotNumber
      ? `Портал · искать лот № ${it.lotNumber}`
      : "Открыть портал ↗";
  if (it.origin === "TenderWeek") return "TenderWeek (нужен вход) ↗";
  return "Первоисточник ↗";
}

export interface NpaMention {
  item_id: string;
  kind: string;
  title: string;
  url: string;
  added: string;
}

export interface NpaEntry {
  key: string;
  itemId: string;
  title: string;
  firstSeen: string;
  mentions: NpaMention[];
}

export interface InsightSection {
  heading: string;
  body: string;
  act_keys?: string[];
}

export interface InsightSource {
  keys: string[];
  title: string;
  url: string;
  itemId: string;
}

export interface Insight {
  id: string;
  kind: string;
  title: string;
  lead: string;
  period: string;
  created: string;
  sections: InsightSection[];
  businessImpact: string[];
  howToPrepare: string[];
  sources: InsightSource[];
}

export interface Meta {
  updatedAt: string;
  counts: { feed: number; items: number; npa: number; insights?: number };
}

export const CATEGORY_LABEL: Record<Category, string> = {
  international_tender: "Международные",
  uz_tender: "Узбекистан",
  job: "Позиции",
  legislation: "НПА",
  news: "Новости",
};

export const CATEGORY_ICON: Record<Category, string> = {
  international_tender: "🌍",
  uz_tender: "🇺🇿",
  job: "🧑‍💼",
  legislation: "⚖️",
  news: "📰",
};

export function npaTypeTitle(key: string): string {
  const t = key.split("-")[0];
  return (
    {
      ZRU: "Закон",
      UP: "Указ Президента",
      PP: "Постановление Президента",
      PKM: "Постановление Кабмина",
      LEX: "Документ lex.uz",
    }[t] ?? "НПА"
  );
}

export function stripRawTitle(title: string): string {
  return title
    .replace(/^\[[^\]]+\]\s*/, "")        // служебный тег источника [WB], [НПА]…
    .replace(/^(#[\S]+\s*)+/, "")          // хештеги lex.uz (#Президент_Фармони …)
    .replace(/[❗❕‼️]/gu, "")
    .trim();
}

export function cleanTitle(it: { titleRu: string | null; title: string }): string {
  if (it.titleRu && it.titleRu.trim().length >= 6) return it.titleRu;
  return stripRawTitle(it.title);
}

export function fmtDate(s: string | null | undefined): string | null {
  if (!s) return null;
  const iso = String(s).match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[3]}.${iso[2]}.${iso[1]}`;
  const ru = String(s).match(/\b(\d{2})[.\/](\d{2})[.\/](\d{4})\b/);
  if (ru) return `${ru[1]}.${ru[2]}.${ru[3]}`;
  return null;
}

export type DlStatus = "expiring" | "active" | "expired" | "none";

export function deadlineStatus(deadline: string | null): {
  status: DlStatus;
  days: number | null;
} {
  const d = daysLeft(deadline);
  if (d === null) return { status: "none", days: null };
  if (d < 0) return { status: "expired", days: d };
  if (d <= 7) return { status: "expiring", days: d };
  return { status: "active", days: d };
}

export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const iso = String(deadline).match(/(\d{4})-(\d{2})-(\d{2})/);
  let d: Date | null = null;
  if (iso) d = new Date(`${iso[1]}-${iso[2]}-${iso[3]}T23:59:59Z`);
  else {
    const ru = String(deadline).match(/\b(\d{2})[.\/](\d{2})[.\/](\d{4})\b/);
    if (ru) d = new Date(`${ru[3]}-${ru[2]}-${ru[1]}T23:59:59Z`);
  }
  if (!d || isNaN(+d)) return null;
  // floor: день дедлайна считается «последним днём» (0), следующий день — уже -1
  return Math.floor((+d - Date.now()) / 86400000);
}
