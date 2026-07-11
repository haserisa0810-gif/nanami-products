/**
 * 天体の基本機能 + ハウス組み合わせの短い説明（断定的な運命判断はしない）
 */
export const planetTextsJa = {
  Sun: {
    name: "太陽",
    function: "自分の中心・生命感・自己表現の核",
  },
  Moon: {
    name: "月",
    function: "感情のリズム・安心の求め方・反応の癖",
  },
  Mercury: {
    name: "水星",
    function: "思考・言葉・情報の扱い方",
  },
  Venus: {
    name: "金星",
    function: "好み・調和・惹かれるものとの関係",
  },
  Mars: {
    name: "火星",
    function: "行動・熱・意志の向け方",
  },
  Jupiter: {
    name: "木星",
    function: "広がり・成長・信念の拡張",
  },
  Saturn: {
    name: "土星",
    function: "構造・責任・時間をかけて築く力",
  },
  Uranus: {
    name: "天王星",
    function: "刷新・自由・思いがけない展開",
  },
  Neptune: {
    name: "海王星",
    function: "想像・溶解・理想や境界のあいまいさ",
  },
  Pluto: {
    name: "冥王星",
    function: "深層の変容・強度・手放しと再生",
  },
  "North Node": {
    name: "北交点",
    function: "成長の方向・これから育てやすいテーマ",
  },
  "South Node": {
    name: "南交点",
    function: "慣れ親しんだパターン・手放しや統合のテーマ",
  },
  Chiron: {
    name: "キロン",
    function: "傷と癒し・教えに変わる弱さ",
  },
};

/**
 * planetId + houseNumber の組み合わせ説明
 * ない場合は genericCombo を使う
 */
export const planetHouseComboJa = {
  "Jupiter:2":
    "木星は「広がりと成長」を表します。第2ハウスでは、価値観や才能、安心の基盤を、少しずつ豊かに育てようとする傾向が現れやすいです。",
  "Sun:5":
    "太陽は「自分の中心」を表します。第5ハウスでは、創作、遊び、自己表現を通して、自分らしさを外へ出そうとします。",
  "Saturn:5":
    "土星は「構造と時間」を表します。第5ハウスでは、喜びや表現にも責任や熟成が伴い、遊びを真剣な技へ育てる流れが生まれやすいです。",
  "Mercury:6":
    "水星は「思考と言葉」を表します。第6ハウスでは、日常の仕事や習慣を分析し、整えるための技能として働きやすいです。",
  "Venus:6":
    "金星は「調和と好み」を表します。第6ハウスでは、日々の整え方や対人の作法に、美意識や心地よさが染み込みやすいです。",
  "Mars:6":
    "火星は「行動と熱」を表します。第6ハウスでは、実務や健康のケア、技術の習得へエネルギーが向きやすいです。",
  "Uranus:7":
    "天王星は「刷新と自由」を表します。第7ハウスでは、一対一の関係や契約のあり方に、型破りな更新や距離感の再設計が現れやすいです。",
  "Pluto:7":
    "冥王星は「深い変容」を表します。第7ハウスでは、他者との境界や対話を通して、関係そのものが強度を帯び、再定義されやすいです。",
  "Neptune:9":
    "海王星は「想像と理想」を表します。第9ハウスでは、世界観や信念、遠い地平への憧れが、詩的で境界の柔らかい探求として現れやすいです。",
  "Moon:11":
    "月は「感情の安心」を表します。第11ハウスでは、仲間や共同体、共有された未来のなかで、心の居場所を感じやすいです。",
};

export function comboText(planetId, houseNumber) {
  const key = planetId + ":" + houseNumber;
  if (planetHouseComboJa[key]) return planetHouseComboJa[key];
  const p = planetTextsJa[planetId];
  const name = p ? p.name : planetId;
  const fn = p ? p.function : "";
  return (
    name +
    "は「" +
    fn +
    "」を表します。第" +
    houseNumber +
    "ハウスのテーマと重なると、その領域でこの天体の質が現れやすくなります。断定ではなく、傾向として読んでください。"
  );
}
