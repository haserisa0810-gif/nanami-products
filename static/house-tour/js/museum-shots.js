/**
 * 各ハウスの「映画的案内」ショット列を生成
 * 遠景 → 近づく → 入口 → 展示物 → まとめ
 */
import { housePosition, EYE_H } from "./scene.js";

/**
 * @param {number} n house 1-12 or 0 core
 * @param {object} houseGroup
 * @param {object} THREE
 * @param {object} housesData
 * @param {string} lang 'ja' | 'en'
 */
export function buildShotsForHouse(n, houseGroup, THREE, housesData, lang) {
  const en = lang === "en";

  if (n === 0) {
    return [
      {
        position: { x: 0, y: 14, z: 28 },
        lookAt: { x: 0, y: 1.5, z: 0 },
        duration: 3.2,
        label: en ? "Birth Chart Museum — Courtyard" : "Birth Chart Museum — 中庭",
        caption: en
          ? "This is the courtyard of your chart. Twelve galleries stand in a ring."
          : "ここは出生図の中庭です。12の展示室が円環に並んでいます。",
      },
      {
        position: { x: 10, y: 4, z: 12 },
        lookAt: { x: 0, y: 1.5, z: 0 },
        duration: 2.6,
        label: en ? "The ring of rooms" : "円環の展示",
        caption: en
          ? "Each house is a room of life. We visit them in order."
          : "各ハウスは「人生の部屋」。順番に巡ります。",
      },
      {
        position: { x: 0, y: EYE_H, z: 8 },
        lookAt: { x: 0, y: 1.5, z: 0 },
        duration: 2.0,
        label: en ? "Ready to begin" : "ツアー開始の位置",
        caption: en
          ? "Press Next to go to the entrance of House 1."
          : "「次へ」で第1ハウスの入口へ進みます。",
      },
    ];
  }

  const h = housesData[n] || {};
  const title = h.title || (en ? "House " + n : "第" + n + "ハウス");
  const space = h.spaceLabel || title;
  const group = houseGroup && houseGroup.group;
  if (!group) return defaultApproach(n, THREE, title, space, en);

  const toWorld = (x, y, z) => {
    const v = new THREE.Vector3(x, y, z);
    group.updateMatrixWorld(true);
    group.localToWorld(v);
    return { x: v.x, y: v.y, z: v.z };
  };

  const arch = houseGroup.arch || { entryZ: 8, w: 16, d: 20, h: 8 };
  const ez = arch.entryZ != null ? arch.entryZ : 8;
  const centerWorld = housePosition(n, THREE);

  const far = toWorld(0, Math.min(12, arch.h * 0.55 + 4), ez + 32);
  const mid = toWorld(0, 4.5, ez + 16);
  const door = toWorld(0, 2.4, ez + 4);
  const foyer = toWorld(0, 2.2, ez * 0.35);
  const interior = toWorld(0, 2.3, -Math.min(4, arch.d * 0.15));

  const shots = [
    {
      position: far,
      lookAt: { x: centerWorld.x, y: arch.h * 0.35, z: centerWorld.z },
      duration: 3.0,
      label: en ? title + " — far view" : title + " — 遠景",
      caption: en
        ? "This is " + title + (space ? " (" + space + ")" : "") + "."
        : "こちらが" + title + "です。" + (space ? "（" + space + "）" : ""),
    },
    {
      position: mid,
      lookAt: toWorld(0, arch.h * 0.35, 0),
      duration: 2.5,
      label: en ? "Approaching" : "近づく",
      caption: en
        ? "We approach so you can see the building as a whole."
        : "建物の姿を確認しながら、入口へ進みます。",
    },
    {
      position: door,
      lookAt: toWorld(0, 2.2, -2),
      duration: 2.2,
      label: en ? "Entrance" : "入口",
      caption: en
        ? "The gallery entrance. Symbolic exhibits wait inside."
        : "展示室の入口です。中には象徴的な展示が並びます。",
    },
  ];

  const exhibits = houseGroup.exhibits || [];
  exhibits.slice(0, 5).forEach((ex) => {
    const p = toWorld(ex.x, ex.y, ex.z);
    const cam2 = toWorld(
      ex.x * 0.4 + (ex.x >= 0 ? -2.5 : 2.5),
      Math.min(4.5, ex.y + 1.2),
      Math.max(ex.z + 4, -arch.d * 0.1)
    );
    const name = en ? ex.nameEn || ex.name : ex.name;
    const cap = en ? ex.captionEn || ex.caption || name : ex.caption || name;
    shots.push({
      position: cam2,
      lookAt: p,
      duration: 2.4,
      label: name || (en ? "Exhibit" : "展示"),
      caption: cap,
    });
  });

  shots.push({
    position: foyer,
    lookAt: interior,
    duration: 2.4,
    label: title,
    caption:
      (h.short ||
        (en
          ? "Sense this room through space and objects."
          : "この展示室のテーマを、空間と物で感じてください。")) +
      (en ? " Press Next for the next house." : " 「次へ」で次のハウスへ。"),
  });

  return shots;
}

function defaultApproach(n, THREE, title, space, en) {
  const pos = housePosition(n, THREE);
  const dir = pos.clone().normalize();
  const far = pos.clone().addScaledVector(dir, -28);
  far.y = 10;
  const mid = pos.clone().addScaledVector(dir, -14);
  mid.y = 4;
  const near = pos.clone().addScaledVector(dir, -6);
  near.y = EYE_H;
  return [
    {
      position: { x: far.x, y: far.y, z: far.z },
      lookAt: { x: pos.x, y: 3, z: pos.z },
      duration: 3,
      label: en ? title + " — far view" : title + " — 遠景",
      caption: en ? "This is " + title + "." : "こちらが" + title + "です。",
    },
    {
      position: { x: mid.x, y: mid.y, z: mid.z },
      lookAt: { x: pos.x, y: 2, z: pos.z },
      duration: 2.5,
      label: space,
      caption: en ? "Approaching the entrance." : "入口へ近づきます。",
    },
    {
      position: { x: near.x, y: near.y, z: near.z },
      lookAt: { x: pos.x, y: 2, z: pos.z },
      duration: 2.2,
      label: title,
      caption: en
        ? "Press Next for the next gallery."
        : "「次へ」で次の展示室へ進めます。",
    },
  ];
}
