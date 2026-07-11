/**
 * Planet texts + house combinations (English)
 * Non-fatalistic wording only.
 */
export const planetTextsEn = {
  Sun: { name: "Sun", function: "Core self, vitality, and how you shine" },
  Moon: { name: "Moon", function: "Emotional rhythm, needs, and instinctive responses" },
  Mercury: { name: "Mercury", function: "Thinking, language, and handling information" },
  Venus: { name: "Venus", function: "Taste, harmony, and what you are drawn to" },
  Mars: { name: "Mars", function: "Drive, heat, and how you direct will" },
  Jupiter: { name: "Jupiter", function: "Growth, expansion, and widening belief" },
  Saturn: { name: "Saturn", function: "Structure, responsibility, and building over time" },
  Uranus: { name: "Uranus", function: "Renewal, freedom, and unexpected turns" },
  Neptune: { name: "Neptune", function: "Imagination, dissolving edges, ideals" },
  Pluto: { name: "Pluto", function: "Deep change, intensity, release and renewal" },
  "North Node": {
    name: "North Node",
    function: "Growth direction — themes that develop through practice",
  },
  "South Node": {
    name: "South Node",
    function: "Familiar patterns — skills to integrate or gently release",
  },
  Chiron: { name: "Chiron", function: "Wound and healing — weakness that can become teaching" },
};

export const planetHouseComboEn = {
  "Jupiter:2":
    "Jupiter speaks of growth and expansion. In the 2nd house, values, talents, and a sense of security may be cultivated more generously over time.",
  "Sun:5":
    "The Sun is the center of self. In the 5th house, creativity, play, and self-expression become paths for showing who you are.",
  "Saturn:5":
    "Saturn brings structure and time. In the 5th, joy and expression may come with responsibility — play maturing into craft.",
  "Mercury:6":
    "Mercury is mind and speech. In the 6th, it often works as skill: analyzing daily work and refining habits.",
  "Venus:6":
    "Venus seeks harmony and preference. In the 6th, care for routine and people may carry a sense of beauty and comfort.",
  "Mars:6":
    "Mars is action and heat. In the 6th, energy may go into practical tasks, health care, and learning technique.",
  "Uranus:7":
    "Uranus seeks freedom and refresh. In the 7th, one-to-one bonds and agreements may be redesigned in unconventional ways.",
  "Pluto:7":
    "Pluto is deep transformation. In the 7th, dialogue and boundaries with others can redefine the relationship itself.",
  "Neptune:9":
    "Neptune is imagination and ideal. In the 9th, worldview and far horizons may be sought with soft, poetic edges.",
  "Moon:11":
    "The Moon seeks emotional safety. In the 11th, belonging may be felt among peers, groups, and shared futures.",
  "Sun:9":
    "The Sun is the core self. In the 9th, meaning, belief, and wider horizons can become a stage for vitality.",
  "Saturn:9":
    "Saturn builds over time. In the 9th, philosophy or long-range goals may be shaped with discipline and structure.",
  "Mercury:8":
    "Mercury thinks and names. In the 8th, curiosity may go toward shared resources, depth, and what is usually private.",
  "Venus:8":
    "Venus relates through attraction. In the 8th, closeness and shared value can feel intense and transformative.",
  "Mars:8":
    "Mars acts with heat. In the 8th, drive may touch deep bonds, crisis, and the courage to change.",
  "Pluto:8":
    "Pluto transforms. In the 8th, themes of sharing, release, and renewal may run especially deep.",
  "Jupiter:10":
    "Jupiter expands. In the 10th, public role, vocation, and reputation may open toward growth and visibility.",
  "Neptune:10":
    "Neptune dissolves and idealizes. In the 10th, calling and public image may carry inspiration — and fog to clarify.",
  "Uranus:11":
    "Uranus renews. In the 11th, networks and future ideals may shift suddenly or favor unconventional communities.",
  "Moon:5":
    "The Moon feels and responds. In the 5th, emotional life may color creativity, play, romance, and joyful expression.",
  "North Node:12":
    "The North Node points to growth. In the 12th, development may involve rest, the unseen, and soft release of control.",
  "South Node:6":
    "The South Node is familiar skill. In the 6th, practical service and routine may feel natural — and worth balancing.",
};

export function comboTextEn(planetId, houseNumber) {
  const key = planetId + ":" + houseNumber;
  if (planetHouseComboEn[key]) return planetHouseComboEn[key];
  const p = planetTextsEn[planetId];
  const name = p ? p.name : planetId;
  const fn = p ? p.function : "";
  return (
    name +
    " relates to “" +
    fn +
    ".” In house " +
    houseNumber +
    ", that quality may color this life area. Read it as a tendency, not a fixed fate."
  );
}
