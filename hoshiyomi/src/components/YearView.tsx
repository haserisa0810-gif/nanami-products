import { C, SERIF, SANS } from "../theme";
import type { TimelineEvent } from "../lib/timeline";
import { yearOf, monthOf } from "../lib/timeline";
import { Eyebrow, Panel } from "./common";
import EventRow from "./EventRow";

export default function YearView({
  year,
  onYearChange,
  events,
  transitDates,
  onOpenDay,
  onOpenMonth,
  onEdit,
  onDelete,
}: {
  year: number;
  onYearChange: (y: number) => void;
  events: TimelineEvent[]; // 占術＋ユーザーのマージ済み全イベント
  transitDates: Set<string>; // 38日窓に存在する日付（日ビューへ遷移可能な日）
  onOpenDay: (date: string) => void;
  onOpenMonth: () => void;
  onEdit: (ev: TimelineEvent) => void;
  onDelete: (id: string) => void;
}) {
  const inYear = events.filter((e) => yearOf(e.date) === year);
  const hasAstro = inYear.some((e) => e.source !== "user");
  const navBtn = {
    background: C.panel, border: `1px solid ${C.line}`, color: C.text,
    borderRadius: 8, width: 34, height: 34, cursor: "pointer", fontSize: 15, fontFamily: SANS,
  } as const;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <button style={navBtn} onClick={() => onYearChange(year - 1)} aria-label="前の年">←</button>
        <span style={{ fontFamily: SERIF, fontSize: 24, letterSpacing: "0.1em" }}>{year}年</span>
        <button style={navBtn} onClick={() => onYearChange(year + 1)} aria-label="次の年">→</button>
        <button
          onClick={onOpenMonth}
          style={{ background: "transparent", border: `1px solid ${C.line}`, color: C.sub, borderRadius: 8, padding: "7px 12px", cursor: "pointer", fontSize: 12.5, fontFamily: SANS }}
        >
          月カレンダーへ →
        </button>
      </div>

      {!hasAstro && (
        <div style={{ fontSize: 12.5, color: C.faint, marginBottom: 14, lineHeight: 1.8 }}>
          この年の占術データはありません（データ供給のある38日窓の外です）。ユーザーイベントのみ表示します。
        </div>
      )}

      {[...Array(12)].map((_, i) => {
        const m = i + 1;
        const list = inYear.filter((e) => monthOf(e.date) === m);
        if (list.length === 0) return null;
        return (
          <Panel key={m} style={{ marginBottom: 12, padding: "14px 16px" }}>
            <Eyebrow>{year} / {String(m).padStart(2, "0")}</Eyebrow>
            {list.map((e) => (
              <EventRow
                key={e.id}
                ev={e}
                onOpenDay={transitDates.has(e.date.slice(0, 10)) ? onOpenDay : undefined}
                onEdit={onEdit}
                onDelete={onDelete}
              />
            ))}
          </Panel>
        );
      })}
      {inYear.length === 0 && (
        <Panel>
          <div style={{ fontSize: 13, color: C.sub }}>この年のイベントはまだありません。「＋ 予定を追加」から記録できます。</div>
        </Panel>
      )}
    </div>
  );
}
