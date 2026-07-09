import type { CSSProperties } from "react";
import { C, SERIF, SANS, SIGN_GLYPH, PLANET, ASPECT, TP, fmtDeg, fmtDate } from "../theme";
import type { ChartData } from "../lib/parseYaml";
import { Eyebrow, H2, Panel, AspectChip } from "./common";

const navBtn = (disabled: boolean): CSSProperties => ({
  background: C.panel,
  border: `1px solid ${C.line}`,
  color: disabled ? C.faint : C.text,
  borderRadius: 8,
  width: 34,
  height: 34,
  cursor: disabled ? "default" : "pointer",
  fontSize: 15,
});

export default function DayDetail({
  data,
  date,
  onNavigate,
  onAskAI,
}: {
  data: ChartData;
  date: string;
  onNavigate: (date: string) => void;
  onAskAI: (date: string) => void;
}) {
  const { daily, summary } = data.transit;
  const idx = daily.findIndex((d) => d.date === date);
  const day = daily[idx];
  if (!day) return null;
  const keyInfo = summary.key_dates.find((k) => k.date === date);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => idx > 0 && onNavigate(daily[idx - 1].date)} disabled={idx === 0} style={navBtn(idx === 0)}>←</button>
          <div>
            <div style={{ fontFamily: SERIF, fontSize: 24, letterSpacing: "0.08em" }}>{fmtDate(date)}</div>
            {keyInfo && <div style={{ fontSize: 12, color: C.conj }}>◆ {keyInfo.theme}</div>}
          </div>
          <button onClick={() => idx < daily.length - 1 && onNavigate(daily[idx + 1].date)} disabled={idx === daily.length - 1} style={navBtn(idx === daily.length - 1)}>→</button>
        </div>
        <button
          onClick={() => onAskAI(date)}
          style={{ background: "transparent", border: `1px solid ${C.dawn}`, color: C.dawn, borderRadius: 8, padding: "7px 14px", cursor: "pointer", fontSize: 13, fontFamily: SANS }}
        >
          この日をAIに読ませる →
        </button>
      </div>

      {/* 朝・昼・夜の帯 — シグネチャ要素 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 16 }} className="grid-collapse">
        {day.moon_timepoints.map((tp) => {
          const t = TP[tp.label];
          return (
            <div key={tp.label} style={{ background: t.grad, border: `1px solid ${C.line}`, borderTop: `2px solid ${t.color}`, borderRadius: 10, padding: "14px 14px 12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span style={{ fontFamily: SERIF, fontSize: 17, color: t.color, letterSpacing: "0.15em" }}>{t.ja}</span>
                <span style={{ fontSize: 10, color: C.faint }}>{t.time}</span>
              </div>
              <div style={{ fontSize: 14, marginTop: 8 }}>
                ☽ {SIGN_GLYPH[tp.sign_ja]} {tp.sign_ja} {fmtDeg(tp.degree)}
              </div>
              <div style={{ fontSize: 11.5, color: C.sub, marginTop: 2 }}>{tp.house}室</div>
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                {tp.aspects.length === 0 ? (
                  <span style={{ fontSize: 11, color: C.faint }}>月のタイトなアスペクトなし</span>
                ) : (
                  tp.aspects.map((a, i) => {
                    const info = ASPECT[a.aspect];
                    const n = PLANET[a.natal_body] || { ja: a.natal_body };
                    return (
                      <span key={i} style={{ fontSize: 12 }}>
                        <span style={{ color: info.color }}>{info.g}</span> N{n.ja}（{info.ja} orb {a.orb.toFixed(2)}）
                      </span>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 16 }} className="grid-collapse">
        <Panel>
          <Eyebrow>Transit → Natal</Eyebrow>
          <H2>この日のアスペクト</H2>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {[...day.natal_aspects].sort((a, b) => a.orb - b.orb).map((a, i) => (
              <div key={i}><AspectChip a={a} /></div>
            ))}
          </div>
        </Panel>
        <Panel>
          <Eyebrow>Transiting Bodies (12:00)</Eyebrow>
          <H2>運行天体</H2>
          {Object.entries(day.transiting_bodies).map(([k, b]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "4px 0", borderBottom: `1px solid ${C.line}44` }}>
              <span>
                <span style={{ color: C.conj, marginRight: 6 }}>{PLANET[k]?.g}</span>
                {PLANET[k]?.ja || k}
              </span>
              <span style={{ color: C.sub }}>
                {SIGN_GLYPH[b.sign_ja]} {b.sign_ja} {fmtDeg(b.degree)} / {b.house}室
                {b.retrograde ? <span style={{ color: C.hard }}> R</span> : ""}
              </span>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}
