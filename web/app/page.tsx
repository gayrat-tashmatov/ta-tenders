import { getFeed, getMeta, getNpa } from "@/lib/data";
import { buildActIndex } from "@/lib/acts";
import { FeedClient } from "./feed-client";

export default function Home() {
  const feed = getFeed();
  const meta = getMeta();
  const actIdx = buildActIndex(getNpa());
  return (
    <>
      <h1 className="page-title">Тендеры и возможности</h1>
      <p className="page-sub">
        Международные тендеры МФО, госзакупки Узбекистана, позиции экспертов и
        новые НПА — в одной ленте, с разбором по каждой позиции. Регуляторные
        дайджесты — в разделе <a href="/analytics">Аналитика</a>.
      </p>
      <FeedClient items={feed} actIdx={actIdx} />
    </>
  );
}
