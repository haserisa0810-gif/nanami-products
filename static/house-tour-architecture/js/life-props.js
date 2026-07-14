/**
 * Architecture Edition — 「生活感」小物レイヤ
 *
 * - 建築本体（arch-builder）から分離
 * - グループ名 lived_in_props でまとめる → 表示ON/OFF で雰囲気を戻せる
 * - 将来 glTF 差し替えは各 addXxx の中身だけ差し替えればよい
 *
 * フラグ:
 *   localStorage "ht-arch-lived-in" = "1" | "0"
 *   URL ?lived_in=0 で強制OFF / ?lived_in=1 で強制ON
 */

const STORAGE_KEY = "ht-arch-lived-in";
const GROUP_NAME = "lived_in_props";

export function isLivedInEnabled() {
  try {
    const q = new URLSearchParams(window.location.search || "").get("lived_in");
    if (q === "0" || q === "false" || q === "off") return false;
    if (q === "1" || q === "true" || q === "on") return true;
  } catch (e) { /* */ }
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    if (s === "0") return false;
    if (s === "1") return true;
  } catch (e) { /* */ }
  // 既定ON（建築の上に生活感）。嫌ならOFFにできる。
  return true;
}

export function setLivedInEnabled(on) {
  try {
    localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
  } catch (e) { /* */ }
}

/** 全棟の lived_in_props の表示を切替（再ビルド不要） */
export function setLivedInVisible(houseGroups, on) {
  if (!houseGroups) return;
  Object.keys(houseGroups).forEach((k) => {
    const hg = houseGroups[k];
    if (!hg || !hg.group) return;
    const g = hg.group.getObjectByName(GROUP_NAME);
    if (g) g.visible = !!on;
  });
}

/**
 * 棟ビルド後に呼ぶ。
 * 常にグループを作り、visible だけ isLivedInEnabled() に合わせる
 * → メニューで ON/OFF しても再読込不要（雰囲気をすぐ戻せる）。
 */
export function attachLivedInProps(ctx) {
  const { THREE, group, mats, n, arch, animatables, exhibits, quality } = ctx;
  if (!group || !mats || !THREE) return null;

  ensurePorcelain(mats);

  const houseFn = {
    1: fillHouse1,
    2: fillHouse2,
    3: fillHouse3,
    4: fillHouse4,
    5: fillHouse5,
    6: fillHouse6,
    7: fillHouse7,
    8: fillHouse8,
    9: fillHouse9,
    10: fillHouse10,
    11: fillHouse11,
    12: fillHouse12,
  }[n];
  if (!houseFn) return null;

  const root = new THREE.Group();
  root.name = GROUP_NAME;
  root.userData.livedIn = true;

  const helpers = makeHelpers(THREE, mats);
  houseFn({
    THREE,
    root,
    mats,
    arch,
    animatables,
    exhibits,
    quality,
    helpers,
  });

  if (!root.children.length) return null;
  root.visible = isLivedInEnabled();
  group.add(root);
  return root;
}

function ensurePorcelain(mats) {
  if (!mats.porcelain) {
    mats.porcelain = new THREE.MeshStandardMaterial({
      color: 0xf2efe8,
      roughness: 0.35,
      metalness: 0.05,
    });
  }
}

// ─── helpers ─────────────────────────────────────────────
function makeHelpers(THREE, mats) {
  function m(geo, mat, x, y, z) {
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  function coffeeCup(x, y, z, scale) {
    const s = scale || 1;
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.07 * s, 0.06 * s, 0.1 * s, 12), mats.porcelain || mats.plaster, 0, 0.05 * s, 0));
    g.add(
      m(
        new THREE.TorusGeometry(0.055 * s, 0.012 * s, 6, 12, Math.PI),
        mats.porcelain || mats.plaster,
        0.07 * s,
        0.05 * s,
        0
      )
    );
    // 中の「液体」
    g.add(
      m(
        new THREE.CylinderGeometry(0.055 * s, 0.055 * s, 0.02 * s, 12),
        new THREE.MeshStandardMaterial({ color: 0x3a2210, roughness: 0.6, metalness: 0 }),
        0,
        0.09 * s,
        0
      )
    );
    // 受け皿
    g.add(m(new THREE.CylinderGeometry(0.1 * s, 0.1 * s, 0.012 * s, 16), mats.plaster, 0, 0.006 * s, 0));
    g.position.set(x, y, z);
    return g;
  }

  function openNotebook(x, y, z, rotY) {
    const g = new THREE.Group();
    const paper = mats.parchment;
    // 左ページ
    g.add(m(new THREE.BoxGeometry(0.28, 0.01, 0.36), paper, -0.14, 0.01, 0));
    // 右ページ
    g.add(m(new THREE.BoxGeometry(0.28, 0.01, 0.36), paper, 0.14, 0.01, 0));
    // 背
    g.add(m(new THREE.BoxGeometry(0.04, 0.015, 0.36), mats.darkMetal, 0, 0.012, 0));
    // 線（簡易）
    for (let i = 0; i < 5; i++) {
      g.add(
        m(
          new THREE.BoxGeometry(0.22, 0.002, 0.008),
          mats.darkMetal,
          -0.14,
          0.018,
          -0.12 + i * 0.05
        )
      );
      g.add(
        m(
          new THREE.BoxGeometry(0.22, 0.002, 0.008),
          mats.darkMetal,
          0.14,
          0.018,
          -0.12 + i * 0.05
        )
      );
    }
    g.position.set(x, y, z);
    if (rotY) g.rotation.y = rotY;
    g.rotation.x = -0.02;
    return g;
  }

  function pen(x, y, z, rotY) {
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.012, 0.012, 0.22, 8), mats.darkMetal, 0, 0.012, 0));
    g.add(m(new THREE.ConeGeometry(0.012, 0.04, 8), mats.brass, 0, 0.012, 0.12));
    g.rotation.z = Math.PI / 2;
    g.rotation.y = rotY || 0.4;
    g.position.set(x, y, z);
    return g;
  }

  function deskLamp(x, y, z, animatables) {
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.12, 0.14, 0.04, 12), mats.darkMetal, 0, 0.02, 0));
    g.add(m(new THREE.CylinderGeometry(0.025, 0.025, 0.45, 8), mats.darkMetal, 0, 0.28, 0));
    const arm = m(new THREE.CylinderGeometry(0.02, 0.02, 0.35, 8), mats.darkMetal, 0.12, 0.48, 0);
    arm.rotation.z = Math.PI / 3;
    g.add(arm);
    const shade = m(
      new THREE.CylinderGeometry(0.08, 0.14, 0.12, 12, 1, true),
      new THREE.MeshStandardMaterial({
        color: 0xf0e0b0,
        emissive: 0xffd080,
        emissiveIntensity: 0.45,
        side: THREE.DoubleSide,
        roughness: 0.7,
      }),
      0.22,
      0.58,
      0
    );
    g.add(shade);
    const bulb = new THREE.PointLight(0xffe0b0, 0.55, 4.5, 2);
    bulb.position.set(0.22, 0.52, 0);
    g.add(bulb);
    g.position.set(x, y, z);
    if (animatables) {
      animatables.push({ mesh: shade, kind: "pulseMat", speed: 1.1 });
    }
    return g;
  }

  function monitor(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.7, 0.45, 0.05), mats.darkMetal, 0, 0.35, 0));
    g.add(
      m(
        new THREE.BoxGeometry(0.62, 0.38, 0.02),
        new THREE.MeshStandardMaterial({
          color: 0x1a2838,
          emissive: 0x3a6a80,
          emissiveIntensity: 0.4,
          roughness: 0.4,
        }),
        0,
        0.35,
        0.03
      )
    );
    g.add(m(new THREE.BoxGeometry(0.12, 0.18, 0.08), mats.darkMetal, 0, 0.1, -0.02));
    g.add(m(new THREE.BoxGeometry(0.28, 0.03, 0.18), mats.darkMetal, 0, 0.02, 0));
    g.position.set(x, y, z);
    return g;
  }

  function checklist(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.22, 0.008, 0.3), mats.parchment, 0, 0.01, 0));
    for (let i = 0; i < 4; i++) {
      g.add(m(new THREE.BoxGeometry(0.04, 0.004, 0.04), mats.darkMetal, -0.07, 0.016, -0.1 + i * 0.06));
      g.add(m(new THREE.BoxGeometry(0.12, 0.003, 0.012), mats.darkMetal, 0.02, 0.016, -0.1 + i * 0.06));
    }
    g.position.set(x, y, z);
    g.rotation.y = -0.25;
    return g;
  }

  function plant(x, y, z, h) {
    const g = new THREE.Group();
    const potH = h || 0.35;
    g.add(m(new THREE.CylinderGeometry(0.12, 0.1, potH, 10), mats.stone, 0, potH / 2, 0));
    g.add(
      m(
        new THREE.SphereGeometry(0.22, 10, 10),
        new THREE.MeshStandardMaterial({ color: 0x2d5a3a, roughness: 0.85 }),
        0,
        potH + 0.18,
        0
      )
    );
    g.add(
      m(
        new THREE.SphereGeometry(0.14, 8, 8),
        new THREE.MeshStandardMaterial({ color: 0x3a7048, roughness: 0.8 }),
        0.12,
        potH + 0.28,
        0.05
      )
    );
    g.position.set(x, y, z);
    return g;
  }

  function booksOnShelf(x, y, z, count) {
    const g = new THREE.Group();
    const n = count || 6;
    for (let i = 0; i < n; i++) {
      const thick = 0.04 + (i % 3) * 0.015;
      const col = [0x4a3020, 0x2a3a50, 0x5a2030, 0x3a4a30][i % 4];
      g.add(
        m(
          new THREE.BoxGeometry(thick, 0.22 + (i % 2) * 0.06, 0.16),
          new THREE.MeshStandardMaterial({ color: col, roughness: 0.8 }),
          i * 0.055,
          0.12,
          0
        )
      );
    }
    g.position.set(x, y, z);
    return g;
  }

  function wallCalendar(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.55, 0.7, 0.03), mats.plaster, 0, 0, 0));
    g.add(m(new THREE.BoxGeometry(0.5, 0.12, 0.02), mats.fabric, 0, 0.25, 0.02));
    // 日付グリッド
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 5; c++) {
        g.add(
          m(
            new THREE.BoxGeometry(0.06, 0.06, 0.01),
            mats.parchment,
            -0.18 + c * 0.09,
            0.08 - r * 0.1,
            0.02
          )
        );
      }
    }
    // 今日の印
    g.add(
      m(
        new THREE.BoxGeometry(0.07, 0.07, 0.015),
        new THREE.MeshStandardMaterial({ color: 0xc04040, emissive: 0x802020, emissiveIntensity: 0.3 }),
        0,
        -0.02,
        0.025
      )
    );
    g.position.set(x, y, z);
    return g;
  }

  function photoFrame(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.28, 0.22, 0.03), mats.woodPanel, 0, 0.12, 0));
    g.add(m(new THREE.BoxGeometry(0.22, 0.16, 0.02), mats.parchment, 0, 0.12, 0.02));
    g.add(m(new THREE.BoxGeometry(0.08, 0.1, 0.04), mats.woodPanel, 0, 0.04, -0.01));
    g.position.set(x, y, z);
    g.rotation.y = 0.3;
    return g;
  }

  function mugSteamHint(x, y, z, animatables) {
    if (!animatables) return null;
    const g = new THREE.Group();
    const mist = m(
      new THREE.SphereGeometry(0.04, 6, 6),
      new THREE.MeshStandardMaterial({
        color: 0xe8e8f0,
        transparent: true,
        opacity: 0.25,
        depthWrite: false,
      }),
      0,
      0.15,
      0
    );
    g.add(mist);
    g.position.set(x, y, z);
    animatables.push({ mesh: mist, kind: "bob", baseY: 0.15, speed: 1.4, amp: 0.04 });
    return g;
  }

  function keys(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.TorusGeometry(0.05, 0.01, 6, 12), mats.brass, 0, 0.02, 0));
    g.add(m(new THREE.BoxGeometry(0.12, 0.02, 0.03), mats.brass, 0.08, 0.02, 0));
    g.add(m(new THREE.BoxGeometry(0.1, 0.02, 0.025), mats.darkMetal, 0.06, 0.02, 0.04));
    g.position.set(x, y, z);
    g.rotation.y = 0.5;
    return g;
  }

  function bag(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.45, 0.35, 0.2), mats.fabric, 0, 0.2, 0));
    g.add(m(new THREE.TorusGeometry(0.12, 0.02, 6, 12, Math.PI), mats.darkMetal, 0, 0.4, 0));
    g.position.set(x, y, z);
    return g;
  }

  function umbrellaStand(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.18, 0.15, 0.5, 12), mats.darkMetal, 0, 0.25, 0));
    g.add(m(new THREE.CylinderGeometry(0.02, 0.02, 0.9, 6), mats.darkMetal, 0.05, 0.7, 0.02));
    g.add(m(new THREE.ConeGeometry(0.12, 0.15, 8), mats.fabric, 0.05, 1.15, 0.02));
    g.position.set(x, y, z);
    return g;
  }

  function glasses(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.TorusGeometry(0.04, 0.008, 6, 12), mats.darkMetal, -0.05, 0.02, 0));
    g.add(m(new THREE.TorusGeometry(0.04, 0.008, 6, 12), mats.darkMetal, 0.05, 0.02, 0));
    g.add(m(new THREE.BoxGeometry(0.04, 0.008, 0.008), mats.darkMetal, 0, 0.02, 0));
    g.position.set(x, y, z);
    return g;
  }

  function bottle(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.05, 0.05, 0.22, 10), mats.glass, 0, 0.12, 0));
    g.add(m(new THREE.CylinderGeometry(0.025, 0.025, 0.08, 8), mats.darkMetal, 0, 0.26, 0));
    g.position.set(x, y, z);
    return g;
  }

  function cushion(x, y, z, color) {
    return m(
      new THREE.BoxGeometry(0.55, 0.12, 0.45),
      new THREE.MeshStandardMaterial({ color: color || 0x6a3040, roughness: 0.95 }),
      x,
      y,
      z
    );
  }

  function candle(x, y, z, animatables) {
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.04, 0.05, 0.18, 10), mats.parchment, 0, 0.1, 0));
    const flame = m(
      new THREE.SphereGeometry(0.035, 8, 8),
      new THREE.MeshStandardMaterial({
        color: 0xffc060,
        emissive: 0xff8020,
        emissiveIntensity: 0.9,
      }),
      0,
      0.22,
      0
    );
    g.add(flame);
    const pl = new THREE.PointLight(0xffa040, 0.35, 3.5, 2);
    pl.position.set(0, 0.25, 0);
    g.add(pl);
    g.position.set(x, y, z);
    if (animatables) animatables.push({ mesh: flame, kind: "pulseMat", speed: 2.2 });
    return g;
  }

  function bowl(x, y, z) {
    return m(new THREE.CylinderGeometry(0.16, 0.12, 0.08, 12), mats.porcelain || mats.plaster, x, y + 0.04, z);
  }

  function nameTag(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.28, 0.08, 0.02), mats.parchment, 0, 0.04, 0));
    g.add(m(new THREE.BoxGeometry(0.22, 0.03, 0.01), mats.darkMetal, 0, 0.04, 0.015));
    g.position.set(x, y, z);
    return g;
  }

  function slippers(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.12, 0.04, 0.28), mats.fabric, -0.1, 0.02, 0));
    g.add(m(new THREE.BoxGeometry(0.12, 0.04, 0.28), mats.fabric, 0.1, 0.02, 0.05));
    g.position.set(x, y, z);
    return g;
  }

  function wineGlass(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.CylinderGeometry(0.015, 0.015, 0.14, 8), mats.glass, 0, 0.08, 0));
    g.add(m(new THREE.CylinderGeometry(0.06, 0.04, 0.1, 12), mats.glass, 0, 0.2, 0));
    g.add(m(new THREE.CylinderGeometry(0.05, 0.05, 0.015, 12), mats.glass, 0, 0.01, 0));
    g.position.set(x, y, z);
    return g;
  }

  function envelope(x, y, z) {
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(0.2, 0.01, 0.14), mats.parchment, 0, 0.01, 0));
    g.position.set(x, y, z);
    g.rotation.y = 0.3;
    return g;
  }

  /**
   * サイドテーブル。topY = 天板上面の高さ。
   * 小物は topY の少し上に置く（浮かないように必ずセットで使う）。
   */
  function sideTable(x, topY, z, opts) {
    opts = opts || {};
    const tw = opts.w || 0.55;
    const td = opts.d || 0.45;
    const legH = Math.max(0.35, topY - 0.04);
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(tw, 0.05, td), mats.woodPanel, 0, topY - 0.025, 0));
    const ox = tw * 0.38;
    const oz = td * 0.35;
    [[-ox, -oz], [ox, -oz], [-ox, oz], [ox, oz]].forEach(function (p) {
      g.add(m(new THREE.CylinderGeometry(0.025, 0.03, legH, 8), mats.woodPanel, p[0], legH / 2, p[1]));
    });
    g.position.set(x, 0, z);
    g.userData.topY = topY;
    return g;
  }

  /** コンソール（細長い玄関テーブル） */
  function consoleTable(x, topY, z, width) {
    const tw = width || 1.4;
    const td = 0.4;
    const legH = Math.max(0.4, topY - 0.04);
    const g = new THREE.Group();
    g.add(m(new THREE.BoxGeometry(tw, 0.05, td), mats.woodPanel, 0, topY - 0.025, 0));
    [[-tw * 0.42, -td * 0.3], [tw * 0.42, -td * 0.3], [-tw * 0.42, td * 0.3], [tw * 0.42, td * 0.3]].forEach(
      function (p) {
        g.add(m(new THREE.BoxGeometry(0.06, legH, 0.06), mats.woodPanel, p[0], legH / 2, p[1]));
      }
    );
    g.position.set(x, 0, z);
    g.userData.topY = topY;
    return g;
  }

  /** ナイトスタンド */
  function nightstand(x, topY, z) {
    const g = new THREE.Group();
    const bodyH = topY - 0.05;
    g.add(m(new THREE.BoxGeometry(0.5, bodyH, 0.4), mats.woodPanel, 0, bodyH / 2, 0));
    g.add(m(new THREE.BoxGeometry(0.54, 0.04, 0.44), mats.woodPanel, 0, topY - 0.02, 0));
    g.position.set(x, 0, z);
    g.userData.topY = topY;
    return g;
  }

  function pushEx(exhibits, name, nameEn, x, y, z, caption, captionEn) {
    if (!exhibits) return;
    exhibits.push({ name, nameEn, x, y, z, caption, captionEn });
  }

  return {
    m,
    coffeeCup,
    openNotebook,
    pen,
    deskLamp,
    monitor,
    checklist,
    plant,
    booksOnShelf,
    wallCalendar,
    photoFrame,
    mugSteamHint,
    keys,
    bag,
    umbrellaStand,
    glasses,
    bottle,
    cushion,
    candle,
    bowl,
    nameTag,
    slippers,
    wineGlass,
    envelope,
    sideTable,
    consoleTable,
    nightstand,
    pushEx,
  };
}

// ─── 1 玄関：出かける直前 ────────────────────────────────
function fillHouse1({ root, arch, exhibits, helpers }) {
  // コンソールの上に鍵・手紙（浮かない）
  const topY = 0.95;
  root.add(helpers.consoleTable(0, topY, 2.2, 1.6));
  root.add(helpers.keys(0.35, topY, 2.25));
  root.add(helpers.envelope(-0.4, topY, 2.15));
  root.add(helpers.photoFrame(0.7, topY, 2.1));
  // 床置きはOK
  root.add(helpers.bag(-1.8, 0, arch.d / 2 - 1.5));
  root.add(helpers.umbrellaStand(2.8, 0, arch.d / 2 - 1.0));
  root.add(helpers.plant(-3.2, 0, -2.5, 0.4));
  helpers.pushEx(
    exhibits,
    "玄関のコンソール",
    "Entry console",
    0,
    1.0,
    2.2,
    "鍵と手紙 — 今から外へ出る気配",
    "Keys and mail — about to step out"
  );
}

// ─── 2 保管庫：仕分けの途中（作業台 top≈1.14 の上） ─────
function fillHouse2({ root, exhibits, helpers }) {
  // 建築の作業台 y≈1.05 天板、その上に載せる
  const topY = 1.16;
  root.add(helpers.openNotebook(-0.5, topY, 2.5, 0.2));
  root.add(helpers.pen(0.1, topY + 0.02, 2.4, -0.4));
  root.add(helpers.checklist(0.8, topY, 2.6));
  root.add(helpers.coffeeCup(1.5, topY, 2.3, 1));
  root.add(helpers.glasses(-1.2, topY, 2.7));
  // 鍵箱の上 (chest ~0.9高)
  root.add(helpers.keys(3.2, 0.95, -3.3));
  helpers.pushEx(
    exhibits,
    "仕分け中の台",
    "Sorting table",
    0,
    1.2,
    2.5,
    "価値を確かめている途中",
    "Mid-inventory of what matters"
  );
}

// ─── 3 回廊：通ったあと（床＋ベンチ上。手紙だけ情報として漂う） ──
function fillHouse3({ root, arch, exhibits, helpers }) {
  const z = arch.d / 2 - 4;
  // 床置き
  root.add(helpers.bag(0.8, 0, z));
  // ベンチ＝サイドテーブルを受け面に
  const benchTop = 0.58;
  root.add(helpers.sideTable(-0.2, benchTop, z + 0.35, { w: 1.35, d: 0.5 }));
  root.add(helpers.bottle(-0.55, benchTop, z + 0.4));
  root.add(helpers.envelope(0.15, benchTop, z + 0.3));
  root.add(helpers.glasses(0.4, benchTop, z + 0.25));
  // 手紙だけ浮遊＝情報・通信の象徴（カップは置かない）
  root.add(helpers.envelope(1.2, 1.45, z - 1.5));
  root.add(helpers.envelope(-1.0, 1.75, z - 2.2));
  helpers.pushEx(
    exhibits,
    "通ったあとの痕跡",
    "Traces of passage",
    0,
    0.8,
    z,
    "ベンチ上のボトルと手紙。漂うのは手紙だけ",
    "Bottle on the bench; only letters drift as messages"
  );
}

// ─── 4 邸宅：肘掛け椅子の横にサイドテーブル ──────────────
function fillHouse4({ root, exhibits, helpers }) {
  // 左アームチェア (-3.2, 1.5) の内側にサイドテーブル
  const topL = 0.88;
  root.add(helpers.sideTable(-2.0, topL, 2.15, { w: 0.6, d: 0.5 }));
  root.add(helpers.coffeeCup(-2.05, topL, 2.2, 1.1));
  root.add(helpers.photoFrame(-1.85, topL, 2.0));

  // 右アームチェア (3.2, 1.5) の内側
  const topR = 0.88;
  root.add(helpers.sideTable(2.0, topR, 2.0, { w: 0.6, d: 0.5 }));
  root.add(helpers.openNotebook(2.0, topR, 2.05, 0.35));
  root.add(helpers.pen(2.25, topR + 0.02, 1.9, 0.4));

  // 床・植物は受け面不要
  root.add(helpers.plant(3.5, 0, -1.5, 0.4));
  root.add(helpers.cushion(-3.0, 0.7, 1.2, 0x5a3048));
  root.add(helpers.cushion(3.0, 0.65, 1.5, 0x4a3a50));

  helpers.pushEx(
    exhibits,
    "暖炉脇のサイドテーブル",
    "Side table by the hearth",
    -2.0,
    0.95,
    2.15,
    "テーブルの上のカップ — さっきまで座っていた気配",
    "Cup on the table — someone was sitting here"
  );
}

// ─── 5 劇場：袖（台の上に譜面） ──────────────────────────
function fillHouse5({ root, exhibits, helpers }) {
  const topL = 1.05;
  root.add(helpers.sideTable(-4.5, topL, 6.0, { w: 0.7, d: 0.5 }));
  root.add(helpers.openNotebook(-4.5, topL, 6.05, 0.1));
  root.add(helpers.pen(-4.2, topL + 0.02, 5.9, 0.2));

  const topR = 1.0;
  root.add(helpers.sideTable(4.5, topR, 5.5, { w: 0.55, d: 0.45 }));
  root.add(helpers.coffeeCup(4.5, topR, 5.55, 1));
  root.add(helpers.bottle(4.7, topR, 5.3));

  root.add(helpers.plant(-5.5, 0, -2, 0.45));
  root.add(helpers.bag(5.0, 0, 4.5));
  helpers.pushEx(
    exhibits,
    "袖の譜面台",
    "Score table in the wings",
    -4.5,
    1.15,
    6,
    "台の上のノート — 次の出番を待つ",
    "Notebook on a stand — waiting for the next entrance"
  );
}

// ─── 6 研究室：毎日の机（厚め） ──────────────────────────
function fillHouse6({ root, arch, animatables, exhibits, helpers }) {
  const dx = 0;
  const dz = 1.5;
  const topY = 1.08;

  root.add(helpers.monitor(dx - 0.15, topY, dz - 0.35));
  root.add(helpers.openNotebook(dx + 0.35, topY, dz + 0.2, -0.2));
  root.add(helpers.pen(dx + 0.55, topY + 0.02, dz + 0.05, 0.5));
  root.add(helpers.coffeeCup(dx - 0.55, topY, dz + 0.25, 1.15));
  const steam = helpers.mugSteamHint(dx - 0.55, topY + 0.08, dz + 0.25, animatables);
  if (steam) root.add(steam);
  root.add(helpers.deskLamp(dx + 0.85, topY, dz - 0.15, animatables));
  root.add(helpers.checklist(dx + 0.15, topY, dz + 0.35));
  root.add(helpers.plant(dx - 0.95, 1.0, dz - 0.4, 0.28));

  root.add(helpers.openNotebook(-3, topY, 1.5, 0.15));
  root.add(helpers.pen(-2.7, topY + 0.02, 1.35, -0.3));
  root.add(helpers.coffeeCup(-3.4, topY, -2, 1));

  root.add(helpers.wallCalendar(arch.w / 2 - 0.25, 2.4, -0.5));
  root.add(helpers.booksOnShelf(-arch.w / 2 + 0.5, 1.8, -arch.d / 2 + 0.6, 8));
  root.add(helpers.booksOnShelf(-arch.w / 2 + 0.5, 2.2, -arch.d / 2 + 0.6, 7));

  helpers.pushEx(
    exhibits,
    "使いかけの机",
    "Lived-in desk",
    0,
    1.2,
    1.5,
    "ノート・カップ・予定 — 今日もここで積み重ねている",
    "Notebook, cup, list — work in progress"
  );
}

// ─── 7 応接：話し合いのあと ──────────────────────────────
function fillHouse7({ root, exhibits, helpers }) {
  root.add(helpers.coffeeCup(-0.6, 1.12, 0.3, 1));
  root.add(helpers.coffeeCup(0.7, 1.12, -0.25, 1));
  root.add(helpers.openNotebook(0.1, 1.12, 0.15, 0));
  root.add(helpers.pen(0.45, 1.14, 0.05, 0.3));
  root.add(helpers.cushion(0, 0.7, 3.0, 0x4a3a60));
  root.add(helpers.bowl(3.2, 1.1, -1.5));
  root.add(helpers.nameTag(-1.0, 1.12, 0.5));
  helpers.pushEx(
    exhibits,
    "向かいの二つのカップ",
    "Two cups across",
    0,
    1.15,
    0,
    "話し合いが続いている机",
    "A table mid-conversation"
  );
}

// ─── 8 金庫：鍵箱の上面に静かな小物（怖くしない） ───────
function fillHouse8({ root, animatables, exhibits, helpers }) {
  // 建築の鍵箱 top ≈ 0.85+0.75 → 約1.6? box height 1.5 center 0.85 → top 1.6
  // 実測: BoxGeometry 1.5 high at y=0.85 → top = 0.85+0.75 = 1.6
  const chestTop = 1.62;
  root.add(helpers.candle(-0.5, chestTop, -2.4, animatables));
  root.add(helpers.openNotebook(0.35, chestTop, -2.35, 0.2));
  root.add(helpers.pen(0.75, chestTop + 0.02, -2.2, -0.2));
  root.add(helpers.keys(0.9, chestTop, -2.55));
  root.add(helpers.glasses(-0.9, chestTop, -2.2));
  helpers.pushEx(
    exhibits,
    "金庫の上の静けさ",
    "Quiet top of the chest",
    0,
    1.7,
    -2.3,
    "深い場所でも、手元は穏やかな手仕事",
    "Even deep inside, gentle work at hand"
  );
}

// ─── 9 天文台：研究机を足して載せる ──────────────────────
function fillHouse9({ root, arch, animatables, exhibits, helpers }) {
  const topY = 1.05;
  root.add(helpers.sideTable(-2.3, topY, 2.4, { w: 1.1, d: 0.65 }));
  root.add(helpers.openNotebook(-2.4, topY, 2.45, -0.25));
  root.add(helpers.pen(-2.0, topY + 0.02, 2.25, 0.6));
  root.add(helpers.coffeeCup(-2.7, topY, 2.55, 1));
  root.add(helpers.glasses(-2.05, topY, 2.55));
  root.add(helpers.sideTable(2.5, 1.05, 2.0, { w: 0.55, d: 0.5 }));
  root.add(helpers.deskLamp(2.5, 1.05, 2.0, animatables));
  root.add(helpers.booksOnShelf(arch.w / 2 - 0.6, 1.5, -2, 5));
  helpers.pushEx(
    exhibits,
    "開いた研究ノート",
    "Open research notes",
    -2.3,
    1.15,
    2.4,
    "机の上の思考 — 遠くを見る前の手元",
    "Thoughts on the desk before looking far"
  );
}

// ─── 10 塔：細長い台の上 ─────────────────────────────────
function fillHouse10({ root, exhibits, helpers }) {
  const topY = 1.0;
  root.add(helpers.sideTable(0.3, topY, 1.4, { w: 1.2, d: 0.55 }));
  root.add(helpers.openNotebook(0.4, topY, 1.45, 0.15));
  root.add(helpers.pen(0.85, topY + 0.02, 1.25, 0.4));
  root.add(helpers.wineGlass(-0.15, topY, 1.3));
  root.add(helpers.photoFrame(0.9, topY, 1.15));
  root.add(helpers.plant(-2.0, 0, -1.0, 0.4));
  root.add(helpers.bag(2.2, 0, 2.0));
  helpers.pushEx(
    exhibits,
    "発表後のテーブル",
    "Table after the speech",
    0.3,
    1.1,
    1.4,
    "台の上に残るメモとグラス",
    "Notes and glass left on the table"
  );
}

// ─── 11 サロン：低いラウンドテーブル風 ───────────────────
function fillHouse11({ root, exhibits, helpers }) {
  // 中央に受け面（大きめサイドテーブル）
  const topY = 0.72;
  root.add(helpers.sideTable(0, topY, 0.2, { w: 1.6, d: 1.2 }));
  root.add(helpers.coffeeCup(-0.45, topY, 0.35, 1));
  root.add(helpers.coffeeCup(0.5, topY, 0.15, 1));
  root.add(helpers.coffeeCup(0.1, topY, -0.35, 1));
  root.add(helpers.bowl(0, topY, 0.05));
  root.add(helpers.nameTag(-0.55, topY, 0.5));
  root.add(helpers.nameTag(0.55, topY, -0.2));
  root.add(helpers.envelope(0.35, topY, 0.45));
  // 周辺の床は植物のみ
  root.add(helpers.plant(3.5, 0, 2.5, 0.45));
  root.add(helpers.plant(-3.5, 0, -2.0, 0.4));
  helpers.pushEx(
    exhibits,
    "集まったあとのテーブル",
    "Table after gathering",
    0,
    0.85,
    0.2,
    "テーブルの上のカップと名札",
    "Cups and name tags on the table"
  );
}

// ─── 12 休息：ナイトスタンドの上 ─────────────────────────
function fillHouse12({ root, arch, animatables, exhibits, helpers }) {
  const bedZ = -arch.d / 2 + 3.5;
  root.add(helpers.slippers(-1.5, 0.05, bedZ + 0.6));
  // ベッド脇ナイトスタンド（受け面の上にだけ小物）
  const topY = 0.78;
  root.add(helpers.nightstand(-2.0, topY, bedZ));
  root.add(helpers.coffeeCup(-2.05, topY, bedZ + 0.05, 1));
  root.add(helpers.openNotebook(-1.9, topY, bedZ - 0.08, 0.25));
  root.add(helpers.nightstand(1.6, topY, bedZ));
  root.add(helpers.candle(1.6, topY, bedZ, animatables));
  root.add(helpers.plant(2.5, 0, 0, 0.5));
  root.add(helpers.cushion(-2.5, 0.6, bedZ, 0x3a3a58));
  helpers.pushEx(
    exhibits,
    "ベッド脇のナイトスタンド",
    "Bedside table",
    -2.0,
    0.85,
    bedZ,
    "台の上のお茶とノート — 今日を終えたあと",
    "Tea and notebook on the stand — after the day softens"
  );
}
