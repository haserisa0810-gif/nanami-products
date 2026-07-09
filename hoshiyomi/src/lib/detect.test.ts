import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { detectPayload } from "./detect";
import { YamlParseError } from "./parseYaml";

const here = dirname(fileURLToPath(import.meta.url));
const chartYaml = readFileSync(
  join(here, "../../tests/fixtures/sample_data_compact.yaml"),
  "utf-8",
);

describe("detectPayload（同梱ファイルの自動判別）", () => {
  it("チャートYAMLを chart と判別する", () => {
    expect(detectPayload(chartYaml)).toEqual({ kind: "chart" });
  });

  it("TimelineEvent 互換配列を life_events と判別し正規化する", () => {
    const text = `
- date: '2028-03-15'
  title: 木星 合 土星
  type: aspect
  description: 主要トランジット
  meta: {orb: 0.4}
- date: '2030-06-01'
  title: サターンリターン
  type: return
`;
    const det = detectPayload(text);
    if (det.kind !== "life_events") throw new Error("life_events expected");
    expect(det.events).toHaveLength(2);
    expect(det.events[0]).toMatchObject({
      date: "2028-03-15",
      title: "木星 合 土星",
      type: "aspect",
      source: "transit_major", // 省略時のデフォルト
    });
    expect(det.events[1].type).toBe("return");
  });

  it("{life_events: [...]} 形式も受ける", () => {
    const det = detectPayload("life_events:\n- {date: '2029-01-01', title: イングレス}\n");
    if (det.kind !== "life_events") throw new Error("life_events expected");
    expect(det.events[0].title).toBe("イングレス");
  });

  it("date や title の欠けた life_events はエラー理由を返す", () => {
    expect(() => detectPayload("- {date: '2029-01-01'}\n")).toThrow(YamlParseError);
    expect(() => detectPayload("- {title: x, date: 'あした'}\n")).toThrow(/date/);
  });

  it("Markdown を readings と判別する", () => {
    const md = "# 基本版鑑定\n\n## 全体像\n\n本鑑定は Gemini 2.5 Flash-Lite により生成しています。";
    const det = detectPayload(md);
    if (det.kind !== "readings") throw new Error("readings expected");
    expect(det.text).toContain("基本版鑑定");
  });

  it("{readings: \"...\"} 形式の readings.yaml も受ける", () => {
    const det = detectPayload('readings: |\n  ## 全体像\n  傾向のまとめ。\n');
    if (det.kind !== "readings") throw new Error("readings expected");
    expect(det.text).toContain("全体像");
  });

  it("SVG を svg と判別する", () => {
    const det = detectPayload('<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>');
    expect(det.kind).toBe("svg");
  });

  it("判別できない入力はエラー理由を返す", () => {
    expect(() => detectPayload("")).toThrow(YamlParseError);
    expect(() => detectPayload("x: 1\ny: 2\n")).toThrow(/対応していない形式/);
  });

  /* 生成側とのデータ契約（docs/receiver_scaffold/README_受け皿.md） */

  it("nanami-readings-v1（sections構造）を readings と判別しモデル注釈を付ける", () => {
    const text = `
version: nanami-readings-v1
model: gemini-2.5-flash-lite
profile_id: profile_xxx
sections:
  - { id: overview, title: 全体像, body: "傾向のまとめです。" }
  - { id: talent, title: 才能・強み, body: "強みの説明です。" }
`;
    const det = detectPayload(text);
    if (det.kind !== "readings") throw new Error("readings expected");
    expect(det.text).toContain("## 全体像");
    expect(det.text).toContain("## 才能・強み");
    expect(det.text).toContain("本鑑定は gemini-2.5-flash-lite により、計算済みデータのみを根拠に生成しています。");
  });

  it("nanami-readings-v1 の note があれば注釈はそれを優先する", () => {
    const det = detectPayload(
      "version: nanami-readings-v1\nmodel: x\nnote: カスタム注釈\nsections:\n- {id: a, title: T, body: B}\n",
    );
    if (det.kind !== "readings") throw new Error("readings expected");
    expect(det.text).toContain("カスタム注釈");
    expect(det.text).not.toContain("本鑑定は x により");
  });

  it("nanami-life-events-v1（クォート無し日付 = js-yaml が Date 化）も正しく読む", () => {
    const text = `
version: nanami-life-events-v1
profile_id: profile_xxx
events:
  - { type: return, date: 2005-08-01, title: サターンリターン, description: 節目, meta: { orb: 0.3 } }
  - { type: ingress, date: 2027-04-01, title: 天王星 双子座入り, granularity: year }
`;
    const det = detectPayload(text);
    if (det.kind !== "life_events") throw new Error("life_events expected");
    expect(det.events[0].date).toBe("2005-08-01"); // Date → ISO 文字列へ正規化
    expect(det.events[0].source).toBe("transit_major");
    expect(det.events[1].date).toBe("2027-04-01");
    expect(det.events[1].meta).toMatchObject({ granularity: "year" });
  });
});
