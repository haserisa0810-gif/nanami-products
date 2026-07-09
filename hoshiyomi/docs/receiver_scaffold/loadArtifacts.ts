// src/lib/loadArtifacts.ts
// 生成側成果物（readings.yaml / life_events.yaml）の読み込み（§10.3）。
// いずれも欠損に寛容: 無ければ null / [] を返し、ビューは空表示にフォールバックする。
// 依存: npm i js-yaml @types/js-yaml
import yaml from "js-yaml";
import type { Readings, LifeEventsFile, LifeEventRaw } from "../types/artifacts";
import { fromLifeEvents, type TimelineEvent } from "./timeline";

// readings.yaml → Readings | null
export function parseReadings(text: string | null | undefined): Readings | null {
  if (!text) return null;
  try {
    const doc = yaml.load(text) as Partial<Readings> | undefined;
    if (!doc || !Array.isArray(doc.sections)) return null;
    return {
      version: doc.version ?? "nanami-readings-v1",
      model: doc.model ?? "unknown",
      generated_at: doc.generated_at,
      profile_id: doc.profile_id,
      sections: doc.sections,
      note: doc.note,
    };
  } catch {
    return null;
  }
}

// life_events.yaml → TimelineEvent[]（source: "transit_major"）
// ファイルは { version, events: [...] } でも、トップレベル配列でも受ける。
export function parseLifeEvents(text: string | null | undefined): TimelineEvent[] {
  if (!text) return [];
  try {
    const doc = yaml.load(text) as LifeEventsFile | LifeEventRaw[] | undefined;
    const raw = Array.isArray(doc) ? doc : doc?.events;
    return fromLifeEvents(raw);
  } catch {
    return [];
  }
}
