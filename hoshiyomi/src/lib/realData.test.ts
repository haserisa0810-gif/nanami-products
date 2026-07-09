/* 本番フル実データ（アンカー/エイリアス付き・body ネスト・オブジェクト日付リスト）での
   パーサ検証。引き継ぎ§3.1 の差分吸収がここで担保される。 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseYamlText } from "./parseYaml";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = readFileSync(
  join(here, "../../tests/fixtures/real_data_full.yaml"),
  "utf-8",
);

describe("parseYamlText（本番フル実データ）", () => {
  it("アンカー/エイリアスを含む実データがそのままパースできる", () => {
    expect(fixture).toMatch(/&id\d+/);
    expect(fixture).toMatch(/\*id\d+/);
    expect(() => parseYamlText(fixture)).not.toThrow();
  });

  const data = parseYamlText(fixture);

  it("38日全日が読める（period.end_date 無しでも最終日にフォールバック）", () => {
    expect(data.transit.daily).toHaveLength(38);
    expect(data.transit.period.start_date).toBe("2026-07-01");
    expect(data.transit.period.end_date).toBe("2026-08-07");
    expect(data.transit.todayDate).toBe("2026-07-01");
  });

  it("body ネストの moon_timepoints をフラットに正規化する（§3.1-4）", () => {
    const day1 = data.transit.daily[0];
    expect(day1.moon_timepoints.map((t) => t.label)).toEqual([
      "morning", "noon", "night",
    ]);
    const noon = day1.moon_timepoints[1];
    expect(noon.sign_ja).toBe("山羊座");
    expect(noon.degree).toBe(21.7151);
    expect(noon.house).toBe(4);
    expect(noon.aspects).toEqual([
      { natal_body: "Mars", aspect: "trine", orb: 0.44 },
    ]);
  });

  it("オブジェクト配列の caution_dates / easy_to_move_days を日付文字列へ正規化する（§3.1-2）", () => {
    expect(data.transit.summary.caution_dates).toEqual([
      "2026-07-01", "2026-07-02", "2026-07-03",
    ]);
    expect(data.transit.summary.easy_to_move_days).toContain("2026-07-01");
    for (const d of [
      ...data.transit.summary.caution_dates,
      ...data.transit.summary.easy_to_move_days,
    ]) {
      expect(d).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });

  it("next_31_days_summary から overall_theme / key_dates / key_periods を取得する（§3.1-1,3）", () => {
    expect(data.transit.summary.overall_theme).toContain("調整");
    expect(data.transit.summary.key_dates[0]).toEqual({
      date: "2026-07-01",
      theme: "自己表現、調整",
    });
    expect(data.transit.summary.key_periods?.[0]).toEqual({
      start_date: "2026-07-02",
      end_date: "2026-07-03",
      theme: "行動力、調整",
    });
    expect(data.transit.summary.action_hints.length).toBeGreaterThan(0);
  });

  it("正規化結果は圧縮版と同じ内部モデルの形になる（画面はスキーマ差を意識しない）", () => {
    expect(data.natal.bodies.Sun).toEqual({
      sign_ja: "獅子座", degree: 17.9572, house: 5, retrograde: false,
    });
    expect(Object.keys(data.asteroids)).toContain("Chiron");
    expect(data.natal.summary.elements).toEqual({ fire: 3, earth: 4, air: 2, water: 1 });
  });

  it("エイリアス由来の共有参照が正規化結果に漏れない（§3.1-5）", () => {
    // 出力内の全オブジェクトは新規生成なので、どの2つのアスペクトも同一参照でない
    const all = data.transit.daily.flatMap((d) => d.natal_aspects);
    const seen = new Set<object>();
    for (const a of all) {
      expect(seen.has(a)).toBe(false);
      seen.add(a);
    }
    // 破壊的変更が他所へ伝播しないこと
    const orig = data.transit.daily[1].natal_aspects[0].orb;
    data.transit.daily[0].natal_aspects[0].orb = 999;
    expect(data.transit.daily[1].natal_aspects[0].orb).toBe(orig);
    data.transit.daily[0].natal_aspects[0].orb = 0.35;
  });
});
