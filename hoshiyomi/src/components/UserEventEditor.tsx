import { useState } from "react";
import { C, SANS } from "../theme";
import type { TimelineEvent, UserEventInput } from "../lib/timeline";
import { Eyebrow, Panel } from "./common";

export default function UserEventEditor({
  initial,
  onSave,
  onCancel,
}: {
  initial: TimelineEvent | null; // null = 新規
  onSave: (input: UserEventInput, id?: string) => void;
  onCancel: () => void;
}) {
  const [date, setDate] = useState(initial?.date?.slice(0, 10) ?? "");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(date) && title.trim().length > 0;

  const input = {
    background: C.panel2,
    color: C.text,
    border: `1px solid ${C.line}`,
    borderRadius: 6,
    padding: "7px 9px",
    fontSize: 13,
    fontFamily: SANS,
  } as const;

  return (
    <Panel style={{ marginBottom: 14 }}>
      <Eyebrow>{initial ? "Edit Event" : "New Event"}</Eyebrow>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ ...input, colorScheme: "dark" }}
          aria-label="日付"
        />
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="タイトル（例: 引越し）"
          style={{ ...input, flex: 1, minWidth: 160 }}
          aria-label="タイトル"
        />
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="説明（任意）"
          style={{ ...input, flex: 1.4, minWidth: 180 }}
          aria-label="説明"
        />
        <button
          onClick={() => valid && onSave({ date, title: title.trim(), description: description.trim() || undefined }, initial?.id)}
          disabled={!valid}
          style={{
            background: "transparent", border: `1px solid ${valid ? C.dawn : C.line}`,
            color: valid ? C.dawn : C.faint, borderRadius: 8, padding: "7px 14px",
            cursor: valid ? "pointer" : "default", fontSize: 13, fontFamily: SANS,
          }}
        >
          保存
        </button>
        <button
          onClick={onCancel}
          style={{ background: "transparent", border: `1px solid ${C.line}`, color: C.sub, borderRadius: 8, padding: "7px 14px", cursor: "pointer", fontSize: 13, fontFamily: SANS }}
        >
          キャンセル
        </button>
      </div>
    </Panel>
  );
}
