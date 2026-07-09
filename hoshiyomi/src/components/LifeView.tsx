/* 人生ビュー（Time River）— 出生から未来までの縦タイムライン（§9.6）。
   データ供給の無い年の占術イベントは表示しない（捏造しない）。 */

import { C, SERIF, SANS } from "../theme";
import type { TimelineEvent } from "../lib/timeline";
import { yearOf } from "../lib/timeline";
import EventRow from "./EventRow";

export default function LifeView({
  birthYear,
  events,
  transitDates,
  onOpenYear,
  onOpenDay,
  onEdit,
  onDelete,
}: {
  birthYear: number;
  events: TimelineEvent[];
  transitDates: Set<string>;
  onOpenYear: (year: number) => void;
  onOpenDay: (date: string) => void;
  onEdit: (ev: TimelineEvent) => void;
  onDelete: (id: string) => void;
}) {
  const currentYear = new Date().getFullYear();
  const lastEventYear = events.reduce((mx, e) => Math.max(mx, yearOf(e.date)), currentYear);
  const years: number[] = [];
  for (let y = birthYear; y <= Math.max(currentYear, lastEventYear) + 1; y++) years.push(y);
  const byYear = new Map<number, TimelineEvent[]>();
  for (const e of events) {
    const y = yearOf(e.date);
    byYear.set(y, [...(byYear.get(y) ?? []), e]);
  }

  return (
    <div style={{ maxWidth: 720 }}>
      {years.map((y) => {
        const list = byYear.get(y) ?? [];
        const isNow = y === currentYear;
        return (
          <div
            key={y}
            style={{
              display: "flex", gap: 14,
              borderTop: `1px solid ${isNow ? C.dawn : C.line}`,
              padding: list.length > 0 ? "8px 0 10px" : "4px 0",
            }}
          >
            <button
              onClick={() => onOpenYear(y)}
              style={{
                background: "transparent", border: "none", cursor: "pointer",
                fontFamily: SERIF, fontSize: list.length > 0 ? 17 : 12.5,
                color: isNow ? C.dawn : list.length > 0 ? C.text : C.faint,
                width: 92, textAlign: "left", padding: 0, letterSpacing: "0.06em",
                display: "flex", alignItems: "baseline", gap: 6, flexShrink: 0,
              }}
              title={`${y}年（${y - birthYear}歳）を見る`}
            >
              {y}
              <span style={{ fontSize: 10, color: C.faint, fontFamily: SANS }}>{y - birthYear}歳</span>
            </button>
            <div style={{ flex: 1, minWidth: 0 }}>
              {isNow && (
                <span style={{ fontSize: 10, color: C.dawn, border: `1px solid ${C.dawn}66`, borderRadius: 4, padding: "1px 7px", letterSpacing: "0.15em" }}>
                  現在
                </span>
              )}
              {list.map((e) => (
                <EventRow
                  key={e.id}
                  ev={e}
                  onOpenDay={transitDates.has(e.date.slice(0, 10)) ? onOpenDay : undefined}
                  onEdit={onEdit}
                  onDelete={onDelete}
                />
              ))}
            </div>
          </div>
        );
      })}
      <div style={{ borderTop: `1px solid ${C.line}`, marginTop: 2 }} />
      <div style={{ fontSize: 11, color: C.faint, marginTop: 12, lineHeight: 1.8 }}>
        占術イベントはYAMLにデータのある期間（38日窓）のみ表示されます。それ以外の年はユーザーイベントの記録欄としてお使いください。
      </div>
    </div>
  );
}
