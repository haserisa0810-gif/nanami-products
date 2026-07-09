import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseYamlText } from "./parseYaml";
import { mergeChartData, chartFromStored } from "./merge";

const here = dirname(fileURLToPath(import.meta.url));
const baseYaml = readFileSync(
  join(here, "../../tests/fixtures/sample_data_compact.yaml"),
  "utf-8",
);

// 月次アドオンを模擬: 期間を2ヶ月後ろへずらしたYAML（2026-07→09、2026-08→10）
const addonYaml = baseYaml
  .replaceAll("2026-07", "2026-09")
  .replaceAll("2026-08", "2026-10")
  .replace("product_type: western_31days_transit_addon", "product_type: western_31days_transit_addon")
  .replace("data_role: base_chart", "data_role: monthly_addon");

describe("月次アドオンYAMLのマージ（§11.3）", () => {
  const base = parseYamlText(baseYaml);
  const addon = parseYamlText(addonYaml);

  it("アドオンの data_role を識別できる", () => {
    expect(base.dataRole).toBe("base_chart");
    expect(addon.dataRole).toBe("monthly_addon");
  });

  it("daily を日付キーでマージし period を拡張する", () => {
    const merged = mergeChartData(base, addon);
    expect(merged.transit.daily).toHaveLength(76); // 38 + 38（重複なし）
    expect(merged.transit.period.start_date).toBe("2026-07-01");
    expect(merged.transit.period.end_date).toBe("2026-10-07");
    expect(merged.transit.period.days).toBe(76);
    // 日付昇順
    const dates = merged.transit.daily.map((d) => d.date);
    expect(dates).toEqual([...dates].sort());
    // 値は加工されない
    expect(merged.transit.daily[0].transiting_bodies.Sun.degree).toBe(9.322);
  });

  it("基準日とテーマは新しい期間側、日付リストは統合される", () => {
    const merged = mergeChartData(base, addon);
    expect(merged.transit.todayDate).toBe("2026-09-01");
    expect(merged.transit.summary.caution_dates).toContain("2026-07-01");
    expect(merged.transit.summary.caution_dates).toContain("2026-09-01");
    expect(merged.transit.summary.key_dates.map((k) => k.date)).toContain("2026-09-02");
  });

  it("重複日はアドオン優先で置き換える", () => {
    const merged = mergeChartData(base, base); // 同一期間を重ねても壊れない
    expect(merged.transit.daily).toHaveLength(38);
    expect(merged.transit.period.days).toBe(38);
  });

  it("chartFromStored はベース＋アドオン群を一括で組み立てる", () => {
    const merged = chartFromStored(baseYaml, [addonYaml]);
    expect(merged.transit.daily).toHaveLength(76);
    expect(merged.profileId).toBe(parseYamlText(baseYaml).profileId);
  });
});
