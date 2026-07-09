/* AI鑑定タブ — レーンA（§6.1・既定）: プロンプトを組み立ててコピー／自分のAIへ受け渡す。
   レーンB（§6.2）: 生成時に焼き込まれた readings があれば表示するだけ。
   ライブ生成は VITE_ANTHROPIC_API_KEY があるときのみの開発検証用（§6.5）。 */

import { useState } from "react";
import { C, SANS, fmtDate } from "../theme";
import type { ChartData } from "../lib/parseYaml";
import {
  AI_SECTIONS, AI_DESTINATIONS, buildFullPrompt, generateReading, devApiKeyAvailable,
  type SectionId,
} from "../lib/reading";
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
  const [active, setActive] = useState<SectionId | null>(null);
  const [readings, setReadings] = useState<StoredReading[]>(initialReadings);
  const [loading, setLoading] = useState<SectionId | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const baked = getProfile(data.profileId)?.baked ?? null;

  const activeSection = AI_SECTIONS.find((s) => s.id === active) ?? null;
  const prompt = activeSection ? buildFullPrompt(data, activeSection.id, selectedDate) : "";

  const copyText = async (key: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 1600);
  };

  const sendTo = async (url: string) => {
    await copyText("prompt", prompt);
    window.open(url, "_blank", "noopener");
  };

  // 開発検証用ライブ生成（§6.5） — 配布ビルドではキーが無いため表示されない
  const runDev = async (sec: (typeof AI_SECTIONS)[number]) => {
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

  const exportMarkdown = () => {
    const p = getProfile(data.profileId);
    if (!p) return;
    const blob = new Blob([readingsToMarkdown(p)], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hoshiyomi_${data.profileId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const smallBtn = {
    background: "transparent", border: `1px solid ${C.line}`, color: C.sub,
    borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 11.5, fontFamily: SANS,
  } as const;
  const accentBtn = (on: boolean) => ({
    background: "transparent", border: `1px solid ${on ? C.dawn : C.line}`,
    color: on ? C.dawn : C.faint, borderRadius: 8, padding: "8px 14px",
    cursor: on ? "pointer" : "default", fontSize: 13, fontFamily: SANS,
  }) as const;

  return (
    <div>
      {/* レーンB: 焼き込み済み基本版鑑定（あれば表示するだけ） */}
      {baked && (
        <Panel style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
            <div>
              <Eyebrow>Bundled Reading</Eyebrow>
              <H2>基本版鑑定（同梱）</H2>
            </div>
            <button style={smallBtn} onClick={() => copyText("baked", baked.text)}>
              {copied === "baked" ? "✓" : "コピー"}
            </button>
          </div>
          <div style={{ fontSize: 14.5, lineHeight: 2.05, color: C.text, whiteSpace: "pre-wrap", fontFamily: SANS }}>
            {baked.text}
          </div>
        </Panel>
      )}

      {/* レーンA: プロンプトを組み立てて自分のAIへ */}
      <Panel style={{ marginBottom: 16 }}>
        <Eyebrow>AI Reading — 自分のAIで読む</Eyebrow>
        <H2>AI鑑定プロンプトを作る</H2>
        <div style={{ fontSize: 13, color: C.sub, marginBottom: 12, lineHeight: 1.8 }}>
          読みたい項目を選ぶと、このYAMLの計算結果だけを根拠に鑑定させるプロンプトを組み立てます。
          コピーして、お使いの ChatGPT / Claude / Gemini（無料版でも可）に貼り付けてください。
          {selectedDate !== data.transit.todayDate && (
            <span>（選択日: <span style={{ color: C.dawn }}>{fmtDate(selectedDate)}</span>）</span>
          )}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {AI_SECTIONS.map((sec) => (
            <button
              key={sec.id}
              onClick={() => setActive(sec.id)}
              style={{
                background: active === sec.id ? C.panel2 : "transparent",
                color: C.text,
                border: `1px solid ${active === sec.id ? C.dawn : C.line}`,
                borderRadius: 8, padding: "8px 14px", cursor: "pointer", fontSize: 13, fontFamily: SANS,
              }}
            >
              {sec.label}
            </button>
          ))}
        </div>

        {activeSection && (
          <div style={{ marginTop: 14 }}>
            <textarea
              readOnly
              value={prompt}
              rows={7}
              onFocus={(e) => e.currentTarget.select()}
              style={{
                width: "100%", boxSizing: "border-box", background: C.panel2, color: C.sub,
                border: `1px solid ${C.line}`, borderRadius: 8, padding: 10,
                fontSize: 11.5, fontFamily: "ui-monospace, monospace", resize: "vertical",
              }}
              aria-label="鑑定プロンプト"
            />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10, alignItems: "center" }}>
              <button style={accentBtn(true)} onClick={() => copyText("prompt", prompt)}>
                {copied === "prompt" ? "コピーしました ✓" : "プロンプトをコピー"}
              </button>
              {AI_DESTINATIONS.map((d) => (
                <button key={d.id} style={{ ...smallBtn, padding: "8px 12px", fontSize: 12.5 }} onClick={() => sendTo(d.url)}>
                  {d.label} へ →
                </button>
              ))}
              <span style={{ fontSize: 11, color: C.faint }}>※ ボタンはコピーしてからサイトを開きます</span>
              {devApiKeyAvailable() && (
                <button
                  style={{ ...smallBtn, borderColor: C.night, color: C.night }}
                  disabled={loading !== null}
                  onClick={() => runDev(activeSection)}
                >
                  {loading === activeSection.id ? "生成中…" : "（開発用）このアプリで生成"}
                </button>
              )}
            </div>
          </div>
        )}
        {error && <div style={{ marginTop: 10, fontSize: 12.5, color: C.hard }}>{error}</div>}
        {readings.length > 0 && (
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button style={smallBtn} onClick={() => copyText("all", readings.map((r) => `## ${r.label}${r.date ? `（${r.date}）` : ""}\n\n${r.text.trim()}`).join("\n\n"))}>
              {copied === "all" ? "コピーしました ✓" : "生成結果を全文コピー"}
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
