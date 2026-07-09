/* YAML（nanami-products-yaml-v1）→ 内部モデルへの正規化レイヤー。
   画面はここで返す ChartData のみを参照し、YAMLの生構造に依存しない。
   絶対ルール: 値の再計算・補正はしない（YAMLの値をそのまま通す）。 */

import yaml from "js-yaml";
import type { AspectName, TimepointLabel } from "../theme";

export const SUPPORTED_VERSION = "nanami-products-yaml-v1";
export const SUPPORTED_SCHEMA_VERSIONS = ["1.0", "1.1"];

export type Body = {
  sign_ja: string;
  degree: number;
  house: number;
  retrograde: boolean;
};

export type HouseCusp = { sign_ja: string; degree: number };

export type NatalAspect = {
  body1: string;
  body2: string;
  aspect: AspectName;
  orb: number;
};

export type TransitAspect = {
  transit_body: string;
  natal_body: string;
  aspect: AspectName;
  orb: number;
};

export type MoonAspect = {
  natal_body: string;
  aspect: AspectName;
  orb: number;
};

export type MoonTimepoint = {
  label: TimepointLabel;
  sign_ja: string;
  degree: number;
  house: number;
  aspects: MoonAspect[];
};

export type TransitDay = {
  date: string;
  transiting_bodies: Record<string, Body>;
  natal_aspects: TransitAspect[];
  moon_timepoints: MoonTimepoint[];
};

export type KeyDate = { date: string; theme: string };

export type PeriodSummary = {
  overall_theme: string;
  key_dates: KeyDate[];
  caution_dates: string[];
  easy_to_move_days: string[];
  key_periods?: { start_date: string; end_date: string; theme: string }[];
  action_hints: string[];
};

export type NatalSummary = {
  elements: { fire: number; earth: number; air: number; water: number };
  modes: { cardinal: number; fixed: number; mutable: number };
  dominant_signs: { sign_ja: string; count: number }[];
};

export type ChartData = {
  profileId: string;
  title: string;
  birthDate: string;
  birthTime: string;
  birthPlace: string;
  birthTimeAccuracy: string;
  flags: {
    allowHouseInterpretation: boolean;
    allowAscMcInterpretation: boolean;
  };
  natal: {
    bodies: Record<string, Body>;
    houses: Record<string, HouseCusp>;
    aspects: NatalAspect[];
    summary: NatalSummary;
  };
  asteroids: Record<string, Body>;
  transit: {
    period: { start_date: string; end_date: string; days: number; timezone: string };
    daily: TransitDay[];
    todayDate: string;
    summary: PeriodSummary;
  };
  horoscopeSvg: string | null;
};

export class YamlParseError extends Error {}

/* eslint-disable @typescript-eslint/no-explicit-any */
function req(obj: any, path: string): any {
  const parts = path.split(".");
  let cur = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object" || !(p in cur)) {
      throw new YamlParseError(`YAMLに必要な項目がありません: ${path}`);
    }
    cur = cur[p];
  }
  return cur;
}

function normBody(raw: any): Body {
  return {
    sign_ja: String(raw.sign_ja ?? ""),
    degree: Number(raw.degree),
    house: Number(raw.house ?? 0),
    retrograde: Boolean(raw.retrograde),
  };
}

export function parseYamlText(text: string): ChartData {
  let doc: any;
  try {
    doc = yaml.load(text);
  } catch (e) {
    throw new YamlParseError(
      `YAMLとして読み取れませんでした: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
  if (doc == null || typeof doc !== "object") {
    throw new YamlParseError("YAMLの中身が空か、形式が想定と異なります。");
  }

  const version = doc.version;
  if (version !== SUPPORTED_VERSION) {
    throw new YamlParseError(
      `このYAMLは対応バージョンではありません（version: ${version ?? "なし"}、対応: ${SUPPORTED_VERSION}）`,
    );
  }
  const schemaVersion = String(req(doc, "meta.schema_version"));
  if (!SUPPORTED_SCHEMA_VERSIONS.includes(schemaVersion)) {
    throw new YamlParseError(
      `このYAMLは対応バージョンではありません（schema_version: ${schemaVersion}、対応: ${SUPPORTED_SCHEMA_VERSIONS.join(" / ")}）`,
    );
  }

  const input = req(doc, "input");
  const natal = req(doc, "systems.western.natal");
  const transit = req(doc, "systems.western.transit");
  const asteroidsRaw = doc.systems.western.asteroids ?? {};

  const daily: TransitDay[] = req(transit, "daily").map((d: any) => ({
    date: String(d.date),
    transiting_bodies: Object.fromEntries(
      Object.entries(d.transiting_bodies ?? {}).map(([k, b]) => [k, normBody(b)]),
    ),
    natal_aspects: (d.natal_aspects ?? []).map((a: any) => ({
      transit_body: String(a.transit_body),
      natal_body: String(a.natal_body),
      aspect: a.aspect as AspectName,
      orb: Number(a.orb),
    })),
    // 圧縮版はフラット {label, sign_ja, degree, house, aspects}、
    // フル版は {label, time, body: {...}, natal_aspects: [...]} にネストする（両対応）
    moon_timepoints: (d.moon_timepoints ?? []).map((tp: any) => {
      const b = tp.body ?? tp;
      return {
        label: tp.label as TimepointLabel,
        sign_ja: String(b.sign_ja),
        degree: Number(b.degree),
        house: Number(b.house),
        aspects: (tp.aspects ?? tp.natal_aspects ?? []).map((a: any) => ({
          natal_body: String(a.natal_body),
          aspect: a.aspect as AspectName,
          orb: Number(a.orb),
        })),
      };
    }),
  }));

  if (daily.length === 0) {
    throw new YamlParseError("トランジット日別データ（daily）が空です。");
  }

  // フル版は next_31_days_summary、圧縮版は summary キーを使う（両対応）
  const summaryRaw = transit.next_31_days_summary ?? transit.summary;
  if (summaryRaw == null) {
    throw new YamlParseError(
      "期間サマリー（next_31_days_summary / summary）が見つかりません。",
    );
  }
  // 日付リストは圧縮版が文字列配列、フル版が {date, reason, ...} オブジェクト配列
  const toDateList = (arr: any[]): string[] =>
    (arr ?? []).map((x) => (typeof x === "string" ? x : String(x.date)));
  const summary: PeriodSummary = {
    overall_theme: String(summaryRaw.overall_theme ?? ""),
    key_dates: (summaryRaw.key_dates ?? []).map((k: any) => ({
      date: String(k.date),
      theme: String(k.theme),
    })),
    caution_dates: toDateList(summaryRaw.caution_dates),
    easy_to_move_days: toDateList(summaryRaw.easy_to_move_days),
    key_periods: summaryRaw.key_periods
      ? summaryRaw.key_periods.map((p: any) => ({
          start_date: String(p.start_date),
          end_date: String(p.end_date),
          theme: String(p.theme),
        }))
      : undefined,
    action_hints: (summaryRaw.action_hints ?? []).map(String),
  };

  const period = req(transit, "period");
  const todayDate = String(
    transit.today?.selected_date ?? period.start_date,
  );

  const flags = doc.interpretation_flags ?? {};

  return {
    profileId: String(doc.meta.profile_id ?? "unknown"),
    title: String(input.title ?? ""),
    birthDate: String(input.birth_date ?? ""),
    birthTime: String(input.birth_time ?? ""),
    birthPlace: String(input.birth_place ?? ""),
    birthTimeAccuracy: String(doc.birth_time?.accuracy ?? "unknown"),
    flags: {
      allowHouseInterpretation: Boolean(flags.allow_house_interpretation),
      allowAscMcInterpretation: Boolean(flags.allow_asc_mc_interpretation),
    },
    natal: {
      bodies: Object.fromEntries(
        Object.entries(req(natal, "bodies")).map(([k, b]) => [k, normBody(b)]),
      ),
      houses: Object.fromEntries(
        Object.entries(natal.houses ?? {}).map(([k, h]: [string, any]) => [
          k,
          { sign_ja: String(h.sign_ja), degree: Number(h.degree) },
        ]),
      ),
      aspects: (natal.aspects ?? []).map((a: any) => ({
        body1: String(a.body1),
        body2: String(a.body2),
        aspect: a.aspect as AspectName,
        orb: Number(a.orb),
      })),
      // アンカー解決後の共有参照を持ち込まないよう、生YAML由来のオブジェクトはコピーする（§3.1-5）
      summary: structuredClone(req(natal, "summary")) as NatalSummary,
    },
    asteroids: Object.fromEntries(
      Object.entries(asteroidsRaw).map(([k, b]) => [k, normBody(b)]),
    ),
    transit: {
      period: {
        start_date: String(period.start_date),
        end_date: String(period.end_date ?? daily[daily.length - 1].date),
        days: Number(period.days ?? daily.length),
        timezone: String(period.timezone ?? ""),
      },
      daily,
      todayDate,
      summary,
    },
    horoscopeSvg:
      typeof doc.assets?.horoscope_svg === "string"
        ? doc.assets.horoscope_svg
        : null,
  };
}
