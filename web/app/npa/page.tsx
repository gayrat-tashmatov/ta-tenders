import Link from "next/link";
import { fmtDate, getItems, getNpa, npaTypeTitle, stripRawTitle } from "@/lib/data";
import type { NpaEntry } from "@/lib/types";

export const metadata = {
  title: "НПА — реестр актов | TA Tenders",
  description:
    "Новые нормативно-правовые акты Узбекистана: один акт — одна карточка, " +
    "новости и разборы прикрепляются к ней без дублей.",
};

interface ActGroup {
  itemId: string;
  keys: string[];
  title: string;
  firstSeen: string;
  mentions: NpaEntry["mentions"];
}

export default function NpaPage() {
  const npa = getNpa();
  const items = new Map(getItems().map((it) => [it.id, it]));

  // Один акт может иметь несколько ключей (реквизит + LEX-id) — группируем по карточке.
  const groups = new Map<string, ActGroup>();
  for (const n of npa) {
    const g = groups.get(n.itemId);
    if (g) {
      g.keys.push(n.key);
      const seen = new Set(g.mentions.map((m) => m.item_id));
      for (const m of n.mentions) if (!seen.has(m.item_id)) g.mentions.push(m);
      if (n.firstSeen < g.firstSeen) g.firstSeen = n.firstSeen;
    } else {
      groups.set(n.itemId, {
        itemId: n.itemId,
        keys: [n.key],
        title: n.title,
        firstSeen: n.firstSeen,
        mentions: [...n.mentions],
      });
    }
  }
  // Реквизит акта информативнее, чем LEX-id — показываем его первым.
  const acts = [...groups.values()].sort((a, b) =>
    b.firstSeen.localeCompare(a.firstSeen),
  );
  for (const a of acts)
    a.keys.sort((x, y) => Number(x.startsWith("LEX")) - Number(y.startsWith("LEX")));

  return (
    <>
      <h1 className="page-title">Законодательство: реестр актов</h1>
      <p className="page-sub">
        Один акт — одна карточка. Публикации СМИ и разборы об уже известном акте
        прикрепляются сюда как упоминания, а не выходят повторно.
      </p>

      {acts.length === 0 && <div className="empty">Реестр пока пуст.</div>}

      {acts.map((n) => {
        const item = items.get(n.itemId);
        const date = fmtDate(n.firstSeen);
        const mainKey = n.keys[0];
        const title = item
          ? (item.titleRu && item.titleRu.trim().length >= 6
              ? item.titleRu
              : stripRawTitle(item.title))
          : stripRawTitle(n.title);
        return (
          <div className="npa-item" key={n.itemId}>
            <div className="card-meta">
              <span className="badge">⚖️ {npaTypeTitle(mainKey)}</span>
              {n.keys
                .filter((k) => !k.startsWith("LEX"))
                .map((k) => (
                  <span className="npa-key" key={k}>
                    {k}
                  </span>
                ))}
              {date && <span>от {date}</span>}
              {item && (
                <a href={item.url} target="_blank" rel="noopener noreferrer">
                  lex.uz ↗
                </a>
              )}
            </div>
            <div>
              {item ? <Link href={`/t/${item.id}`}>{title}</Link> : title}
            </div>
            {n.mentions.length > 0 && (
              <ul className="npa-mentions">
                {n.mentions.map((m) => (
                  <li key={m.item_id}>
                    <a href={m.url} target="_blank" rel="noopener noreferrer">
                      {stripRawTitle(m.title)}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </>
  );
}
