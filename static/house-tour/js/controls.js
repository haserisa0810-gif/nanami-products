/**
 * PC / モバイル操作
 * 自由歩行は Google マップ風:
 *  - ドラッグ … 見回す
 *  - クリック … その地点へゆっくり近づく
 *  - ホイール … 向いている方向へ前後
 *  - WASD も併用可（任意）
 */
import { EYE_H, WORLD_BOUND, housePosition, RING_R } from "./scene.js";

export function createControls(ctx, options) {
  const { camera, THREE, scene } = ctx;
  const canvas = ctx.renderer.domElement;
  const onHouseAuto = options.onHouseAuto || function () {};
  const onPick = options.onPick || function () {};
  const onClickMove = options.onClickMove || function () {};

  let mode = "walk"; // walk | orbit | cinematic
  let pointerLocked = false;
  const keys = {};
  let moveF = false,
    moveB = false,
    moveL = false,
    moveR = false;
  const velocity = new THREE.Vector3();
  const euler = new THREE.Euler(0, 0, 0, "YXZ");

  const orbitTarget = new THREE.Vector3(0, 1.2, 0);
  const orbit = { theta: 0.35, phi: 0.95, radius: 48 };
  let orbitDragging = false;
  let orbitLast = { x: 0, y: 0 };

  // walk: Google Maps 風ドラッグ視点
  let walkDrag = {
    active: false,
    id: null,
    x: 0,
    y: 0,
    moved: false,
    button: 0,
  };

  // クリック移動の目標
  let walkTarget = null; // THREE.Vector3 | null
  const walkTargetSpeed = 5.5;

  // クリック地点マーカー
  const markerGeo = new THREE.RingGeometry(0.35, 0.55, 24);
  const markerMat = new THREE.MeshBasicMaterial({
    color: 0xc9a96e,
    transparent: true,
    opacity: 0.85,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const moveMarker = new THREE.Mesh(markerGeo, markerMat);
  moveMarker.rotation.x = -Math.PI / 2;
  moveMarker.position.y = 0.08;
  moveMarker.visible = false;
  if (scene) scene.add(moveMarker);

  // mobile virtual stick
  const stick = {
    active: false,
    dx: 0,
    dy: 0,
    id: null,
  };
  let lookTouch = { active: false, id: null, lx: 0, ly: 0 };

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  let pickables = [];
  let lastClickTime = 0;

  function setPickables(list) {
    pickables = list || [];
  }

  function clamp(v, a, b) {
    return Math.max(a, Math.min(b, v));
  }

  function setMode(m) {
    mode = m;
    if (mode !== "walk" && document.pointerLockElement) {
      document.exitPointerLock();
    }
    if (mode !== "walk") {
      walkTarget = null;
      moveMarker.visible = false;
    }
    // カーソル
    if (mode === "walk") canvas.style.cursor = "grab";
    else if (mode === "orbit") canvas.style.cursor = "grab";
    else canvas.style.cursor = "default";
    options.onModeChange && options.onModeChange(mode);
  }

  function syncEulerFromCamera() {
    euler.setFromQuaternion(camera.quaternion, "YXZ");
  }

  function setPose(pos, lookAt) {
    camera.position.set(pos.x, pos.y, pos.z);
    camera.lookAt(lookAt.x, lookAt.y, lookAt.z);
    euler.setFromQuaternion(camera.quaternion, "YXZ");
    walkTarget = null;
    moveMarker.visible = false;
  }

  function getMode() {
    return mode;
  }

  function onKeyDown(e) {
    keys[e.code] = true;
    if (e.code === "KeyW" || e.code === "ArrowUp") moveF = true;
    if (e.code === "KeyS" || e.code === "ArrowDown") moveB = true;
    if (e.code === "KeyA" || e.code === "ArrowLeft") moveL = true;
    if (e.code === "KeyD" || e.code === "ArrowRight") moveR = true;
    if (e.code === "KeyM") options.onToggleMap && options.onToggleMap();
    if (e.code === "Escape") options.onMenu && options.onMenu();
    if (e.code === "KeyN") options.onNext && options.onNext();
    if (e.code === "KeyP") options.onPrev && options.onPrev();
    if (e.code === "KeyC") options.onCore && options.onCore();
    if (e.code === "Digit1") options.onJump && options.onJump(1);
    if (e.code === "Digit2") options.onJump && options.onJump(2);
    if (e.code === "Digit3") options.onJump && options.onJump(3);
    if (e.code === "Digit4") options.onJump && options.onJump(4);
    if (e.code === "Digit5") options.onJump && options.onJump(5);
    if (e.code === "Digit6") options.onJump && options.onJump(6);
    if (e.code === "Digit7") options.onJump && options.onJump(7);
    if (e.code === "Digit8") options.onJump && options.onJump(8);
    if (e.code === "Digit9") options.onJump && options.onJump(9);
    if (e.code === "Digit0") options.onJump && options.onJump(10);
    if (e.code === "Minus") options.onJump && options.onJump(11);
    if (e.code === "Equal") options.onJump && options.onJump(12);
  }
  function onKeyUp(e) {
    keys[e.code] = false;
    if (e.code === "KeyW" || e.code === "ArrowUp") moveF = false;
    if (e.code === "KeyS" || e.code === "ArrowDown") moveB = false;
    if (e.code === "KeyA" || e.code === "ArrowLeft") moveL = false;
    if (e.code === "KeyD" || e.code === "ArrowRight") moveR = false;
  }
  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("keyup", onKeyUp);

  // ポイントロックは任意（使わなくてもOK）。クリック移動と両立
  document.addEventListener("pointerlockchange", () => {
    pointerLocked = document.pointerLockElement === canvas;
    options.onPointerLock && options.onPointerLock(pointerLocked);
  });

  document.addEventListener("mousemove", (e) => {
    if (!pointerLocked || mode !== "walk") return;
    applyLookDelta(e.movementX || 0, e.movementY || 0, 0.0022);
  });

  function applyLookDelta(dx, dy, sens) {
    euler.y -= dx * sens;
    euler.x -= dy * sens;
    euler.x = clamp(euler.x, -Math.PI / 2.4, Math.PI / 2.4);
    camera.quaternion.setFromEuler(euler);
  }

  function setPointerFromEvent(e) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  }

  /** 床（y=0）との交点。無ければ視線前方の水平点 */
  function groundHitFromEvent(e) {
    setPointerFromEvent(e);
    raycaster.setFromCamera(pointer, camera);
    const hit = new THREE.Vector3();
    const ok = raycaster.ray.intersectPlane(groundPlane, hit);
    if (ok && Number.isFinite(hit.x)) {
      return hit;
    }
    // 床と交わらない（空を向いている）→ 視線水平前方へ一定距離
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    dir.y = 0;
    if (dir.lengthSq() < 1e-6) dir.set(0, 0, -1);
    dir.normalize();
    return camera.position.clone().addScaledVector(dir, 10);
  }

  function tryPickPlanet(e) {
    if (!pickables.length) return false;
    setPointerFromEvent(e);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(pickables, true);
    if (!hits.length) return false;
    let obj = hits[0].object;
    while (obj && !(obj.userData && obj.userData.pickable) && obj.parent) obj = obj.parent;
    if (obj && obj.userData && obj.userData.pickable === "planet") {
      onPick(obj.userData);
      return true;
    }
    return false;
  }

  function setWalkTarget(point, isDouble) {
    const target = point.clone();
    target.y = EYE_H;
    // 遠すぎるクリックは少し手前までに制限
    const cam = camera.position;
    const dx = target.x - cam.x;
    const dz = target.z - cam.z;
    let dist = Math.hypot(dx, dz);
    const maxStep = isDouble ? 28 : 18;
    if (dist > maxStep && dist > 0.01) {
      const s = maxStep / dist;
      target.x = cam.x + dx * s;
      target.z = cam.z + dz * s;
    }
    // ワールド境界
    const r = Math.hypot(target.x, target.z);
    if (r > WORLD_BOUND - 1) {
      target.x *= (WORLD_BOUND - 1) / r;
      target.z *= (WORLD_BOUND - 1) / r;
    }
    walkTarget = target;
    moveMarker.position.set(target.x, 0.08, target.z);
    moveMarker.visible = true;
    moveMarker.scale.setScalar(isDouble ? 1.35 : 1);
    onClickMove(target, isDouble);
  }

  canvas.addEventListener("pointerdown", (e) => {
    if (mode === "cinematic") return;

    if (mode === "orbit") {
      orbitDragging = true;
      orbitLast = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
      canvas.style.cursor = "grabbing";
      return;
    }

    if (mode !== "walk") return;

    // モバイル: 左=スティック / 右=見回す / 中央タップ=その地点へ近づく
    if (isMobile()) {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const w = rect.width;
      if (x < w * 0.32) {
        stick.active = true;
        stick.id = e.pointerId;
        stick.ox = e.clientX;
        stick.oy = e.clientY;
        stick.dx = 0;
        stick.dy = 0;
        options.onStickStart && options.onStickStart(e.clientX, e.clientY);
      } else if (x > w * 0.68) {
        lookTouch.active = true;
        lookTouch.id = e.pointerId;
        lookTouch.lx = e.clientX;
        lookTouch.ly = e.clientY;
      } else {
        // 中央帯: タップで移動 / 少し動かすと見回し
        walkDrag.active = true;
        walkDrag.id = e.pointerId;
        walkDrag.x = e.clientX;
        walkDrag.y = e.clientY;
        walkDrag.moved = false;
        walkDrag.button = 0;
        canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
      }
      return;
    }

    // PC: 左ドラッグ = 見回す、クリック = 移動
    if (e.button === 0 || e.button === 2) {
      walkDrag.active = true;
      walkDrag.id = e.pointerId;
      walkDrag.x = e.clientX;
      walkDrag.y = e.clientY;
      walkDrag.moved = false;
      walkDrag.button = e.button;
      canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
      canvas.style.cursor = "grabbing";
    }
  });

  canvas.addEventListener("pointermove", (e) => {
    if (mode === "orbit" && orbitDragging) {
      const dx = e.clientX - orbitLast.x;
      const dy = e.clientY - orbitLast.y;
      orbitLast = { x: e.clientX, y: e.clientY };
      orbit.theta -= dx * 0.005;
      orbit.phi = clamp(orbit.phi - dy * 0.005, 0.25, 1.45);
      return;
    }

    if (stick.active && e.pointerId === stick.id) {
      stick.dx = clamp((e.clientX - stick.ox) / 48, -1, 1);
      stick.dy = clamp((e.clientY - stick.oy) / 48, -1, 1);
      options.onStickMove && options.onStickMove(stick.dx, stick.dy);
    }
    if (lookTouch.active && e.pointerId === lookTouch.id && mode === "walk") {
      const dx = e.clientX - lookTouch.lx;
      const dy = e.clientY - lookTouch.ly;
      lookTouch.lx = e.clientX;
      lookTouch.ly = e.clientY;
      applyLookDelta(dx, dy, 0.005);
    }

    if (mode === "walk" && walkDrag.active && e.pointerId === walkDrag.id) {
      const dx = e.clientX - walkDrag.x;
      const dy = e.clientY - walkDrag.y;
      if (Math.hypot(dx, dy) > 4) walkDrag.moved = true;
      if (walkDrag.moved) {
        applyLookDelta(dx, dy, 0.0045);
        walkDrag.x = e.clientX;
        walkDrag.y = e.clientY;
      }
    }
  });

  function endPointer(e) {
    if (orbitDragging) {
      orbitDragging = false;
      if (mode === "orbit") canvas.style.cursor = "grab";
    }
    if (stick.active && e.pointerId === stick.id) {
      stick.active = false;
      stick.dx = 0;
      stick.dy = 0;
      options.onStickEnd && options.onStickEnd();
    }
    if (lookTouch.active && e.pointerId === lookTouch.id) {
      lookTouch.active = false;
    }

    if (mode === "walk" && walkDrag.active && e.pointerId === walkDrag.id) {
      const wasDrag = walkDrag.moved;
      const btn = walkDrag.button;
      walkDrag.active = false;
      canvas.style.cursor = "grab";

      // ドラッグでなければクリック = 移動 or 天体選択
      if (!wasDrag && (btn === 0 || isMobile())) {
        if (tryPickPlanet(e)) {
          // 天体優先
        } else {
          const now = performance.now();
          const isDouble = now - lastClickTime < 320;
          lastClickTime = now;
          const hit = groundHitFromEvent(e);
          setWalkTarget(hit, isDouble);
        }
      }
    }
  }
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);

  // 右クリックメニュー抑制（ドラッグ視点用）
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  canvas.addEventListener(
    "wheel",
    (e) => {
      if (mode === "cinematic") return;
      e.preventDefault();
      if (mode === "orbit") {
        orbit.radius = clamp(orbit.radius + e.deltaY * 0.04, 18, 110);
        return;
      }
      if (mode === "walk") {
        // 向いている方向へ前後（マップのズーム感）
        const dir = new THREE.Vector3();
        camera.getWorldDirection(dir);
        dir.y = 0;
        if (dir.lengthSq() < 1e-6) return;
        dir.normalize();
        const step = clamp(e.deltaY * 0.02, -4, 4);
        // ホイール下 = 近づく（前）、上 = 下がる（後）— ブラウザ慣例に合わせ deltaY>0 で後ろ寄りに感じる人もいるので反転
        camera.position.addScaledVector(dir, -step);
        camera.position.y = EYE_H;
        clampWorld();
        walkTarget = null;
        moveMarker.visible = false;
      }
    },
    { passive: false }
  );

  // 旧 click ハンドラは pointerup に統合（二重発火防止）
  // ダブルクリック明示
  canvas.addEventListener("dblclick", (e) => {
    if (mode !== "walk") return;
    e.preventDefault();
    if (tryPickPlanet(e)) return;
    const hit = groundHitFromEvent(e);
    setWalkTarget(hit, true);
  });

  let entryPoints = {};

  function setEntryPoints(map) {
    entryPoints = map || {};
  }

  function detectHouse() {
    const p = camera.position;
    let best = 0;
    let bestDist = RING_R * 0.42;
    for (let n = 1; n <= 12; n++) {
      const hp = housePosition(n, THREE);
      const d = Math.hypot(p.x - hp.x, p.z - hp.z);
      if (d < bestDist) {
        bestDist = d;
        best = n;
      }
    }
    if (Math.hypot(p.x, p.z) < 14) best = 0;
    return best;
  }

  function clampWorld() {
    const r = Math.hypot(camera.position.x, camera.position.z);
    if (r > WORLD_BOUND) {
      camera.position.x *= WORLD_BOUND / r;
      camera.position.z *= WORLD_BOUND / r;
    }
  }

  function teleport(num) {
    walkTarget = null;
    moveMarker.visible = false;
    if (num === 0) {
      camera.position.set(0, EYE_H, 8);
      euler.set(0, 0, 0);
      camera.quaternion.setFromEuler(euler);
      orbitTarget.set(0, 1.2, 0);
      orbit.radius = 72;
      return;
    }
    const pos = housePosition(num, THREE);
    const dir = pos.clone().normalize();
    if (entryPoints[num]) {
      camera.position.set(entryPoints[num].x, entryPoints[num].y || EYE_H, entryPoints[num].z);
    } else {
      const stand = pos.clone().addScaledVector(dir, -4);
      stand.y = EYE_H;
      camera.position.copy(stand);
    }
    const look = pos.clone();
    look.y = EYE_H + 0.4;
    camera.lookAt(look);
    euler.setFromQuaternion(camera.quaternion, "YXZ");
    orbitTarget.copy(pos);
    orbitTarget.y = 4;
    orbit.radius = 28;
    orbit.theta = Math.atan2(pos.x, pos.z) + Math.PI;
  }

  function updateOrbit() {
    const { phi, theta, radius } = orbit;
    camera.position.x = orbitTarget.x + radius * Math.sin(phi) * Math.sin(theta);
    camera.position.y = orbitTarget.y + radius * Math.cos(phi);
    camera.position.z = orbitTarget.z + radius * Math.sin(phi) * Math.cos(theta);
    camera.lookAt(orbitTarget);
  }

  let lastHouse = 0;
  function updateWalk(dt) {
    // クリック移動（目標へスムーズに）
    if (walkTarget) {
      const dx = walkTarget.x - camera.position.x;
      const dz = walkTarget.z - camera.position.z;
      const dist = Math.hypot(dx, dz);
      if (dist < 0.25) {
        walkTarget = null;
        moveMarker.visible = false;
      } else {
        const step = Math.min(dist, walkTargetSpeed * dt);
        camera.position.x += (dx / dist) * step;
        camera.position.z += (dz / dist) * step;
        camera.position.y = EYE_H;
        // マーカー点滅
        moveMarker.material.opacity = 0.45 + 0.4 * Math.sin(performance.now() * 0.008);
      }
    }

    velocity.x -= velocity.x * 8 * dt;
    velocity.z -= velocity.z * 8 * dt;

    let fz = Number(moveF) - Number(moveB);
    let fx = Number(moveR) - Number(moveL);
    if (stick.active) {
      fz += -stick.dy;
      fx += stick.dx;
    }
    const len = Math.hypot(fx, fz);
    if (len > 1) {
      fx /= len;
      fz /= len;
    }

    const speed = 4.2;
    if (fz !== 0 || fx !== 0) {
      // キーボード移動中はクリック目標をキャンセル
      if (walkTarget && (Math.abs(fz) > 0.1 || Math.abs(fx) > 0.1)) {
        walkTarget = null;
        moveMarker.visible = false;
      }
      if (fz !== 0) velocity.z -= fz * speed * dt * 12;
      if (fx !== 0) velocity.x -= fx * speed * dt * 12;
    }

    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();
    const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
    camera.position.addScaledVector(forward, -velocity.z * dt);
    camera.position.addScaledVector(right, -velocity.x * dt);
    camera.position.y = EYE_H;
    clampWorld();

    const h = detectHouse();
    if (h !== lastHouse) {
      lastHouse = h;
      onHouseAuto(h);
    }
  }

  function update(dt, started) {
    if (!started) {
      const t = performance.now() * 0.00008;
      camera.position.x = Math.sin(t) * 55;
      camera.position.z = Math.cos(t) * 55;
      camera.position.y = 22;
      camera.lookAt(0, 2, 0);
      return;
    }
    if (mode === "cinematic") return;
    if (mode === "walk") updateWalk(dt);
    else updateOrbit();
  }

  function isMobile() {
    return window.matchMedia("(max-width: 720px), (pointer: coarse)").matches;
  }

  function syncLastHouse(n) {
    lastHouse = n;
  }

  return {
    setMode,
    getMode,
    teleport,
    update,
    setPickables,
    setEntryPoints,
    setPose,
    syncEulerFromCamera,
    isMobile,
    syncLastHouse,
    dispose() {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keyup", onKeyUp);
      if (moveMarker.parent) moveMarker.parent.remove(moveMarker);
    },
  };
}
