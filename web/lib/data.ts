import "server-only";
import fs from "node:fs";
import path from "node:path";
import type { FeedItem, FullItem, Insight, Meta, NpaEntry } from "./types";

export * from "./types";

function read<T>(name: string, fallback: T): T {
  try {
    const p = path.join(process.cwd(), "data", name);
    return JSON.parse(fs.readFileSync(p, "utf-8")) as T;
  } catch {
    return fallback;
  }
}

export const getFeed = () => read<FeedItem[]>("feed.json", []);
export const getItems = () => read<FullItem[]>("items.json", []);
export const getNpa = () => read<NpaEntry[]>("npa.json", []);
export const getMeta = () =>
  read<Meta>("meta.json", {
    updatedAt: "",
    counts: { feed: 0, items: 0, npa: 0 },
  });

export const getItem = (id: string) =>
  getItems().find((it) => it.id === id) ?? null;

export const getInsights = () => read<Insight[]>("insights.json", []);
export const getInsight = (id: string) =>
  getInsights().find((i) => i.id === id) ?? null;
