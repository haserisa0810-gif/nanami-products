import { useRef, useState, type DragEvent } from "react";
import { C, SANS, SERIF } from "../theme";
import { Eyebrow, H2, Panel } from "./common";

export default function YamlLoader({
  onLoad,
  error,
}: {
  onLoad: (text: string) => void;
  error: string | null;
}) {
  const [text, setText] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const readFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => onLoad(String(reader.result ?? ""));
    reader.readAsText(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) readFile(file);
  };

  return (
    <Panel>
      <Eyebrow>Load YAML</Eyebrow>
      <H2>YAMLを読み込む</H2>
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileInput.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && fileInput.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? C.dawn : C.line}`,
          borderRadius: 10,
          padding: "28px 16px",
          textAlign: "center",
          color: dragOver ? C.dawn : C.sub,
          cursor: "pointer",
          fontFamily: SERIF,
          fontSize: 14.5,
          letterSpacing: "0.06em",
          marginBottom: 14,
          transition: "border-color .15s",
        }}
      >
        ここにYAMLファイルをドロップ（クリックで選択）
        <input
          ref={fileInput}
          type="file"
          accept=".yaml,.yml,.txt"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) readFile(f);
            e.target.value = "";
          }}
        />
      </div>
      <div style={{ fontSize: 12, color: C.faint, marginBottom: 6 }}>またはYAMLテキストを貼り付け:</div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        placeholder="version: nanami-products-yaml-v1&#10;meta: ..."
        style={{
          width: "100%",
          boxSizing: "border-box",
          background: C.panel2,
          color: C.text,
          border: `1px solid ${C.line}`,
          borderRadius: 8,
          padding: 10,
          fontSize: 12,
          fontFamily: "ui-monospace, monospace",
          resize: "vertical",
        }}
      />
      <div style={{ marginTop: 10 }}>
        <button
          onClick={() => text.trim() && onLoad(text)}
          disabled={!text.trim()}
          style={{
            background: "transparent",
            border: `1px solid ${text.trim() ? C.dawn : C.line}`,
            color: text.trim() ? C.dawn : C.faint,
            borderRadius: 8,
            padding: "8px 18px",
            cursor: text.trim() ? "pointer" : "default",
            fontSize: 13,
            fontFamily: SANS,
          }}
        >
          読み込む
        </button>
      </div>
      {error && (
        <div style={{ marginTop: 12, fontSize: 12.5, color: C.hard, lineHeight: 1.7 }}>{error}</div>
      )}
    </Panel>
  );
}
