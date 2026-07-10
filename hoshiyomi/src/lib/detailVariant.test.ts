/* detail 版（nanami-products-yaml-detail-v1 / AI貼り付け用抜粋）のパーサ検証。
   フル版との構造差: aspects.items / asteroids.bodies / daily 無し（today のみ・
   moon_timepoints はオブジェクト形）を正規化層で吸収する。 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseYamlText } from "./parseYaml";
import { detectPayload } from "./detect";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = readFileSync(
  join(here, "../../tests/fixtures/real_data_detail.yaml"),
  "utf-8",
);

describe("parseYamlText（detail 版）", () => {
  const data = parseYamlText(fixture);

  it("バリアント版の version を受理し、変種情報を保持する", () => {
    expect(detectPayload(fixture)).toEqual({ kind: "chart" });
    expect(data.yamlVariant).toBe("detail");
    expect(data.dataRole).toBe("addon");
    expect(data.profileId).toBe("profile_bfd713c3dc78dda7");
    expect(data.title).toBe("リサフル6/1");
  });

  it("aspects.items 形式のネイタルアスペクトを読める", () => {
    expect(data.natal.aspects.length).toBeGreaterThan(10);
    expect(data.natal.aspects[0]).toEqual({
      body1: "North Node",
      body2: "South Node",
      aspect: "opposition",
      orb: 0.0,
    });
  });

  it("asteroids.bodies 形式の小惑星を読める", () => {
    expect(Object.keys(data.asteroids)).toEqual([
      "Lilith", "Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Vertex",
    ]);
    expect(data.asteroids.Ceres.sign_ja).toBe("獅子座");
  });

  it("daily 無しのとき today から当日1日分を合成する", () => {
    expect(data.transit.daily).toHaveLength(1);
    const day = data.transit.daily[0];
    expect(day.date).toBe("2026-07-09");
    expect(day.transiting_bodies.Sun.degree).toBe(16.9489);
    expect(day.natal_aspects[0]).toEqual({
      transit_body: "Moon",
      natal_body: "Uranus",
      aspect: "opposition",
      orb: 0.35,
    });
    expect(data.transit.todayDate).toBe("2026-07-09");
  });

  it("オブジェクト形の today.moon_timepoints を朝昼夜の配列へ変換する（§3.1-4）", () => {
    const tps = data.transit.daily[0].moon_timepoints;
    expect(tps.map((t) => t.label)).toEqual(["morning", "noon", "night"]);
    const noon = tps[1];
    expect(noon.sign_ja).toBe("牡牛座");
    expect(noon.degree).toBe(3.7807);
    expect(noon.house).toBe(7);
    expect(noon.aspects).toEqual([
      { natal_body: "Uranus", aspect: "opposition", orb: 0.35 },
      { natal_body: "Venus", aspect: "trine", orb: 1.16 },
    ]);
    expect(tps[2].aspects[0].natal_body).toBe("Saturn");
  });

  it("next_31_days_summary（アンカー参照付き）を正規化する", () => {
    expect(data.transit.summary.overall_theme).toContain("調整");
    expect(data.transit.summary.caution_dates).toEqual([
      "2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05",
    ]);
    expect(data.transit.summary.key_dates.map((k) => k.date)).toContain("2026-07-09");
    expect(data.transit.period.end_date).toBe("2026-07-09"); // daily 最終日フォールバック
  });

  it("フル版はバリアント full として扱われる", () => {
    const full = readFileSync(
      join(here, "../../tests/fixtures/real_data_full.yaml"),
      "utf-8",
    );
    const fullData = parseYamlText(full);
    expect(fullData.yamlVariant).toBe("full");
    expect(fullData.dataRole).toBe("base_chart");
  });
});
