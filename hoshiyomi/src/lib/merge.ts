/* 月次トランジット追加YAMLのマージ（§11.3）。
   daily[] を日付キーでマージ（重複日は新しい addon 優先）、period は最小 start 〜 最大 end。
   値そのものは一切加工しない（§1）。 */

import { parseYamlText, type ChartData } from "./parseYaml";

export function mergeChartData(base: ChartData, addon: ChartData): ChartData {
  const byDate = new Map(base.transit.daily.map((d) => [d.date, d]));
  for (const d of addon.transit.daily) byDate.set(d.date, d); // 重複日は addon 優先
  const daily = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));

  // 基準日と期間サマリー（テーマ・行動ヒント）は期間の新しい側を採用
  const newer =
    addon.transit.period.start_date >= base.transit.period.start_date ? addon : base;
  const dedupe = (arr: string[]) => [...new Set(arr)].sort();
  const keyDateMap = new Map(
    [...base.transit.summary.key_dates, ...addon.transit.summary.key_dates].map((k) => [
      k.date,
      k,
    ]),
  );

  return {
    ...base,
    transit: {
      period: {
        start_date:
          base.transit.period.start_date < addon.transit.period.start_date
            ? base.transit.period.start_date
            : addon.transit.period.start_date,
        end_date:
          base.transit.period.end_date > addon.transit.period.end_date
            ? base.transit.period.end_date
            : addon.transit.period.end_date,
        days: daily.length,
        timezone: base.transit.period.timezone || addon.transit.period.timezone,
      },
      daily,
      todayDate: newer.transit.todayDate,
      summary: {
        overall_theme: newer.transit.summary.overall_theme,
        action_hints: newer.transit.summary.action_hints,
        key_periods: newer.transit.summary.key_periods,
        key_dates: [...keyDateMap.values()].sort((a, b) => a.date.localeCompare(b.date)),
        caution_dates: dedupe([
          ...base.transit.summary.caution_dates,
          ...addon.transit.summary.caution_dates,
        ]),
        easy_to_move_days: dedupe([
          ...base.transit.summary.easy_to_move_days,
          ...addon.transit.summary.easy_to_move_days,
        ]),
      },
    },
  };
}

/* ベースYAML＋アドオンYAML群から表示用 ChartData を組み立てる */
export function chartFromStored(baseYaml: string, addonYamls: string[] = []): ChartData {
  let data = parseYamlText(baseYaml);
  for (const a of addonYamls) {
    data = mergeChartData(data, parseYamlText(a));
  }
  return data;
}
