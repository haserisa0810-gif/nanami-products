import { C, SANS } from "../theme";
import { gcalUrl, type TimelineEvent } from "../lib/timeline";

const SOURCE_LABEL: Record<string, { label: string; color: string }> = {
  transit: { label: "transit", color: C.day },
  transit_major: { label: "major", color: C.night },
  user: { label: "user", color: C.dawn },
  diary: { label: "diary", color: C.good },
};

const EDITABLE_SOURCES = new Set(["user", "diary"]);

export default function EventRow({
  ev,
  onOpenDay,
  onEdit,
  onDelete,
}: {
  ev: TimelineEvent;
  onOpenDay?: (date: string) => void;
  onEdit?: (ev: TimelineEvent) => void;
  onDelete?: (id: string) => void;
}) {
  const src = SOURCE_LABEL[ev.source] ?? SOURCE_LABEL.transit;
  const [, m, d] = ev.date.slice(0, 10).split("-").map(Number);
  const clickable = onOpenDay != null;
  const iconBtn = {
    background: "transparent",
    border: "none",
    color: C.faint,
    cursor: "pointer",
    fontSize: 12,
    padding: "2px 4px",
    fontFamily: SANS,
  } as const;
  return (
    <div
      style={{
        display: "flex", alignItems: "baseline", gap: 8,
        padding: "5px 2px", borderBottom: `1px solid ${C.line}44`, fontSize: 13,
      }}
    >
      <span style={{ width: 44, color: C.sub, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
        {m}/{d}
      </span>
      <span
        role={clickable ? "button" : undefined}
        tabIndex={clickable ? 0 : undefined}
        onClick={() => onOpenDay?.(ev.date.slice(0, 10))}
        onKeyDown={(e) => e.key === "Enter" && onOpenDay?.(ev.date.slice(0, 10))}
        style={{ color: C.text, cursor: clickable ? "pointer" : "default", flex: 1, minWidth: 0 }}
        title={ev.description}
      >
        {ev.title}
        {ev.description && <span style={{ color: C.faint, fontSize: 11.5 }}>　{ev.description}</span>}
      </span>
      <span style={{ fontSize: 10, color: src.color, border: `1px solid ${src.color}55`, borderRadius: 4, padding: "1px 6px", flexShrink: 0 }}>
        {src.label}
      </span>
      <a
        href={gcalUrl(ev)}
        target="_blank"
        rel="noreferrer"
        title="Googleカレンダーに追加"
        style={{ color: C.faint, textDecoration: "none", fontSize: 12, flexShrink: 0 }}
      >
        📅
      </a>
      {EDITABLE_SOURCES.has(ev.source) && onEdit && (
        <button style={iconBtn} title="編集" onClick={() => onEdit(ev)}>✎</button>
      )}
      {EDITABLE_SOURCES.has(ev.source) && onDelete && (
        <button style={iconBtn} title="削除" onClick={() => onDelete(ev.id)}>×</button>
      )}
    </div>
  );
}
