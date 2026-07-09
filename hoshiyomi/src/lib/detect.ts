/* 読み込みUIに渡されたテキストの種類を自動判別する（§10.3 のZIP同梱物を一括で受ける）。
   チャートYAML / life_events.yaml / readings（焼き込み鑑定 Markdown） / horoscope.svg */

import yaml from "js-yaml";
import { SUPPORTED_VERSION, YamlParseError } from "./parseYaml";
import type { TimelineEvent, TimelineSource } from "./timeline";

export type DetectedPayload =
  | { kind: "chart" }
  | { kind: "life_events"; events: TimelineEvent[] }
  | { kind: "readings"; text: string }
  | { kind: "svg"; svg: string };

const DATE_RE = /^\d{4}-\d{2}-\d{2}/;

const looksMarkdown = (text: string) => /^#{1,3}\s|\n#{1,3}\s/.test(text);

/* eslint-disable @typescript-eslint/no-explicit-any */
function normalizeLifeEvents(arr: any[]): TimelineEvent[] {
  return arr.map((e, i) => {
    const date = String(e.date ?? "").slice(0, 10);
    if (!DATE_RE.test(date) || !e.title) {
      throw new YamlParseError(
        `life_events の ${i + 1} 件目に date（YYYY-MM-DD）または title がありません。`,
      );
    }
    return {
      id: String(e.id ?? `life:${date}:${i}`),
      type: String(e.type ?? "aspect"),
      date,
      endDate: e.endDate ? String(e.endDate) : e.end_date ? String(e.end_date) : undefined,
      title: String(e.title),
      description: e.description ? String(e.description) : undefined,
      source: (e.source as TimelineSource) ?? "transit_major",
      meta: e.meta,
    };
  });
}

export function detectPayload(text: string): DetectedPayload {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    throw new YamlParseError("入力が空です。");
  }
  if (trimmed.startsWith("<svg") || (trimmed.startsWith("<?xml") && trimmed.includes("<svg"))) {
    return { kind: "svg", svg: trimmed };
  }

  let doc: any;
  try {
    doc = yaml.load(text);
  } catch (e) {
    if (looksMarkdown(text)) return { kind: "readings", text: trimmed };
    throw new YamlParseError(
      `YAMLとして読み取れませんでした: ${e instanceof Error ? e.message : String(e)}`,
    );
  }

  if (doc != null && typeof doc === "object" && !Array.isArray(doc)) {
    if ("version" in doc || "systems" in doc) return { kind: "chart" }; // バージョン検証は parseYamlText 側
    if (Array.isArray(doc.life_events)) {
      return { kind: "life_events", events: normalizeLifeEvents(doc.life_events) };
    }
    if (Array.isArray(doc.events)) {
      return { kind: "life_events", events: normalizeLifeEvents(doc.events) };
    }
    // readings.yaml が {readings: "...markdown..."} 形式の場合
    for (const key of ["readings", "reading", "markdown", "text"]) {
      if (typeof doc[key] === "string" && doc[key].trim().length > 0) {
        return { kind: "readings", text: doc[key].trim() };
      }
    }
    throw new YamlParseError(
      "対応していない形式です（チャートYAML / life_events.yaml / readings / horoscope.svg を読み込めます）。",
    );
  }

  if (Array.isArray(doc)) {
    return { kind: "life_events", events: normalizeLifeEvents(doc) };
  }

  // yaml.load が文字列を返す＝プレーンテキスト（焼き込み鑑定 Markdown 想定）
  if (typeof doc === "string" && (looksMarkdown(text) || trimmed.length > 80)) {
    return { kind: "readings", text: trimmed };
  }

  throw new YamlParseError(
    "対応していない形式です（チャートYAML / life_events.yaml / readings / horoscope.svg を読み込めます）。",
  );
}

export { SUPPORTED_VERSION };
