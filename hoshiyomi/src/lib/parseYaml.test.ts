import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import yaml from "js-yaml";
import { parseYamlText, YamlParseError } from "./parseYaml";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = readFileSync(
  join(here, "../../tests/fixtures/sample_data_compact.yaml"),
  "utf-8",
);

describe("parseYamlText", () => {
  const data = parseYamlText(fixture);

  it("ヘッダー情報を正規化する", () => {
    expect(data.title).toBe("リサフル6/1");
    expect(data.birthDate).toBe("1976-08-10");
    expect(data.birthTime).toBe("20:41");
    expect(data.birthPlace).toBe("東京都");
    expect(data.birthTimeAccuracy).toBe("exact");
    expect(data.flags.allowHouseInterpretation).toBe(true);
    expect(data.profileId).toBe("profile_bfd713c3dc78dda7");
  });

  it("出生図の天体をYAMLの値のまま保持する（再計算しない）", () => {
    expect(data.natal.bodies.Sun).toEqual({
      sign_ja: "獅子座",
      degree: 17.9572,
      house: 5,
      retrograde: false,
    });
    expect(data.natal.bodies.Neptune.retrograde).toBe(true);
    expect(Object.keys(data.natal.bodies)).toContain("ASC");
    expect(Object.keys(data.natal.bodies)).toContain("MC");
  });

  it("ハウスカスプ12室を保持する", () => {
    expect(Object.keys(data.natal.houses)).toHaveLength(12);
    expect(data.natal.houses["1"].degree).toBe(6.3569);
    expect(data.natal.houses["10"].sign_ja).toBe("山羊座");
  });

  it("ネイタルアスペクトのorbが一致する", () => {
    const first = data.natal.aspects[0];
    expect(first.body1).toBe("North Node");
    expect(first.body2).toBe("South Node");
    expect(first.aspect).toBe("opposition");
    expect(first.orb).toBe(0.0);
  });

  it("エレメント・モードのサマリーを保持する", () => {
    expect(data.natal.summary.elements).toEqual({ fire: 3, earth: 4, air: 2, water: 1 });
    expect(data.natal.summary.modes.fixed).toBe(5);
    expect(data.natal.summary.dominant_signs[0].sign_ja).toBe("乙女座");
  });

  it("小惑星7天体を保持する", () => {
    expect(Object.keys(data.asteroids)).toEqual([
      "Lilith", "Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Vertex",
    ]);
    expect(data.asteroids.Chiron.retrograde).toBe(true);
  });

  it("38日全日がカレンダーに出せる", () => {
    expect(data.transit.daily).toHaveLength(38);
    expect(data.transit.daily[0].date).toBe("2026-07-01");
    expect(data.transit.daily[37].date).toBe("2026-08-07");
    expect(data.transit.period.days).toBe(38);
    // 全日に正午の月と朝昼夜3点が揃っている
    for (const d of data.transit.daily) {
      expect(d.transiting_bodies.Moon).toBeDefined();
      expect(d.moon_timepoints.map((t) => t.label)).toEqual([
        "morning", "noon", "night",
      ]);
    }
  });

  it("日別のトランジットアスペクトがYAMLの値と一致する", () => {
    const day1 = data.transit.daily[0];
    expect(day1.natal_aspects[0]).toEqual({
      transit_body: "Sun",
      natal_body: "Pluto",
      aspect: "square",
      orb: 0.35,
    });
    const noon = day1.moon_timepoints.find((t) => t.label === "noon")!;
    expect(noon.aspects[0]).toEqual({
      natal_body: "Mars",
      aspect: "trine",
      orb: 0.44,
    });
  });

  it("基準日と期間サマリーを正規化する（summary / next_31_days_summary 両対応）", () => {
    expect(data.transit.todayDate).toBe("2026-07-01");
    expect(data.transit.summary.overall_theme).toContain("調整");
    expect(data.transit.summary.caution_dates).toContain("2026-07-02");
    expect(data.transit.summary.easy_to_move_days).toContain("2026-07-10");
    expect(data.transit.summary.key_dates[0]).toEqual({
      date: "2026-07-01",
      theme: "自己表現、調整",
    });
    expect(data.transit.summary.action_hints.length).toBeGreaterThan(0);
  });

  it("next_31_days_summary キーでも読める", () => {
    // natal.summary も同じインデントにあるため、today: 行直後の summary だけを狙う
    const renamed = fixture.replace(
      /(^ {6}today: .*\n) {6}summary:/m,
      "$1      next_31_days_summary:",
    );
    const d2 = parseYamlText(renamed);
    expect(d2.transit.summary.overall_theme).toBe(data.transit.summary.overall_theme);
  });

  it("today が無い場合は period.start_date にフォールバックする", () => {
    const removed = fixture.replace(/^ {6}today: .*\n/m, "");
    const d2 = parseYamlText(removed);
    expect(d2.transit.todayDate).toBe("2026-07-01");
  });

  it("versionが違うYAMLは拒否する", () => {
    expect(() =>
      parseYamlText(fixture.replace("version: nanami-products-yaml-v1", "version: other-v9")),
    ).toThrow(YamlParseError);
    expect(() =>
      parseYamlText(fixture.replace("schema_version: '1.1'", "schema_version: '9.9'")),
    ).toThrow(/対応バージョン/);
  });

  it("YAMLとして壊れている入力はエラー理由を返す", () => {
    expect(() => parseYamlText("{{{")).toThrow(YamlParseError);
    expect(() => parseYamlText("")).toThrow(YamlParseError);
  });

  it("本番フル版スキーマ（body ネスト・natal_aspects・オブジェクト日付リスト）でも同じ結果になる", () => {
    // 圧縮版をフル版の構造に変換して、正規化結果が一致することを確認する
    const doc: any = yaml.load(fixture);
    const t = doc.systems.western.transit;
    for (const d of t.daily) {
      d.time = "12:00";
      d.moon_timepoints = d.moon_timepoints.map((tp: any) => ({
        label: tp.label,
        time: { morning: "06:00", noon: "12:00", night: "21:00" }[tp.label as string],
        body: {
          sign: "Xxx",
          sign_ja: tp.sign_ja,
          degree: tp.degree,
          house: tp.house,
          retrograde: false,
        },
        natal_aspects: tp.aspects.map((a: any) => ({
          ...a,
          transit_body: "Moon",
          meaning_hint: "テスト",
        })),
      }));
    }
    t.next_31_days_summary = {
      ...t.summary,
      caution_dates: t.summary.caution_dates.map((date: string) => ({
        date,
        reason: "調整が必要な配置がある日",
      })),
      easy_to_move_days: t.summary.easy_to_move_days.map((date: string) => ({
        date,
        reason: "動きが出やすい日",
      })),
    };
    delete t.summary;
    doc.assets = { horoscope_svg: { available: true, file_name: "horoscope.svg" } };

    const full = parseYamlText(yaml.dump(doc));
    expect(full.transit.daily).toEqual(data.transit.daily);
    expect(full.transit.summary.caution_dates).toEqual(data.transit.summary.caution_dates);
    expect(full.transit.summary.easy_to_move_days).toEqual(data.transit.summary.easy_to_move_days);
    expect(full.horoscopeSvg).toBeNull();
  });
});
