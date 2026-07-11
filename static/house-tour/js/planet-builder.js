/**
 * 天体の配置と見た目（象徴的発光体）
 */
import { planetMeta } from "./data/sample-chart.js";
import { getPlanetTexts, getComboText } from "./i18n.js";

/** 既存の天体メッシュをハウスから除去 */
export function clearPlanets(planetMeshes) {
  if (!planetMeshes) return;
  planetMeshes.forEach((p) => {
    if (p.mesh && p.mesh.parent) p.mesh.parent.remove(p.mesh);
  });
  planetMeshes.length = 0;
}

export function buildPlanets(ctx, houseGroups, bodies) {
  const { THREE } = ctx;
  const planetMeshes = [];
  const pickables = [];

  bodies.forEach((b) => {
    const hg = houseGroups[b.house];
    if (!hg) return;
    const col = new THREE.Color(b.color || "#fff");
    const group = new THREE.Group();
    group.name = "planet_" + b.id;
    group.userData = {
      pickable: "planet",
      planetId: b.id,
      house: b.house,
    };

    // 中心球体
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.42, 18, 18),
      new THREE.MeshStandardMaterial({
        color: col.getHex(),
        emissive: col.getHex(),
        emissiveIntensity: 0.55,
        roughness: 0.3,
        metalness: 0.4,
      })
    );
    group.add(core);

    // ビジュアル差異
    if (b.visual === "expanding_ring" || b.id === "Jupiter" || b.id === "Saturn") {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.75, 0.04, 8, 28),
        new THREE.MeshBasicMaterial({ color: col.getHex(), transparent: true, opacity: 0.55 })
      );
      ring.rotation.x = Math.PI / 2.3;
      group.add(ring);
    }
    if (b.visual === "deep_pulse" || b.id === "Pluto") {
      const shell = new THREE.Mesh(
        new THREE.SphereGeometry(0.62, 14, 14),
        new THREE.MeshBasicMaterial({
          color: col.getHex(),
          transparent: true,
          opacity: 0.18,
          wireframe: true,
        })
      );
      group.add(shell);
    }
    if (b.visual === "electric" || b.id === "Uranus") {
      const spike = new THREE.Mesh(
        new THREE.OctahedronGeometry(0.55, 0),
        new THREE.MeshStandardMaterial({
          color: col.getHex(),
          emissive: col.getHex(),
          emissiveIntensity: 0.4,
          wireframe: true,
        })
      );
      group.add(spike);
    }
    if (b.visual === "mist" || b.id === "Neptune") {
      const haze = new THREE.Mesh(
        new THREE.SphereGeometry(0.7, 12, 12),
        new THREE.MeshBasicMaterial({ color: col.getHex(), transparent: true, opacity: 0.2 })
      );
      group.add(haze);
    }

    // グリフ
    const spr = makeGlyph(THREE, b.glyph || "●", col.getStyle());
    spr.position.y = 0.95;
    group.add(spr);

    // ハウス内の意味ある位置（舞台中央など）へ
    const slots = hg.planetSlots || [];
    const idx = b.indexInHouse || 0;
    if (slots[idx]) {
      group.position.copy(slots[idx]);
    } else if (slots[0]) {
      group.position.copy(slots[0]);
      group.position.x += (idx % 3 - 1) * 1.8;
      group.position.y += Math.floor(idx / 3) * 0.8;
    } else {
      group.position.set(((idx % 3) - 1) * 2.2, 2.8 + (idx % 2) * 0.45, -1.0);
    }
    // 少し大きくして「模型」感を減らす
    group.scale.setScalar(1.35);
    hg.group.add(group);

    // クリック用ヒット球体
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(0.7, 8, 8),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.userData = group.userData;
    group.add(hit);

    planetMeshes.push({
      mesh: group,
      core,
      spin: 0.35 + Math.random() * 0.25,
      bob: 0.12 + Math.random() * 0.08,
      baseY: group.position.y,
      body: b,
    });
    pickables.push(group);
  });

  return { planetMeshes, pickables };
}

function makeGlyph(THREE, text, color) {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 128;
  const ctx = c.getContext("2d");
  ctx.beginPath();
  ctx.arc(64, 64, 48, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(10,11,18,0.8)";
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.font = "bold 48px Cinzel, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 64, 66);
  return new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false })
  );
}

export function animatePlanets(planetMeshes, t, dt, reducedMotion) {
  planetMeshes.forEach((p) => {
    p.mesh.rotation.y += (reducedMotion ? 0 : p.spin) * dt;
    if (!reducedMotion && p.bob) {
      p.mesh.position.y = p.baseY + Math.sin(t * 1.2 + p.baseY) * p.bob;
    }
  });
}

export function planetDetail(planetId, houseNumber, houseData, bodyExtra) {
  const meta = planetMeta[planetId] || { id: planetId, glyph: "?" };
  const planetTexts = getPlanetTexts();
  const text = planetTexts[planetId] || { name: planetId, function: "" };
  const houseTitle = houseData ? houseData.title : "House " + houseNumber;
  const houseShort = houseData ? houseData.short : "";
  const extra = bodyExtra || {};
  let posLine = "";
  // 英語UIでも星座は sign_ja がなければ sign を使う
  const signLabel = extra.sign_en || extra.sign_ja || extra.sign || "";
  if (signLabel || typeof extra.degree === "number") {
    posLine =
      signLabel +
      (typeof extra.degree === "number" ? " " + extra.degree.toFixed(1) + "°" : "") +
      (extra.retrograde ? " R" : "");
  }
  return {
    planetId,
    glyph: meta.glyph,
    name: text.name,
    color: meta.color,
    house: houseNumber,
    houseTitle,
    function: text.function,
    houseTheme: houseShort,
    position: posLine,
    combo: getComboText(planetId, houseNumber),
  };
}
