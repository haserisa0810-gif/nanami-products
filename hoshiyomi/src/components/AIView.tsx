import { useState } from "react";
import { C, SANS, fmtDate } from "../theme";
import type { ChartData } from "../lib/parseYaml";
import { AI_SECTIONS, generateReading, type SectionId } from "../lib/reading";
import { saveReading, readingsToMarkdown, getProfile, type StoredReading } from "../lib/storage";
import { Eyebrow, H2, Panel } from "./common";

export default function AIView({
  data,
  selectedDate,
  initialReadings,
}: {
  data: ChartData;
  selectedDate: string;
  initialReadings: StoredReading[];
}) {
  const [readings, setReadings] = useState<StoredReading[]>(initialReadings);
  const [loading, setLoading] = useState<SectionId | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const findReading = (id: SectionId) =>
    readings.find((r) => r.sectionId === id && (id !== "selectedDay" || r.date === selectedDate));

  const run = async (sec: (typeof AI_SECTIONS)[number]) => {
    setLoading(sec.id);
    setError(null);
    try {
      const text = await generateReading(data, sec.id, selectedDate);
      const reading: StoredReading = {
        sectionId: sec.id,
        label: sec.label,
        date: sec.id === "selectedDay" ? selectedDate : undefined,
        text,
        generatedAt: new Date().toISOString(),
      };
      setReadings((rs) => [
        ...rs.filter((r) => !(r.sectionId === sec.id && r.date === reading.date)),
        reading,
      ]);
      saveReading(data.profileId, reading);
    } catch (e) {
      setError(`生成できませんでした: ${e instanceof Error ? e.message : String(e)}`);
    }
    setLoading(null);
  };

  const copyText = async (key: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  };

  const exportMarkdown = () => {
    const p = getProfile(data.profileId);
    if (!p) return;
    const md = readingsToMarkdown(p);
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hoshiyomi_${data.profileId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const smallBtn = {
    background: "transparent",
    border: `1px solid ${C.line}`,
    color: C.sub,
    borderRadius: 6,
    padding: "4px 10px",
    cursor: "pointer",
    fontSize: 11.5,
    fontFamily: SANS,
  } as const;

  return (
    <div>
      <Panel style={{ marginBottom: 16 }}>
        <Eyebrow>AI Reading</Eyebrow>
        <H2>AI鑑定を生成する</H2>
        <div style={{ fontSize: 13, color: C.sub, marginBottom: 12, lineHeight: 1.8 }}>
          読みたい項目を選ぶと、このYAMLの計算結果だけを根拠にClaudeが鑑定文を生成します。
          {selectedDate !== data.transit.todayDate && (
            <span>（選択日: <span style={{ color: C.dawn }}>{fmtDate(selectedDate)}</span>）</span>
          )}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {AI_SECTIONS.map((sec) => (
            <button
              key={sec.id}
              onClick={() => run(sec)}
              disabled={loading !== null}
              style={{
                background: findReading(sec.id) ? C.panel2 : "transparent",
                color: loading === sec.id ? C.faint : C.text,
                border: `1px solid ${findReading(sec.id) ? C.conj : C.line}`,
                borderRadius: 8,
                padding: "8px 14px",
                cursor: loading ? "default" : "pointer",
                fontSize: 13,
                fontFamily: SANS,
              }}
            >
              {loading === sec.id ? "生成中…" : sec.label}
              {findReading(sec.id) && " ✓"}
            </button>
          ))}
        </div>
        {error && <div style={{ marginTop: 10, fontSize: 12.5, color: C.hard }}>{error}</div>}
        {readings.length > 0 && (
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button style={smallBtn} onClick={() => copyText("all", readings.map((r) => `## ${r.label}${r.date ? `（${r.date}）` : ""}\n\n${r.text.trim()}`).join("\n\n"))}>
              {copied === "all" ? "コピーしました ✓" : "全文コピー"}
            </button>
            <button style={smallBtn} onClick={exportMarkdown}>Markdownエクスポート</button>
          </div>
        )}
      </Panel>
      {readings.map((r) => (
        <Panel key={`${r.sectionId}:${r.date ?? ""}`} style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
            <div>
              <Eyebrow>Reading</Eyebrow>
              <H2>{r.label}{r.date ? `（${fmtDate(r.date)}）` : ""}</H2>
            </div>
            <button style={smallBtn} onClick={() => copyText(r.sectionId + (r.date ?? ""), r.text)}>
              {copied === r.sectionId + (r.date ?? "") ? "✓" : "コピー"}
            </button>
          </div>
          <div style={{ fontSize: 14.5, lineHeight: 2.05, color: C.text, whiteSpace: "pre-wrap", fontFamily: SANS }}>
            {r.text}
          </div>
        </Panel>
      ))}
    </div>
  );
}
