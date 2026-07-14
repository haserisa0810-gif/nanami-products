/**
 * Architecture Edition — 現実にありそうな博物館建築
 * 第4・5・9 をヒーロー棟として詳細化。他は建築シェル。
 * 抽象版 house-builder とは独立。
 */
import { housePosition, hexColor } from "../../house-tour/js/scene.js";
import { createMaterialKit, stdMat } from "./materials.js";
import { attachLivedInProps } from "./life-props.js";

/** 抽象版と同じ円環半径を使い、ショット計算を共有する */
export { RING_R, EYE_H, WORLD_BOUND } from "../../house-tour/js/scene.js";
import { RING_R, EYE_H, WORLD_BOUND } from "../../house-tour/js/scene.js";

/** 実寸に近いスケール（メートル想定） */
const ARCH = {
  1: { w: 10, d: 12, h: 5.5, entryZ: 7 },
  2: { w: 11, d: 14, h: 4.8, entryZ: 8 },
  3: { w: 7, d: 18, h: 4.5, entryZ: 9 },
  4: { w: 12, d: 14, h: 6.5, entryZ: 8 },
  5: { w: 16, d: 20, h: 8, entryZ: 10 },
  6: { w: 12, d: 14, h: 4.5, entryZ: 8 },
  7: { w: 11, d: 12, h: 5, entryZ: 7 },
  8: { w: 10, d: 12, h: 4.2, entryZ: 7 },
  9: { w: 14, d: 16, h: 10, entryZ: 9 },
  10: { w: 10, d: 10, h: 14, entryZ: 7 },
  11: { w: 16, d: 16, h: 5.5, entryZ: 9 },
  12: { w: 8, d: 20, h: 4.8, entryZ: 10 },
};

export function buildCampus(ctx, housesData) {
  const { THREE, scene, quality } = ctx;
  const mats = createMaterialKit(THREE);
  const animatables = [];
  const houseGroups = {};
  const entryWorld = {};

  // 広場（石畳）
  const plaza = new THREE.Mesh(
    new THREE.CircleGeometry(RING_R + 18, 64),
    mats.stone
  );
  plaza.rotation.x = -Math.PI / 2;
  plaza.receiveShadow = true;
  scene.add(plaza);

  // 中央ホール（小さなガラス屋根のロビー）
  buildLobby(THREE, scene, mats, quality);

  // リング線
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(RING_R - 0.4, RING_R + 0.15, 96),
    new THREE.MeshBasicMaterial({
      color: 0xc9a96e,
      transparent: true,
      opacity: 0.28,
      side: THREE.DoubleSide,
    })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.03;
  scene.add(ring);

  for (let n = 1; n <= 12; n++) {
    const h = housesData[n];
    if (!h) continue;
    const built = buildBuilding(ctx, n, h, mats, animatables);
    houseGroups[n] = built;
    built.group.updateMatrixWorld(true);
    const world = built.entryLocal.clone();
    built.group.localToWorld(world);
    entryWorld[n] = { x: world.x, y: EYE_H, z: world.z };
  }

  return { houseGroups, animatables, entryWorld, mats };
}

function buildLobby(THREE, scene, mats, quality) {
  const base = mesh(THREE, new THREE.CylinderGeometry(5.5, 6, 0.4, 32), mats.stone, 0, 0.2, 0);
  scene.add(base);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const col = mesh(
      THREE,
      new THREE.CylinderGeometry(0.28, 0.32, 4.2, 12),
      mats.stone,
      Math.cos(a) * 4.2,
      2.3,
      Math.sin(a) * 4.2
    );
    scene.add(col);
  }
  const roof = mesh(
    THREE,
    new THREE.CylinderGeometry(5.8, 5.8, 0.2, 32),
    mats.darkMetal,
    0,
    4.5,
    0
  );
  scene.add(roof);
  // 中心の案内台
  const desk = mesh(THREE, new THREE.CylinderGeometry(1.2, 1.3, 1.0, 20), mats.woodPanel, 0, 0.7, 0);
  scene.add(desk);
  const crystal = mesh(
    THREE,
    new THREE.IcosahedronGeometry(0.55, 1),
    stdMat(THREE, 0xe8d5b0, { metalness: 0.4, roughness: 0.25, emissive: 0xc9a96e, emissiveIntensity: 0.35 }),
    0,
    1.8,
    0
  );
  scene.add(crystal);
}

function buildBuilding(ctx, n, houseData, mats, animatables) {
  const { THREE, scene, quality } = ctx;
  const arch = ARCH[n];
  const group = new THREE.Group();
  group.name = "arch_house_" + n;
  const pos = housePosition(n, THREE);
  group.position.copy(pos);
  group.lookAt(0, 0, 0);
  group.rotateY(Math.PI);

  const pal = houseData.palette || {};
  const primary = hexColor(THREE, pal.primary || "#888");
  const accent = hexColor(THREE, pal.accent || "#ccc");
  const lightCol = hexColor(THREE, pal.light || "#fff");

  const exhibits = [];
  const planetSlots = [];
  const lights = { pl: null, spot: null, kind: "steady", base: 0.9, spotBase: 0.5 };

  const builders = {
    1: buildHouse1,
    2: buildHouse2,
    3: buildHouse3,
    4: buildHouse4,
    5: buildHouse5,
    6: buildHouse6,
    7: buildHouse7,
    8: buildHouse8,
    9: buildHouse9,
    10: buildHouse10,
    11: buildHouse11,
    12: buildHouse12,
  };
  const builder = builders[n] || buildGenericShell;
  const buildCtx = {
    THREE,
    group,
    arch,
    mats,
    primary,
    accent,
    lightCol,
    quality,
    exhibits,
    planetSlots,
    lights,
    animatables,
    n,
  };
  builder(buildCtx);

  // 生活感レイヤ（ON/OFF 可・本体建築とは別グループ）
  attachLivedInProps(buildCtx);

  // アプローチ道
  const path = mesh(
    THREE,
    new THREE.BoxGeometry(2.2, 0.08, 28),
    mats.stone,
    0,
    0.04,
    arch.entryZ + 12
  );
  group.add(path);

  // 館名プレート
  const plate = makePlate(THREE, "H" + n, primary.getStyle());
  plate.position.set(0, 2.8, arch.entryZ + 0.6);
  group.add(plate);

  scene.add(group);

  ensureLight(THREE, group, lights, lightCol, accent, arch);

  return {
    group,
    light: lights.pl,
    spot: lights.spot,
    lightKind: lights.kind,
    baseIntensity: lights.base,
    spotBase: lights.spotBase,
    palette: pal,
    planetSlots,
    exhibits,
    entryLocal: new THREE.Vector3(0, EYE_H, arch.entryZ + 12),
    arch,
  };
}

// ─── 1 夜明けの門・玄関ホール ────────────────────────────
function buildHouse1(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  addWalls(THREE, group, w, d, h, mats.stone, { openFront: true });
  floor(THREE, group, w - 0.3, d - 0.3, mats.stone);
  // 大きな門柱
  [-w * 0.32, w * 0.32].forEach((x) => {
    group.add(mesh(THREE, new THREE.BoxGeometry(1.1, h * 0.95, 1.1), mats.stone, x, h * 0.48, d / 2 - 0.4));
  });
  group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.75, 0.55, 1.0), mats.stone, 0, h * 0.88, d / 2 - 0.4));
  // 半開きの重い扉
  const doorL = mesh(THREE, new THREE.BoxGeometry(1.5, 2.8, 0.14), mats.woodPanel, -0.95, 1.45, d / 2 - 0.55);
  doorL.rotation.y = 0.55;
  group.add(doorL);
  const doorR = mesh(THREE, new THREE.BoxGeometry(1.5, 2.8, 0.14), mats.woodPanel, 0.95, 1.45, d / 2 - 0.55);
  doorR.rotation.y = -0.4;
  group.add(doorR);
  // 姿見
  group.add(mesh(THREE, new THREE.BoxGeometry(2.4, 3.4, 0.12), mats.glass, 0, 2.1, -d / 2 + 0.5));
  group.add(mesh(THREE, new THREE.BoxGeometry(2.7, 3.7, 0.18), mats.brass, 0, 2.1, -d / 2 + 0.4));
  // 足跡
  for (let i = 0; i < 6; i++) {
    group.add(
      mesh(THREE, new THREE.BoxGeometry(0.35, 0.04, 0.55), mats.darkMetal, (i % 2) * 0.35 - 0.15, 0.14, d * 0.2 - i * 0.9)
    );
  }
  const mask = mesh(
    THREE,
    new THREE.SphereGeometry(0.4, 12, 10, 0, Math.PI * 2, 0, Math.PI / 1.6),
    stdMat(THREE, accent.getHex(), { emissive: accent.getHex(), emissiveIntensity: 0.25 }),
    3.2,
    2.0,
    -1
  );
  group.add(mask);
  animatables.push({ mesh: mask, kind: "bob", baseY: 2.0, speed: 1.1, amp: 0.08 });

  pushEx(exhibits, "姿見", "Mirror", 0, 2.1, -d / 2 + 0.5, "自分の輪郭", "Your outline");
  pushEx(exhibits, "半開きの扉", "Half-open doors", 0, 1.5, d / 2 - 0.5, "世界への入口", "Door into the world");
  pushEx(exhibits, "足跡", "Footprints", 0, 0.2, 1, "行動の始まり", "Beginning of action");

  lights.pl = point(THREE, group, lightCol.getHex(), 0.7, -2, 4, 2, 20);
  lights.base = 0.7;
  lights.spot = spot(THREE, group, 0xffb089, 1.2, new THREE.Vector3(-5, 6, 4), new THREE.Vector3(0, 1, -2), Math.PI / 5);
  lights.spotBase = 1.2;
  lights.kind = "dawn";
  planetSlots.push(new THREE.Vector3(0, 2.4, 0));
}

// ─── 2 保管庫 ───────────────────────────────────────────
function buildHouse2(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  addWalls(THREE, group, w, d, h, mats.stone, { openFront: true });
  floor(THREE, group, w - 0.3, d - 0.3, mats.woodFloor);
  // 両側の棚
  for (let side = -1; side <= 1; side += 2) {
    for (let row = 0; row < 4; row++) {
      group.add(mesh(THREE, new THREE.BoxGeometry(2.8, 0.1, 0.9), mats.woodPanel, side * 3.8, 0.9 + row * 0.95, -1));
      for (let k = 0; k < 3; k++) {
        group.add(
          mesh(
            THREE,
            k === 1 ? new THREE.SphereGeometry(0.28, 10, 10) : new THREE.BoxGeometry(0.45, 0.4, 0.45),
            k === 2 ? mats.brass : mats.woodPanel,
            side * 3.8 + (k - 1) * 0.7,
            1.2 + row * 0.95,
            -1
          )
        );
      }
    }
  }
  // 作業台
  group.add(mesh(THREE, new THREE.BoxGeometry(4.2, 0.18, 1.4), mats.woodPanel, 0, 1.05, 2.5));
  [[-1.7, 2.0], [1.7, 2.0], [-1.7, 3.0], [1.7, 3.0]].forEach(([x, z]) => {
    group.add(mesh(THREE, new THREE.BoxGeometry(0.12, 1.0, 0.12), mats.darkMetal, x, 0.5, z));
  });
  const craft = mesh(THREE, new THREE.IcosahedronGeometry(0.4, 0), mats.brass, 1.2, 1.55, 2.5);
  group.add(craft);
  animatables.push({ mesh: craft, kind: "spin", speed: 0.35, axis: "y" });
  group.add(mesh(THREE, new THREE.BoxGeometry(1.6, 0.9, 1.1), mats.darkMetal, 3.2, 0.55, -3.5));
  const key = mesh(THREE, new THREE.TorusGeometry(0.22, 0.05, 8, 14), mats.brass, 3.5, 1.8, -3.2);
  group.add(key);
  animatables.push({ mesh: key, kind: "bob", baseY: 1.8, speed: 1.2, amp: 0.1 });

  pushEx(exhibits, "保管棚", "Shelves", -3.8, 2, -1, "価値あるもの", "What you keep");
  pushEx(exhibits, "道具台", "Workbench", 0, 1.2, 2.5, "才能を使う場", "Where talent is used");
  pushEx(exhibits, "鍵のかかった箱", "Locked chest", 3.2, 0.8, -3.5, "守るもの", "What you protect");

  lights.pl = point(THREE, group, lightCol.getHex(), 1.05, 0, 3.5, 0, 22);
  lights.base = 1.05;
  lights.spot = spot(THREE, group, 0xffe0a0, 0.55, new THREE.Vector3(0, 5, 2), new THREE.Vector3(0, 1, 2));
  lights.spotBase = 0.55;
  lights.kind = "warm";
  planetSlots.push(new THREE.Vector3(0, 2.8, 0));
}

// ─── 3 書斎回廊 ─────────────────────────────────────────
function buildHouse3(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  addWalls(THREE, group, w, d, h, mats.plaster, { openFront: true });
  floor(THREE, group, w - 0.2, d - 0.2, mats.woodFloor);
  // 長い書架
  for (let i = 0; i < 12; i++) {
    const z = d / 2 - 2.5 - i * 1.2;
    group.add(mesh(THREE, new THREE.BoxGeometry(0.9, h * 0.75, 0.35), mats.woodPanel, -w / 2 + 0.5, h * 0.4, z));
    group.add(mesh(THREE, new THREE.BoxGeometry(0.9, h * 0.75, 0.35), mats.woodPanel, w / 2 - 0.5, h * 0.4, z));
    for (let b = 0; b < 3; b++) {
      group.add(
        mesh(
          THREE,
          new THREE.BoxGeometry(0.22, 0.5 + (b % 2) * 0.15, 0.25),
          b % 2 ? mats.woodPanel : stdMat(THREE, 0x4a6080, { roughness: 0.7 }),
          -w / 2 + 0.5,
          1.0 + b * 0.7,
          z
        )
      );
    }
  }
  // 浮遊する手紙
  for (let p = 0; p < 5; p++) {
    const letter = mesh(THREE, new THREE.PlaneGeometry(0.4, 0.55), mats.parchment, -1 + p * 0.7, 2.2, d / 2 - 5 - p * 2);
    letter.material = mats.parchment.clone();
    letter.material.side = THREE.DoubleSide;
    group.add(letter);
    animatables.push({
      mesh: letter,
      kind: "drift",
      baseY: letter.position.y,
      baseX: letter.position.x,
      speed: 0.6 + p * 0.08,
      amp: 0.2,
      phase: p,
    });
  }
  // 自転車
  group.add(mesh(THREE, new THREE.TorusGeometry(0.55, 0.06, 8, 16), mats.darkMetal, -1.5, 0.6, d / 2 - 1.8));
  group.add(mesh(THREE, new THREE.TorusGeometry(0.55, 0.06, 8, 16), mats.darkMetal, 0.5, 0.6, d / 2 - 1.8));
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.04, 0.04, 1.3, 6), mats.darkMetal, -0.5, 1.0, d / 2 - 1.8));

  pushEx(exhibits, "書架", "Book stacks", -w / 2 + 0.5, 2, 0, "言葉と学び", "Words and learning");
  pushEx(exhibits, "手紙", "Letters", 0, 2.2, 0, "行き交う情報", "Messages in motion");
  pushEx(exhibits, "自転車", "Bicycle", -0.5, 0.8, d / 2 - 1.8, "日常の移動", "Daily movement");

  lights.pl = point(THREE, group, lightCol.getHex(), 0.85, 0, 3.2, 0, 28);
  lights.base = 0.85;
  lights.spot = spot(THREE, group, 0xb8e0f0, 0.4, new THREE.Vector3(2, 4, 0), new THREE.Vector3(0, 1, 0));
  lights.spotBase = 0.4;
  lights.kind = "cool";
  planetSlots.push(new THREE.Vector3(0, 2.5, 0));
}

// ─── Hero: 4 邸宅 ───────────────────────────────────────
function buildHouse4(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;

  // 外壁
  addWalls(THREE, group, w, d, h * 0.75, mats.stone, { openFront: true });
  // 切妻屋根
  const roofL = mesh(THREE, new THREE.BoxGeometry(w * 0.72, 0.25, d + 0.6), mats.darkMetal, -w * 0.2, h * 0.82, 0);
  roofL.rotation.z = 0.48;
  group.add(roofL);
  const roofR = mesh(THREE, new THREE.BoxGeometry(w * 0.72, 0.25, d + 0.6), mats.darkMetal, w * 0.2, h * 0.82, 0);
  roofR.rotation.z = -0.48;
  group.add(roofR);
  // 煙突
  group.add(mesh(THREE, new THREE.BoxGeometry(0.9, 2.2, 0.9), mats.stone, -w * 0.25, h * 0.95, -d * 0.2));

  // 床
  floor(THREE, group, w - 0.4, d - 0.4, mats.woodFloor);

  // 入口ドア
  group.add(mesh(THREE, new THREE.BoxGeometry(1.6, 2.4, 0.12), mats.woodPanel, 0, 1.25, d / 2 - 0.2));
  group.add(mesh(THREE, new THREE.SphereGeometry(0.06, 8, 8), mats.brass, 0.55, 1.2, d / 2 - 0.1));

  // 窓
  [-w * 0.35, w * 0.35].forEach((x) => {
    group.add(mesh(THREE, new THREE.BoxGeometry(1.4, 1.5, 0.1), mats.glass, x, 2.4, d / 2 - 0.15));
    group.add(mesh(THREE, new THREE.BoxGeometry(1.55, 1.65, 0.08), mats.woodPanel, x, 2.4, d / 2 - 0.22));
  });

  // 暖炉
  group.add(mesh(THREE, new THREE.BoxGeometry(3.2, 2.6, 1.0), mats.stone, 0, 1.4, -d / 2 + 0.7));
  group.add(mesh(THREE, new THREE.BoxGeometry(2.2, 1.4, 0.5), mats.stageBlack, 0, 1.0, -d / 2 + 1.1));
  const fire = mesh(
    THREE,
    new THREE.ConeGeometry(0.4, 0.9, 8),
    stdMat(THREE, 0xff8844, { emissive: 0xff6622, emissiveIntensity: 0.8, roughness: 0.5 }),
    0,
    1.35,
    -d / 2 + 1.15
  );
  group.add(fire);
  animatables.push({ mesh: fire, kind: "flame", baseY: 1.35, speed: 5.5, amp: 0.1 });

  // 肘掛け椅子
  addArmchair(THREE, group, mats, -3.2, 0, 1.5);
  addArmchair(THREE, group, mats, 3.2, 0, 1.5);
  // 写真
  group.add(mesh(THREE, new THREE.BoxGeometry(0.9, 1.1, 0.08), mats.woodPanel, 3.5, 2.4, -d / 2 + 0.45));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.7, 0.9, 0.04), mats.parchment, 3.5, 2.4, -d / 2 + 0.52));
  // 古い箱
  group.add(mesh(THREE, new THREE.BoxGeometry(1.3, 0.7, 0.9), mats.woodPanel, -3.5, 0.4, -2));

  pushEx(exhibits, "暖炉", "Hearth", 0, 1.5, -d / 2 + 1.2, "心の土台の火", "Fire of the home");
  pushEx(exhibits, "肘掛け椅子", "Armchair", -3.2, 1, 1.5, "安心できる席", "A seat of rest");
  pushEx(exhibits, "写真立て", "Photo frame", 3.5, 2.4, -d / 2 + 0.5, "記憶と家族", "Memory and family");

  lights.kind = "flicker";
  lights.pl = point(THREE, group, lightCol.getHex(), 1.3, 0, 2.0, -d / 2 + 1.5, 14);
  lights.base = 1.3;
  lights.spot = spot(THREE, group, 0xffaa66, 0.35, new THREE.Vector3(0, 5, 0), new THREE.Vector3(0, 0, 0));
  lights.spotBase = 0.35;
  planetSlots.push(new THREE.Vector3(0, 2.5, 0));
}

// ─── Hero: 5 劇場 ───────────────────────────────────────
function buildHouse5(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;

  // 外郭（ダークブリック）
  const brick = stdMat(THREE, 0x3a3038, { roughness: 0.88 });
  addWalls(THREE, group, w, d, h, brick, { openFront: true });
  floor(THREE, group, w - 0.3, d - 0.3, mats.stageBlack);

  // 客席段（後ろが高い）
  for (let row = 0; row < 6; row++) {
    const z = d * 0.38 - row * 1.35;
    const y = 0.25 + row * 0.28;
    group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.72, 0.35, 1.15), mats.fabric, 0, y, z));
    for (let s = -3; s <= 3; s++) {
      group.add(
        mesh(THREE, new THREE.BoxGeometry(0.95, 0.85, 0.12), mats.fabric, s * 1.35, y + 0.55, z - 0.4)
      );
    }
  }

  // 舞台
  group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.78, 0.55, d * 0.32), mats.woodFloor, 0, 0.4, -d * 0.28));
  // プロセニアム
  group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.85, 0.5, 0.4), mats.brass, 0, h * 0.72, -d * 0.08));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.45, h * 0.65, 0.4), mats.brass, -w * 0.38, h * 0.38, -d * 0.08));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.45, h * 0.65, 0.4), mats.brass, w * 0.38, h * 0.38, -d * 0.08));

  // 幕
  const curtain = mesh(THREE, new THREE.PlaneGeometry(w * 0.7, h * 0.5), mats.fabric, 0, h * 0.5, -d / 2 + 0.5);
  curtain.material = mats.fabric.clone();
  curtain.material.side = THREE.DoubleSide;
  group.add(curtain);
  animatables.push({ mesh: curtain, kind: "sway", speed: 0.5, amp: 0.03 });

  // ピアノ（袖）
  group.add(mesh(THREE, new THREE.BoxGeometry(2.4, 0.9, 1.0), mats.darkMetal, 5.5, 1.1, -d * 0.15));
  group.add(mesh(THREE, new THREE.BoxGeometry(2.2, 0.1, 0.35), mats.parchment, 5.5, 1.6, -d * 0.05));
  // イーゼル＋未完成の絵
  group.add(mesh(THREE, new THREE.BoxGeometry(0.08, 2.2, 0.08), mats.woodPanel, -5.5, 1.5, -d * 0.18));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.4, 1.7, 0.08), mats.parchment, -5.5, 2.0, -d * 0.12));
  group.add(
    mesh(
      THREE,
      new THREE.BoxGeometry(0.7, 0.5, 0.04),
      stdMat(THREE, 0xc4788a, { emissive: 0x802040, emissiveIntensity: 0.2 }),
      -5.5,
      2.1,
      -d * 0.08
    )
  );
  // スポット光球
  const ball = mesh(
    THREE,
    new THREE.SphereGeometry(0.25, 12, 12),
    stdMat(THREE, 0xffe0a0, { emissive: 0xffcc66, emissiveIntensity: 0.9 }),
    0,
    h - 1.2,
    -d * 0.15
  );
  group.add(ball);
  animatables.push({ mesh: ball, kind: "pulseMat", speed: 2 });

  pushEx(exhibits, "舞台", "Stage", 0, 1.0, -d * 0.28, "表現の中心", "Center of expression");
  pushEx(exhibits, "客席", "Seats", 0, 1.2, d * 0.25, "見る側の闇", "The dark of watching");
  pushEx(exhibits, "ピアノ", "Piano", 5.5, 1.3, -d * 0.1, "創るための楽器", "Instrument for making");
  pushEx(exhibits, "描きかけの絵", "Unfinished art", -5.5, 2.0, -d * 0.12, "途中の創作", "Work in progress");

  lights.kind = "spotlight";
  lights.pl = point(THREE, group, 0x1a1018, 0.2, 0, 3, d * 0.2, 16);
  lights.base = 0.2;
  lights.spot = spot(
    THREE,
    group,
    lightCol.getHex(),
    2.4,
    new THREE.Vector3(0, h - 0.5, -d * 0.05),
    new THREE.Vector3(0, 0.8, -d * 0.28),
    Math.PI / 9
  );
  lights.spotBase = 2.4;
  planetSlots.push(new THREE.Vector3(0, 2.6, -d * 0.28));
  planetSlots.push(new THREE.Vector3(-5, 2.2, -d * 0.2));
}

// ─── Hero: 9 天文台＋図書館 ─────────────────────────────
function buildHouse9(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables, quality } = c;
  const { w, d, h } = arch;

  // 円筒の石造天文台本体
  const cylMat = mats.stone.clone();
  cylMat.side = THREE.DoubleSide;
  const cyl = mesh(
    THREE,
    new THREE.CylinderGeometry(w * 0.38, w * 0.4, h * 0.55, 32, 1, true),
    cylMat,
    0,
    h * 0.28,
    -1
  );
  group.add(cyl);
  // 内壁
  const innerMat = mats.plaster.clone();
  innerMat.side = THREE.BackSide;
  group.add(
    mesh(
      THREE,
      new THREE.CylinderGeometry(w * 0.36, w * 0.36, h * 0.55, 32, 1, true),
      innerMat,
      0,
      h * 0.28,
      -1
    )
  );

  // ドーム
  const dome = mesh(
    THREE,
    new THREE.SphereGeometry(w * 0.4, 28, 16, 0, Math.PI * 2, 0, Math.PI / 2),
    stdMat(THREE, 0x6a7a90, { metalness: 0.35, roughness: 0.45 }),
    0,
    h * 0.55,
    -1
  );
  group.add(dome);
  // 観測スリット
  group.add(mesh(THREE, new THREE.BoxGeometry(1.2, 0.15, w * 0.45), mats.darkMetal, 0, h * 0.72, -1));

  // 図書館ウィング（横に長方形）
  group.add(mesh(THREE, new THREE.BoxGeometry(6, 4.2, 8), mats.stone, -w * 0.55, 2.1, 2));
  floor(THREE, group, w, d, mats.woodFloor);

  // 入口ポルチコ
  group.add(mesh(THREE, new THREE.BoxGeometry(4.5, 0.3, 2.5), mats.stone, 0, 3.6, d / 2 - 0.5));
  [-1.6, 1.6].forEach((x) => {
    group.add(mesh(THREE, new THREE.CylinderGeometry(0.25, 0.28, 3.4, 12), mats.stone, x, 1.75, d / 2 - 0.3));
  });
  group.add(mesh(THREE, new THREE.BoxGeometry(1.8, 2.6, 0.12), mats.woodPanel, 0, 1.4, d / 2 - 0.5));

  // 地球儀（台座）
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.7, 0.85, 0.9, 16), mats.woodPanel, -3.5, 0.5, 2));
  const globe = mesh(
    THREE,
    new THREE.SphereGeometry(1.1, 24, 24),
    stdMat(THREE, 0x3a6a8a, { roughness: 0.45, metalness: 0.15, emissive: 0x102030, emissiveIntensity: 0.1 }),
    -3.5,
    2.0,
    2
  );
  group.add(globe);
  // 経線
  const meridian = mesh(THREE, new THREE.TorusGeometry(1.15, 0.02, 8, 32), mats.brass, -3.5, 2.0, 2);
  meridian.rotation.y = 0.5;
  group.add(meridian);
  animatables.push({ mesh: globe, kind: "spin", speed: 0.2, axis: "y" });

  // 真鍮望遠鏡
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.45, 0.55, 0.8, 12), mats.woodPanel, 3.5, 0.45, 1.5));
  const scope = mesh(THREE, new THREE.CylinderGeometry(0.14, 0.22, 3.2, 12), mats.brass, 3.5, 2.0, 0.3);
  scope.rotation.z = -0.55;
  scope.rotation.x = 0.25;
  group.add(scope);
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.18, 0.18, 0.35, 10), mats.darkMetal, 3.5, 2.85, -0.3));

  // 世界地図パネル
  group.add(mesh(THREE, new THREE.BoxGeometry(4.2, 2.2, 0.1), mats.woodPanel, 0, 3.0, -d / 2 + 0.4));
  group.add(mesh(THREE, new THREE.BoxGeometry(3.8, 1.9, 0.06), mats.parchment, 0, 3.0, -d / 2 + 0.5));
  // 航路線
  for (let i = 0; i < 5; i++) {
    group.add(
      mesh(THREE, new THREE.BoxGeometry(2.8 - i * 0.2, 0.03, 0.03), mats.brass, 0, 3.4 - i * 0.25, -d / 2 + 0.55)
    );
  }

  // 本棚（人間スケール・側面）
  for (let row = 0; row < 4; row++) {
    group.add(mesh(THREE, new THREE.BoxGeometry(4.5, 0.1, 0.5), mats.woodPanel, -5.5, 0.9 + row * 0.85, -2));
    for (let b = 0; b < 8; b++) {
      group.add(
        mesh(
          THREE,
          new THREE.BoxGeometry(0.35, 0.6 + (b % 3) * 0.08, 0.35),
          b % 2 ? mats.woodPanel : stdMat(THREE, 0x4a6080, { roughness: 0.7 }),
          -7 + b * 0.5,
          1.25 + row * 0.85,
          -2
        )
      );
    }
  }

  // 羅針盤テーブル
  group.add(mesh(THREE, new THREE.CylinderGeometry(1.1, 1.15, 0.9, 20), mats.woodPanel, 0, 0.5, 4));
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.95, 0.95, 0.08, 24), mats.brass, 0, 1.0, 4));
  const needle = mesh(THREE, new THREE.BoxGeometry(0.1, 0.06, 1.3), stdMat(THREE, 0x802020, { metalness: 0.5 }), 0, 1.1, 4);
  group.add(needle);
  animatables.push({ mesh: needle, kind: "spin", speed: 0.15, axis: "y" });

  // 遠方の橋（屋外展示）
  group.add(mesh(THREE, new THREE.BoxGeometry(1.8, 0.2, 8), mats.stone, 0, 0.3, -d / 2 - 3));
  [-0.85, 0.85].forEach((x) => {
    group.add(mesh(THREE, new THREE.BoxGeometry(0.12, 0.7, 8), mats.brass, x, 0.7, -d / 2 - 3));
  });
  group.add(mesh(THREE, new THREE.BoxGeometry(2.8, 3.2, 0.25), mats.stone, 0, 1.8, -d / 2 - 7));

  // ドーム内の星
  if (quality !== "low") {
    const count = 100;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const th = Math.random() * Math.PI * 2;
      const ph = Math.random() * 0.9;
      const r = 4 + Math.random() * 2;
      pos[i * 3] = Math.cos(th) * Math.sin(ph) * r;
      pos[i * 3 + 1] = 5 + Math.cos(ph) * r * 0.5;
      pos[i * 3 + 2] = -1 + Math.sin(th) * Math.sin(ph) * r;
    }
    const stars = new THREE.Points(
      new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
      new THREE.PointsMaterial({ color: 0xd0e0ff, size: 0.08, transparent: true, opacity: 0.85, depthWrite: false })
    );
    group.add(stars);
  }

  pushEx(exhibits, "地球儀", "Globe", -3.5, 2.0, 2, "世界を球体として見る", "The world as a sphere");
  pushEx(exhibits, "真鍮の望遠鏡", "Brass telescope", 3.5, 2.0, 0.5, "遠くを見る道具", "A tool for looking far");
  pushEx(exhibits, "世界地図", "World map", 0, 3.0, -d / 2 + 0.5, "場所を超える想像", "Imagination beyond place");
  pushEx(exhibits, "古書の棚", "Library shelves", -5.5, 2.0, -2, "思想の積層", "Layers of thought");
  pushEx(exhibits, "遠方の橋", "Bridge outward", 0, 1.0, -d / 2 - 4, "今を超えて進む", "Beyond the present");

  lights.kind = "open";
  lights.pl = point(THREE, group, lightCol.getHex(), 0.75, 0, 5, 0, 28);
  lights.base = 0.75;
  lights.spot = spot(THREE, group, 0xa8c8ff, 0.8, new THREE.Vector3(0, 9, -1), new THREE.Vector3(0, 0, 0), Math.PI / 5);
  lights.spotBase = 0.8;
  // 展示スポット
  const s2 = spot(THREE, group, 0xffe0b0, 0.7, new THREE.Vector3(-3, 5, 3), new THREE.Vector3(-3.5, 1, 2), Math.PI / 8);
  group.add(s2);
  planetSlots.push(new THREE.Vector3(0, 3.2, -1));
  planetSlots.push(new THREE.Vector3(2, 2.8, 2));
}

// ─── 6 工房・研究室 ─────────────────────────────────────
function buildHouse6(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  addWalls(THREE, group, w, d, h, mats.plaster, { openFront: true });
  floor(THREE, group, w - 0.3, d - 0.3, mats.stone);
  // 作業机 2列
  [-3, 0, 3].forEach((x) => {
    [1.5, -2].forEach((z) => {
      group.add(mesh(THREE, new THREE.BoxGeometry(2.4, 0.12, 1.2), mats.woodPanel, x, 1.0, z));
      [[-0.9, 0.4], [0.9, 0.4], [-0.9, -0.4], [0.9, -0.4]].forEach(([dx, dz]) => {
        group.add(mesh(THREE, new THREE.BoxGeometry(0.1, 0.95, 0.1), mats.darkMetal, x + dx, 0.48, z + dz));
      });
      // モニター
      group.add(
        mesh(
          THREE,
          new THREE.BoxGeometry(1.0, 0.65, 0.08),
          stdMat(THREE, 0x1a2030, { emissive: 0x305060, emissiveIntensity: 0.3 }),
          x,
          1.6,
          z - 0.35
        )
      );
      group.add(mesh(THREE, new THREE.BoxGeometry(0.5, 0.03, 0.65), mats.parchment, x + 0.55, 1.08, z + 0.15));
    });
  });
  // 壁時計
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.9, 0.9, 0.12, 24), mats.brass, 0, 3.6, -d / 2 + 0.35));
  const hand = mesh(THREE, new THREE.BoxGeometry(0.06, 0.7, 0.04), mats.darkMetal, 0, 3.6, -d / 2 + 0.45);
  group.add(hand);
  animatables.push({ mesh: hand, kind: "spin", speed: 0.12, axis: "z" });
  // 歯車
  const gear = mesh(THREE, new THREE.CylinderGeometry(0.7, 0.7, 0.15, 12), mats.darkMetal, -4.5, 2.5, -d / 2 + 0.5);
  group.add(gear);
  animatables.push({ mesh: gear, kind: "spin", speed: 0.5, axis: "z" });
  // ホワイトボード
  group.add(mesh(THREE, new THREE.BoxGeometry(3.2, 2.0, 0.08), mats.plaster, 4, 2.5, -d / 2 + 0.35));
  for (let i = 0; i < 4; i++) {
    group.add(mesh(THREE, new THREE.BoxGeometry(2.4, 0.04, 0.02), mats.darkMetal, 4, 3.1 - i * 0.3, -d / 2 + 0.4));
  }

  pushEx(exhibits, "作業デスク", "Work desks", 0, 1.2, 1.5, "毎日の積み重ね", "Daily craft");
  pushEx(exhibits, "壁時計", "Wall clock", 0, 3.6, -d / 2 + 0.4, "時間と習慣", "Time and habit");
  pushEx(exhibits, "歯車", "Gears", -4.5, 2.5, -d / 2 + 0.5, "仕組みを整える", "Mechanism");

  lights.pl = point(THREE, group, lightCol.getHex(), 1.1, 0, 3.5, 0, 24);
  lights.base = 1.1;
  lights.spot = spot(THREE, group, 0xe0f0c8, 0.45, new THREE.Vector3(0, 5, -2), new THREE.Vector3(0, 1, 0));
  lights.spotBase = 0.45;
  lights.kind = "even";
  planetSlots.push(new THREE.Vector3(-2.5, 2.5, 0));
  planetSlots.push(new THREE.Vector3(0, 2.6, -1));
  planetSlots.push(new THREE.Vector3(2.8, 2.4, 0.5));
}

// ─── 7 応接・契約の間 ───────────────────────────────────
function buildHouse7(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  addWalls(THREE, group, w, d, h, mats.plaster, { openFront: true });
  floor(THREE, group, w - 0.3, d - 0.3, mats.woodFloor);
  // 長いテーブル
  group.add(mesh(THREE, new THREE.BoxGeometry(3.2, 0.14, 1.4), mats.woodPanel, 0, 1.0, 0));
  [[-1.3, 0.5], [1.3, 0.5], [-1.3, -0.5], [1.3, -0.5]].forEach(([x, z]) => {
    group.add(mesh(THREE, new THREE.CylinderGeometry(0.08, 0.08, 0.95, 8), mats.darkMetal, x, 0.48, z));
  });
  group.add(mesh(THREE, new THREE.BoxGeometry(1.0, 0.04, 1.2), mats.parchment, 0, 1.12, 0));
  // 向かい合う椅子
  addArmchair(THREE, group, mats, 0, 0, 3.0);
  // 反対向きの椅子（簡易）
  group.add(mesh(THREE, new THREE.BoxGeometry(1.1, 0.15, 1.0), mats.fabric, 0, 0.55, -3.0));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.1, 1.0, 0.15), mats.fabric, 0, 1.1, -2.55));
  // 双鏡
  group.add(mesh(THREE, new THREE.BoxGeometry(1.6, 2.4, 0.1), mats.glass, -w / 2 + 0.4, 2.0, 0));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.6, 2.4, 0.1), mats.glass, w / 2 - 0.4, 2.0, 0));
  // 天秤
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.05, 0.05, 1.6, 6), mats.darkMetal, 3.5, 2.2, -2.5));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.5, 0.05, 0.08), mats.brass, 3.5, 3.0, -2.5));
  const panL = mesh(THREE, new THREE.CylinderGeometry(0.3, 0.25, 0.06, 10), mats.brass, 2.9, 2.55, -2.5);
  const panR = mesh(THREE, new THREE.CylinderGeometry(0.3, 0.25, 0.06, 10), mats.brass, 4.1, 2.55, -2.5);
  group.add(panL);
  group.add(panR);
  animatables.push({ mesh: panL, kind: "bob", baseY: 2.55, speed: 0.9, amp: 0.05, phase: 0 });
  animatables.push({ mesh: panR, kind: "bob", baseY: 2.55, speed: 0.9, amp: 0.05, phase: Math.PI });
  // 握手の象徴
  const hands = new THREE.Group();
  hands.add(mesh(THREE, new THREE.SphereGeometry(0.18, 8, 8), mats.brass, -0.2, 0, 0));
  hands.add(mesh(THREE, new THREE.SphereGeometry(0.18, 8, 8), mats.darkMetal, 0.2, 0, 0));
  hands.position.set(0, 2.4, 0);
  group.add(hands);
  animatables.push({ mesh: hands, kind: "bob", baseY: 2.4, speed: 0.8, amp: 0.08 });

  pushEx(exhibits, "向かい合う椅子", "Facing chairs", 0, 1, 3, "他者と向き合う", "Facing the other");
  pushEx(exhibits, "契約書", "Contract", 0, 1.15, 0, "約束と境界", "Promise and boundary");
  pushEx(exhibits, "握手", "Handshake", 0, 2.4, 0, "出会いの瞬間", "Moment of meeting");

  lights.pl = point(THREE, group, lightCol.getHex(), 0.8, 0, 3.5, 0, 20);
  lights.base = 0.8;
  lights.spot = spot(THREE, group, accent.getHex(), 0.5, new THREE.Vector3(-3, 5, 0), new THREE.Vector3(0, 1, 0));
  lights.spotBase = 0.5;
  lights.kind = "mirror";
  planetSlots.push(new THREE.Vector3(-2.5, 2.8, 0));
  planetSlots.push(new THREE.Vector3(2.5, 2.6, 0));
}

// ─── 8 地下金庫（恐怖ではなく変容） ─────────────────────
function buildHouse8(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  addWalls(THREE, group, w, d, h * 0.9, mats.stone, { openFront: true });
  floor(THREE, group, w - 0.2, d - 0.2, mats.stone);
  // 狭い入口
  group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.5, h, 0.45), mats.stone, 0, h / 2, d / 2 - 0.8));
  group.add(mesh(THREE, new THREE.BoxGeometry(2.0, 2.6, 0.5), mats.stageBlack, 0, 1.4, d / 2 - 0.75));
  // 鍵箱
  group.add(mesh(THREE, new THREE.BoxGeometry(2.6, 1.5, 1.6), mats.darkMetal, 0, 0.85, -3));
  const lock = mesh(THREE, new THREE.TorusGeometry(0.32, 0.06, 8, 16), mats.brass, 0.6, 1.3, -2.1);
  group.add(lock);
  animatables.push({ mesh: lock, kind: "pulseMat", speed: 1.3 });
  // 水面
  const water = mesh(
    THREE,
    new THREE.CylinderGeometry(2.4, 2.4, 0.1, 28),
    stdMat(THREE, accent.getHex(), { transparent: true, opacity: 0.5, emissive: accent.getHex(), emissiveIntensity: 0.25 }),
    0,
    0.2,
    2.5
  );
  group.add(water);
  animatables.push({ mesh: water, kind: "pulseMat", speed: 0.6 });
  // 灰と芽
  group.add(mesh(THREE, new THREE.ConeGeometry(0.5, 0.28, 10), mats.darkMetal, -3, 0.25, 0));
  const sprout = mesh(THREE, new THREE.ConeGeometry(0.12, 0.55, 6), mats.brass, -3, 0.7, 0);
  group.add(sprout);
  animatables.push({ mesh: sprout, kind: "bob", baseY: 0.7, speed: 1.0, amp: 0.05 });
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.28, 0.2, 0.45, 12), mats.brass, 3, 0.45, 1));

  pushEx(exhibits, "鍵のかかった箱", "Locked chest", 0, 1.0, -3, "共有と秘密", "Sharing and secrecy");
  pushEx(exhibits, "水面", "Water", 0, 0.3, 2.5, "深い層", "Deep layer");
  pushEx(exhibits, "灰と芽", "Ash and sprout", -3, 0.5, 0, "終わりと再生", "Ending and renewal");

  lights.kind = "slit";
  lights.pl = point(THREE, group, lightCol.getHex(), 0.3, 0, 3, 0, 14);
  lights.base = 0.3;
  lights.spot = spot(THREE, group, accent.getHex(), 1.3, new THREE.Vector3(0, h - 0.3, -d / 2 + 1), new THREE.Vector3(0, 0.3, 2), Math.PI / 18);
  lights.spotBase = 1.3;
  planetSlots.push(new THREE.Vector3(0, 2.2, 0));
}

// ─── 10 塔・展望台 ──────────────────────────────────────
function buildHouse10(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables, quality } = c;
  const { w, d, h } = arch;
  // 円塔
  const outer = mats.stone.clone();
  outer.side = THREE.DoubleSide;
  group.add(mesh(THREE, new THREE.CylinderGeometry(w * 0.42, w * 0.45, h * 0.85, 28, 1, true), outer, 0, h * 0.42, 0));
  floor(THREE, group, w * 0.75, d * 0.75, mats.stone);
  // 螺旋階段
  const steps = quality === "low" ? 14 : 22;
  for (let i = 0; i < steps; i++) {
    const ang = i * 0.5;
    const r = 2.4;
    const y = 0.3 + i * ((h * 0.7) / steps);
    group.add(
      mesh(
        THREE,
        new THREE.BoxGeometry(1.5, 0.18, 0.85),
        i % 2 ? mats.stone : mats.woodPanel,
        Math.cos(ang) * r,
        y,
        Math.sin(ang) * r
      )
    );
  }
  // 展望デッキ
  group.add(mesh(THREE, new THREE.CylinderGeometry(4.5, 4.5, 0.3, 24), mats.stone, 0, h * 0.78, 0));
  const rail = mesh(THREE, new THREE.TorusGeometry(4.3, 0.08, 8, 32), mats.brass, 0, h * 0.85, 0);
  rail.rotation.x = Math.PI / 2;
  group.add(rail);
  // 紋章
  group.add(mesh(THREE, new THREE.BoxGeometry(1.2, 1.5, 0.12), mats.brass, 0, h * 0.45, -w * 0.4));
  // 灯台
  group.add(mesh(THREE, new THREE.CylinderGeometry(0.3, 0.5, 2.8, 10), mats.stone, 3.2, h * 0.78 + 1.5, 2));
  const lamp = mesh(
    THREE,
    new THREE.SphereGeometry(0.35, 12, 12),
    stdMat(THREE, 0xffe0a0, { emissive: 0xffcc66, emissiveIntensity: 0.85 }),
    3.2,
    h * 0.78 + 3.1,
    2
  );
  group.add(lamp);
  animatables.push({ mesh: lamp, kind: "pulseMat", speed: 1.4 });
  // 遠景の街灯
  if (quality !== "low") {
    for (let i = 0; i < 16; i++) {
      group.add(
        mesh(
          THREE,
          new THREE.SphereGeometry(0.1, 6, 6),
          stdMat(THREE, 0xffe0a0, { emissive: 0xffcc80, emissiveIntensity: 0.6 }),
          (Math.random() - 0.5) * 30,
          0.8 + Math.random() * 2,
          10 + Math.random() * 15
        )
      );
    }
  }

  pushEx(exhibits, "螺旋階段", "Spiral stairs", 2, 4, 0, "役割への登り", "Ascent to role");
  pushEx(exhibits, "展望デッキ", "Lookout deck", 0, h * 0.82, 0, "社会から見える位置", "Where society sees you");
  pushEx(exhibits, "灯台", "Lighthouse", 3.2, h * 0.9, 2, "公の光", "Public light");

  lights.pl = point(THREE, group, lightCol.getHex(), 1.15, 0, h * 0.9, 0, 32);
  lights.base = 1.15;
  lights.spot = spot(THREE, group, accent.getHex(), 0.7, new THREE.Vector3(0, h + 2, 0), new THREE.Vector3(0, h * 0.75, 0));
  lights.spotBase = 0.7;
  lights.kind = "summit";
  planetSlots.push(new THREE.Vector3(0, h * 0.85, 0));
}

// ─── 11 円卓のホール ────────────────────────────────────
function buildHouse11(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables } = c;
  const { w, d, h } = arch;
  // 開放的：低い円壁
  const wall = mesh(THREE, new THREE.CylinderGeometry(w * 0.45, w * 0.45, 1.4, 40, 1, true), mats.stone, 0, 0.7, 0);
  wall.material = mats.stone.clone();
  wall.material.side = THREE.DoubleSide;
  group.add(wall);
  floor(THREE, group, w * 0.85, d * 0.85, mats.stone);
  // 円卓
  group.add(mesh(THREE, new THREE.CylinderGeometry(3.2, 3.2, 0.2, 32), mats.woodPanel, 0, 0.9, 0));
  for (let i = 0; i < 8; i++) {
    const ang = (i / 8) * Math.PI * 2;
    const x = Math.cos(ang) * 4.5;
    const z = Math.sin(ang) * 4.5;
    group.add(mesh(THREE, new THREE.BoxGeometry(0.9, 0.12, 0.9), mats.fabric, x, 0.5, z));
    group.add(
      mesh(THREE, new THREE.BoxGeometry(0.9, 0.85, 0.12), mats.fabric, x + Math.cos(ang) * 0.35, 1.0, z + Math.sin(ang) * 0.35)
    );
  }
  // 光のノード
  for (let j = 0; j < 8; j++) {
    const ang = (j / 8) * Math.PI * 2;
    const nd = mesh(
      THREE,
      new THREE.SphereGeometry(0.32, 12, 12),
      stdMat(THREE, accent.getHex(), { emissive: accent.getHex(), emissiveIntensity: 0.5 }),
      Math.cos(ang) * 6.5,
      2.2 + (j % 2) * 0.4,
      Math.sin(ang) * 6.5
    );
    group.add(nd);
    animatables.push({ mesh: nd, kind: "pulseMat", speed: 1.3 + j * 0.05, phase: j });
    animatables.push({ mesh: nd, kind: "bob", baseY: nd.position.y, speed: 0.7, amp: 0.12, phase: j });
  }
  const ring = mesh(THREE, new THREE.TorusGeometry(6.5, 0.04, 8, 40), mats.brass, 0, 2.4, 0);
  ring.rotation.x = Math.PI / 2;
  group.add(ring);
  animatables.push({ mesh: ring, kind: "spin", speed: 0.1, axis: "y" });
  // 掲示板
  group.add(mesh(THREE, new THREE.BoxGeometry(2.8, 1.8, 0.12), mats.woodPanel, 0, 2.8, -7.5));

  pushEx(exhibits, "円卓", "Round table", 0, 1.0, 0, "共有のテーブル", "Shared table");
  pushEx(exhibits, "光のノード", "Light nodes", 6.5, 2.4, 0, "つながりの点", "Points of connection");
  pushEx(exhibits, "掲示板", "Board", 0, 2.8, -7.5, "共同の計画", "Shared plans");

  lights.pl = point(THREE, group, accent.getHex(), 0.9, 0, 4, 0, 28);
  lights.base = 0.9;
  lights.spot = spot(THREE, group, lightCol.getHex(), 0.5, new THREE.Vector3(0, 8, 0), new THREE.Vector3(0, 0, 0), Math.PI / 4);
  lights.spotBase = 0.5;
  lights.kind = "pulse";
  planetSlots.push(new THREE.Vector3(0, 3.2, 0));
}

// ─── 12 静かな回廊・水辺 ────────────────────────────────
function buildHouse12(c) {
  const { THREE, group, arch, mats, lightCol, accent, exhibits, planetSlots, lights, animatables, quality } = c;
  const { w, d, h } = arch;
  // 長い回廊：側壁は半透明
  const mistWall = stdMat(THREE, 0x5a6a9a, { transparent: true, opacity: 0.28, emissive: 0x304060, emissiveIntensity: 0.12, side: THREE.DoubleSide });
  group.add(mesh(THREE, new THREE.BoxGeometry(0.2, h, d), mistWall, -w / 2, h / 2, 0));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.2, h, d), mistWall, w / 2, h / 2, 0));
  floor(THREE, group, w - 0.2, d - 0.2, mats.stone);
  // アーチ列
  for (let i = 0; i < 6; i++) {
    const z = d / 2 - 2.5 - i * 3.2;
    group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.85, 0.25, 0.25), mats.stone, 0, h * 0.7, z));
    [-w * 0.32, w * 0.32].forEach((x) => {
      group.add(mesh(THREE, new THREE.BoxGeometry(0.25, h * 0.65, 0.25), mats.stone, x, h * 0.35, z));
    });
  }
  // 長い水面
  const water = mesh(
    THREE,
    new THREE.BoxGeometry(w * 0.55, 0.08, d * 0.65),
    stdMat(THREE, accent.getHex(), { transparent: true, opacity: 0.45, emissive: accent.getHex(), emissiveIntensity: 0.2 }),
    0,
    0.18,
    -1
  );
  group.add(water);
  animatables.push({ mesh: water, kind: "pulseMat", speed: 0.5 });
  // ヴェール
  for (let i = 0; i < 4; i++) {
    const veil = mesh(THREE, new THREE.PlaneGeometry(2.0, h * 0.65), mistWall, (i % 2 ? -1 : 1) * 2.2, h * 0.4, d / 2 - 4 - i * 4);
    veil.material = mistWall.clone();
    veil.material.side = THREE.DoubleSide;
    group.add(veil);
    animatables.push({ mesh: veil, kind: "sway", speed: 0.35 + i * 0.05, amp: 0.06 });
  }
  // ベッド alcove
  group.add(mesh(THREE, new THREE.BoxGeometry(2.8, 0.35, 1.6), mats.woodPanel, -2.5, 0.35, -d / 2 + 3));
  group.add(mesh(THREE, new THREE.BoxGeometry(2.5, 0.2, 1.3), mats.fabric, -2.5, 0.55, -d / 2 + 3));
  // 月
  const moon = mesh(
    THREE,
    new THREE.SphereGeometry(0.9, 16, 16),
    stdMat(THREE, 0xc8d0f0, { emissive: 0xa0b0e0, emissiveIntensity: 0.55, transparent: true, opacity: 0.9 }),
    0,
    h - 1.2,
    -d / 2 + 2
  );
  group.add(moon);
  animatables.push({ mesh: moon, kind: "pulseMat", speed: 0.7 });
  animatables.push({ mesh: moon, kind: "bob", baseY: h - 1.2, speed: 0.4, amp: 0.12 });
  // 霧粒子
  if (quality !== "low") {
    const count = 100;
    const pos = new Float32Array(count * 3);
    const phases = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * w * 0.8;
      pos[i * 3 + 1] = 0.5 + Math.random() * (h - 1);
      pos[i * 3 + 2] = (Math.random() - 0.5) * d * 0.8;
      phases[i] = Math.random() * Math.PI * 2;
    }
    const pts = new THREE.Points(
      new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
      new THREE.PointsMaterial({
        color: 0xb0b8e0,
        size: 0.35,
        transparent: true,
        opacity: 0.3,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    );
    pts.userData = { kind: "mist", phases };
    group.add(pts);
    animatables.push({ mesh: pts, kind: "particles" });
  }

  pushEx(exhibits, "水面", "Water", 0, 0.3, -1, "静かな内界", "Quiet inner world");
  pushEx(exhibits, "月明かり", "Moonlight", 0, h - 1.2, -d / 2 + 2, "夢と休息", "Dream and rest");
  pushEx(exhibits, "ベッド", "Bed", -2.5, 0.5, -d / 2 + 3, "手放しと休息", "Release and rest");

  lights.kind = "mist";
  lights.pl = point(THREE, group, lightCol.getHex(), 0.4, 0, 3.5, 0, 30);
  lights.base = 0.4;
  lights.spot = spot(THREE, group, 0xc8d0f0, 0.75, new THREE.Vector3(0, h, -d / 2 + 3), new THREE.Vector3(0, 0, 0), Math.PI / 5);
  lights.spotBase = 0.75;
  planetSlots.push(new THREE.Vector3(0, 2.8, -d * 0.15));
}

// ─── Generic fallback ───────────────────────────────────
function buildGenericShell(c) {
  buildHouse1(c);
}

// ─── helpers ────────────────────────────────────────────
function mesh(THREE, geo, mat, x, y, z) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

function floor(THREE, group, w, d, mat) {
  const f = mesh(THREE, new THREE.BoxGeometry(w, 0.12, d), mat, 0, 0.06, 0);
  group.add(f);
  return f;
}

function addWalls(THREE, group, w, d, h, mat, opts) {
  opts = opts || {};
  group.add(mesh(THREE, new THREE.BoxGeometry(w, h, 0.3), mat, 0, h / 2, -d / 2));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.3, h, d), mat, -w / 2, h / 2, 0));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.3, h, d), mat, w / 2, h / 2, 0));
  if (!opts.openFront) {
    group.add(mesh(THREE, new THREE.BoxGeometry(w, h, 0.3), mat, 0, h / 2, d / 2));
  } else {
    // 前面は開口＋壁の両袖
    group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.28, h, 0.3), mat, -w * 0.36, h / 2, d / 2));
    group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.28, h, 0.3), mat, w * 0.36, h / 2, d / 2));
    group.add(mesh(THREE, new THREE.BoxGeometry(w * 0.5, h * 0.25, 0.3), mat, 0, h * 0.88, d / 2));
  }
  group.add(mesh(THREE, new THREE.BoxGeometry(w, 0.2, d), mat, 0, h, 0));
}

function addArmchair(THREE, group, mats, x, y, z) {
  group.add(mesh(THREE, new THREE.BoxGeometry(1.1, 0.15, 1.0), mats.fabric, x, 0.55 + y, z));
  group.add(mesh(THREE, new THREE.BoxGeometry(1.1, 1.0, 0.15), mats.fabric, x, 1.1 + y, z - 0.4));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.15, 0.5, 0.9), mats.woodPanel, x - 0.5, 0.7 + y, z));
  group.add(mesh(THREE, new THREE.BoxGeometry(0.15, 0.5, 0.9), mats.woodPanel, x + 0.5, 0.7 + y, z));
}

function point(THREE, group, color, intensity, x, y, z, dist) {
  const pl = new THREE.PointLight(color, intensity, dist || 20, 2);
  pl.position.set(x, y, z);
  group.add(pl);
  return pl;
}

function spot(THREE, group, color, intensity, pos, target, angle) {
  const s = new THREE.SpotLight(color, intensity, 35, angle || Math.PI / 6, 0.4, 1.2);
  s.position.copy(pos);
  s.target.position.copy(target);
  group.add(s);
  group.add(s.target);
  return s;
}

function ensureLight(THREE, group, lights, lightCol, accent, arch) {
  if (!lights.pl) {
    lights.pl = point(THREE, group, lightCol.getHex(), 0.9, 0, arch.h * 0.5, 0, 22);
    lights.base = 0.9;
  }
  if (!lights.spot) {
    lights.spot = spot(
      THREE,
      group,
      accent.getHex(),
      0.5,
      new THREE.Vector3(0, arch.h + 1, 2),
      new THREE.Vector3(0, 0, 0)
    );
    lights.spotBase = 0.5;
  }
}

function pushEx(exhibits, name, nameEn, x, y, z, caption, captionEn) {
  exhibits.push({ name, nameEn, x, y, z, caption, captionEn });
}

function makePlate(THREE, text, color) {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 96;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "rgba(20,18,16,0.9)";
  ctx.fillRect(0, 0, 256, 96);
  ctx.strokeStyle = color || "#c9a96e";
  ctx.lineWidth = 4;
  ctx.strokeRect(6, 6, 244, 84);
  ctx.fillStyle = color || "#e8d5b0";
  ctx.font = "600 42px Cinzel, Georgia, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 50);
  const spr = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false })
  );
  spr.scale.set(2.8, 1.05, 1);
  return spr;
}

export function animateArch(animatables, houseGroups, current, t, dt, reducedMotion) {
  if (reducedMotion) return;
  animatables.forEach((a) => {
    if (!a.mesh) return;
    const ph = a.phase || 0;
    if (a.kind === "spin") {
      if (a.axis === "z") a.mesh.rotation.z += (a.speed || 1) * dt;
      else a.mesh.rotation.y += (a.speed || 1) * dt;
    } else if (a.kind === "flame") {
      a.mesh.position.y = a.baseY + Math.sin(t * (a.speed || 5) + ph) * (a.amp || 0.1);
      a.mesh.scale.y = 1 + Math.sin(t * 7) * 0.15;
      if (a.mesh.material && a.mesh.material.emissiveIntensity != null) {
        a.mesh.material.emissiveIntensity = 0.55 + Math.sin(t * 9) * 0.25;
      }
    } else if (a.kind === "sway") {
      a.mesh.rotation.y = Math.sin(t * (a.speed || 1) + ph) * (a.amp || 0.05);
    } else if (a.kind === "pulseMat") {
      if (a.mesh.material && a.mesh.material.emissiveIntensity != null) {
        a.mesh.material.emissiveIntensity = 0.4 + Math.sin(t * (a.speed || 2) + ph) * 0.35;
      }
    } else if (a.kind === "bob") {
      const by = a.baseY != null ? a.baseY : a.mesh.position.y;
      a.mesh.position.y = by + Math.sin(t * (a.speed || 1) + ph) * (a.amp || 0.1);
    } else if (a.kind === "drift") {
      a.mesh.position.y = (a.baseY || 2) + Math.sin(t * (a.speed || 0.8) + ph) * (a.amp || 0.2);
      a.mesh.position.x = (a.baseX || 0) + Math.cos(t * (a.speed || 0.8) * 0.6 + ph) * (a.amp || 0.2);
    } else if (a.kind === "particles") {
      const pos = a.mesh.geometry && a.mesh.geometry.attributes.position;
      if (!pos) return;
      const phases = a.mesh.userData.phases;
      const arr = pos.array;
      for (let i = 0; i < pos.count; i++) {
        const ix = i * 3;
        const pf = phases ? phases[i] : i;
        arr[ix] += Math.sin(t * 0.3 + pf) * dt * 0.2;
        arr[ix + 2] += Math.cos(t * 0.25 + pf) * dt * 0.15;
      }
      pos.needsUpdate = true;
    }
  });
  Object.keys(houseGroups).forEach((k) => {
    const g = houseGroups[k];
    if (!g || !g.light) return;
    const n = parseInt(k, 10);
    const active = n === current;
    const bi = g.baseIntensity || 0.9;
    const mult = active ? 1.15 : 0.35;
    if (g.lightKind === "flicker") {
      g.light.intensity = bi * mult * (0.75 + Math.random() * 0.4);
    } else if (g.lightKind === "spotlight" && active && g.spot) {
      g.spot.intensity = (g.spotBase || 1) * (0.95 + Math.sin(t * 1.2) * 0.1);
    } else {
      g.light.intensity = bi * mult;
      if (g.spot) g.spot.intensity = (g.spotBase || 0.5) * (active ? 1.1 : 0.3);
    }
  });
}

export function applyArchAtmosphere(ctx, houseGroups, housesData, num) {
  const { fog, ambient, hemi, scene } = ctx;
  const THREE = ctx.THREE;
  if (num >= 1 && housesData[num]) {
    const pal = housesData[num].palette;
    const fogCol = hexColor(THREE, pal.fog || "#0a0c12").getHex();
    fog.color.setHex(fogCol);
    fog.density = num === 5 ? 0.012 : num === 12 ? 0.022 : 0.01;
    scene.background.setHex(fogCol);
    ambient.color.copy(hexColor(THREE, pal.light || "#fff"));
    ambient.intensity = num === 5 ? 0.1 : 0.28;
    Object.keys(houseGroups).forEach((k) => {
      const g = houseGroups[k];
      const active = parseInt(k, 10) === num;
      g.light.intensity = (g.baseIntensity || 0.9) * (active ? 1.15 : 0.35);
      if (g.spot) g.spot.intensity = (g.spotBase || 0.5) * (active ? 1.1 : 0.28);
    });
  } else {
    fog.color.setHex(0x0a0c12);
    fog.density = 0.008;
    scene.background.setHex(0x0a0c12);
    ambient.color.set(0xb8b0a0);
    ambient.intensity = 0.3;
  }
}
