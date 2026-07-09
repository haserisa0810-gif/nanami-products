import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseYamlText } from "./parseYaml";
import {
  fromTransitDaily,
  fromKeyDates,
  fromUserEvent,
  mergeEvents,
  gcalUrl,
  yearOf,
  monthOf,
} from "./timeline";

const here = dirname(fileURLToPath(import.meta.url));
const data = parseYamlText(
  readFileSync(join(here, "../../tests/fixtures/sample_data_compact.yaml"), "utf-8"),
);

describe("timeline adapters", () => {
  it("fromTransitDaily は orb 閾値で重要アスペクトのみ抽出する", () => {
    const events = fromTransitDaily(data.transit.daily, 0.5);
    expect(events.length).toBeGreaterThan(0);
    for (const e of events) {
      expect(e.source).toBe("transit");
      expect(e.type).toBe("aspect");
      expect((e.meta!.orb as number)).toBeLessThanOrEqual(0.5);
    }
    // 2026-07-01 の Sun square Pluto (orb 0.35) が含まれ、タイトルは日本語
    const sunPluto = events.find((e) => e.id === "transit:2026-07-01:Sun:square:Pluto");
    expect(sunPluto?.title).toBe("太陽 スクエア 冥王星");
    // orb 0.97 の Mars square Venus は含まれない
    expect(events.find((e) => e.id.includes("2026-07-01:Mars"))).toBeUndefined();
  });

  it("fromTransitDaily は38日窓の外のイベントを生成しない（§9.0）", () => {
    const events = fromTransitDaily(data.transit.daily, 99);
    const dates = new Set(data.transit.daily.map((d) => d.date));
    for (const e of events) expect(dates.has(e.date)).toBe(true);
  });

  it("fromKeyDates は YAML の key_dates をイベント化する", () => {
    const events = fromKeyDates(data.transit.summary);
    expect(events[0]).toMatchObject({
      date: "2026-07-01",
      title: "◆ 自己表現、調整",
      source: "transit",
      type: "key_date",
    });
  });

  it("fromUserEvent / mergeEvents", () => {
    const u = fromUserEvent({ date: "2026-07-09", title: "AI占い公開", description: "note" });
    expect(u.source).toBe("user");
    expect(u.id).toMatch(/^user:/);
    const merged = mergeEvents(fromKeyDates(data.transit.summary), [u]);
    expect(merged.map((e) => e.date)).toEqual([...merged.map((e) => e.date)].sort());
    expect(merged.some((e) => e.id === u.id)).toBe(true);
  });

  it("gcalUrl は終日リンク（終了日排他）を生成する", () => {
    const u = fromUserEvent({ date: "2026-07-09", title: "AI占い公開", description: "メモ" }, "user:x");
    const url = gcalUrl(u);
    expect(url).toContain("https://calendar.google.com/calendar/render?");
    expect(url).toContain("action=TEMPLATE");
    expect(url).toContain(`text=${encodeURIComponent("AI占い公開")}`);
    expect(url).toContain("dates=20260709%2F20260710");
    expect(url).toContain(`details=${encodeURIComponent("メモ")}`);
    // 月末の繰り上がり
    const eom = gcalUrl(fromUserEvent({ date: "2026-07-31", title: "x" }, "user:y"));
    expect(eom).toContain("dates=20260731%2F20260801");
  });

  it("yearOf / monthOf", () => {
    expect(yearOf("2026-07-09")).toBe(2026);
    expect(monthOf("2026-07-09")).toBe(7);
  });
});
