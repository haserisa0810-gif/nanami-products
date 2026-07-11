/**
 * Three.js シーン基盤
 */
/** 円環を広げ、遠景→アプローチ→入口が分かる余白を確保（ミュージアム） */
export const RING_R = 72;
export const ROOM_W = 18; // 既定（各ハウスは個別スケール可）
export const ROOM_D = 22;
export const ROOM_H = 8;
export const EYE_H = 1.65;
export const WORLD_BOUND = 120;

export function createSceneContext(canvas, quality) {
  const THREE = window.THREE;
  if (!THREE) throw new Error("Three.js not loaded");

  const q = quality || "high";
  const pixelRatio = q === "low" ? 1 : Math.min(window.devicePixelRatio || 1, 2);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: q !== "low",
    alpha: false,
    powerPreference: q === "high" ? "high-performance" : "default",
  });
  renderer.setPixelRatio(pixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.shadowMap.enabled = q === "high";
  if (renderer.shadowMap.enabled) {
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07080e);
  const fog = new THREE.FogExp2(0x07080e, 0.012);
  scene.fog = fog;

  const camera = new THREE.PerspectiveCamera(
    65,
    window.innerWidth / window.innerHeight,
    0.1,
    300
  );
  camera.position.set(0, EYE_H, 8);

  const ambient = new THREE.AmbientLight(0xb8b0a0, 0.28);
  scene.add(ambient);
  const hemi = new THREE.HemisphereLight(0x8899bb, 0x1a1410, 0.45);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xffe8c8, 0.5);
  key.position.set(12, 28, 8);
  if (q === "high") {
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
  }
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x8090c0, 0.16);
  fill.position.set(-16, 10, -12);
  scene.add(fill);

  const clock = new THREE.Clock();

  function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }
  window.addEventListener("resize", onResize);

  return {
    THREE,
    renderer,
    scene,
    camera,
    fog,
    ambient,
    hemi,
    key,
    clock,
    quality: q,
    dispose() {
      window.removeEventListener("resize", onResize);
      renderer.dispose();
    },
  };
}

export function houseAngle(n) {
  return ((n - 1) * 30 - 90) * (Math.PI / 180);
}

export function housePosition(n, THREE) {
  const a = houseAngle(n);
  return new THREE.Vector3(Math.cos(a) * RING_R, 0, Math.sin(a) * RING_R);
}

export function buildCourtyard(ctx, chartName) {
  const { THREE, scene, quality } = ctx;

  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(RING_R + 22, quality === "low" ? 32 : 72),
    new THREE.MeshStandardMaterial({ color: 0x14161f, roughness: 0.92, metalness: 0.05 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const ring = new THREE.Mesh(
    new THREE.RingGeometry(RING_R - 0.35, RING_R + 0.15, 64),
    new THREE.MeshBasicMaterial({
      color: 0xc9a96e,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
    })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.02;
  scene.add(ring);

  const inner = new THREE.Mesh(
    new THREE.RingGeometry(6.5, 6.7, 48),
    new THREE.MeshBasicMaterial({
      color: 0xc9a96e,
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
    })
  );
  inner.rotation.x = -Math.PI / 2;
  inner.position.y = 0.025;
  scene.add(inner);

  const ped = new THREE.Mesh(
    new THREE.CylinderGeometry(1.6, 2.0, 0.35, 24),
    new THREE.MeshStandardMaterial({ color: 0x2a2430, roughness: 0.55, metalness: 0.25 })
  );
  ped.position.y = 0.18;
  ped.castShadow = true;
  scene.add(ped);

  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.85, 1),
    new THREE.MeshStandardMaterial({
      color: 0xe8d5b0,
      emissive: 0xc9a96e,
      emissiveIntensity: 0.45,
      roughness: 0.25,
      metalness: 0.55,
      transparent: true,
      opacity: 0.92,
    })
  );
  core.position.y = 1.35;
  core.name = "natalCore";
  core.userData = { pickable: "core" };
  scene.add(core);

  // 12 方向の床ガイド線
  for (let n = 1; n <= 12; n++) {
    const cuspA = houseAngle(n) - (15 * Math.PI) / 180;
    const pts = [
      new THREE.Vector3(Math.cos(cuspA) * 7, 0.03, Math.sin(cuspA) * 7),
      new THREE.Vector3(Math.cos(cuspA) * (RING_R - 1), 0.03, Math.sin(cuspA) * (RING_R - 1)),
    ];
    scene.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: 0xc9a96e, transparent: true, opacity: 0.12 })
      )
    );
  }

  // 星
  const count = quality === "low" ? 350 : 900;
  const pos = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const r = 80 + Math.random() * 100;
    const theta = Math.random() * Math.PI * 2;
    let phi = Math.acos(2 * Math.random() - 1);
    phi = Math.abs(phi - Math.PI / 2) * 0.7 + 0.15;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = Math.abs(r * Math.cos(phi)) + 8;
    pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
  }
  const stars = new THREE.Points(
    new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
    new THREE.PointsMaterial({
      color: 0xe8e4d6,
      size: 0.35,
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
    })
  );
  scene.add(stars);

  // 外周壁
  const wall = new THREE.Mesh(
    new THREE.CylinderGeometry(RING_R + 28, RING_R + 28, 2.2, 48, 1, true),
    new THREE.MeshStandardMaterial({ color: 0x0c0e16, roughness: 1, side: THREE.BackSide })
  );
  wall.position.y = 1.1;
  scene.add(wall);

  return { core, chartName };
}

export function hexColor(THREE, hex) {
  return new THREE.Color(hex);
}
