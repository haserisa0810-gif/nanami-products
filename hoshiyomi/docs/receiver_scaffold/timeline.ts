// src/lib/timeline.ts
// タイムライン共通イベントモデルとアダプタ（引き継ぎ §9.1 / §9.4 / §10.2）。
// すべてのビュー（日/月/年/人生）はこの TimelineEvent[] を消費する。ソース非依存。

import type { TransitDay, LifeEventRaw } from "../types/artifacts";

export type TimelineScale = "day" | "month" | "year" | "life";

export type TimelineSource =
  | "transit"        // 38日トランジット（natal_aspects 由来）
  | "transit_major"  // life_events.yaml（外惑星の主要トランジット・リターン・イングレス）
  | "user"           // ユーザー入力イベント
  | "diary";         // 日次の一言メモ
// 将来: "shichusuimei" | "acg" | "solar_return" | "progression" | "note" | "ai_archive"

export interface TimelineEvent {
  id: string;
  type: string;            // "aspect" | "return" | "ingress" | "milestone" | "custom" | "diary"
  date: string;            // 'YYYY-MM-DD'（時刻付きは 'YYYY-MM-DDTHH:mm'）
  endDate?: string;
  title: string;
  description?: string;
  source: TimelineSource;
  meta?: Record<string, unknown>;
}

export const isoDate = (s: string) => s.slice(0, 10);
export const yearOf = (s: string) => s.slice(0, 4);
export const monthOf = (s: string) => s.slice(0, 7);

const ASPECT_JA: Record<string, string> = {
  conjunction: "合",
  opposition: "オポ",
  square: "スクエア",
  trine: "トライン",
  sextile: "セクスタイル",
};

// ---- アダプタ: 各ソース → TimelineEvent[] ----

// 38日 daily[] → タイトな natal_aspects をイベント化（source: "transit"）
export function fromTransitDaily(
  days: TransitDay[],
  opts: { orbMax?: number } = {}
): TimelineEvent[] {
  const orbMax = opts.orbMax ?? 0.8;
  const out: TimelineEvent[] = [];
  for (const d of days) {
    for (const a of d.natalAspects ?? []) {
      if (a.orb > orbMax) continue;
      out.push({
        id: `transit:${d.date}:${a.transitBody}-${a.aspect}-${a.natalBody}`,
        type: "aspect",
        date: d.date,
        title: `T${a.transitBody} ${ASPECT_JA[a.aspect] ?? a.aspect} N${a.natalBody}`,
        description: `orb ${a.orb.toFixed(2)}`,
        source: "transit",
        meta: { transitBody: a.transitBody, natalBody: a.natalBody, aspect: a.aspect, orb: a.orb },
      });
    }
  }
  return out;
}

// life_events.yaml（TimelineEvent 互換）→ 正規化・検証（source: "transit_major"）
export function fromLifeEvents(raw: LifeEventRaw[] | undefined | null): TimelineEvent[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((e) => e && e.date && e.title)
    .map((e, i) => ({
      id: e.id ?? `major:${e.date}:${i}`,
      type: e.type ?? "aspect",
      date: e.date,
      endDate: e.endDate,
      title: e.title,
      description: e.description,
      source: "transit_major" as const,
      meta: e.meta ?? {},
    }));
}

// ---- マージ / 並べ替え / グルーピング（§9.4）----

export function mergeEvents(...lists: TimelineEvent[][]): TimelineEvent[] {
  const map = new Map<string, TimelineEvent>();
  for (const list of lists) for (const e of list) map.set(e.id, e); // 同一id は後勝ち
  return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function groupByYear(events: TimelineEvent[]): Record<string, TimelineEvent[]> {
  const g: Record<string, TimelineEvent[]> = {};
  for (const e of events) (g[yearOf(e.date)] ??= []).push(e);
  return g;
}

export function groupByMonth(events: TimelineEvent[]): Record<string, TimelineEvent[]> {
  const g: Record<string, TimelineEvent[]> = {};
  for (const e of events) (g[monthOf(e.date)] ??= []).push(e);
  return g;
}

// スケール別に「表示すべき」イベントへ絞る（§9.2）。
// 日/月は既存カレンダー側が扱うのでそのまま返す。年/人生はノイズを間引く。
export function selectForScale(events: TimelineEvent[], scale: TimelineScale): TimelineEvent[] {
  if (scale === "day" || scale === "month") return events;
  return events.filter((e) => {
    if (e.source === "transit_major" || e.source === "user" || e.source === "diary") return true;
    const orb = (e.meta?.orb as number) ?? 1;
    return orb <= 0.5; // 38日トランジットは特にタイトな日だけ
  });
}

// 現在位置（today 以降で最初、なければ today 以前で最後）。「現在」バッジ用。
export function currentIndex(events: TimelineEvent[], todayISO: string): number {
  const i = events.findIndex((e) => isoDate(e.date) >= todayISO);
  return i === -1 ? events.length - 1 : i;
}
