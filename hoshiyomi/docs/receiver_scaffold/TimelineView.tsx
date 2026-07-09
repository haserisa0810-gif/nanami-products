// src/components/timeline/TimelineView.tsx
// ズーム切替の受け皿（日→月→年→人生）。日・月は既存カレンダー/日別詳細へ委譲。
// 年・人生は TimelineEvent[] をここで描画する（§9.2 / §9.4 / §9.6 Time River）。
// スタイルは仮。既存プロトタイプの C トークンへ置き換えること。
import { useMemo, useState } from "react";
import type { TimelineEvent, TimelineScale } from "../../lib/timeline";
import { groupByYear, selectForScale } from "../../lib/timeline";

const C = { text: "#E8E4D8", sub: "#9BA0B2", faint: "#6C7183", line: "#2E3348", dawn: "#E8A87C" };
const SCALES: TimelineScale[] = ["day", "month", "year", "life"];
const LABEL: Record<TimelineScale, string> = { day: "日", month: "月", year: "年", life: "人生" };

export function TimelineView({
  events,
  todayISO,
  renderDay,
  renderMonth,
  onOpenEvent,
  initialScale = "month",
}: {
  events: TimelineEvent[];
  todayISO: string;              // 'YYYY-MM-DD'（today.selected_date）
  renderDay?: () => JSX.Element;    // 既存の日別詳細を差し込む
  renderMonth?: () => JSX.Element;  // 既存の38日カレンダーを差し込む
  onOpenEvent?: (e: TimelineEvent) => void; // 詳細/AI用YAML/カレンダー登録へ（§9.5）
  initialScale?: TimelineScale;
}) {
  const [scale, setScale] = useState<TimelineScale>(initialScale);
  const scoped = useMemo(() => selectForScale(events, scale), [events, scale]);

  return (
    <div>
      <nav style={{ display: "flex", gap: 4, marginBottom: 14 }}>
        {SCALES.map((s) => (
          <button
            key={s}
            onClick={() => setScale(s)}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: `2px solid ${scale === s ? C.dawn : "transparent"}`,
              color: scale === s ? C.text : C.sub,
              padding: "8px 14px",
              cursor: "pointer",
              letterSpacing: "0.1em",
            }}
          >
            {LABEL[s]}
          </button>
        ))}
      </nav>

      {scale === "day" && (renderDay?.() ?? <Empty label="日ビューは既存の日別詳細を接続してください。" />)}
      {scale === "month" && (renderMonth?.() ?? <Empty label="月ビューは既存の38日カレンダーを接続してください。" />)}
      {scale === "year" && <YearLife events={scoped} todayISO={todayISO} mode="year" onOpenEvent={onOpenEvent} />}
      {scale === "life" && <YearLife events={scoped} todayISO={todayISO} mode="life" onOpenEvent={onOpenEvent} />}
    </div>
  );
}

// 年 / 人生の縦タイムライン（Time River）。年境界に区切り、現在の年を強調。
function YearLife({
  events,
  todayISO,
  mode,
  onOpenEvent,
}: {
  events: TimelineEvent[];
  todayISO: string;
  mode: "year" | "life";
  onOpenEvent?: (e: TimelineEvent) => void;
}) {
  const byYear = useMemo(() => groupByYear(events), [events]);
  const years = Object.keys(byYear).sort();
  const curYear = todayISO.slice(0, 4);

  if (years.length === 0) {
    return <Empty label="占術イベント（life_events.yaml）が未供給です。ユーザーイベント＋38日窓のみ表示します。" />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {years.map((y) => {
        const rows = mode === "year" ? byYear[y] : topPerYear(byYear[y]);
        return (
          <section key={y} style={{ borderTop: `1px solid ${C.line}`, paddingTop: 10, marginTop: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <h3 style={{ margin: 0, color: y === curYear ? C.dawn : C.text, letterSpacing: "0.08em" }}>{y}</h3>
              {y === curYear && <span style={{ fontSize: 11, color: C.dawn }}>現在</span>}
            </div>
            {rows.map((e) => (
              <button
                key={e.id}
                onClick={() => onOpenEvent?.(e)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: "none",
                  color: C.text,
                  padding: "5px 0",
                  cursor: onOpenEvent ? "pointer" : "default",
                }}
              >
                <span style={{ color: C.faint, fontSize: 12, marginRight: 8 }}>{e.date.slice(5)}</span>
                {e.title}
                {e.source === "diary" && <span style={{ color: C.sub, fontSize: 11, marginLeft: 6 }}>（日記）</span>}
              </button>
            ))}
          </section>
        );
      })}
    </div>
  );
}

// 人生スケール: 1年あたり最重要のみ（transit_major 優先、無ければ先頭数件）
function topPerYear(list: TimelineEvent[]): TimelineEvent[] {
  const major = list.filter((e) => e.source === "transit_major");
  return (major.length ? major : list).slice(0, 3);
}

const Empty = ({ label }: { label: string }) => (
  <p style={{ color: C.faint, fontSize: 13, padding: "8px 0" }}>{label}</p>
);
