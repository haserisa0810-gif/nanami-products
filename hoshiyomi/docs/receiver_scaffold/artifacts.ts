// src/types/artifacts.ts
// 生成側（nanami-astro / 引き継ぎ §10）が出力する成果物のスキーマ「契約」。
// アプリはこの形を受け皿として受け取る。生成側はこの契約に合わせて出力すること。

// ---- readings.yaml（§6.2 / §10.1: Flash-Lite 焼き込み鑑定）----
export interface ReadingSection {
  id: string;      // "overview" | "talent" | ...
  title: string;   // "全体像" 等
  body: string;    // 本文（Markdown可）
}

export interface Readings {
  version: string;          // "nanami-readings-v1"
  model: string;            // "gemini-2.5-flash-lite" 等（注釈表示に使用・§6.2必須）
  generated_at?: string;
  profile_id?: string;
  sections: ReadingSection[];
  note?: string;            // モデル注釈文。未指定なら model から自動生成
}

// ---- life_events.yaml（§10.2: 年/人生スケールの主要イベント）----
// TimelineEvent 互換。生成側は Swiss Ephemeris の広域スキャン結果をこの形で出す。
export interface LifeEventRaw {
  id?: string;
  type?: string;            // "aspect" | "return" | "ingress"
  date: string;             // ピーク日 'YYYY-MM-DD'
  endDate?: string;
  title: string;            // "木星 合 土星" 等
  description?: string;     // meaning_hint
  meta?: Record<string, unknown>; // { bodies, aspect, orb }
  granularity?: "year" | "month" | "day";
}

export interface LifeEventsFile {
  version?: string;         // "nanami-life-events-v1"
  profile_id?: string;
  events: LifeEventRaw[];
}

// ---- parseYaml.ts（Phase1）の正規化結果に合わせる最小型 ----
// NOTE: 実際の parseYaml.ts の型に合わせてここを調整すること（フィールド名の単一の真実はパーサ側）。
export interface NormalizedAspect {
  transitBody: string;
  natalBody: string;
  aspect: string;   // "conjunction" | "opposition" | "square" | "trine" | "sextile"
  orb: number;
}

export interface TransitDay {
  date: string;             // 'YYYY-MM-DD'
  natalAspects?: NormalizedAspect[];
  // bodies / moonTimepoints などは parseYaml.ts の型に合わせて拡張
}
