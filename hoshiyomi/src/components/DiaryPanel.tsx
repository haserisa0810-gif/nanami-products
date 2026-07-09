/* 日記レイヤー（§11.3）— 各日付に一言メモ。source:"diary" として userEvents と同じキーに保存し、
   年・人生ビューにもそのまま載る。 */

import { useEffect, useState } from "react";
import { C, SANS } from "../theme";
import type { TimelineEvent } from "../lib/timeline";
import { Eyebrow, Panel } from "./common";

export default function DiaryPanel({
  date,
  entry,
  onSave,
  onDelete,
}: {
  date: string;
  entry: TimelineEvent | null;
  onSave: (text: string) => void;
  onDelete: () => void;
}) {
  const stored = entry?.description ?? entry?.title ?? "";
  const [text, setText] = useState(stored);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setText(stored);
    setSaved(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date, stored]);

  const dirty = text.trim() !== stored;
  const btn = (on: boolean) => ({
    background: "transparent", border: `1px solid ${on ? C.dawn : C.line}`,
    color: on ? C.dawn : C.faint, borderRadius: 8, padding: "7px 14px",
    cursor: on ? "pointer" : "default", fontSize: 12.5, fontFamily: SANS,
  }) as const;

  return (
    <Panel style={{ marginTop: 16 }} >
      <Eyebrow>Diary</Eyebrow>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          type="text"
          value={text}
          onChange={(e) => { setText(e.target.value); setSaved(false); }}
          placeholder="この日の一言メモ（タイムラインに残ります）"
          style={{
            flex: 1, minWidth: 200, background: C.panel2, color: C.text,
            border: `1px solid ${C.line}`, borderRadius: 8, padding: "8px 10px",
            fontSize: 13, fontFamily: SANS,
          }}
          aria-label={`${date} のメモ`}
        />
        <button
          style={btn(dirty && text.trim().length > 0)}
          disabled={!dirty || text.trim().length === 0}
          onClick={() => { onSave(text.trim()); setSaved(true); }}
        >
          {saved && !dirty ? "保存しました ✓" : "保存"}
        </button>
        {entry && (
          <button style={{ ...btn(false), cursor: "pointer", color: C.sub }} onClick={onDelete}>
            削除
          </button>
        )}
      </div>
    </Panel>
  );
}
