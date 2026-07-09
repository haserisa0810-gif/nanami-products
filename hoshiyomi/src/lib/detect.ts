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

/* YAML でクォート無しの 2005-08-01 は js-yaml が Date にするため、両方受ける */
function toIsoDate(v: any): string {
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  return String(v ?? "").slice(0, 10);
}

function normalizeLifeEvents(arr: any[]): TimelineEvent[] {
  return arr.map((e, i) => {
    const date = toIsoDate(e.date);
    if (!DATE_RE.test(date) || !e.title) {
      throw new YamlParseError(
        `life_events の ${i + 1} 件目に date（YYYY-MM-DD）または title がありません。`,
      );
    }
    const endRaw = e.endDate ?? e.end_date;
    return {
      id: String(e.id ?? `life:${date}:${i}`),
      type: String(e.type ?? "aspect"),
      date,
      endDate: endRaw != null ? toIsoDate(endRaw) : undefined,
      title: String(e.title),
      description: e.description ? String(e.description) : undefined,
      source: (e.source as TimelineSource) ?? "transit_major",
      // 契約（nanami-life-events-v1）の granularity は meta に畳んで保持する
      meta: e.granularity ? { ...(e.meta ?? {}), granularity: e.granularity } : e.meta,
    };
  });
}

/* readings.yaml 契約（nanami-readings-v1）: model / note / sections[{id,title,body}]。
   表示用に1本のテキストへ組み立て、モデル注釈（§6.2 必須）を末尾に付ける */
function readingsFromSections(doc: any): string {
  const parts: string[] = [];
  for (const s of doc.sections) {
    if (s?.title) parts.push(`## ${s.title}`);
    if (s?.body) parts.push(String(s.body).trim());
  }
  const note =
    doc.note ??
    (doc.model ? `本鑑定は ${doc.model} により、計算済みデータのみを根拠に生成しています。` : null);
  if (note) parts.push(`---\n${note}`);
  return parts.join("\n\n");
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
    // 生成側契約（README_受け皿.md）: version で種類を宣言するファイルを先に判別
    if (typeof doc.version === "string" && doc.version.startsWith("nanami-readings")) {
      if (!Array.isArray(doc.sections)) {
        throw new YamlParseError("readings.yaml に sections 配列がありません。");
      }
      return { kind: "readings", text: readingsFromSections(doc) };
    }
    if (typeof doc.version === "string" && doc.version.startsWith("nanami-life-events")) {
      return { kind: "life_events", events: normalizeLifeEvents(doc.events ?? []) };
    }
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
