/**
 * ミュージアム案内用シネマティックカメラ
 * キーフレーム間をスムーズに補間する
 */
export function createCinematicPlayer(camera, THREE) {
  let queue = null;
  let shotIndex = 0;
  let t = 0;
  let fromPos = new THREE.Vector3();
  let toPos = new THREE.Vector3();
  let fromLook = new THREE.Vector3();
  let toLook = new THREE.Vector3();
  let duration = 1;
  let onShot = null;
  let onDone = null;
  let lookCurrent = new THREE.Vector3();

  function isPlaying() {
    return !!queue;
  }

  function play(shots, handlers) {
    handlers = handlers || {};
    if (!shots || !shots.length) {
      handlers.onDone && handlers.onDone();
      return;
    }
    queue = shots.slice();
    shotIndex = 0;
    onShot = handlers.onShot || null;
    onDone = handlers.onDone || null;
    beginShot(0, true);
  }

  function beginShot(i, instant) {
    if (!queue || i >= queue.length) {
      const done = onDone;
      queue = null;
      done && done();
      return;
    }
    shotIndex = i;
    const shot = queue[i];
    duration = Math.max(0.4, shot.duration || 2.2);
    t = 0;

    fromPos.copy(camera.position);
    toPos.set(shot.position.x, shot.position.y, shot.position.z);
    // 現在の注視点の推定
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    fromLook.copy(camera.position).addScaledVector(dir, 8);
    toLook.set(shot.lookAt.x, shot.lookAt.y, shot.lookAt.z);

    if (instant && i === 0) {
      // 最初のショットは少し補間（ abrupt すぎない）
      fromPos.lerp(toPos, 0.15);
    }

    onShot && onShot(shot, i, queue.length);
  }

  function easeInOut(x) {
    return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
  }

  function update(dt) {
    if (!queue) return false;
    t += dt;
    const u = Math.min(1, t / duration);
    const e = easeInOut(u);
    camera.position.lerpVectors(fromPos, toPos, e);
    lookCurrent.lerpVectors(fromLook, toLook, e);
    camera.lookAt(lookCurrent);

    if (u >= 1) {
      beginShot(shotIndex + 1, false);
    }
    return true;
  }

  /** 現在のショットを飛ばして次へ。全部終わったら true */
  function skipShot() {
    if (!queue) return true;
    beginShot(shotIndex + 1, false);
    return !queue;
  }

  function skipAll() {
    if (!queue) return;
    const done = onDone;
    queue = null;
    done && done();
  }

  function stop() {
    queue = null;
    onShot = null;
    onDone = null;
  }

  return {
    play,
    update,
    skipShot,
    skipAll,
    stop,
    isPlaying,
  };
}
