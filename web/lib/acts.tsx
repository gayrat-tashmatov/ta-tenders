import Link from "next/link";
import type { ReactNode } from "react";
import type { NpaEntry } from "./types";

/** npa_key ('PP-289', 'LEX-…') → id карточки акта (/t/[id]) */
export type ActIndex = Record<string, string>;

export function buildActIndex(npa: NpaEntry[]): ActIndex {
  const idx: ActIndex = {};
  for (const n of npa) idx[n.key] = n.itemId;
  return idx;
}

/* Реквизиты в тексте пишутся по-разному (ЗРУ-1126, УП №60, PP-289) —
   нормализуем к ключам реестра, как в pipeline/dedupe.py. */
const TYPE_MAP: Record<string, string> = {
  "зру": "ZRU", "zru": "ZRU", "ўрқ": "ZRU", "orq": "ZRU",
  "уп": "UP", "пф": "UP", "up": "UP", "pf": "UP",
  "пп": "PP", "пқ": "PP", "pp": "PP", "pq": "PP",
  "пкм": "PKM", "вмқ": "PKM", "pkm": "PKM", "vmq": "PKM",
};

const ACT_RE =
  /(?<![A-Za-zА-Яа-яЁёҚқЎў0-9])(ЗРУ|ЎРҚ|ORQ|ZRU|УП|ПФ|UP|PF|ПП|ПҚ|PP|PQ|ПКМ|ВМҚ|PKM|VMQ)\s*[-–—]?\s*№?\s*(\d{1,5})(?!\d)/giu;

export function normalizeActKey(typ: string, num: string): string | null {
  const t = TYPE_MAP[typ.toLowerCase()];
  return t ? `${t}-${parseInt(num, 10)}` : null;
}

/**
 * Превращает упоминания актов в тексте в ссылки на их карточки.
 * selfId — id текущей страницы (сам на себя не ссылаемся).
 */
export function linkifyActs(
  text: string | null | undefined,
  idx: ActIndex,
  selfId?: string,
): ReactNode {
  if (!text) return null;
  const nodes: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(ACT_RE)) {
    const key = normalizeActKey(m[1], m[2]);
    const target = key ? idx[key] : undefined;
    if (!target || target === selfId) continue;
    if (m.index! > last) nodes.push(text.slice(last, m.index));
    nodes.push(
      <Link key={`${key}-${m.index}`} href={`/t/${target}`}>
        {m[0]}
      </Link>,
    );
    last = m.index! + m[0].length;
  }
  if (nodes.length === 0) return text;
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
