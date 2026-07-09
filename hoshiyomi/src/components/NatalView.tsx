import { C, SIGN_GLYPH, PLANET, ASPECT, fmtDeg } from "../theme";
import type { ChartData } from "../lib/parseYaml";
import { Eyebrow, H2, Panel } from "./common";

export default function NatalView({
  data,
  horoscopeSvg,
}: {
  data: ChartData;
  horoscopeSvg?: string;
}) {
  const natal = data.natal;
  const bodies = Object.entries(natal.bodies);
  const el = natal.summary.elements;
  const mo = natal.summary.modes;
  const bar = (label: string, val: number, max: number, color: string) => (
    <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
      <span style={{ width: 44, fontSize: 12, color: C.sub }}>{label}</span>
      <div style={{ flex: 1, height: 8, background: C.panel2, borderRadius: 4, overflow: "hidden" }}>
        <div style={{ width: `${(val / max) * 100}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
      <span style={{ width: 16, fontSize: 12, color: C.text, textAlign: "right" }}>{val}</span>
    </div>
  );
  const tightAspects = natal.aspects.filter((a) => a.orb <= 2.2);
  return (
    <div>
      {/* 同梱 horoscope.svg（§11.2）— 無ければ天体テーブルのみ */}
      {horoscopeSvg && (
        <Panel style={{ marginBottom: 16, textAlign: "center" }}>
          <Eyebrow>Horoscope Chart</Eyebrow>
          <img
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(horoscopeSvg)}`}
            alt="ホロスコープ図"
            style={{ maxWidth: "min(520px, 100%)", height: "auto" }}
          />
        </Panel>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(300px,1.4fr) minmax(240px,1fr)", gap: 16 }} className="grid-collapse">
        <Panel>
          <Eyebrow>Natal Bodies</Eyebrow>
          <H2>天体配置</H2>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
            <thead>
              <tr style={{ color: C.faint, fontSize: 11, letterSpacing: "0.1em" }}>
                {["天体", "サイン", "度数", "ハウス", ""].map((h, i) => (
                  <th key={i} style={{ textAlign: "left", padding: "4px 6px", borderBottom: `1px solid ${C.line}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodies.map(([k, b]) => (
                <tr key={k} style={{ borderBottom: `1px solid ${C.line}55` }}>
                  <td style={{ padding: "6px" }}>
                    <span style={{ color: C.conj, marginRight: 6, fontSize: 15 }}>{PLANET[k]?.g}</span>
                    {PLANET[k]?.ja || k}
                  </td>
                  <td style={{ padding: "6px" }}>
                    <span style={{ marginRight: 4 }}>{SIGN_GLYPH[b.sign_ja]}</span>
                    {b.sign_ja}
                  </td>
                  <td style={{ padding: "6px", color: C.sub }}>{fmtDeg(b.degree)}</td>
                  <td style={{ padding: "6px", color: C.sub }}>{b.house}室</td>
                  <td style={{ padding: "6px", color: C.hard, fontSize: 11 }}>{b.retrograde ? "R" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Panel>
            <Eyebrow>Balance</Eyebrow>
            <H2>エレメント / モード</H2>
            {bar("火", el.fire, 6, C.dawn)}
            {bar("地", el.earth, 6, C.conj)}
            {bar("風", el.air, 6, C.day)}
            {bar("水", el.water, 6, C.night)}
            <div style={{ height: 10 }} />
            {bar("活動", mo.cardinal, 6, C.day)}
            {bar("固定", mo.fixed, 6, C.dawn)}
            {bar("柔軟", mo.mutable, 6, C.night)}
            <div style={{ marginTop: 12, fontSize: 12.5, color: C.sub }}>
              強調サイン: {natal.summary.dominant_signs.map((s) => `${s.sign_ja}(${s.count})`).join(" / ")}
            </div>
          </Panel>
          <Panel>
            <Eyebrow>Asteroids</Eyebrow>
            <H2>小惑星</H2>
            {Object.entries(data.asteroids).map(([k, b]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "4px 0", borderBottom: `1px solid ${C.line}44` }}>
                <span>
                  <span style={{ color: C.night, marginRight: 6 }}>{PLANET[k]?.g}</span>
                  {PLANET[k]?.ja || k}
                </span>
                <span style={{ color: C.sub }}>
                  {SIGN_GLYPH[b.sign_ja]} {b.sign_ja} {fmtDeg(b.degree)} / {b.house}室{b.retrograde ? " R" : ""}
                </span>
              </div>
            ))}
          </Panel>
        </div>
      </div>
      <Panel style={{ marginTop: 16 }}>
        <Eyebrow>Natal Aspects (orb ≤ 2.2)</Eyebrow>
        <H2>主要アスペクト</H2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {tightAspects.map((a, i) => {
            const info = ASPECT[a.aspect];
            const b1 = PLANET[a.body1] || { ja: a.body1 };
            const b2 = PLANET[a.body2] || { ja: a.body2 };
            return (
              <span key={i} style={{ fontSize: 12.5, background: C.panel2, border: `1px solid ${C.line}`, borderLeft: `3px solid ${info.color}`, borderRadius: 6, padding: "4px 9px" }}>
                {b1.ja} <span style={{ color: info.color }}>{info.g}</span> {b2.ja}{" "}
                <span style={{ color: C.faint, fontSize: 10 }}>orb {a.orb.toFixed(2)}</span>
              </span>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}
