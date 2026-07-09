/* デザイントークン — 「夜の暦」テーマ（引き継ぎ§5準拠、変更禁止） */

export const C = {
  bg: "#14161E",
  panel: "#1C2030",
  panel2: "#232840",
  line: "#2E3348",
  text: "#E8E4D8",
  sub: "#9BA0B2",
  faint: "#6C7183",
  dawn: "#E8A87C",
  day: "#86BFCB",
  night: "#A79BD4",
  good: "#8FBF9F",
  hard: "#D98A93",
  conj: "#D4B475",
} as const;

export const SERIF =
  '"Shippori Mincho","Hiragino Mincho ProN","Yu Mincho","BIZ UDMincho",serif';
export const SANS =
  '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif';

export const SIGN_GLYPH: Record<string, string> = {
  牡羊座: "♈", 牡牛座: "♉", 双子座: "♊", 蟹座: "♋",
  獅子座: "♌", 乙女座: "♍", 天秤座: "♎", 蠍座: "♏",
  射手座: "♐", 山羊座: "♑", 水瓶座: "♒", 魚座: "♓",
};

export const PLANET: Record<string, { g: string; ja: string }> = {
  Sun: { g: "☉", ja: "太陽" },
  Moon: { g: "☽", ja: "月" },
  Mercury: { g: "☿", ja: "水星" },
  Venus: { g: "♀", ja: "金星" },
  Mars: { g: "♂", ja: "火星" },
  Jupiter: { g: "♃", ja: "木星" },
  Saturn: { g: "♄", ja: "土星" },
  Uranus: { g: "♅", ja: "天王星" },
  Neptune: { g: "♆", ja: "海王星" },
  Pluto: { g: "♇", ja: "冥王星" },
  "North Node": { g: "☊", ja: "Nノード" },
  "South Node": { g: "☋", ja: "Sノード" },
  ASC: { g: "AC", ja: "ASC" },
  MC: { g: "MC", ja: "MC" },
  Lilith: { g: "⚸", ja: "リリス" },
  Chiron: { g: "⚷", ja: "キロン" },
  Ceres: { g: "⚳", ja: "セレス" },
  Pallas: { g: "⚴", ja: "パラス" },
  Juno: { g: "⚵", ja: "ジュノー" },
  Vesta: { g: "⚶", ja: "ベスタ" },
  Vertex: { g: "Vx", ja: "バーテックス" },
};

export type AspectName =
  | "conjunction"
  | "opposition"
  | "square"
  | "trine"
  | "sextile";

export const ASPECT: Record<
  AspectName,
  { g: string; ja: string; color: string; tone: "neutral" | "good" | "hard" }
> = {
  conjunction: { g: "☌", ja: "合", color: C.conj, tone: "neutral" },
  opposition: { g: "☍", ja: "オポジション", color: C.hard, tone: "hard" },
  square: { g: "□", ja: "スクエア", color: C.hard, tone: "hard" },
  trine: { g: "△", ja: "トライン", color: C.good, tone: "good" },
  sextile: { g: "⚹", ja: "セクスタイル", color: C.good, tone: "good" },
};

export type TimepointLabel = "morning" | "noon" | "night";

export const TP: Record<
  TimepointLabel,
  { ja: string; time: string; color: string; grad: string }
> = {
  morning: { ja: "朝", time: "6:00", color: C.dawn, grad: "linear-gradient(160deg,#2A2333,#3A2C33)" },
  noon: { ja: "昼", time: "12:00", color: C.day, grad: "linear-gradient(160deg,#1E2A38,#22333C)" },
  night: { ja: "夜", time: "21:00", color: C.night, grad: "linear-gradient(160deg,#1E2038,#262042)" },
};

export const fmtDeg = (d: number): string => {
  // 分を先に丸めてから度へ繰り上げる（15.9952 → 16°00′。floor+round だと 15°60′ になる）
  const total = Math.round(d * 60);
  return `${Math.floor(total / 60)}°${String(total % 60).padStart(2, "0")}′`;
};

export const wdJa = ["日", "月", "火", "水", "木", "金", "土"];

export const fmtDate = (s: string): string => {
  const [y, m, d] = s.split("-").map(Number);
  return `${m}/${d}(${wdJa[new Date(y, m - 1, d).getDay()]})`;
};
