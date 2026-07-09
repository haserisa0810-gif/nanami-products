/* タイムライン拡張（引き継ぎ§9）— 共通イベント型とアダプタ。
   すべてのビューは TimelineEvent[] だけを消費し、ソースを区別しない。
   データ供給の無い期間の占術イベントを推測・生成してはならない（§9.0）。 */

import type { TransitDay, PeriodSummary } from "./parseYaml";
import { PLANET, ASPECT } from "../theme";

export type TimelineScale = "day" | "month" | "year" | "life";

export type TimelineSource =
  | "transit" // 既存 daily / natal_aspects 由来
  | "transit_major" // 外惑星の主要イベント（将来のデータ供給）
  | "user"; // ユーザー入力
// 将来: "shichusuimei" | "acg" | "solar_return" | "progression" | "note" | "ai_archive"

export type TimelineEvent = {
  id: string;
  type: string; // "aspect" | "ingress" | "milestone" | "custom" | "key_date" など
  date: string; // 'YYYY-MM-DD'（時刻は任意で 'YYYY-MM-DDTHH:mm'）
  endDate?: string; // 期間イベント用
  title: string;
  description?: string;
  source: TimelineSource;
  meta?: Record<string, unknown>;
};

const bodyJa = (name: string) => PLANET[name]?.ja ?? name;

/* daily の natal_aspects から orb 閾値で「重要」を抽出する */
export function fromTransitDaily(
  daily: TransitDay[],
  orbMax = 0.5,
): TimelineEvent[] {
  const out: TimelineEvent[] = [];
  for (const d of daily) {
    for (const a of d.natal_aspects) {
      if (a.orb > orbMax) continue;
      out.push({
        id: `transit:${d.date}:${a.transit_body}:${a.aspect}:${a.natal_body}`,
        type: "aspect",
        date: d.date,
        title: `${bodyJa(a.transit_body)} ${ASPECT[a.aspect].ja} ${bodyJa(a.natal_body)}`,
        description: `T${bodyJa(a.transit_body)} → N${bodyJa(a.natal_body)}（orb ${a.orb.toFixed(2)}）`,
        source: "transit",
        meta: {
          orb: a.orb,
          aspect: a.aspect,
          transit_body: a.transit_body,
          natal_body: a.natal_body,
        },
      });
    }
  }
  return out;
}

/* 期間サマリーの key_dates（YAML内の計算済みイベント）をイベント化する */
export function fromKeyDates(summary: PeriodSummary): TimelineEvent[] {
  return summary.key_dates.map((k) => ({
    id: `keydate:${k.date}`,
    type: "key_date",
    date: k.date,
    title: `◆ ${k.theme}`,
    source: "transit",
    meta: { theme: k.theme },
  }));
}

export type UserEventInput = {
  date: string;
  title: string;
  description?: string;
  endDate?: string;
};

export function fromUserEvent(input: UserEventInput, id?: string): TimelineEvent {
  return {
    id: id ?? `user:${crypto.randomUUID()}`,
    type: "custom",
    date: input.date,
    endDate: input.endDate || undefined,
    title: input.title,
    description: input.description || undefined,
    source: "user",
  };
}

/* 日付昇順マージ（同日なら user を先に） */
export function mergeEvents(...lists: TimelineEvent[][]): TimelineEvent[] {
  return lists
    .flat()
    .sort(
      (a, b) =>
        a.date.localeCompare(b.date) ||
        (a.source === "user" ? -1 : 0) - (b.source === "user" ? -1 : 0),
    );
}

/* Googleカレンダー追加リンク（§9.5、API不使用・終日は終端排他） */
export function gcalUrl(ev: TimelineEvent): string {
  const compact = (s: string) => s.replaceAll("-", "");
  const addDays = (s: string, n: number) => {
    const [y, m, d] = s.slice(0, 10).split("-").map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d + n));
    return dt.toISOString().slice(0, 10).replaceAll("-", "");
  };
  const start = compact(ev.date.slice(0, 10));
  const end = addDays(ev.endDate ?? ev.date, 1); // Googleの終日イベントは終了日が排他的
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: ev.title,
    dates: `${start}/${end}`,
  });
  if (ev.description) params.set("details", ev.description);
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export const yearOf = (date: string): number => Number(date.slice(0, 4));
export const monthOf = (date: string): number => Number(date.slice(5, 7));
