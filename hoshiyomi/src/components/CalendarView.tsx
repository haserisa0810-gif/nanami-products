import { C, SERIF, SIGN_GLYPH, ASPECT, wdJa, SANS } from "../theme";
import type { ChartData } from "../lib/parseYaml";
import { Eyebrow, Panel } from "./common";

export default function CalendarView({
  data,
  selected,
  onSelect,
}: {
  data: ChartData;
  selected: string;
  onSelect: (date: string) => void;
}) {
  const { daily, summary, todayDate } = data.transit;
  const first = daily[0].date;
  const [y, m, d] = first.split("-").map(Number);
  const lead = new Date(y, m - 1, d).getDay();
  const cells: (typeof daily[number] | null)[] = [...Array(lead).fill(null), ...daily];
  const cautionSet = new Set(summary.caution_dates);
  const moveSet = new Set(summary.easy_to_move_days);
  const keyMap = Object.fromEntries(summary.key_dates.map((k) => [k.date, k.theme]));
  return (
    <div>
      <Panel style={{ marginBottom: 16 }}>
        <Eyebrow>Overall Theme</Eyebrow>
        <div style={{ fontFamily: SERIF, fontSize: 15.5, lineHeight: 1.9, color: C.text }}>{summary.overall_theme}</div>
        <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 12, color: C.sub, flexWrap: "wrap" }}>
          <span><span style={{ color: C.good }}>●</span> 動きやすい日</span>
          <span><span style={{ color: C.hard }}>●</span> 注意したい日</span>
          <span><span style={{ color: C.conj }}>◆</span> キーデート</span>
        </div>
      </Panel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 6 }}>
        {wdJa.map((w, i) => (
          <div key={w} style={{ textAlign: "center", fontSize: 11, color: i === 0 ? C.hard : i === 6 ? C.day : C.faint, padding: "2px 0", letterSpacing: "0.2em" }}>
            {w}
          </div>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={`b${i}`} />;
          const dt = day.date;
          const isSel = dt === selected;
          const isToday = dt === todayDate;
          const noonMoon = day.transiting_bodies.Moon;
          const hard = day.natal_aspects.filter((a) => ASPECT[a.aspect].tone === "hard" && a.orb <= 1).length;
          const good = day.natal_aspects.filter((a) => ASPECT[a.aspect].tone === "good" && a.orb <= 1).length;
          return (
            <button
              key={dt}
              onClick={() => onSelect(dt)}
              style={{
                background: isSel ? C.panel2 : C.panel,
                border: `1px solid ${isSel ? C.conj : isToday ? C.dawn : C.line}`,
                borderRadius: 8, padding: "8px 6px", cursor: "pointer", textAlign: "left", minHeight: 74,
                color: C.text, fontFamily: SANS, position: "relative", transition: "border-color .15s",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span style={{ fontFamily: SERIF, fontSize: 15 }}>{Number(dt.slice(8))}</span>
                <span style={{ fontSize: 9, color: C.faint }}>{dt.slice(5, 7)}月</span>
              </div>
              <div style={{ fontSize: 11, color: C.sub, marginTop: 2 }}>
                ☽ {SIGN_GLYPH[noonMoon.sign_ja]} {noonMoon.sign_ja.replace("座", "")}
              </div>
              <div style={{ display: "flex", gap: 3, marginTop: 5, alignItems: "center", flexWrap: "wrap" }}>
                {[...Array(good)].map((_, j) => (
                  <span key={`g${j}`} style={{ width: 5, height: 5, borderRadius: 3, background: C.good, display: "inline-block" }} />
                ))}
                {[...Array(hard)].map((_, j) => (
                  <span key={`h${j}`} style={{ width: 5, height: 5, borderRadius: 3, background: C.hard, display: "inline-block" }} />
                ))}
                {keyMap[dt] && <span style={{ color: C.conj, fontSize: 9 }}>◆</span>}
              </div>
              {isToday && <span style={{ position: "absolute", top: 5, right: 6, fontSize: 8, color: C.dawn, letterSpacing: "0.1em" }}>今日</span>}
              {cautionSet.has(dt) && <span style={{ position: "absolute", bottom: 5, right: 6, fontSize: 8, color: C.hard }}>注意</span>}
              {moveSet.has(dt) && !cautionSet.has(dt) && <span style={{ position: "absolute", bottom: 5, right: 6, fontSize: 8, color: C.good }}>動</span>}
            </button>
          );
        })}
      </div>
      <Panel style={{ marginTop: 16 }}>
        <Eyebrow>Action Hints</Eyebrow>
        {summary.action_hints.map((h, i) => (
          <div key={i} style={{ fontSize: 13.5, color: C.sub, lineHeight: 1.9 }}>・{h}</div>
        ))}
      </Panel>
    </div>
  );
}
