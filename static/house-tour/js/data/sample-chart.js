/**
 * 固定サンプル出生図 + 天体メタ
 */
export const sampleChart = {
  name: "サンプル・ナナミ",
  name_en: "Sample Natal Chart",
  birth_date: "1990-08-15",
  birth_time: "14:22",
  birth_place: "東京都",
  house_system: "Placidus",
  note: "固定デモ用の架空出生図。鑑定・注文処理とは無関係。",
  source: "sample",
  angles: {
    ASC: { sign_ja: "蠍座", degree: 12.4 },
    MC: { sign_ja: "獅子座", degree: 8.1 },
  },
  houses: {
    1: [],
    2: ["Jupiter"],
    3: [],
    4: [],
    5: ["Sun", "Saturn"],
    6: ["Mercury", "Venus", "Mars"],
    7: ["Uranus", "Pluto"],
    8: [],
    9: ["Neptune"],
    10: [],
    11: ["Moon"],
    12: [],
  },
  bodyDetails: {},
};

/** 天体の見た目・基本メタ（言語非依存）
 * 色は発光オーブ用パレット（黄金太陽・銀月など）
 */
export const planetMeta = {
  Sun: { id: "Sun", glyph: "☉", color: "#ffd700", visual: "warm_core" },
  Moon: { id: "Moon", glyph: "☽", color: "#cccccc", visual: "silver_sphere" },
  Mercury: { id: "Mercury", glyph: "☿", color: "#88ccff", visual: "letters" },
  Venus: { id: "Venus", glyph: "♀", color: "#ff99cc", visual: "curves" },
  Mars: { id: "Mars", glyph: "♂", color: "#ff4444", visual: "sparks" },
  Jupiter: { id: "Jupiter", glyph: "♃", color: "#e8a84a", visual: "expanding_ring" },
  Saturn: { id: "Saturn", glyph: "♄", color: "#c4b48a", visual: "structure" },
  Uranus: { id: "Uranus", glyph: "♅", color: "#55e0e8", visual: "electric" },
  Neptune: { id: "Neptune", glyph: "♆", color: "#4488ee", visual: "mist" },
  Pluto: { id: "Pluto", glyph: "♇", color: "#aa3366", visual: "deep_pulse" },
  "North Node": { id: "North Node", glyph: "☊", color: "#90a0c0", visual: "structure" },
  "South Node": { id: "South Node", glyph: "☋", color: "#706858", visual: "structure" },
  Chiron: { id: "Chiron", glyph: "⚷", color: "#c080a0", visual: "curves" },
};

/**
 * チャートオブジェクトから表示用 body リストを生成
 * @param {object} chart sampleChart と同型
 */
export function bodiesFromChart(chart) {
  const list = [];
  if (!chart || !chart.houses) return list;
  const details = chart.bodyDetails || {};
  Object.keys(chart.houses).forEach((hn) => {
    const n = parseInt(hn, 10);
    (chart.houses[hn] || []).forEach((id, idx) => {
      const meta = planetMeta[id] || {
        id,
        glyph: "●",
        color: "#c9a96e",
        visual: "warm_core",
      };
      const d = details[id] || {};
      list.push({
        ...meta,
        house: n,
        indexInHouse: idx,
        sign_ja: d.sign_ja || "",
        degree: d.degree,
        retrograde: !!d.retrograde,
      });
    });
  });
  return list;
}

/** @deprecated use bodiesFromChart(sampleChart) */
export function bodiesInChart() {
  return bodiesFromChart(sampleChart);
}
