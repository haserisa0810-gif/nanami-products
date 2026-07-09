import type { CSSProperties, ReactNode } from "react";
import { C, SERIF, ASPECT, PLANET } from "../theme";
import type { TransitAspect } from "../lib/parseYaml";

export const Eyebrow = ({ children }: { children: ReactNode }) => (
  <div style={{ fontSize: 11, letterSpacing: "0.28em", color: C.faint, textTransform: "uppercase", marginBottom: 6 }}>
    {children}
  </div>
);

export const H2 = ({ children }: { children: ReactNode }) => (
  <h2 style={{ fontFamily: SERIF, fontSize: 22, fontWeight: 600, color: C.text, margin: "0 0 14px", letterSpacing: "0.06em" }}>
    {children}
  </h2>
);

export const Panel = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => (
  <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: 18, ...style }}>
    {children}
  </div>
);

export const AspectChip = ({ a, dense }: { a: TransitAspect; dense?: boolean }) => {
  const info = ASPECT[a.aspect];
  const t = PLANET[a.transit_body] || { g: "", ja: a.transit_body };
  const n = PLANET[a.natal_body] || { g: "", ja: a.natal_body };
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 5, fontSize: dense ? 11 : 12.5,
        background: C.panel2, border: `1px solid ${C.line}`, borderLeft: `3px solid ${info.color}`,
        borderRadius: 6, padding: dense ? "3px 7px" : "4px 9px", color: C.text, whiteSpace: "nowrap",
      }}
    >
      <span style={{ color: C.sub }}>T</span>{t.ja}
      <span style={{ color: info.color, fontSize: dense ? 12 : 14 }}>{info.g}</span>
      <span style={{ color: C.sub }}>N</span>{n.ja}
      <span style={{ color: C.faint, fontSize: 10 }}>orb {a.orb.toFixed(2)}</span>
    </span>
  );
};
