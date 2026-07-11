/**
 * 博物館品質向けの簡易手続きテクスチャ / 素材
 * 外部アセットなし（Canvas 生成）。後で glTF 差し替え可能。
 */
export function createMaterialKit(THREE) {
  const woodMap = canvasTexture(256, (ctx, w, h) => {
    ctx.fillStyle = "#5c4030";
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 40; i++) {
      const y = (i / 40) * h + Math.sin(i * 1.7) * 3;
      ctx.strokeStyle = i % 3 === 0 ? "rgba(30,18,10,0.35)" : "rgba(90,60,40,0.25)";
      ctx.lineWidth = 1 + (i % 3);
      ctx.beginPath();
      ctx.moveTo(0, y);
      for (let x = 0; x < w; x += 8) {
        ctx.lineTo(x, y + Math.sin(x * 0.04 + i) * 2);
      }
      ctx.stroke();
    }
  }, THREE);

  const stoneMap = canvasTexture(256, (ctx, w, h) => {
    ctx.fillStyle = "#8a8680";
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 80; i++) {
      ctx.fillStyle = `rgba(${120 + (i % 40)},${118 + (i % 30)},${110 + (i % 25)},0.35)`;
      ctx.fillRect((i * 37) % w, (i * 53) % h, 12 + (i % 20), 8 + (i % 14));
    }
    for (let y = 0; y < h; y += 28) {
      ctx.strokeStyle = "rgba(40,40,40,0.25)";
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
      for (let x = (y / 28) % 2 === 0 ? 0 : 30; x < w; x += 60) {
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, y + 28);
        ctx.stroke();
      }
    }
  }, THREE);

  const plasterMap = canvasTexture(128, (ctx, w, h) => {
    ctx.fillStyle = "#e8e2d6";
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 200; i++) {
      ctx.fillStyle = `rgba(200,190,175,${0.1 + (i % 5) * 0.05})`;
      ctx.fillRect((i * 17) % w, (i * 29) % h, 2, 2);
    }
  }, THREE);

  const fabricMap = canvasTexture(128, (ctx, w, h) => {
    ctx.fillStyle = "#6a2030";
    ctx.fillRect(0, 0, w, h);
    for (let y = 0; y < h; y += 4) {
      ctx.fillStyle = y % 8 === 0 ? "rgba(0,0,0,0.12)" : "rgba(255,255,255,0.04)";
      ctx.fillRect(0, y, w, 2);
    }
  }, THREE);

  const brass = new THREE.MeshStandardMaterial({
    color: 0xb08d57,
    metalness: 0.85,
    roughness: 0.35,
    envMapIntensity: 1,
  });

  return {
    woodFloor: new THREE.MeshStandardMaterial({
      map: woodMap,
      color: 0xffffff,
      roughness: 0.65,
      metalness: 0.05,
    }),
    woodPanel: new THREE.MeshStandardMaterial({
      map: woodMap,
      color: 0xddd0c0,
      roughness: 0.55,
      metalness: 0.08,
    }),
    stone: new THREE.MeshStandardMaterial({
      map: stoneMap,
      color: 0xffffff,
      roughness: 0.9,
      metalness: 0.02,
    }),
    plaster: new THREE.MeshStandardMaterial({
      map: plasterMap,
      color: 0xffffff,
      roughness: 0.85,
      metalness: 0,
    }),
    fabric: new THREE.MeshStandardMaterial({
      map: fabricMap,
      color: 0xffffff,
      roughness: 0.95,
      metalness: 0,
    }),
    brass,
    // r128 互換: transmission 依存を避け、半透明ガラスに
    glass: new THREE.MeshStandardMaterial({
      color: 0xa8c8e8,
      metalness: 0.1,
      roughness: 0.08,
      transparent: true,
      opacity: 0.45,
    }),
    darkMetal: new THREE.MeshStandardMaterial({
      color: 0x2a2a30,
      metalness: 0.7,
      roughness: 0.4,
    }),
    stageBlack: new THREE.MeshStandardMaterial({
      color: 0x121018,
      roughness: 0.95,
      metalness: 0,
    }),
    parchment: new THREE.MeshStandardMaterial({
      color: 0xe8dcc0,
      roughness: 0.9,
      metalness: 0,
    }),
  };
}

function canvasTexture(size, draw, THREE) {
  const c = document.createElement("canvas");
  c.width = size;
  c.height = size;
  const ctx = c.getContext("2d");
  draw(ctx, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  if (tex.encoding !== undefined) tex.encoding = THREE.sRGBEncoding;
  return tex;
}

export function stdMat(THREE, color, opts) {
  opts = opts || {};
  return new THREE.MeshStandardMaterial({
    color: color,
    roughness: opts.roughness != null ? opts.roughness : 0.7,
    metalness: opts.metalness != null ? opts.metalness : 0.05,
    emissive: opts.emissive || 0x000000,
    emissiveIntensity: opts.emissiveIntensity || 0,
    map: opts.map || null,
    transparent: !!opts.transparent,
    opacity: opts.opacity != null ? opts.opacity : 1,
    side: opts.side || THREE.FrontSide,
  });
}
