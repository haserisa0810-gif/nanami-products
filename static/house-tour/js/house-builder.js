/**
 * 各ハウスを「展示ブース」ではなく固有の建物・スケールで構築する。
 * 説明文を読まなくても、建築・オブジェクト・光・広さで意味が伝わること。
 */
import { RING_R, housePosition, hexColor } from "./scene.js";

/**
 * ハウスごとの建築スケールと入口オフセット（ローカル座標）
 * z+ = 中庭側（入り口）、z- = 奥
 */
/** ミュージアム展示室スケール。入口は中庭側（+z）から遠景で見えるよう余白を取る */
const ARCH = {
  1: { w: 14, d: 20, h: 9, style: "gateway", entryZ: 10, labelY: 10 },
  2: { w: 16, d: 22, h: 7.5, style: "storehouse", entryZ: 11, labelY: 9 },
  3: { w: 11, d: 26, h: 8, style: "corridor", entryZ: 12, labelY: 9 },
  4: { w: 15, d: 18, h: 9, style: "home", entryZ: 10, labelY: 10 },
  5: { w: 18, d: 24, h: 10, style: "theater", entryZ: 12, labelY: 11 },
  6: { w: 16, d: 20, h: 7.5, style: "office", entryZ: 10, labelY: 9 },
  7: { w: 15, d: 18, h: 8, style: "dialogue", entryZ: 10, labelY: 9 },
  8: { w: 14, d: 20, h: 6.5, style: "crypt", entryZ: 10, labelY: 8 },
  9: { w: 18, d: 22, h: 12, style: "observatory", entryZ: 12, labelY: 13 },
  10: { w: 14, d: 16, h: 18, style: "tower", entryZ: 10, labelY: 16 },
  11: { w: 22, d: 22, h: 9, style: "plaza", entryZ: 12, labelY: 10 },
  12: { w: 12, d: 28, h: 8, style: "cloister", entryZ: 14, labelY: 9 },
};

export function buildAllHouses(ctx, housesData) {
  const houseGroups = {};
  const animatables = [];
  const entryWorld = {};

  for (let n = 1; n <= 12; n++) {
    const h = housesData[n];
    if (!h) continue;
    const built = buildOneHouse(ctx, n, h, animatables);
    houseGroups[n] = built;

    // ワールド座標の入口（建物のドア直前）
    built.group.updateMatrixWorld(true);
    const world = built.entryLocal.clone();
    built.group.localToWorld(world);
    entryWorld[n] = { x: world.x, y: 1.65, z: world.z };
  }
  return { houseGroups, animatables, entryWorld };
}

function buildOneHouse(ctx, n, h, animatables) {
  const { THREE, scene, quality } = ctx;
  const arch = ARCH[n] || { w: 18, d: 22, h: 8, style: "default", entryZ: 8, labelY: 9 };
  const group = new THREE.Group();
  group.name = "house_" + n;
  const pos = housePosition(n, THREE);
  group.position.copy(pos);
  group.lookAt(0, 0, 0);
  group.rotateY(Math.PI);

  const pal = h.palette || {};
  const primary = hexColor(THREE, pal.primary || "#888");
  const secondary = hexColor(THREE, pal.secondary || "#111");
  const accent = hexColor(THREE, pal.accent || "#ccc");
  const lightCol = hexColor(THREE, pal.light || "#fff");

  const planetSlots = [];
  const exhibits = [];
  const lights = { pl: null, spot: null, extra: null, kind: "steady", base: 0.9, spotBase: 0.5 };

  // ── 建築本体（ハウスごとに完全分岐）──
  const builder = BUILDERS[n] || BUILDERS.default;
  builder({
    THREE,
    group,
    arch,
    primary,
    secondary,
    accent,
    lightCol,
    quality,
    animatables,
    planetSlots,
    exhibits,
    lights,
  });

  // 長いアプローチ通路（遠景→入口が分かる）
  const pathLen = 36;
  const path = box(THREE, 2.4, 0.06, pathLen, primary.getHex(), {
    emissive: primary.getHex(),
    emissiveIntensity: 0.1,
  });
  path.position.set(0, 0.03, arch.entryZ + pathLen * 0.5 - 2);
  group.add(path);
  // 道沿いの小さな灯り
  for (let i = 0; i < 5; i++) {
    const lz = arch.entryZ + 6 + i * 6;
    group.add(
      box(THREE, 0.15, 0.9, 0.15, accent.getHex(), {
        emissive: accent.getHex(),
        emissiveIntensity: 0.35,
      })
    ).position.set(-1.6, 0.5, lz);
    group.add(
      box(THREE, 0.15, 0.9, 0.15, accent.getHex(), {
        emissive: accent.getHex(),
        emissiveIntensity: 0.35,
      })
    ).position.set(1.6, 0.5, lz);
  }

  const label = makeLabel(THREE, String(n), primary.getStyle());
  label.position.set(0, arch.labelY || arch.h + 1.5, arch.entryZ + 1);
  group.add(label);

  // 展示室プラーク（入口上）
  const plaque = makePlaque(THREE, "H" + n, primary.getStyle());
  plaque.position.set(0, 3.2, arch.entryZ + 0.5);
  group.add(plaque);

  scene.add(group);

  // 歩行開始位置：建物から十分離れたアプローチ上
  const entryLocal = new THREE.Vector3(0, 1.65, arch.entryZ + 14);

  return {
    group,
    light: lights.pl,
    spot: lights.spot,
    extraLight: lights.extra,
    lightKind: lights.kind,
    baseIntensity: lights.base,
    spotBase: lights.spotBase,
    palette: pal,
    planetSlots,
    exhibits,
    entryLocal,
    arch,
  };
}

/**
 * 展示登録ヘルパ
 * caption は string または { ja, en }
 */
export function pushExhibit(exhibits, name, x, y, z, caption, nameEn, captionEn) {
  if (!exhibits) return;
  let capJa = caption;
  let capEn = captionEn;
  let nEn = nameEn;
  if (caption && typeof caption === "object") {
    capJa = caption.ja || name;
    capEn = caption.en || nameEn || name;
  }
  exhibits.push({
    name: name,
    nameEn: nEn || name,
    x: x,
    y: y,
    z: z,
    caption: capJa || name,
    captionEn: capEn || nEn || name,
  });
}

function makePlaque(THREE, text, color) {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 96;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "rgba(12,14,22,0.85)";
  ctx.fillRect(0, 0, 256, 96);
  ctx.strokeStyle = color || "#c9a96e";
  ctx.lineWidth = 4;
  ctx.strokeRect(4, 4, 248, 88);
  ctx.fillStyle = color || "#e8d5b0";
  ctx.font = "600 40px Cinzel, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 48);
  const spr = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(c),
      transparent: true,
      depthWrite: false,
    })
  );
  spr.scale.set(3.2, 1.2, 1);
  return spr;
}

// ═══════════════════════════════════════════════════════════
// ユーティリティ
// ═══════════════════════════════════════════════════════════

function box(THREE, w, h, d, color, opts) {
  opts = opts || {};
  const m = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({
      color,
      roughness: opts.roughness != null ? opts.roughness : 0.78,
      metalness: opts.metalness != null ? opts.metalness : 0.08,
      emissive: opts.emissive || 0x000000,
      emissiveIntensity: opts.emissiveIntensity || 0,
      transparent: !!opts.transparent,
      opacity: opts.opacity != null ? opts.opacity : 1,
      side: opts.side || THREE.FrontSide,
    })
  );
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

function mesh(THREE, geo, mat, x, y, z) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

function matP(THREE, primary, ei) {
  return new THREE.MeshStandardMaterial({
    color: primary.getHex(),
    roughness: 0.45,
    metalness: 0.28,
    emissive: primary.getHex(),
    emissiveIntensity: ei != null ? ei : 0.22,
  });
}
function matA(THREE, accent, ei) {
  return new THREE.MeshStandardMaterial({
    color: accent.getHex(),
    roughness: 0.4,
    metalness: 0.3,
    emissive: accent.getHex(),
    emissiveIntensity: ei != null ? ei : 0.2,
  });
}
function matDark(THREE) {
  return new THREE.MeshStandardMaterial({ color: 0x1a1a22, roughness: 0.75, metalness: 0.12 });
}
function matMirror(THREE) {
  return new THREE.MeshStandardMaterial({
    color: 0xc8d0e0,
    roughness: 0.06,
    metalness: 0.95,
    emissive: 0x203040,
    emissiveIntensity: 0.12,
  });
}

function floorSlab(THREE, group, w, d, color) {
  const f = box(THREE, w, 0.2, d, color, { roughness: 0.92 });
  f.position.y = 0.1;
  group.add(f);
  return f;
}

function addPointLight(THREE, group, lights, color, intensity, x, y, z, dist) {
  const pl = new THREE.PointLight(color, intensity, dist || 28, 2);
  pl.position.set(x, y, z);
  group.add(pl);
  if (!lights.pl) {
    lights.pl = pl;
    lights.base = intensity;
  }
  return pl;
}

function addSpot(THREE, group, lights, color, intensity, pos, target, angle) {
  const spot = new THREE.SpotLight(color, intensity, 40, angle || Math.PI / 6, 0.4, 1.2);
  spot.position.copy(pos);
  spot.target.position.copy(target);
  group.add(spot);
  group.add(spot.target);
  if (!lights.spot) {
    lights.spot = spot;
    lights.spotBase = intensity;
  }
  return spot;
}

function makeLabel(THREE, text, color) {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 128;
  const ctx = c.getContext("2d");
  ctx.beginPath();
  ctx.arc(64, 64, 48, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(10,11,18,0.8)";
  ctx.fill();
  ctx.strokeStyle = color || "#c9a96e";
  ctx.lineWidth = 4;
  ctx.stroke();
  ctx.fillStyle = color || "#e8d5b0";
  ctx.font = "bold 52px Cinzel, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 64, 66);
  const spr = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(c),
      transparent: true,
      depthWrite: false,
    })
  );
  spr.scale.set(2.4, 2.4, 1);
  return spr;
}

function silhouetteFigure(THREE, mat, x, y, z, scale) {
  // 簡略人物シルエット（胴+頭）
  const g = new THREE.Group();
  const body = mesh(THREE, new THREE.CylinderGeometry(0.28 * scale, 0.35 * scale, 1.4 * scale, 8), mat, 0, 0.9 * scale, 0);
  const head = mesh(THREE, new THREE.SphereGeometry(0.28 * scale, 10, 10), mat, 0, 1.85 * scale, 0);
  g.add(body);
  g.add(head);
  g.position.set(x, y, z);
  return g;
}

// ═══════════════════════════════════════════════════════════
// ハウス別ビルダー
// ═══════════════════════════════════════════════════════════

const BUILDERS = {};

/** 1: 夜明けの門 — 大きなアーチと姿見、足跡、開き扉 */
BUILDERS[1] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, secondary.getHex());

  // 巨大門柱
  const colMat = matP(THREE, primary, 0.25);
  [-w * 0.38, w * 0.38].forEach((x) => {
    group.add(mesh(THREE, new THREE.BoxGeometry(1.4, h, 1.4), colMat, x, h / 2, d * 0.35));
  });
  // アーチ梁
  group.add(box(THREE, w * 0.85, 1.2, 1.2, primary.getHex(), {
    emissive: primary.getHex(),
    emissiveIntensity: 0.3,
  })).position.set(0, h * 0.88, d * 0.35);

  // 半開きの扉（2枚）
  const doorL = box(THREE, w * 0.28, h * 0.75, 0.2, secondary.getHex());
  doorL.position.set(-w * 0.18, h * 0.4, d * 0.32);
  doorL.rotation.y = 0.55;
  group.add(doorL);
  const doorR = box(THREE, w * 0.28, h * 0.75, 0.2, secondary.getHex());
  doorR.position.set(w * 0.18, h * 0.4, d * 0.32);
  doorR.rotation.y = -0.4;
  group.add(doorR);

  // 奥の大姿見
  group.add(mesh(THREE, new THREE.BoxGeometry(5, 7, 0.15), matMirror(THREE), 0, 3.8, -d * 0.4));
  group.add(box(THREE, 5.4, 7.4, 0.25, primary.getHex(), {
    emissive: primary.getHex(),
    emissiveIntensity: 0.15,
  })).position.set(0, 3.8, -d * 0.42);

  // 足跡
  for (let i = 0; i < 8; i++) {
    group.add(box(THREE, 0.4, 0.04, 0.6, accent.getHex(), {
      emissive: accent.getHex(),
      emissiveIntensity: 0.2,
    })).position.set((i % 2) * 0.4 - 0.2, 0.22, d * 0.25 - i * 1.1);
  }

  // 靴・仮面
  group.add(mesh(THREE, new THREE.BoxGeometry(0.55, 0.25, 0.9), matDark(THREE), -3, 0.3, 2));
  const mask = mesh(THREE, new THREE.SphereGeometry(0.45, 12, 10, 0, Math.PI * 2, 0, Math.PI / 1.6), matA(THREE, accent, 0.3), 3.5, 2.2, -2);
  group.add(mask);
  animatables.push({ mesh: mask, kind: "bob", baseY: 2.2, speed: 1.1, amp: 0.1 });

  // 自分の輪郭シルエット（姿見の前）
  const sil = silhouetteFigure(THREE, matA(THREE, accent, 0.15), 0, 0, -d * 0.25, 1.1);
  sil.children.forEach((ch) => {
    if (ch.material) {
      ch.material = ch.material.clone();
      ch.material.transparent = true;
      ch.material.opacity = 0.35;
    }
  });
  group.add(sil);

  // 夜明けの斜光
  lights.kind = "dawn";
  addPointLight(THREE, group, lights, lightCol.getHex(), 0.5, 0, 6, 0, 30);
  addSpot(THREE, group, lights, lightCol.getHex(), 1.4,
    new THREE.Vector3(-8, 12, 10), new THREE.Vector3(0, 1, -4), Math.PI / 5);

  planetSlots.push(new THREE.Vector3(0, 3.5, -d * 0.15));
};

/** 2: 保管庫 — 棚・道具・作品・食料・鍵（金運だけにしない） */
BUILDERS[2] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, secondary.getHex());
  // 壁・天井
  group.add(box(THREE, w, h, 0.4, secondary.getHex())).position.set(0, h / 2, -d / 2);
  group.add(box(THREE, 0.4, h, d, secondary.getHex())).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.4, h, d, secondary.getHex())).position.set(w / 2, h / 2, 0);
  group.add(box(THREE, w, 0.3, d, secondary.clone().offsetHSL(0, 0, -0.02).getHex())).position.set(0, h, 0);

  // 両側の棚（高さのある保管）
  for (let side = -1; side <= 1; side += 2) {
    for (let row = 0; row < 4; row++) {
      group.add(box(THREE, 3.5, 0.12, 1.2, matDark(THREE).color.getHex())).position.set(side * 5.5, 1.2 + row * 1.4, -2 - row * 0.2);
      // 棚の中身: 壺・箱・作品
      for (let k = 0; k < 3; k++) {
        const item = mesh(
          THREE,
          k === 1 ? new THREE.SphereGeometry(0.35, 10, 10) : new THREE.BoxGeometry(0.5, 0.45, 0.5),
          k === 2 ? matA(THREE, accent, 0.25) : matP(THREE, primary, 0.15),
          side * 5.5 + (k - 1) * 0.9,
          1.55 + row * 1.4,
          -2
        );
        group.add(item);
      }
    }
  }

  // 中央: 道具ベンチ + 手作り作品
  group.add(box(THREE, 5, 0.2, 1.8, accent.getHex(), {
    emissive: accent.getHex(),
    emissiveIntensity: 0.12,
  })).position.set(0, 1.1, 2);
  group.add(mesh(THREE, new THREE.BoxGeometry(1.2, 0.15, 0.15), matDark(THREE), -1, 1.3, 2));
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.08, 0.08, 1.1, 6), matDark(THREE), 0.5, 1.5, 2.2));
  const craft = mesh(THREE, new THREE.IcosahedronGeometry(0.55, 0), matA(THREE, accent, 0.35), 1.5, 1.7, 2);
  group.add(craft);
  animatables.push({ mesh: craft, kind: "spin", speed: 0.3, axis: "y" });

  // 食料壺・鍵付き箱・金貨（一部）
  group.add(mesh(THREE, new THREE.SphereGeometry(0.6, 12, 12), matP(THREE, primary, 0.15), -3, 0.7, 5));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.8, 1.0, 1.2), matDark(THREE), 3, 0.7, 5));
  const key = mesh(THREE, new THREE.TorusGeometry(0.25, 0.06, 8, 14), matA(THREE, accent, 0.4), 3.5, 2.2, 4.5);
  group.add(key);
  animatables.push({ mesh: key, kind: "bob", baseY: 2.2, speed: 1.2, amp: 0.12 });

  lights.kind = "warm";
  addPointLight(THREE, group, lights, lightCol.getHex(), 1.1, 0, 5, 0, 32);
  addSpot(THREE, group, lights, accent.getHex(), 0.5,
    new THREE.Vector3(0, 7, 2), new THREE.Vector3(0, 1, 2));

  // Jupiter slot: 保管庫の中心上
  planetSlots.push(new THREE.Vector3(0, 3.8, 0));
};

/** 3: 言葉の長い回廊 — 本・手紙・自転車 */
BUILDERS[3] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, secondary.getHex());
  // 長い両壁の書架
  group.add(box(THREE, 0.5, h, d * 0.95, secondary.getHex())).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.5, h, d * 0.95, secondary.getHex())).position.set(w / 2, h / 2, 0);
  group.add(box(THREE, w, 0.3, d, secondary.getHex())).position.set(0, h, 0);
  // 本
  for (let i = 0; i < 20; i++) {
    const side = i % 2 === 0 ? -1 : 1;
    group.add(box(THREE, 0.35, 0.7 + (i % 4) * 0.15, 0.55,
      i % 3 === 0 ? primary.getHex() : accent.getHex(),
      { emissive: primary.getHex(), emissiveIntensity: 0.08 }
    )).position.set(side * (w / 2 - 0.5), 1 + (i % 5) * 1.1, d / 2 - 2 - Math.floor(i / 2) * 1.3);
  }
  // 浮遊する手紙
  for (let p = 0; p < 8; p++) {
    const letter = mesh(THREE, new THREE.PlaneGeometry(0.55, 0.75), matA(THREE, accent, 0.2),
      (p % 3 - 1) * 1.5, 2.5 + (p % 4) * 0.4, d / 2 - 4 - p * 2);
    letter.material = matA(THREE, accent, 0.2);
    letter.material.side = THREE.DoubleSide;
    group.add(letter);
    animatables.push({
      mesh: letter, kind: "drift",
      baseY: letter.position.y, baseX: letter.position.x,
      speed: 0.6 + p * 0.08, amp: 0.35, phase: p,
    });
  }
  // 入口の自転車
  group.add(mesh(THREE, new THREE.TorusGeometry(0.7, 0.08, 8, 16), matDark(THREE), -2, 0.75, d / 2 - 1.5));
  group.add(mesh(THREE, new THREE.TorusGeometry(0.7, 0.08, 8, 16), matDark(THREE), 0.5, 0.75, d / 2 - 1.5));
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.05, 0.05, 1.6, 6), matDark(THREE), -0.7, 1.2, d / 2 - 1.5));

  lights.kind = "cool";
  addPointLight(THREE, group, lights, lightCol.getHex(), 0.85, 0, 5, 0, 36);
  lights.extra = new THREE.PointLight(0xa8d4e8, 0.4, 20, 2);
  lights.extra.position.set(2, 4, -5);
  lights.extra.userData = { base: 0.4 };
  group.add(lights.extra);

  planetSlots.push(new THREE.Vector3(0, 3.2, 0));
};

/** 4: 家そのもの — 屋根・暖炉の居間・写真 */
BUILDERS[4] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w * 0.95, d * 0.9, 0x2a2218);

  // 家の外壁（入口が開いた箱）
  const wallC = secondary.getHex();
  group.add(box(THREE, w, h * 0.7, 0.45, wallC)).position.set(0, h * 0.35, -d * 0.4);
  group.add(box(THREE, 0.45, h * 0.7, d * 0.85, wallC)).position.set(-w * 0.45, h * 0.35, 0);
  group.add(box(THREE, 0.45, h * 0.7, d * 0.85, wallC)).position.set(w * 0.45, h * 0.35, 0);
  // 切妻屋根
  const roofMat = matP(THREE, primary, 0.12);
  const roofL = mesh(THREE, new THREE.BoxGeometry(w * 0.7, 0.35, d * 0.95), roofMat, -w * 0.18, h * 0.78, 0);
  roofL.rotation.z = 0.45;
  group.add(roofL);
  const roofR = mesh(THREE, new THREE.BoxGeometry(w * 0.7, 0.35, d * 0.95), roofMat, w * 0.18, h * 0.78, 0);
  roofR.rotation.z = -0.45;
  group.add(roofR);

  // 暖炉
  group.add(mesh(THREE, new THREE.BoxGeometry(3.2, 2.8, 1.2), matDark(THREE), 0, 1.5, -d * 0.32));
  const fire = mesh(THREE, new THREE.ConeGeometry(0.55, 1.2, 8), matA(THREE, accent, 0.7), 0, 1.6, -d * 0.28);
  fire.material = matA(THREE, accent, 0.85);
  group.add(fire);
  animatables.push({ mesh: fire, kind: "flame", baseY: 1.6, speed: 6, amp: 0.14 });
  const fire2 = mesh(THREE, new THREE.ConeGeometry(0.3, 0.8, 6), matP(THREE, primary, 0.6), 0.2, 1.7, -d * 0.26);
  group.add(fire2);
  animatables.push({ mesh: fire2, kind: "flame", baseY: 1.7, speed: 7.5, amp: 0.1, phase: 1 });

  // 揺り椅子・写真・古い箱
  group.add(box(THREE, 1.3, 0.15, 1.1, matDark(THREE).color.getHex())).position.set(-4.5, 0.7, 1);
  group.add(box(THREE, 1.3, 1.1, 0.12, matDark(THREE).color.getHex())).position.set(-4.5, 1.35, 0.5);
  group.add(box(THREE, 1.0, 1.2, 0.1, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.15,
  })).position.set(4, 2.4, -d * 0.35);
  group.add(box(THREE, 1.4, 0.9, 1.0, matDark(THREE).color.getHex())).position.set(4, 0.55, 2);

  // 根のような床の装飾
  for (let i = 0; i < 5; i++) {
    group.add(mesh(THREE, new THREE.CylinderGeometry(0.08, 0.15, 1.5 + i * 0.2, 6), matP(THREE, primary, 0.1),
      -3 + i * 1.5, 0.3, 4)).rotation.z = 0.9 + i * 0.1;
  }

  lights.kind = "flicker";
  const pl = addPointLight(THREE, group, lights, lightCol.getHex(), 1.5, 0, 2.2, -d * 0.25, 18);
  lights.pl = pl;
  lights.base = 1.5;
  addSpot(THREE, group, lights, 0x442210, 0.25,
    new THREE.Vector3(0, 6, 0), new THREE.Vector3(0, 0, 0));

  planetSlots.push(new THREE.Vector3(0, 3.2, 0));
};

/**
 * 5: 本物の劇場
 * 暗い客席 → 明るい舞台 → 袖に絵・ピアノ・原稿・玩具 → 中央に天体
 */
BUILDERS[5] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;

  // 床: 客席側は暗い、舞台側は明るい板
  const floorDark = box(THREE, w, 0.25, d * 0.55, 0x0a0a10, { roughness: 0.95 });
  floorDark.position.set(0, 0.12, d * 0.2);
  group.add(floorDark);
  const stageFloor = box(THREE, w * 0.85, 0.55, d * 0.4, primary.getHex(), {
    roughness: 0.55,
    metalness: 0.15,
    emissive: primary.getHex(),
    emissiveIntensity: 0.08,
  });
  stageFloor.position.set(0, 0.45, -d * 0.28);
  group.add(stageFloor);

  // 壁（客席は暗い）
  group.add(box(THREE, w, h, 0.5, 0x120810)).position.set(0, h / 2, -d / 2);
  group.add(box(THREE, 0.4, h, d, 0x10080e)).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.4, h, d, 0x10080e)).position.set(w / 2, h / 2, 0);
  group.add(box(THREE, w, 0.35, d, 0x0c060a)).position.set(0, h, 0);

  // 客席（段々・暗い）
  for (let row = 0; row < 5; row++) {
    const seat = box(THREE, w * 0.7, 0.45 + row * 0.15, 1.3, 0x1a1018);
    seat.position.set(0, 0.4 + row * 0.35, d * 0.42 - row * 1.5);
    group.add(seat);
    // 椅子の背
    for (let s = -2; s <= 2; s++) {
      group.add(box(THREE, 1.0, 0.9, 0.15, 0x221018)).position.set(s * 2.2, 1.0 + row * 0.35, d * 0.42 - row * 1.5 - 0.4);
    }
  }

  // プロセニアム（額縁）
  group.add(box(THREE, w * 0.9, 0.6, 0.5, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.25,
  })).position.set(0, h * 0.75, -d * 0.05);
  group.add(box(THREE, 0.5, h * 0.7, 0.5, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.2,
  })).position.set(-w * 0.4, h * 0.4, -d * 0.05);
  group.add(box(THREE, 0.5, h * 0.7, 0.5, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.2,
  })).position.set(w * 0.4, h * 0.4, -d * 0.05);

  // 幕
  const curtain = mesh(THREE, new THREE.PlaneGeometry(w * 0.75, h * 0.55), matA(THREE, accent, 0.15), 0, h * 0.55, -d * 0.48);
  curtain.material = matA(THREE, accent, 0.15);
  curtain.material.side = THREE.DoubleSide;
  curtain.material.transparent = true;
  curtain.material.opacity = 0.75;
  group.add(curtain);
  animatables.push({ mesh: curtain, kind: "sway", speed: 0.6, amp: 0.03 });

  // 舞台袖: 描きかけの絵
  const canvas = box(THREE, 1.8, 2.2, 0.12, 0xf5e6d0);
  canvas.position.set(-7, 2.5, -d * 0.2);
  group.add(canvas);
  group.add(box(THREE, 2.0, 2.4, 0.15, matDark(THREE).color.getHex())).position.set(-7, 2.5, -d * 0.21);
  // 絵の具の跡
  group.add(box(THREE, 0.8, 0.6, 0.05, primary.getHex(), {
    emissive: primary.getHex(), emissiveIntensity: 0.3,
  })).position.set(-7, 2.6, -d * 0.13);

  // ピアノ
  group.add(box(THREE, 2.8, 1.0, 1.2, 0x1a1a1a)).position.set(6.5, 1.1, -d * 0.15);
  group.add(box(THREE, 2.6, 0.12, 0.35, 0xf0e8d8)).position.set(6.5, 1.65, -d * 0.05);
  // 鍵（白）
  for (let k = 0; k < 8; k++) {
    group.add(box(THREE, 0.22, 0.05, 0.4, 0xffffff)).position.set(5.5 + k * 0.28, 1.72, -d * 0.02);
  }

  // 原稿の山
  for (let m = 0; m < 4; m++) {
    group.add(box(THREE, 0.7, 0.04, 0.9, 0xe8dcc8)).position.set(-5.5, 1.0 + m * 0.06, -d * 0.08);
  }
  // 絵筆
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.04, 0.05, 1.2, 6), matDark(THREE), -5.8, 1.5, -d * 0.12));

  // 子供のおもちゃ
  group.add(mesh(THREE, new THREE.SphereGeometry(0.35, 10, 10), matA(THREE, accent, 0.3), 5, 0.9, -d * 0.05));
  group.add(box(THREE, 0.6, 0.4, 0.6, primary.getHex())).position.set(5.8, 0.85, 0.2);

  // 完成作品（壁掛け）
  group.add(box(THREE, 1.5, 1.8, 0.1, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.2,
  })).position.set(-w / 2 + 0.6, 4, -d * 0.35);
  group.add(box(THREE, 1.5, 1.8, 0.1, primary.getHex(), {
    emissive: primary.getHex(), emissiveIntensity: 0.2,
  })).position.set(w / 2 - 0.6, 4, -d * 0.35);

  // 脚光（舞台中央へ強烈）
  lights.kind = "spotlight";
  addPointLight(THREE, group, lights, 0x221018, 0.25, 0, 4, d * 0.25, 20); // 客席は暗い
  const spot = addSpot(THREE, group, lights, lightCol.getHex(), 2.2,
    new THREE.Vector3(0, h - 1, -d * 0.05),
    new THREE.Vector3(0, 1.2, -d * 0.28),
    Math.PI / 8);
  lights.spot = spot;
  lights.spotBase = 2.2;
  // 補助スポット
  lights.extra = new THREE.SpotLight(accent.getHex(), 0.7, 30, Math.PI / 10, 0.5, 1);
  lights.extra.position.set(3, h - 1.5, -d * 0.1);
  lights.extra.target.position.set(0, 1, -d * 0.3);
  lights.extra.userData = { base: 0.7 };
  group.add(lights.extra);
  group.add(lights.extra.target);

  // 天体: 舞台中央が1番目（Sun）、袖が2番目（Saturn）
  planetSlots.push(new THREE.Vector3(0, 2.8, -d * 0.28)); // Sun 中心
  planetSlots.push(new THREE.Vector3(-6, 2.4, -d * 0.22)); // Saturn 袖
};

/**
 * 6: 毎日の積み重ねの職場
 * 机・書類・PC・時計・歯車・コーヒー・本棚・道具
 */
BUILDERS[6] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, 0x1a1e16);
  group.add(box(THREE, w, h, 0.35, secondary.getHex())).position.set(0, h / 2, -d / 2);
  group.add(box(THREE, 0.35, h, d, secondary.getHex())).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.35, h, d, secondary.getHex())).position.set(w / 2, h / 2, 0);
  group.add(box(THREE, w, 0.25, d, secondary.getHex())).position.set(0, h, 0);

  // 作業デスク列
  const desks = [
    [-4, 2], [0, 2], [4, 2],
    [-4, -3], [0, -3], [4, -3],
  ];
  desks.forEach(([x, z], i) => {
    group.add(box(THREE, 2.8, 0.12, 1.5, 0x3a4030)).position.set(x, 1.05, z);
    group.add(box(THREE, 0.12, 1.05, 0.12, matDark(THREE).color.getHex())).position.set(x - 1.1, 0.52, z - 0.5);
    group.add(box(THREE, 0.12, 1.05, 0.12, matDark(THREE).color.getHex())).position.set(x + 1.1, 0.52, z - 0.5);
    // モニター
    group.add(box(THREE, 1.2, 0.75, 0.08, 0x1a2030, {
      emissive: 0x305060, emissiveIntensity: 0.35,
    })).position.set(x, 1.7, z - 0.4);
    // 書類
    for (let p = 0; p < 3; p++) {
      group.add(box(THREE, 0.55, 0.03, 0.7, 0xe8e0d0)).position.set(x + 0.6, 1.15 + p * 0.04, z + 0.2);
    }
    // キーボード
    group.add(box(THREE, 0.9, 0.05, 0.3, 0x2a2a2a)).position.set(x - 0.2, 1.15, z + 0.15);
  });

  // 巨大壁時計
  group.add(mesh(THREE, new THREE.CylinderGeometry(1.4, 1.4, 0.15, 24), matA(THREE, accent, 0.15), 0, 5.5, -d / 2 + 0.4));
  const hand = mesh(THREE, new THREE.BoxGeometry(0.08, 1.0, 0.05), matDark(THREE), 0, 5.5, -d / 2 + 0.5);
  group.add(hand);
  animatables.push({ mesh: hand, kind: "spin", speed: 0.15, axis: "z" });

  // 歯車
  const gear = mesh(THREE, new THREE.CylinderGeometry(0.9, 0.9, 0.2, 12), matP(THREE, primary, 0.25), -7, 3, -d / 2 + 0.6);
  group.add(gear);
  animatables.push({ mesh: gear, kind: "spin", speed: 0.5, axis: "z" });
  const gear2 = mesh(THREE, new THREE.CylinderGeometry(0.55, 0.55, 0.15, 10), matA(THREE, accent, 0.25), -5.8, 2.4, -d / 2 + 0.6);
  group.add(gear2);
  animatables.push({ mesh: gear2, kind: "spin", speed: -0.7, axis: "z" });

  // 本棚
  for (let row = 0; row < 5; row++) {
    group.add(box(THREE, 4, 0.1, 0.5, matDark(THREE).color.getHex())).position.set(7, 1.2 + row * 1.1, -2);
    for (let b = 0; b < 5; b++) {
      group.add(box(THREE, 0.35, 0.7 + (b % 3) * 0.1, 0.4,
        b % 2 ? primary.getHex() : accent.getHex()
      )).position.set(5.8 + b * 0.5, 1.65 + row * 1.1, -2);
    }
  }

  // コーヒーカップ
  const cupMat = new THREE.MeshStandardMaterial({ color: 0xf5f0e8, roughness: 0.5 });
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.18, 0.15, 0.28, 10), cupMat, 1.2, 1.25, 2.3));
  group.add(mesh(THREE, new THREE.TorusGeometry(0.12, 0.03, 6, 10), cupMat, 1.4, 1.25, 2.3));

  // 道具箱
  group.add(box(THREE, 1.5, 0.7, 0.9, matP(THREE, primary, 0.1).color.getHex())).position.set(-7, 0.5, 4);
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.06, 0.06, 1.0, 6), matDark(THREE), -6.5, 1.2, 4.2));

  // ホワイトボード / チェックリスト
  group.add(box(THREE, 3.5, 2.5, 0.1, 0xe8ece0)).position.set(0, 4, -d / 2 + 0.3);
  for (let i = 0; i < 5; i++) {
    group.add(box(THREE, 2.5, 0.06, 0.02, 0x445544)).position.set(0, 4.8 - i * 0.35, -d / 2 + 0.36);
  }

  lights.kind = "even";
  addPointLight(THREE, group, lights, lightCol.getHex(), 1.15, 0, 5.5, 0, 30);
  lights.extra = new THREE.PointLight(0xe0f0c8, 0.45, 18, 2);
  lights.extra.position.set(0, 4, -4);
  lights.extra.userData = { base: 0.45 };
  group.add(lights.extra);
  addSpot(THREE, group, lights, 0xc4d8a8, 0.4,
    new THREE.Vector3(0, 7, 2), new THREE.Vector3(0, 1, 0));

  // Mercury, Venus, Mars
  planetSlots.push(new THREE.Vector3(-3, 3.0, 0));
  planetSlots.push(new THREE.Vector3(0, 3.2, -2));
  planetSlots.push(new THREE.Vector3(3.5, 2.9, 1));
};

/**
 * 7: 対話室 — 二脚の椅子・テーブル・契約書・向かい合うシルエット・握手
 */
BUILDERS[7] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, secondary.getHex());
  // 対称のホール
  group.add(box(THREE, w, h, 0.4, secondary.getHex())).position.set(0, h / 2, -d / 2);
  group.add(box(THREE, 0.35, h, d, secondary.getHex())).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.35, h, d, secondary.getHex())).position.set(w / 2, h / 2, 0);
  group.add(box(THREE, w, 0.25, d, secondary.getHex())).position.set(0, h, 0);
  // 中央の線（境界）
  group.add(box(THREE, 0.08, 0.05, d * 0.7, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.35,
  })).position.set(0, 0.22, 0);

  // テーブル
  group.add(box(THREE, 3.5, 0.15, 1.6, 0x2a2438)).position.set(0, 1.05, 0);
  [-1.4, 1.4].forEach((x) => {
    group.add(box(THREE, 0.12, 1.0, 0.12, matDark(THREE).color.getHex())).position.set(x, 0.5, 0.5);
    group.add(box(THREE, 0.12, 1.0, 0.12, matDark(THREE).color.getHex())).position.set(x, 0.5, -0.5);
  });
  // 契約書
  group.add(box(THREE, 1.1, 0.04, 1.4, 0xf0e8d8)).position.set(0, 1.18, 0);
  group.add(box(THREE, 0.35, 0.02, 0.5, primary.getHex(), {
    emissive: primary.getHex(), emissiveIntensity: 0.2,
  })).position.set(0.2, 1.22, 0.2);

  // 向かい合う椅子
  function chair(x, z, rotY) {
    const g = new THREE.Group();
    g.add(box(THREE, 1.1, 0.12, 1.1, matDark(THREE).color.getHex()));
    const back = box(THREE, 1.1, 1.3, 0.12, matDark(THREE).color.getHex());
    back.position.set(0, 0.7, -0.5);
    g.add(back);
    g.position.set(x, 0.55, z);
    g.rotation.y = rotY;
    group.add(g);
  }
  chair(-0.05, 3.2, 0);
  chair(0.05, -3.2, Math.PI);

  // 向かい合う人物シルエット
  const figA = silhouetteFigure(THREE, matP(THREE, primary, 0.12), -2.5, 0, 2.5, 1.15);
  const figB = silhouetteFigure(THREE, matA(THREE, accent, 0.12), 2.5, 0, -2.5, 1.15);
  [figA, figB].forEach((f) => {
    f.traverse((ch) => {
      if (ch.material) {
        ch.material = ch.material.clone();
        ch.material.transparent = true;
        ch.material.opacity = 0.45;
      }
    });
    group.add(f);
  });

  // 握手のシルエット（中央上空）
  const hands = new THREE.Group();
  hands.add(mesh(THREE, new THREE.SphereGeometry(0.22, 8, 8), matA(THREE, accent, 0.35), -0.25, 0, 0));
  hands.add(mesh(THREE, new THREE.SphereGeometry(0.22, 8, 8), matP(THREE, primary, 0.35), 0.25, 0, 0));
  hands.add(mesh(THREE, new THREE.BoxGeometry(0.7, 0.15, 0.2), matA(THREE, accent, 0.25), 0, 0, 0));
  hands.position.set(0, 2.6, 0);
  group.add(hands);
  animatables.push({ mesh: hands, kind: "bob", baseY: 2.6, speed: 0.9, amp: 0.1 });

  // 双鏡
  group.add(mesh(THREE, new THREE.BoxGeometry(2.2, 3.5, 0.1), matMirror(THREE), -w / 2 + 0.5, 2.5, 0));
  group.add(mesh(THREE, new THREE.BoxGeometry(2.2, 3.5, 0.1), matMirror(THREE), w / 2 - 0.5, 2.5, 0));

  // 天秤
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.06, 0.06, 2.0, 6), matDark(THREE), 5, 2.5, -5));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.8, 0.06, 0.08), matA(THREE, accent, 0.3), 5, 3.5, -5));
  const panL = mesh(THREE, new THREE.CylinderGeometry(0.35, 0.3, 0.08, 10), matA(THREE, accent, 0.25), 4.2, 3.0, -5);
  const panR = mesh(THREE, new THREE.CylinderGeometry(0.35, 0.3, 0.08, 10), matA(THREE, accent, 0.25), 5.8, 3.0, -5);
  group.add(panL);
  group.add(panR);
  animatables.push({ mesh: panL, kind: "bob", baseY: 3.0, speed: 0.9, amp: 0.06, phase: 0 });
  animatables.push({ mesh: panR, kind: "bob", baseY: 3.0, speed: 0.9, amp: 0.06, phase: Math.PI });

  // 向かい合う扉
  group.add(box(THREE, 2.2, 3.5, 0.2, primary.getHex(), {
    emissive: primary.getHex(), emissiveIntensity: 0.12,
  })).position.set(-6, 2, d / 2 - 0.5);
  group.add(box(THREE, 2.2, 3.5, 0.2, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.12,
  })).position.set(6, 2, d / 2 - 0.5);

  lights.kind = "mirror";
  addPointLight(THREE, group, lights, lightCol.getHex(), 0.75, 0, 5, 0, 26);
  lights.extra = new THREE.PointLight(accent.getHex(), 0.55, 16, 2);
  lights.extra.position.set(0, 3, 3);
  lights.extra.userData = { base: 0.55 };
  group.add(lights.extra);
  addSpot(THREE, group, lights, accent.getHex(), 0.6,
    new THREE.Vector3(-4, 6, 0), new THREE.Vector3(0, 1, 0));
  // 反対側
  const spot2 = new THREE.SpotLight(primary.getHex(), 0.55, 28, Math.PI / 6, 0.4, 1);
  spot2.position.set(4, 6, 0);
  spot2.target.position.set(0, 1, 0);
  group.add(spot2);
  group.add(spot2.target);

  // Uranus, Pluto
  planetSlots.push(new THREE.Vector3(-3.5, 3.5, 0));
  planetSlots.push(new THREE.Vector3(3.5, 3.2, 0));
};

/** 8: 地下の変容庫 — 下りる感覚・水面・鍵箱・芽 */
BUILDERS[8] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  // 床を一段下げる演出: 周囲に段差
  floorSlab(THREE, group, w, d, 0x10080e);
  group.add(box(THREE, w + 2, 1.2, d + 2, 0x0a0508)).position.set(0, -0.5, 0);

  // 石壁・低い天井
  group.add(box(THREE, w, h, 0.5, secondary.getHex())).position.set(0, h / 2, -d / 2);
  group.add(box(THREE, 0.5, h, d, secondary.getHex())).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.5, h, d, secondary.getHex())).position.set(w / 2, h / 2, 0);
  group.add(box(THREE, w, 0.4, d, 0x0c060a)).position.set(0, h, 0);

  // 狭い入口アーチ
  group.add(box(THREE, w * 0.55, h, 0.6, secondary.getHex())).position.set(0, h / 2, d / 2 - 1);
  group.add(box(THREE, 2.4, 3.2, 0.7, 0x050308)).position.set(0, 1.8, d / 2 - 1);

  // 鍵のかかった大箱
  group.add(box(THREE, 3.2, 1.8, 2.0, matDark(THREE).color.getHex())).position.set(0, 1.0, -4);
  const lock = mesh(THREE, new THREE.TorusGeometry(0.4, 0.08, 8, 16), matA(THREE, accent, 0.45), 0.8, 1.6, -2.8);
  group.add(lock);
  animatables.push({ mesh: lock, kind: "pulseMat", speed: 1.3 });

  // 水面
  const water = mesh(THREE, new THREE.CylinderGeometry(3.5, 3.5, 0.15, 28), matA(THREE, accent, 0.2), 0, 0.25, 3);
  water.material = matA(THREE, accent, 0.35);
  water.material.transparent = true;
  water.material.opacity = 0.55;
  group.add(water);
  animatables.push({ mesh: water, kind: "pulseMat", speed: 0.6 });

  // 灰と芽
  group.add(mesh(THREE, new THREE.ConeGeometry(0.7, 0.35, 10), matDark(THREE), -4, 0.3, -1));
  const sprout = mesh(THREE, new THREE.ConeGeometry(0.15, 0.7, 6), matA(THREE, accent, 0.4), -4, 0.85, -1);
  group.add(sprout);
  animatables.push({ mesh: sprout, kind: "bob", baseY: 0.85, speed: 1.0, amp: 0.06 });

  // 共有の杯
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.35, 0.22, 0.55, 12), matP(THREE, primary, 0.25), 4, 0.6, 1));

  // 細い一筋の光
  lights.kind = "slit";
  addPointLight(THREE, group, lights, lightCol.getHex(), 0.3, 0, 4, 0, 16);
  lights.extra = new THREE.SpotLight(accent.getHex(), 1.4, 20, Math.PI / 20, 0.15, 1);
  lights.extra.position.set(0, h - 0.3, -d / 2 + 1);
  lights.extra.target.position.set(0, 0.3, 2);
  lights.extra.userData = { base: 1.4 };
  group.add(lights.extra);
  group.add(lights.extra.target);
  addSpot(THREE, group, lights, 0x401020, 0.2,
    new THREE.Vector3(0, 5, 0), new THREE.Vector3(0, 0, 0));

  planetSlots.push(new THREE.Vector3(0, 2.5, 0));
};

/**
 * 9: 探求のミュージアム展示室
 * 壁に埋まらない — 床の展示物（地球儀・地図・望遠鏡・古書・航海図・遠方の橋）
 */
BUILDERS[9] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, quality, animatables, planetSlots, exhibits, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w + 4, d + 4, 0x0a1020);

  // 背面の低い壁のみ（囲いすぎない）
  group.add(box(THREE, w, h * 0.55, 0.35, secondary.getHex())).position.set(0, h * 0.28, -d / 2);
  // 柱だけ（開放的なホール）
  const colMat = matP(THREE, primary, 0.12);
  [[-w * 0.4, d * 0.35], [w * 0.4, d * 0.35], [-w * 0.4, -d * 0.3], [w * 0.4, -d * 0.3]].forEach(([x, z]) => {
    group.add(mesh(THREE, new THREE.CylinderGeometry(0.35, 0.4, h * 0.7, 10), colMat, x, h * 0.35, z));
  });
  // 開放ドーム（薄い）
  const dome = mesh(
    THREE,
    new THREE.SphereGeometry(w * 0.42, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshStandardMaterial({
      color: primary.getHex(),
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
      emissive: primary.getHex(),
      emissiveIntensity: 0.08,
    }),
    0,
    h * 0.45,
    -2
  );
  group.add(dome);

  // 展示台 + 巨大地球儀
  group.add(box(THREE, 2.2, 0.9, 2.2, 0x1a2030)).position.set(-4, 0.45, 1);
  const globe = mesh(THREE, new THREE.SphereGeometry(1.35, 20, 20), matP(THREE, primary, 0.25), -4, 2.2, 1);
  group.add(globe);
  animatables.push({ mesh: globe, kind: "spin", speed: 0.25, axis: "y" });
  pushExhibit(
    exhibits,
    "巨大な地球儀",
    -4,
    2.2,
    1,
    "世界をひとつの球体として見る視点",
    "Great globe",
    "Seeing the world as one sphere"
  );

  // 世界地図（壁掛けパネル）
  group.add(box(THREE, 4.5, 2.4, 0.12, 0xc8d8e8, {
    emissive: accent.getHex(),
    emissiveIntensity: 0.12,
  })).position.set(0, 3.2, -d / 2 + 0.4);
  group.add(box(THREE, 4.7, 2.6, 0.15, matDark(THREE).color.getHex())).position.set(0, 3.2, -d / 2 + 0.3);
  pushExhibit(
    exhibits,
    "世界地図",
    0,
    3.2,
    -d / 2 + 0.5,
    "地図は「今いる場所」を超える想像力",
    "World map",
    "A map that stretches imagination beyond here"
  );

  // 望遠鏡（見やすい高さ・手前から見る）
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.5, 0.7, 0.9, 10), matDark(THREE), 4.5, 0.5, 2));
  const scope = mesh(THREE, new THREE.CylinderGeometry(0.18, 0.28, 3.8, 10), matA(THREE, accent, 0.25), 4.5, 2.4, 0.5);
  scope.rotation.z = -0.65;
  scope.rotation.x = 0.2;
  group.add(scope);
  pushExhibit(
    exhibits,
    "望遠鏡",
    4.5,
    2.2,
    1.2,
    "遠くを見るための道具",
    "Telescope",
    "A tool for looking farther"
  );

  // 本棚（側面の低め — 壁にならない）
  for (let row = 0; row < 3; row++) {
    group.add(box(THREE, 3.5, 0.12, 0.55, matDark(THREE).color.getHex())).position.set(-6.5, 1.0 + row * 0.9, -3);
    for (let b = 0; b < 6; b++) {
      group.add(box(THREE, 0.4, 0.65, 0.4, b % 2 ? primary.getHex() : accent.getHex())).position.set(
        -7.5 + b * 0.55,
        1.4 + row * 0.9,
        -3
      );
    }
  }
  pushExhibit(
    exhibits,
    "古書の棚",
    -6.5,
    2.0,
    -3,
    "思想と学びが積まれた棚",
    "Shelf of old books",
    "Thought and study stacked quietly"
  );

  // 羅針盤の台
  group.add(mesh(THREE, new THREE.CylinderGeometry(1.2, 1.2, 0.15, 24), matA(THREE, accent, 0.2), 0, 0.35, 4));
  const needle = mesh(THREE, new THREE.BoxGeometry(0.12, 0.08, 1.6), matP(THREE, primary, 0.35), 0, 0.5, 4);
  group.add(needle);
  animatables.push({ mesh: needle, kind: "spin", speed: 0.18, axis: "y" });
  pushExhibit(
    exhibits,
    "羅針盤",
    0,
    0.6,
    4,
    "方角を定め、旅の軸をつくる",
    "Compass",
    "Setting direction for the journey"
  );

  // 航海図（床に広げた大きなシート）
  group.add(box(THREE, 3.2, 0.04, 2.0, 0xd8c8a0)).position.set(5, 0.22, -4);
  for (let i = 0; i < 4; i++) {
    group.add(box(THREE, 2.6, 0.02, 0.04, primary.getHex())).position.set(5, 0.28, -4.6 + i * 0.4);
  }
  pushExhibit(
    exhibits,
    "航海図",
    5,
    0.5,
    -4,
    "未知の航路を描いた図",
    "Sea chart",
    "A chart of unknown routes"
  );

  // 遠方へ続く橋（展示の奥）
  group.add(box(THREE, 2.0, 0.2, 10, 0x2a3040)).position.set(0, 0.35, -d / 2 - 4);
  group.add(box(THREE, 0.15, 0.9, 10, accent.getHex(), {
    emissive: accent.getHex(),
    emissiveIntensity: 0.15,
  })).position.set(-1.1, 0.8, -d / 2 - 4);
  group.add(box(THREE, 0.15, 0.9, 10, accent.getHex(), {
    emissive: accent.getHex(),
    emissiveIntensity: 0.15,
  })).position.set(1.1, 0.8, -d / 2 - 4);
  // 遠方の門
  group.add(box(THREE, 3.5, 4.0, 0.3, primary.getHex(), {
    emissive: primary.getHex(),
    emissiveIntensity: 0.2,
  })).position.set(0, 2.2, -d / 2 - 9);
  pushExhibit(
    exhibits,
    "遠方へ続く橋",
    0,
    1.5,
    -d / 2 - 5,
    "今いる場所を超えて進む道",
    "Bridge to the far",
    "A path beyond where you stand"
  );

  // 星空（上の点）
  if (quality !== "low") {
    const count = 80;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * w;
      pos[i * 3 + 1] = 6 + Math.random() * 5;
      pos[i * 3 + 2] = (Math.random() - 0.5) * d;
    }
    group.add(
      new THREE.Points(
        new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
        new THREE.PointsMaterial({
          color: 0xc8d8ff,
          size: 0.14,
          transparent: true,
          opacity: 0.7,
          depthWrite: false,
        })
      )
    );
  }

  lights.kind = "open";
  addPointLight(THREE, group, lights, lightCol.getHex(), 0.7, 0, 6, 0, 36);
  lights.extra = new THREE.HemisphereLight(lightCol.getHex(), 0x0a1020, 0.5);
  group.add(lights.extra);
  addSpot(THREE, group, lights, accent.getHex(), 0.7,
    new THREE.Vector3(-4, 8, 2), new THREE.Vector3(-4, 1, 1), Math.PI / 7);
  const spot2 = new THREE.SpotLight(0xa8c8ff, 0.55, 28, Math.PI / 8, 0.4, 1);
  spot2.position.set(4, 7, 2);
  spot2.target.position.set(4.5, 1, 1);
  group.add(spot2);
  group.add(spot2.target);

  planetSlots.push(new THREE.Vector3(0, 3.5, -1));
  planetSlots.push(new THREE.Vector3(-2, 3.2, 2));
};

/**
 * 10: 塔 — 階段を登り街を見下ろす
 */
BUILDERS[10] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, quality, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, 0x14120c);

  // 柱廊（高い）
  const colMat = matP(THREE, primary, 0.2);
  for (let i = 0; i < 8; i++) {
    const ang = (i / 8) * Math.PI * 2;
    if (ang > 1.8 && ang < 4.5) continue; // 入口空け
    const x = Math.cos(ang) * 6;
    const z = Math.sin(ang) * 6;
    group.add(mesh(THREE, new THREE.CylinderGeometry(0.45, 0.55, h * 0.75, 10), colMat, x, h * 0.38, z));
  }

  // 螺旋階段（段）
  const steps = quality === "low" ? 12 : 20;
  for (let i = 0; i < steps; i++) {
    const ang = i * 0.45;
    const r = 3.2;
    const y = 0.35 + i * (h * 0.55 / steps);
    group.add(box(THREE, 1.8, 0.25, 1.0, i % 2 ? primary.getHex() : accent.getHex(), {
      emissive: primary.getHex(), emissiveIntensity: 0.08,
    })).position.set(Math.cos(ang) * r, y, Math.sin(ang) * r - 1);
  }

  // 展望デッキ
  group.add(box(THREE, 10, 0.35, 10, 0x2a2418)).position.set(0, h * 0.72, 0);
  // 手すり
  group.add(mesh(THREE, new THREE.TorusGeometry(5.2, 0.1, 8, 32), matA(THREE, accent, 0.2), 0, h * 0.78, 0)).rotation.x = Math.PI / 2;

  // 紋章（王冠ではない）
  group.add(box(THREE, 1.6, 2.0, 0.15, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.35,
  })).position.set(0, h * 0.45, -7);

  // 灯台
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.4, 0.7, 4, 10), matP(THREE, primary, 0.15), 5, h * 0.72 + 2.2, 3));
  const lamp = mesh(THREE, new THREE.SphereGeometry(0.45, 12, 12), matA(THREE, accent, 0.7), 5, h * 0.72 + 4.5, 3);
  group.add(lamp);
  animatables.push({ mesh: lamp, kind: "pulseMat", speed: 1.4 });

  // 街の灯（遠景パーティクル代わりの小球）
  for (let i = 0; i < (quality === "low" ? 12 : 24); i++) {
    const lx = (Math.random() - 0.5) * 40;
    const lz = 12 + Math.random() * 20;
    group.add(mesh(THREE, new THREE.SphereGeometry(0.12, 6, 6),
      new THREE.MeshBasicMaterial({ color: 0xffe0a0 }),
      lx, 1 + Math.random() * 3, lz
    ));
  }

  lights.kind = "summit";
  addPointLight(THREE, group, lights, lightCol.getHex(), 1.2, 0, h * 0.85, 0, 40);
  addSpot(THREE, group, lights, accent.getHex(), 0.9,
    new THREE.Vector3(0, h + 2, 0), new THREE.Vector3(0, h * 0.7, 0));

  planetSlots.push(new THREE.Vector3(0, h * 0.82, 0));
};

/**
 * 11: つながりの広場 — 大きな円卓・多数の椅子・光のノード網
 */
BUILDERS[11] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, 0x0a1616);

  // 低い円形の縁のみ（開放）
  group.add(mesh(THREE, new THREE.TorusGeometry(w * 0.42, 0.35, 8, 40), matP(THREE, primary, 0.15), 0, 0.4, 0)).rotation.x = Math.PI / 2;

  // 巨大円卓
  group.add(mesh(THREE, new THREE.CylinderGeometry(4.5, 4.5, 0.25, 32), matDark(THREE), 0, 0.95, 0));
  // 椅子がたくさん
  for (let i = 0; i < 10; i++) {
    const ang = (i / 10) * Math.PI * 2;
    const x = Math.cos(ang) * 6.2;
    const z = Math.sin(ang) * 6.2;
    group.add(box(THREE, 1.0, 0.12, 1.0, matDark(THREE).color.getHex())).position.set(x, 0.55, z);
    group.add(box(THREE, 1.0, 1.0, 0.12, matDark(THREE).color.getHex())).position.set(
      x + Math.cos(ang) * 0.4, 1.1, z + Math.sin(ang) * 0.4
    );
  }

  // 光のノード網
  const nodes = [];
  for (let j = 0; j < 9; j++) {
    const ang = (j / 9) * Math.PI * 2;
    const r = 8 + (j % 3) * 1.5;
    const nd = mesh(THREE, new THREE.SphereGeometry(0.45, 12, 12), matA(THREE, accent, 0.5),
      Math.cos(ang) * r, 2.5 + Math.sin(j) * 0.8, Math.sin(ang) * r);
    nd.material = matA(THREE, accent, 0.55);
    group.add(nd);
    nodes.push(nd);
    animatables.push({ mesh: nd, kind: "pulseMat", speed: 1.3 + j * 0.07, phase: j });
    animatables.push({ mesh: nd, kind: "bob", baseY: nd.position.y, speed: 0.7, amp: 0.15, phase: j });
  }
  // リング
  const ring = mesh(THREE, new THREE.TorusGeometry(9, 0.06, 8, 48), matP(THREE, primary, 0.3), 0, 2.8, 0);
  group.add(ring);
  animatables.push({ mesh: ring, kind: "spin", speed: 0.12, axis: "y" });

  // 共同設計図
  group.add(box(THREE, 2.5, 0.05, 1.8, 0xe0f0e8)).position.set(0, 1.15, 0);
  for (let i = 0; i < 4; i++) {
    group.add(box(THREE, 1.8, 0.02, 0.04, primary.getHex())).position.set(0, 1.2, -0.5 + i * 0.35);
  }

  // 掲示板
  group.add(box(THREE, 3, 2.2, 0.15, 0x1a2828)).position.set(0, 3.5, -11);
  group.add(box(THREE, 2.6, 0.4, 0.05, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.25,
  })).position.set(0, 4.2, -10.9);

  lights.kind = "pulse";
  addPointLight(THREE, group, lights, accent.getHex(), 0.85, 0, 5, 0, 35);
  addSpot(THREE, group, lights, primary.getHex(), 0.5,
    new THREE.Vector3(0, 10, 0), new THREE.Vector3(0, 0, 0), Math.PI / 4);

  planetSlots.push(new THREE.Vector3(0, 4.5, 0)); // Moon
};

/**
 * 12: 霧の長い回廊 — 端が見えない・水面・月明かり・ベッドの alcove
 */
BUILDERS[12] = function (c) {
  const { THREE, group, arch, primary, secondary, accent, lightCol, quality, animatables, planetSlots, lights } = c;
  const { w, d, h } = arch;
  floorSlab(THREE, group, w, d, 0x0c0e18);

  // 長い半透明の壁（回廊）
  const wallMatOpts = {
    transparent: true,
    opacity: 0.22,
    emissive: primary.getHex(),
    emissiveIntensity: 0.15,
    side: THREE.DoubleSide,
  };
  group.add(box(THREE, 0.3, h, d, primary.getHex(), wallMatOpts)).position.set(-w / 2, h / 2, 0);
  group.add(box(THREE, 0.3, h, d, primary.getHex(), wallMatOpts)).position.set(w / 2, h / 2, 0);
  // アーチ列
  for (let i = 0; i < 7; i++) {
    const z = d / 2 - 3 - i * 4.5;
    group.add(box(THREE, w * 0.9, 0.35, 0.35, accent.getHex(), {
      transparent: true, opacity: 0.4, emissive: accent.getHex(), emissiveIntensity: 0.2,
    })).position.set(0, h * 0.75, z);
    group.add(box(THREE, 0.35, h * 0.7, 0.35, secondary.getHex(), {
      transparent: true, opacity: 0.5,
    })).position.set(-w * 0.35, h * 0.35, z);
    group.add(box(THREE, 0.35, h * 0.7, 0.35, secondary.getHex(), {
      transparent: true, opacity: 0.5,
    })).position.set(w * 0.35, h * 0.35, z);
  }

  // 水面（長い）
  const water = box(THREE, w * 0.6, 0.08, d * 0.7, accent.getHex(), {
    transparent: true, opacity: 0.4, emissive: accent.getHex(), emissiveIntensity: 0.2,
  });
  water.position.set(0, 0.2, -2);
  group.add(water);
  animatables.push({ mesh: water, kind: "pulseMat", speed: 0.5 });

  // カーテン / ヴェール
  for (let i = 0; i < 4; i++) {
    const veil = mesh(THREE, new THREE.PlaneGeometry(2.5, h * 0.7), matP(THREE, primary, 0.1),
      (i % 2 === 0 ? -1 : 1) * 3, h * 0.4, d / 2 - 6 - i * 5);
    veil.material = matP(THREE, primary, 0.1);
    veil.material.transparent = true;
    veil.material.opacity = 0.3;
    veil.material.side = THREE.DoubleSide;
    group.add(veil);
    animatables.push({ mesh: veil, kind: "sway", speed: 0.35 + i * 0.05, amp: 0.08 });
  }

  // ベッド alcove
  group.add(box(THREE, 3.5, 0.4, 2.0, matDark(THREE).color.getHex())).position.set(-3, 0.4, -d / 2 + 4);
  group.add(box(THREE, 3.2, 0.25, 1.6, accent.getHex(), {
    emissive: accent.getHex(), emissiveIntensity: 0.08,
  })).position.set(-3, 0.65, -d / 2 + 4);

  // 閉じた本
  group.add(box(THREE, 0.7, 0.9, 0.2, matDark(THREE).color.getHex())).position.set(3, 0.7, -d / 2 + 6);

  // 月明かりの球体
  const moon = mesh(THREE, new THREE.SphereGeometry(1.2, 16, 16),
    new THREE.MeshStandardMaterial({
      color: 0xc8d0f0,
      emissive: 0xa0b0e0,
      emissiveIntensity: 0.65,
      transparent: true,
      opacity: 0.85,
    }), 0, h - 1.5, -d / 2 + 2);
  group.add(moon);
  animatables.push({ mesh: moon, kind: "pulseMat", speed: 0.7 });
  animatables.push({ mesh: moon, kind: "bob", baseY: h - 1.5, speed: 0.4, amp: 0.15 });

  // 遠くの扉（霞）
  group.add(box(THREE, 2.5, 3.5, 0.2, accent.getHex(), {
    transparent: true, opacity: 0.25, emissive: accent.getHex(), emissiveIntensity: 0.15,
  })).position.set(0, 2, -d / 2 + 0.5);

  lights.kind = "mist";
  addPointLight(THREE, group, lights, lightCol.getHex(), 0.4, 0, 4, 0, 40);
  addSpot(THREE, group, lights, 0xc8d0f0, 0.8,
    new THREE.Vector3(0, h, -d / 2 + 3), new THREE.Vector3(0, 0, 0), Math.PI / 5);

  // 濃い霧パーティクル
  if (quality !== "low") {
    const count = 140;
    const pos = new Float32Array(count * 3);
    const phases = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * w * 0.9;
      pos[i * 3 + 1] = 0.5 + Math.random() * (h - 1);
      pos[i * 3 + 2] = (Math.random() - 0.5) * d * 0.9;
      phases[i] = Math.random() * Math.PI * 2;
    }
    const pts = new THREE.Points(
      new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
      new THREE.PointsMaterial({
        color: accent.getHex(),
        size: 0.45,
        transparent: true,
        opacity: 0.32,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    );
    pts.userData = { kind: "mist", phases, house: 12 };
    group.add(pts);
    animatables.push({ mesh: pts, kind: "particles", house: 12 });
  }

  planetSlots.push(new THREE.Vector3(0, 3.5, -d * 0.2));
};

BUILDERS.default = BUILDERS[1];

// ═══════════════════════════════════════════════════════════
// パーティクル（簡易・低負荷）— ハウス固有は一部で内蔵
// ═══════════════════════════════════════════════════════════

function addHouseAmbientParticles(THREE, group, n, primary, accent, arch, animatables) {
  if (n === 12) return; // 既に濃霧を入れた
  let kind = "dust";
  let color = primary.getHex();
  let size = 0.12;
  let count = 50;
  if (n === 4) { kind = "ember"; color = accent.getHex(); count = 40; }
  if (n === 3) { kind = "paper"; color = accent.getHex(); }
  if (n === 5) { kind = "glitter"; color = accent.getHex(); count = 60; }
  if (n === 9) { kind = "star"; color = 0xc8d8ff; count = 80; size = 0.16; }
  if (n === 11) { kind = "spark"; color = accent.getHex(); }
  if (n === 8) { kind = "ash"; color = 0x804060; count = 35; }

  const pos = new Float32Array(count * 3);
  const phases = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() - 0.5) * arch.w * 0.85;
    pos[i * 3 + 1] = 0.5 + Math.random() * (arch.h - 1.5);
    pos[i * 3 + 2] = (Math.random() - 0.5) * arch.d * 0.85;
    phases[i] = Math.random() * Math.PI * 2;
  }
  const points = new THREE.Points(
    new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
    new THREE.PointsMaterial({
      color,
      size,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
  );
  points.userData = { kind, phases, house: n };
  group.add(points);
  animatables.push({ mesh: points, kind: "particles", house: n });
}

// 各ビルダー後に粒子を足すラッパー — buildOneHouse から呼ぶ
const _origBuilders = { ...BUILDERS };
Object.keys(ARCH).forEach((key) => {
  const n = parseInt(key, 10);
  const orig = BUILDERS[n];
  if (!orig) return;
  BUILDERS[n] = function (c) {
    orig(c);
    if (c.quality !== "low") {
      addHouseAmbientParticles(c.THREE, c.group, n, c.primary, c.accent, c.arch, c.animatables);
    }
    // ライトが未設定ならフォールバック
    if (!c.lights.pl) {
      addPointLight(c.THREE, c.group, c.lights, c.lightCol.getHex(), 0.9, 0, c.arch.h * 0.6, 0, 28);
    }
    if (!c.lights.spot) {
      addSpot(c.THREE, c.group, c.lights, c.accent.getHex(), 0.45,
        new c.THREE.Vector3(0, c.arch.h + 1, c.arch.entryZ * 0.3),
        new c.THREE.Vector3(0, 0, -2));
    }
    // 展示マーカーが無い部屋は中央付近に既定展示を足す（案内カメラ用）
    if (c.exhibits && c.exhibits.length === 0) {
      const defaults = DEFAULT_EXHIBITS[n] || [
        {
          name: "展示の中心",
          nameEn: "Center exhibit",
          x: 0,
          y: 2.2,
          z: 0,
          caption: "この部屋の象徴",
          captionEn: "The symbol of this room",
        },
      ];
      defaults.forEach((ex) =>
        pushExhibit(c.exhibits, ex.name, ex.x, ex.y, ex.z, ex.caption, ex.nameEn, ex.captionEn)
      );
    }
  };
});

/** シネマティック案内用の既定展示ポイント */
const DEFAULT_EXHIBITS = {
  1: [
    { name: "姿見", nameEn: "Mirror", x: 0, y: 2.5, z: -6, caption: "自分の輪郭を映す鏡", captionEn: "A mirror for your outline" },
    { name: "半開きの扉", nameEn: "Half-open door", x: 0, y: 2, z: 4, caption: "世界へ踏み出す入口", captionEn: "A door into the world" },
    { name: "足跡", nameEn: "Footprints", x: 0, y: 0.3, z: 2, caption: "行動の始まり", captionEn: "The start of action" },
  ],
  2: [
    { name: "保管棚", nameEn: "Storage shelves", x: -5, y: 2, z: -2, caption: "価値あるものが並ぶ棚", captionEn: "What you keep and value" },
    { name: "道具台", nameEn: "Workbench", x: 0, y: 1.3, z: 2, caption: "才能を使う作業台", captionEn: "Where talent becomes use" },
    { name: "鍵", nameEn: "Key", x: 3, y: 2, z: 4, caption: "大切に守るもの", captionEn: "What you protect" },
  ],
  3: [
    { name: "本棚", nameEn: "Bookshelf", x: -3, y: 2, z: -4, caption: "言葉と学び", captionEn: "Words and learning" },
    { name: "手紙", nameEn: "Letters", x: 0, y: 2.5, z: 0, caption: "行き交う情報", captionEn: "Messages in motion" },
    { name: "自転車", nameEn: "Bicycle", x: 2, y: 1, z: 8, caption: "日常の移動", captionEn: "Daily movement" },
  ],
  4: [
    { name: "暖炉", nameEn: "Hearth", x: 0, y: 1.5, z: -5, caption: "心の土台の火", captionEn: "Fire of the inner base" },
    { name: "写真", nameEn: "Photo", x: 4, y: 2.2, z: -5, caption: "記憶と家族", captionEn: "Memory and family" },
    { name: "椅子", nameEn: "Chair", x: -4, y: 1, z: 1, caption: "安心できる居場所", captionEn: "A place to rest" },
  ],
  5: [
    { name: "舞台", nameEn: "Stage", x: 0, y: 1.2, z: -6, caption: "表現の中心", captionEn: "Center of expression" },
    { name: "客席", nameEn: "Audience seats", x: 0, y: 1.5, z: 6, caption: "見る側の闇", captionEn: "The dark of watching" },
    { name: "ピアノ", nameEn: "Piano", x: 6, y: 1.2, z: -3, caption: "創るための楽器", captionEn: "An instrument for making" },
    { name: "描きかけの絵", nameEn: "Unfinished painting", x: -6, y: 2.2, z: -4, caption: "途中の創作", captionEn: "Creation in progress" },
  ],
  6: [
    { name: "作業デスク", nameEn: "Work desk", x: 0, y: 1.2, z: 2, caption: "毎日の積み重ね", captionEn: "Daily accumulation" },
    { name: "壁時計", nameEn: "Wall clock", x: 0, y: 5, z: -8, caption: "時間と習慣", captionEn: "Time and habit" },
    { name: "歯車", nameEn: "Gears", x: -6, y: 2.5, z: -6, caption: "仕組みを整える", captionEn: "Tuning the mechanism" },
  ],
  7: [
    { name: "向かい合う椅子", nameEn: "Facing chairs", x: 0, y: 1, z: 3, caption: "他者と向き合う席", captionEn: "Seats facing the other" },
    { name: "契約書", nameEn: "Contract", x: 0, y: 1.2, z: 0, caption: "約束と境界", captionEn: "Promise and boundary" },
    { name: "握手", nameEn: "Handshake", x: 0, y: 2.6, z: 0, caption: "出会いの瞬間", captionEn: "The moment of meeting" },
  ],
  8: [
    { name: "鍵のかかった箱", nameEn: "Locked chest", x: 0, y: 1.2, z: -4, caption: "共有と秘密", captionEn: "Sharing and secrecy" },
    { name: "水面", nameEn: "Water surface", x: 0, y: 0.4, z: 3, caption: "深い感情の層", captionEn: "Deep emotional layer" },
    { name: "灰と芽", nameEn: "Ash and sprout", x: -4, y: 0.8, z: -1, caption: "終わりと再生", captionEn: "Ending and renewal" },
  ],
  10: [
    { name: "螺旋階段", nameEn: "Spiral stairs", x: 2, y: 4, z: 0, caption: "役割への登り", captionEn: "Ascent toward role" },
    { name: "展望デッキ", nameEn: "Lookout deck", x: 0, y: 12, z: 0, caption: "社会から見える位置", captionEn: "Where society can see you" },
    { name: "灯台", nameEn: "Lighthouse", x: 5, y: 14, z: 3, caption: "公の光", captionEn: "A public light" },
  ],
  11: [
    { name: "円卓", nameEn: "Round table", x: 0, y: 1, z: 0, caption: "共有のテーブル", captionEn: "A shared table" },
    { name: "光のノード", nameEn: "Light nodes", x: 6, y: 2.5, z: 0, caption: "つながりの点", captionEn: "Points of connection" },
    { name: "掲示板", nameEn: "Board", x: 0, y: 3.5, z: -10, caption: "共同の計画", captionEn: "Shared plans" },
  ],
  12: [
    { name: "水面", nameEn: "Water", x: 0, y: 0.4, z: -2, caption: "静かな内界", captionEn: "Quiet inner world" },
    { name: "月明かり", nameEn: "Moonlight", x: 0, y: 6, z: -8, caption: "夢と休息の光", captionEn: "Light of dream and rest" },
    { name: "ベッド", nameEn: "Bed", x: -3, y: 0.6, z: -10, caption: "手放しと休息", captionEn: "Release and rest" },
  ],
};

// ═══════════════════════════════════════════════════════════
// アニメ・大気
// ═══════════════════════════════════════════════════════════

export function animateSymbolics(animatables, houseGroups, currentHouse, t, dt, reducedMotion) {
  if (reducedMotion) return;

  animatables.forEach((a) => {
    if (!a.mesh) return;
    const ph = a.phase || 0;
    if (a.kind === "bob") {
      const by = a.baseY != null ? a.baseY : a.mesh.position.y;
      a.mesh.position.y = by + Math.sin(t * (a.speed || 1) + ph) * (a.amp || 0.1);
    } else if (a.kind === "sway") {
      a.mesh.rotation.y = Math.sin(t * (a.speed || 1) + ph) * (a.amp || 0.08);
    } else if (a.kind === "spin") {
      if (a.axis === "z") a.mesh.rotation.z += (a.speed || 1) * dt;
      else if (a.axis === "x") a.mesh.rotation.x += (a.speed || 1) * dt;
      else a.mesh.rotation.y += (a.speed || 1) * dt;
    } else if (a.kind === "flame") {
      const fy = a.baseY != null ? a.baseY : 1.8;
      a.mesh.position.y = fy + Math.sin(t * (a.speed || 6) + ph) * (a.amp || 0.1);
      a.mesh.scale.y = 1 + Math.sin(t * (a.speed || 6) * 1.3 + ph) * 0.18;
      if (a.mesh.material && a.mesh.material.emissiveIntensity != null) {
        a.mesh.material.emissiveIntensity = 0.55 + Math.sin(t * 8 + ph) * 0.25;
      }
    } else if (a.kind === "pulseMat") {
      if (a.mesh.material && a.mesh.material.emissiveIntensity != null) {
        a.mesh.material.emissiveIntensity = 0.3 + Math.sin(t * (a.speed || 2) + ph) * 0.35;
      }
    } else if (a.kind === "drift") {
      a.mesh.position.y = (a.baseY || 2) + Math.sin(t * (a.speed || 0.8) + ph) * (a.amp || 0.2);
      a.mesh.position.x = (a.baseX || 0) + Math.cos(t * (a.speed || 0.8) * 0.6 + ph) * (a.amp || 0.2);
    } else if (a.kind === "particles") {
      const pos = a.mesh.geometry.attributes.position;
      const phases = a.mesh.userData.phases;
      const kind = a.mesh.userData.kind || "dust";
      const arr = pos.array;
      const hMax = 12;
      for (let i = 0; i < pos.count; i++) {
        const ix = i * 3;
        const pf = phases ? phases[i] : i;
        if (kind === "ember" || kind === "ash") {
          arr[ix + 1] += dt * 0.45;
          if (arr[ix + 1] > hMax) arr[ix + 1] = 0.3;
        } else if (kind === "mist") {
          arr[ix] += Math.sin(t * 0.3 + pf) * dt * 0.25;
          arr[ix + 2] += Math.cos(t * 0.22 + pf) * dt * 0.2;
        } else if (kind === "glitter" || kind === "paper") {
          arr[ix + 1] += Math.sin(t * 0.9 + pf) * dt * 0.2;
        } else {
          arr[ix + 1] += Math.sin(t * 0.6 + pf) * dt * 0.12;
        }
      }
      pos.needsUpdate = true;
    }
  });

  Object.keys(houseGroups).forEach((k) => {
    const g = houseGroups[k];
    if (!g || !g.light) return;
    const n = parseInt(k, 10);
    const active = n === currentHouse;
    const bi = g.baseIntensity != null ? g.baseIntensity : 0.85;
    const mult = active ? 1.2 : 0.35;
    if (g.lightKind === "flicker") {
      g.light.intensity = bi * mult * (0.7 + Math.random() * 0.45);
    } else if (g.lightKind === "pulse") {
      g.light.intensity = bi * mult * (0.85 + Math.sin(t * 2.2 + n) * 0.25);
    } else if (g.lightKind === "spotlight" && active && g.spot) {
      g.spot.intensity = (g.spotBase || 1) * (0.95 + Math.sin(t * 1.3) * 0.12);
    }
  });
}

export function applyAtmosphere(ctx, houseGroups, housesData, num) {
  const { fog, ambient, hemi, scene } = ctx;
  const THREE = ctx.THREE;

  if (num >= 1 && housesData[num]) {
    const pal = housesData[num].palette;
    const fogCol = hexColor(THREE, pal.fog || "#07080e").getHex();
    fog.color.setHex(fogCol);
    // スケールに合わせた霧
    if (num === 12) fog.density = 0.035;
    else if (num === 8) fog.density = 0.03;
    else if (num === 5) fog.density = 0.014; // 劇場: 客席の暗さを保つ
    else if (num === 9 || num === 10) fog.density = 0.008;
    else fog.density = 0.016;

    scene.background.setHex(fogCol);
    ambient.color.copy(hexColor(THREE, pal.light || "#fff"));
    // 第5は客席暗め
    ambient.intensity = num === 5 ? 0.12 : num === 8 ? 0.14 : num === 12 ? 0.2 : 0.32;
    hemi.color.copy(hexColor(THREE, pal.accent || "#fff"));
    hemi.groundColor.copy(hexColor(THREE, pal.secondary || "#111"));

    Object.keys(houseGroups).forEach((k) => {
      const g = houseGroups[k];
      const active = parseInt(k, 10) === num;
      const bi = g.baseIntensity != null ? g.baseIntensity : 0.85;
      const sb = g.spotBase != null ? g.spotBase : 0.5;
      g.light.intensity = active ? bi * 1.2 : bi * 0.3;
      if (g.spot) g.spot.intensity = active ? sb * 1.15 : sb * 0.25;
    });
  } else {
    fog.color.setHex(0x07080e);
    fog.density = 0.01;
    scene.background.setHex(0x07080e);
    ambient.color.set(0xb8b0a0);
    ambient.intensity = 0.28;
    Object.keys(houseGroups).forEach((k) => {
      const g = houseGroups[k];
      g.light.intensity = (g.baseIntensity || 0.85) * 0.85;
      if (g.spot) g.spot.intensity = (g.spotBase || 0.5) * 0.75;
    });
  }
}
