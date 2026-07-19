/**
 * 天体の配置と見た目（象徴的発光オーブ）
 * YAML ハウス配置 + サイズ/発光強度 + Additive グロー
 * 第1ハウス: 浮遊神殿ゲート + Dream Sky 風粒子フィールド
 */
import { planetMeta } from "./data/sample-chart.js";
import { getPlanetTexts, getComboText, localizeSign } from "./i18n.js";

/**
 * 天体ごとの相対サイズ・発光強度
 * スニペット比（Sun=1.2 等）を展示スケール ≈0.48 で縮尺。
 */
const ORB_SPECS = {
  Sun: { size: 0.58, intensity: 1.8 }, // 黄金・最大
  Moon: { size: 0.43, intensity: 1.2 }, // 銀
  Mercury: { size: 0.34, intensity: 1.0 },
  Venus: { size: 0.38, intensity: 1.3 },
  Mars: { size: 0.36, intensity: 1.1 },
  Jupiter: { size: 0.52, intensity: 1.25 },
  Saturn: { size: 0.48, intensity: 0.95 },
  Uranus: { size: 0.4, intensity: 1.15 },
  Neptune: { size: 0.4, intensity: 1.1 },
  Pluto: { size: 0.32, intensity: 1.05 },
  "North Node": { size: 0.3, intensity: 0.85 },
  "South Node": { size: 0.3, intensity: 0.8 },
  Chiron: { size: 0.34, intensity: 0.95 },
};

const DEFAULT_ORB = { size: 0.38, intensity: 1.0 };

// ═══════════════════════════════════════════════════════════
// 第1ハウス — 浮遊神殿ゲートウェイ + 粒子フィールド
// ═══════════════════════════════════════════════════════════

/**
 * 浮遊神殿ゲートウェイ（光の構造物）
 * 寸法はスニペット準拠（大アーチ R=8 / 柱 H=12）。
 * 展示室内では enhanceFirstHouse 側で scale 調整する。
 *
 * @param {typeof THREE} THREE
 * @returns {THREE.Group}
 */
export function createSymbolicGate(THREE) {
  const gateGroup = new THREE.Group();
  gateGroup.name = "symbolic_gate_h1";

  // メインアーチ
  const arch = new THREE.Mesh(
    new THREE.TorusGeometry(8, 1.2, 24, 48, Math.PI * 1.8),
    new THREE.MeshPhongMaterial({
      color: 0xeeddaa,
      emissive: 0xccaa77,
      emissiveIntensity: 0.5,
      shininess: 100,
      transparent: true,
      opacity: 0.94,
    })
  );
  arch.rotation.x = Math.PI / 2;
  arch.position.y = 4;
  gateGroup.add(arch);

  // 外側の薄い光輪（Additive）
  const halo = new THREE.Mesh(
    new THREE.TorusGeometry(8.6, 0.18, 8, 48, Math.PI * 1.8),
    new THREE.MeshBasicMaterial({
      color: 0xffe8b0,
      transparent: true,
      opacity: 0.32,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  halo.rotation.x = Math.PI / 2;
  halo.position.y = 4;
  gateGroup.add(halo);

  // 左右の柱
  for (let i = -1; i <= 1; i += 2) {
    const pillar = new THREE.Mesh(
      new THREE.CylinderGeometry(0.8, 1.2, 12, 24),
      new THREE.MeshPhongMaterial({
        color: 0xdddddd,
        emissive: 0xaaaa99,
        emissiveIntensity: 0.4,
        shininess: 70,
      })
    );
    // 柱の中心を y=0 付近に（高さ12 → 底〜頂）
    pillar.position.set(i * 7, 6, -2);
    gateGroup.add(pillar);

    // 柱頭の発光玉
    const cap = new THREE.Mesh(
      new THREE.SphereGeometry(0.9, 16, 16),
      new THREE.MeshPhongMaterial({
        color: 0xffe8b0,
        emissive: 0xffd080,
        emissiveIntensity: 0.75,
        shininess: 90,
      })
    );
    cap.position.set(i * 7, 12.2, -2);
    gateGroup.add(cap);
  }

  // 敷居の光帯
  const sill = new THREE.Mesh(
    new THREE.BoxGeometry(15, 0.15, 1.6),
    new THREE.MeshBasicMaterial({
      color: 0xffe8b0,
      transparent: true,
      opacity: 0.38,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  sill.position.set(0, 0.1, -0.5);
  gateGroup.add(sill);

  return gateGroup;
}

/**
 * Dream Sky 風の粒子フィールド
 * @param {typeof THREE} THREE
 * @param {number} [count=800]
 * @param {number} [color=0x88aaff]
 * @param {{ w?: number, h?: number, d?: number }} [bounds]
 * @returns {THREE.Points}
 */
export function createParticleField(THREE, count, color, bounds) {
  const n = count != null ? count : 800;
  const col = color != null ? color : 0x88aaff;
  const bw = (bounds && bounds.w) || 20;
  const bh = (bounds && bounds.h) || 14;
  const bd = (bounds && bounds.d) || 24;

  const pos = new Float32Array(n * 3);
  const phases = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    pos[i * 3] = (Math.random() - 0.5) * bw;
    pos[i * 3 + 1] = 0.4 + Math.random() * bh;
    pos[i * 3 + 2] = (Math.random() - 0.5) * bd;
    phases[i] = Math.random() * Math.PI * 2;
  }

  const points = new THREE.Points(
    new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
    new THREE.PointsMaterial({
      color: col,
      size: 0.16,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    })
  );
  points.name = "particle_field_h1";
  points.userData = { kind: "star", phases, house: 1 };
  return points;
}

/**
 * 天体名 + body メタからオーブ Group を組み立て（createFirstHouseScene 用）
 * @param {typeof THREE} THREE
 * @param {string} name
 * @param {object} [body]
 * @returns {THREE.Group}
 */
export function createPlanetOrbMesh(THREE, name, body) {
  body = body || {};
  const id = body.id || name || "Sun";
  const meta = planetMeta[id] || {};
  const col = new THREE.Color(body.color || meta.color || "#ffd700");
  const colorHex = col.getHex();
  const spec = ORB_SPECS[id] || DEFAULT_ORB;
  const size = body.size != null ? body.size : spec.size;
  const intensity = body.intensity != null ? body.intensity : spec.intensity;

  const wrap = new THREE.Group();
  wrap.name = "planet_" + id;
  wrap.userData = {
    name: id,
    planetId: id,
    pickable: "planet",
    house: body.house != null ? Number(body.house) : 1,
  };

  const { core, glow } = createPlanetOrb(THREE, colorHex, size, intensity);
  wrap.add(core);

  const spr = makeGlyph(THREE, body.glyph || meta.glyph || "●", col.getStyle());
  spr.position.y = size + 0.55;
  wrap.add(spr);

  wrap.userData._glow = glow;
  wrap.userData._core = core;
  return wrap;
}

/**
 * 第1ハウス装飾を既存グループへ追加（浮遊ゲート + 粒子）。
 * 天体オーブは通常 buildPlanets（YAML）側。placeOrbs=true でここにも配置可。
 *
 * @param {typeof THREE} THREE
 * @param {THREE.Group} houseGroup
 * @param {{ quality?: string, animatables?: array, arch?: object, bodies?: array, placeOrbs?: boolean }} [opts]
 * @returns {{ gate: THREE.Group, particles: THREE.Points|null, orbs: THREE.Group[] }}
 */
export function enhanceFirstHouse(THREE, houseGroup, opts) {
  opts = opts || {};
  const quality = opts.quality || "high";
  const animatables = opts.animatables || null;
  const arch = opts.arch || { w: 18, d: 26, h: 14 };

  const gate = createSymbolicGate(THREE);
  // スニペット: gate.position (0, 1.5, -12) をハウス局所座標へ
  // 入口が +z なので、ゲートは奥寄り（-z）に置く
  const gateScale = opts.gateScale != null ? opts.gateScale : 0.72;
  gate.scale.setScalar(gateScale);
  gate.position.set(0, 1.5 * gateScale, -Math.min(arch.d * 0.35, 10));
  houseGroup.add(gate);

  if (animatables) {
    animatables.push({
      mesh: gate,
      kind: "bob",
      baseY: gate.position.y,
      speed: 0.35,
      amp: 0.1,
    });
    // 光輪をゆっくり回転（children[1] = halo）
    if (gate.children[1]) {
      animatables.push({ mesh: gate.children[1], kind: "spin", speed: 0.12 });
    }
  }

  let particles = null;
  if (quality !== "low") {
    const count = quality === "high" ? 800 : 320;
    particles = createParticleField(THREE, count, 0x88aaff, {
      w: arch.w * 1.1,
      h: arch.h + 2,
      d: arch.d * 1.0,
    });
    houseGroup.add(particles);
    if (animatables) {
      animatables.push({ mesh: particles, kind: "particles", house: 1 });
    }
  }

  // オプション: 第1ハウス天体をゲート前に浮遊配置
  const orbs = [];
  if (opts.placeOrbs && opts.bodies && opts.bodies.length) {
    opts.bodies.forEach((body, idx) => {
      const hid = body.house;
      if (!(hid === 1 || hid === "1")) return;
      const orb = createPlanetOrbMesh(THREE, body.id || body.name, body);
      // スニペット風のばらつき（決定論: idx ベース）
      const jx = ((idx * 1.7) % 1) - 0.5;
      const jy = ((idx * 2.3) % 1);
      orb.position.set(jx * 4, 2 + jy * 3, -Math.min(arch.d * 0.28, 8));
      orb.scale.setScalar(1.35);
      houseGroup.add(orb);
      orbs.push(orb);
      if (animatables) {
        animatables.push({
          mesh: orb,
          kind: "bob",
          baseY: orb.position.y,
          speed: 0.8 + idx * 0.1,
          amp: 0.12,
        });
      }
    });
  }

  return { gate, particles, orbs };
}

/**
 * 第1ハウス・シーンを組み立てて scene に追加する。
 * 通常の house-tour では BUILDERS[1] → enhanceFirstHouse + buildPlanets を使用。
 *
 * シグネチャ互換:
 *   createFirstHouseScene(THREE, scene, houseData)
 *   createFirstHouseScene(scene, houseData)  // window.THREE 前提
 *
 * @param {typeof THREE|THREE.Scene} THREEOrScene
 * @param {THREE.Scene|object} sceneOrData
 * @param {object} [maybeData]
 * @returns {THREE.Group}
 */
export function createFirstHouseScene(THREEOrScene, sceneOrData, maybeData) {
  let THREE;
  let scene;
  let houseData;

  if (THREEOrScene && THREEOrScene.Scene) {
    // (THREE, scene, houseData)
    THREE = THREEOrScene;
    scene = sceneOrData;
    houseData = maybeData || {};
  } else if (typeof window !== "undefined" && window.THREE) {
    // (scene, houseData) — スニペット互換
    THREE = window.THREE;
    scene = THREEOrScene;
    houseData = sceneOrData || {};
  } else {
    throw new Error("createFirstHouseScene: THREE is required");
  }

  houseData = houseData || {};
  const group = new THREE.Group();
  group.name = "first_house_scene";

  // 1. 浮遊神殿ゲートウェイ
  const gate = createSymbolicGate(THREE);
  gate.position.set(0, 1.5, -12);
  group.add(gate);

  // 2. 天体オーブ配置（YAML の第1ハウス）
  const bodies = houseData.bodies || [];
  bodies.forEach((body) => {
    const hid = body.house;
    if (!(hid === 1 || hid === "1")) return;
    const orb = createPlanetOrbMesh(THREE, body.id || body.name, body);
    orb.position.set(
      (Math.random() - 0.5) * 4,
      2 + Math.random() * 3,
      -10
    );
    orb.scale.setScalar(1.35);
    group.add(orb);
  });

  // 3. 粒子フィールド（Dream Sky らしさ）
  const particles = createParticleField(THREE, 800, 0x88aaff, {
    w: 22,
    h: 16,
    d: 28,
  });
  group.add(particles);

  if (scene && scene.add) scene.add(group);
  return group;
}

/** 既存の天体メッシュをハウスから除去 */
export function clearPlanets(planetMeshes) {
  if (!planetMeshes) return;
  planetMeshes.forEach((p) => {
    if (p.mesh && p.mesh.parent) p.mesh.parent.remove(p.mesh);
  });
  planetMeshes.length = 0;
}

/**
 * 発光オーブ本体 + 外側グローを生成
 * @returns {{ core: THREE.Mesh, glow: THREE.Mesh }}
 */
function createPlanetOrb(THREE, colorHex, size, intensity) {
  // r128 互換。セグメントは展示距離向け（64 は過剰負荷）
  const segs = 32;
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(size, segs, segs),
    new THREE.MeshPhongMaterial({
      color: colorHex,
      emissive: colorHex,
      emissiveIntensity: intensity * 0.6,
      shininess: 90,
      transparent: true,
      opacity: 0.95,
    })
  );

  // Additive 外側グロー（スニペット: size * 1.3, opacity 0.25）
  const glow = new THREE.Mesh(
    new THREE.SphereGeometry(size * 1.3, 24, 24),
    new THREE.MeshBasicMaterial({
      color: colorHex,
      transparent: true,
      opacity: 0.25 * Math.min(intensity / 1.2, 1.35),
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  // 子としてコアに載せるとコアと一緒に回転
  core.add(glow);
  glow.renderOrder = 1;

  return { core, glow };
}

export function buildPlanets(ctx, houseGroups, bodies) {
  const { THREE } = ctx;
  const planetMeshes = [];
  const pickables = [];

  bodies.forEach((b) => {
    const hg = houseGroups[b.house];
    if (!hg) return;
    const col = new THREE.Color(b.color || "#fff");
    const colorHex = col.getHex();
    const spec = ORB_SPECS[b.id] || DEFAULT_ORB;
    const size = spec.size;
    const intensity = spec.intensity;

    const group = new THREE.Group();
    group.name = "planet_" + b.id;
    group.userData = {
      pickable: "planet",
      planetId: b.id,
      house: b.house,
      name: b.id,
    };

    // 発光オーブ（中心球 + Additive グロー。glow は core の子）
    const { core, glow } = createPlanetOrb(THREE, colorHex, size, intensity);
    group.add(core);

    // 天体ごとのビジュアル差異（リング・パルス等）
    if (b.visual === "expanding_ring" || b.id === "Jupiter" || b.id === "Saturn") {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(size * 1.75, size * 0.08, 8, 32),
        new THREE.MeshBasicMaterial({
          color: colorHex,
          transparent: true,
          opacity: 0.55,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
      );
      ring.rotation.x = Math.PI / 2.3;
      group.add(ring);
    }
    if (b.visual === "deep_pulse" || b.id === "Pluto") {
      const shell = new THREE.Mesh(
        new THREE.SphereGeometry(size * 1.45, 16, 16),
        new THREE.MeshBasicMaterial({
          color: colorHex,
          transparent: true,
          opacity: 0.16,
          wireframe: true,
        })
      );
      group.add(shell);
    }
    if (b.visual === "electric" || b.id === "Uranus") {
      const spike = new THREE.Mesh(
        new THREE.OctahedronGeometry(size * 1.3, 0),
        new THREE.MeshPhongMaterial({
          color: colorHex,
          emissive: colorHex,
          emissiveIntensity: intensity * 0.35,
          wireframe: true,
          transparent: true,
          opacity: 0.85,
        })
      );
      group.add(spike);
    }
    if (b.visual === "mist" || b.id === "Neptune") {
      const haze = new THREE.Mesh(
        new THREE.SphereGeometry(size * 1.65, 14, 14),
        new THREE.MeshBasicMaterial({
          color: colorHex,
          transparent: true,
          opacity: 0.18,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
      );
      group.add(haze);
    }

    // グリフ（オーブサイズに応じて浮かせる）
    const spr = makeGlyph(THREE, b.glyph || "●", col.getStyle());
    spr.position.y = size + 0.55;
    group.add(spr);

    // ハウス内スロットへ配置（YAML ハウス番号に従う）
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
    // 展示スケール（模型感を抑える）
    group.scale.setScalar(1.35);
    hg.group.add(group);

    // クリック用ヒット球体
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(size * 1.6, 0.55), 8, 8),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.userData = group.userData;
    group.add(hit);

    planetMeshes.push({
      mesh: group,
      core,
      glow,
      spin: 0.28 + Math.random() * 0.2,
      bob: 0.1 + Math.random() * 0.07,
      baseY: group.position.y,
      intensity,
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
    // ゆっくり自転
    p.mesh.rotation.y += (reducedMotion ? 0 : p.spin) * dt;
    if (!reducedMotion && p.bob) {
      p.mesh.position.y = p.baseY + Math.sin(t * 1.2 + p.baseY) * p.bob;
    }
    // グローをわずかに脈動（Additive のにじみ）
    if (!reducedMotion && p.glow && p.glow.material) {
      const pulse = 0.88 + 0.12 * Math.sin(t * 1.5 + p.baseY);
      p.glow.scale.setScalar(pulse);
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
  // 星座名は表示言語に合わせる（sign_en 優先、無ければ sign_ja / sign を変換）
  const signLabel = localizeSign(extra.sign_en || extra.sign_ja || extra.sign || "");
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
