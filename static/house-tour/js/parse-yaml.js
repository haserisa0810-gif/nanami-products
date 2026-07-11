/**
 * nanami-products YAML（detail / full / base）→ House Tour 用チャート
 * クライアント側のみ。計算APIは呼ばない。
 */
import { planetMeta } from "./data/sample-chart.js";

const ANGLE_IDS = new Set(["ASC", "MC", "DSC", "IC", "Vertex"]);

/** 表示する天体（ハウス内モニュメント） */
const TOUR_BODY_IDS = [
  "Sun", "Moon", "Mercury", "Venus", "Mars",
  "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
  "North Node", "South Node", "Chiron",
];

/**
 * @param {string} text YAML 文字列
 * @returns {{ chart: object, warnings: string[] }}
 */
export function parseNatalYaml(text) {
  if (typeof jsyaml === "undefined" || !jsyaml.load) {
    throw new Error("js-yaml が読み込まれていません");
  }
  const raw = String(text || "").trim();
  if (!raw) throw new Error("YAMLが空です");

  let doc;
  try {
    doc = jsyaml.load(raw);
  } catch (e) {
    throw new Error("YAMLの解析に失敗しました: " + (e.message || e));
  }
  if (!doc || typeof doc !== "object") {
    throw new Error("YAMLオブジェクトを取得できませんでした");
  }

  return chartFromDoc(doc);
}

/**
 * 既にパース済みのオブジェクトからチャートを構築
 */
export function chartFromDoc(doc) {
  const warnings = [];
  const natal =
    (doc.systems && doc.systems.western && doc.systems.western.natal) ||
    (doc.western && doc.western.natal) ||
    null;

  if (!natal || !natal.bodies) {
    throw new Error(
      "systems.western.natal.bodies が見つかりません。出生図（western natal）入りのYAMLを貼ってください。"
    );
  }

  const input = doc.input || {};
  const calc = doc.calculation || {};
  const housesMap = { 1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: [], 8: [], 9: [], 10: [], 11: [], 12: [] };
  const bodyDetails = {};

  const bodies = natal.bodies;
  Object.keys(bodies).forEach((id) => {
    const b = bodies[id];
    if (!b || typeof b !== "object") return;
    if (ANGLE_IDS.has(id)) return;
    if (TOUR_BODY_IDS.indexOf(id) < 0) {
      // 小惑星など: メタがあれば取り込む余地を残し、当面スキップ（ChironはTOURに含む）
      if (!planetMeta[id] && id !== "Chiron") return;
    }
    const house = parseInt(b.house, 10);
    if (!(house >= 1 && house <= 12)) {
      warnings.push(id + " のハウス番号が不正です（" + b.house + "）");
      return;
    }
    housesMap[house].push(id);
    bodyDetails[id] = {
      id,
      house,
      sign: b.sign || "",
      sign_ja: b.sign_ja || b.sign || "",
      degree: typeof b.degree === "number" ? b.degree : parseFloat(b.degree) || 0,
      retrograde: !!b.retrograde,
      absolute_longitude: b.absolute_longitude,
    };
  });

  // 各ハウス内は degree でソート（安定配置）
  for (let h = 1; h <= 12; h++) {
    housesMap[h].sort((a, b) => {
      const da = (bodyDetails[a] && bodyDetails[a].degree) || 0;
      const db = (bodyDetails[b] && bodyDetails[b].degree) || 0;
      return da - db;
    });
  }

  const asc = bodies.ASC || null;
  const mc = bodies.MC || null;

  // カスプ
  const cusps = {};
  if (natal.houses) {
    Object.keys(natal.houses).forEach((k) => {
      const n = parseInt(k, 10);
      if (n >= 1 && n <= 12 && natal.houses[k]) {
        cusps[n] = {
          sign_ja: natal.houses[k].sign_ja || natal.houses[k].sign || "",
          degree: natal.houses[k].degree,
        };
      }
    });
  }

  const houseSystem =
    calc.house_system === "P" || calc.house_system === "Placidus"
      ? "Placidus"
      : calc.house_system || "Placidus";

  const chart = {
    name: input.title || doc.meta && doc.meta.profile_id || "読み込みチャート",
    name_en: "Loaded Natal Chart",
    birth_date: input.birth_date || "",
    birth_time: input.birth_time || input.calculation_time || "",
    birth_place:
      input.birth_place ||
      input.prefecture ||
      "",
    house_system: houseSystem,
    note: "YAMLから読み込み（クライアント側のみ・再計算なし）",
    source: "yaml",
    angles: {
      ASC: asc
        ? { sign_ja: asc.sign_ja || asc.sign || "", degree: asc.degree }
        : null,
      MC: mc
        ? { sign_ja: mc.sign_ja || mc.sign || "", degree: mc.degree }
        : null,
    },
    cusps,
    houses: housesMap,
    bodyDetails,
  };

  const totalBodies = Object.keys(bodyDetails).length;
  if (totalBodies === 0) {
    throw new Error("配置できる天体がありませんでした");
  }

  return { chart, warnings, bodyCount: totalBodies };
}
