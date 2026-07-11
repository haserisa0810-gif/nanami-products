/**
 * House Tour — entry point
 * 固定サンプル or YAML貼り付けの出生図を3D空間で歩く
 */
import { sampleChart, bodiesFromChart } from "./data/sample-chart.js";
import { nekoChart } from "./data/neko-chart.js";
import { parseNatalYaml } from "./parse-yaml.js";
import { createSceneContext, buildCourtyard } from "./scene.js";
import { buildAllHouses, animateSymbolics, applyAtmosphere } from "./house-builder.js";
import {
  buildPlanets,
  clearPlanets,
  animatePlanets,
  planetDetail,
} from "./planet-builder.js";
import { createControls } from "./controls.js";
import { createTourController } from "./tour-controller.js";
import { createCinematicPlayer } from "./cinematic.js";
import { buildShotsForHouse } from "./museum-shots.js";
import { createUI } from "./ui.js";
import {
  initLang,
  getLang,
  setLang,
  onLangChange,
  t,
  getHousesData,
  getPlanetTexts,
  applyDomI18n,
} from "./i18n.js";

(function boot() {
  if (typeof THREE === "undefined") {
    console.error("[HouseTour] Three.js missing");
    return;
  }

  initLang();
  applyDomI18n(document);

  let housesData = getHousesData();
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let quality = localStorage.getItem("ht-quality") || (isProbablyMobile() ? "low" : "high");
  let soundOn = false;
  let audioCtx = null;
  let masterGain = null;
  let oscNodes = [];
  let started = false;
  let mapOpen = false;

  // 現在のチャート状態（サンプル or YAML）
  let chart = sampleChart;
  let bodies = [];
  let bodiesByHouse = emptyBodiesByHouse();
  let planetMeshes = [];
  let pickables = [];

  const ui = createUI(document);
  ui.setQualityLabel(quality);
  ui.setSoundLabel(false);

  let ctx;
  try {
    ctx = createSceneContext(document.getElementById("ht-canvas"), quality);
  } catch (e) {
    ui.showError("3Dの初期化に失敗しました。<br><small>" + e.message + "</small>");
    return;
  }

  buildCourtyard(ctx, chart.name);
  const { houseGroups, animatables, entryWorld } = buildAllHouses(ctx, housesData);
  const cine = createCinematicPlayer(ctx.camera, THREE);

  const tour = createTourController({
    onVisit(num, opts) {
      opts = opts || {};
      const h = housesData[num] || housesData[0];
      ui.renderHouse(num, withCuspHint(h, num), enrichBodies(bodiesByHouse[num] || []), {
        silent: opts.silentTeleport || opts.playCinematic,
      });
      ui.updateNavActive(num, housesData);
      applyAtmosphere(ctx, houseGroups, housesData, num);
      ui.hidePlanetPanel();

      if (opts.playCinematic) {
        playMuseumGuide(num);
        return;
      }

      if (!opts.silentTeleport) {
        controls.setMode(controls.getMode() === "orbit" ? "orbit" : "walk");
        controls.teleport(num);
        controls.syncLastHouse(num);
      }
      if (soundOn) retuneAudio(num);
      ui.setGuideLabel(guideLabelText());
      ui.hideCaption();
      if (!opts.silentTeleport && opts.reason !== "walk") {
        ui.toast(
          num === 0
            ? t("loc_core")
            : t("loc_house", { n: num }) + " · " + (h.spaceLabel || "")
        );
      }
    },
    onMode(m) {
      ui.setModeLabel(m === "guide" ? t("mode_guide") : t("mode_free"));
    },
    onPhase(p) {
      if (p === "playing") ui.setModeLabel(t("mode_playing"));
      if (p === "waiting") ui.setModeLabel(t("mode_waiting"));
    },
    onGuideComplete() {
      ui.hideCaption();
      ui.toast(t("toast_guide_done"), 3600);
    },
  });

  function playMuseumGuide(num) {
    tour.setPhase("playing");
    controls.setMode("cinematic");
    ui.showMobileStick(false);
    const hg = num === 0 ? null : houseGroups[num];
    const shots = buildShotsForHouse(num, hg, THREE, housesData, getLang());
    cine.play(shots, {
      onShot(shot, i, total) {
        ui.setCaption(
          shot.label,
          shot.caption,
          t("caption_guide", { i: i + 1, total: total })
        );
        ui.setGuideLabel(guideLabelText());
      },
      onDone() {
        tour.setPhase("waiting");
        controls.syncEulerFromCamera();
        if (num === 0) {
          controls.setMode("walk");
          controls.teleport(0);
        } else {
          controls.setMode("walk");
          if (entryWorld[num]) {
            controls.setPose(
              entryWorld[num],
              houseGroups[num]
                ? (() => {
                    const p = houseGroups[num].group.position;
                    return { x: p.x, y: 2.2, z: p.z };
                  })()
                : { x: 0, y: 2, z: 0 }
            );
          } else {
            controls.teleport(num);
          }
        }
        controls.syncLastHouse(num);
        ui.showMobileStick(controls.isMobile());
        const h = housesData[num] || housesData[0];
        ui.setCaption(
          h.title || t("loc_core"),
          t("caption_done_body"),
          t("caption_done")
        );
        ui.setGuideLabel(guideLabelText());
        if (soundOn) retuneAudio(num);
      },
    });
  }

  function guideLabelText() {
    if (tour.getMode() !== "guide") return "";
    if (tour.getPhase() === "playing") return t("guide_playing");
    const step = tour.getCurrent();
    if (step === 0) return t("guide_core");
    if (step >= 12) return t("guide_last");
    return t("guide_room", { n: step });
  }

  const controls = createControls(ctx, {
    onHouseAuto(n) {
      tour.onAutoEnter(n);
    },
    onClickMove() {
      // クリック移動時の軽いフィードバック（初回だけ案内してもよい）
      if (tour.getMode() !== "guide" || tour.getPhase() !== "playing") {
        /* toast はうるさいので省略。マーカー表示のみ */
      }
    },
    onPick(data) {
      if (data.pickable === "planet") {
        openPlanetDetail(data.planetId, data.house);
      }
    },
    onModeChange(m) {
      ui.setModeLabel(
        tour.getMode() === "guide"
          ? t("mode_guide")
          : m === "orbit"
            ? t("mode_orbit")
            : t("mode_walk")
      );
    },
    onPointerLock(locked) {
      if (ui.el.crosshair) ui.el.crosshair.classList.toggle("is-visible", locked);
    },
    onNext() {
      handleNext();
    },
    onPrev() {
      handlePrev();
    },
    onCore() {
      tour.setCurrent(0);
    },
    onJump(n) {
      tour.setCurrent(n);
    },
    onToggleMap() {
      mapOpen = !mapOpen;
      ui.setMapOpen(mapOpen);
    },
    onMenu() {
      if (!started) return;
      const open = ui.el.menuOverlay && ui.el.menuOverlay.hidden;
      ui.setMenuOpen(open);
    },
    onStickMove(dx, dy) {
      ui.updateStickKnob(dx, dy);
    },
    onStickEnd() {
      ui.resetStickKnob();
    },
  });
  if (controls.setEntryPoints) controls.setEntryPoints(entryWorld || {});

  // ── YAML UI ──
  const yamlInput = document.getElementById("ht-yaml-input");
  const yamlStatus = document.getElementById("ht-yaml-status");
  const btnLoadYaml = document.getElementById("ht-load-yaml");
  const btnSample = document.getElementById("ht-use-sample");
  const btnNeko = document.getElementById("ht-load-neko");

  function setYamlStatus(msg, kind) {
    if (!yamlStatus) return;
    yamlStatus.textContent = msg || "";
    yamlStatus.classList.remove("is-ok", "is-err");
    if (kind === "ok") yamlStatus.classList.add("is-ok");
    if (kind === "err") yamlStatus.classList.add("is-err");
  }

  function loadYamlText(text, opts) {
    opts = opts || {};
    const { chart: loaded, warnings, bodyCount } = parseNatalYaml(text);
    applyChart(loaded, {
      status:
        t("status_loaded", { name: loaded.name, n: bodyCount }) +
        (warnings && warnings.length
          ? t("status_warn", { n: warnings.length })
          : ""),
      statusOk: true,
    });
    if (!opts.silentToast) ui.toast(t("toast_yaml_ok", { name: loaded.name }), 2800);
    try {
      sessionStorage.setItem("ht-last-yaml", text);
      sessionStorage.setItem("ht-chart-pref", "yaml");
    } catch (e) { /* ignore */ }
    return loaded;
  }

  if (btnLoadYaml) {
    btnLoadYaml.addEventListener("click", () => {
      try {
        loadYamlText(yamlInput ? yamlInput.value : "");
      } catch (e) {
        setYamlStatus(String(e.message || e), "err");
        ui.toast(t("toast_yaml_err"), 2800);
      }
    });
  }

  if (btnNeko) {
    btnNeko.addEventListener("click", () => {
      applyChart(nekoChart, {
        status: t("status_neko_short"),
        statusOk: true,
      });
      ui.toast(t("toast_neko"), 2600);
      try {
        sessionStorage.setItem("ht-chart-pref", "neko");
      } catch (e) { /* ignore */ }
    });
  }

  if (btnSample) {
    btnSample.addEventListener("click", () => {
      if (yamlInput) yamlInput.value = "";
      applyChart(sampleChart, {
        status: t("status_sample"),
        statusOk: true,
      });
      ui.toast(t("toast_sample"), 2000);
      try {
        sessionStorage.setItem("ht-chart-pref", "sample");
      } catch (e) { /* ignore */ }
    });
  }

  // 言語切替
  document.querySelectorAll("[data-lang-set]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.getAttribute("data-lang-set");
      setLang(next);
    });
  });

  onLangChange(() => {
    housesData = getHousesData();
    applyDomI18n(document);
    ui.setQualityLabel(quality);
    ui.setSoundLabel(soundOn);
    // 天体名ラベル再生成
    bodies = bodiesFromChart(chart).map((b) => {
      const pt = getPlanetTexts()[b.id];
      return {
        ...b,
        name_ja: pt ? pt.name : b.id,
        name: pt ? pt.name : b.id,
      };
    });
    bodiesByHouse = emptyBodiesByHouse();
    bodies.forEach((b) => {
      if (b.house >= 1 && b.house <= 12) bodiesByHouse[b.house].push(b);
    });
    const cur = tour.getCurrent();
    ui.renderHouse(
      cur,
      withCuspHint(housesData[cur] || housesData[0], cur),
      enrichBodies(bodiesByHouse[cur] || []),
      { silent: true }
    );
    ui.fillProfile(chart);
    ui.setGuideLabel(guideLabelText());
    ui.setModeLabel(
      tour.getMode() === "guide"
        ? tour.getPhase() === "playing"
          ? t("mode_playing")
          : tour.getPhase() === "waiting"
            ? t("mode_waiting")
            : t("mode_guide")
        : controls.getMode() === "orbit"
          ? t("mode_orbit")
          : t("mode_free")
    );
  });

  // 初回: URL ?chart=neko / 前回YAML / ねこ編集長デフォルト寄り
  (function initialChart() {
    const params = new URLSearchParams(window.location.search || "");
    const q = (params.get("chart") || params.get("load") || "").toLowerCase();

    if (q === "neko" || q === "neko-editor") {
      applyChart(nekoChart, {
        status: t("status_neko_short"),
        statusOk: true,
      });
      return;
    }
    if (q === "sample" || q === "demo") {
      applyChart(sampleChart, {
        status: t("status_sample"),
        statusOk: true,
      });
      return;
    }

    try {
      const pref = sessionStorage.getItem("ht-chart-pref");
      const saved = sessionStorage.getItem("ht-last-yaml");
      if (saved && yamlInput) {
        yamlInput.value = saved;
        if (pref === "yaml" || !pref) {
          try {
            loadYamlText(saved, { silentToast: true });
            setYamlStatus(t("status_yaml_restored"), "ok");
            return;
          } catch (e) {
            setYamlStatus(t("status_yaml_fail"), "err");
          }
        }
      }
      if (pref === "neko") {
        applyChart(nekoChart, {
          status: t("status_neko"),
          statusOk: true,
        });
        return;
      }
    } catch (e) { /* ignore */ }

    applyChart(nekoChart, {
      status: t("status_neko"),
      statusOk: true,
    });
  })();

  // ── チャート適用 ──
  function applyChart(nextChart, opts) {
    opts = opts || {};
    chart = nextChart;
    bodies = bodiesFromChart(chart).map((b) => {
      const pt = getPlanetTexts()[b.id];
      return {
        ...b,
        name_ja: pt ? pt.name : b.id,
        name: pt ? pt.name : b.id,
      };
    });
    bodiesByHouse = emptyBodiesByHouse();
    bodies.forEach((b) => {
      if (b.house >= 1 && b.house <= 12) bodiesByHouse[b.house].push(b);
    });

    // 3D天体を張り替え
    clearPlanets(planetMeshes);
    const built = buildPlanets(ctx, houseGroups, bodies);
    planetMeshes = built.planetMeshes;
    pickables = built.pickables;
    controls.setPickables(pickables);

    ui.fillProfile(chart);
    ui.buildNav(bodiesByHouse, (n) => {
      if (cine.isPlaying()) cine.stop();
      tour.setPhase("idle");
      tour.setCurrent(n, {
        playCinematic: tour.getMode() === "guide",
        reason: "jump",
      });
    });
    ui.updateNavActive(tour.getCurrent(), housesData);

    // 進行中なら現在ハウスのパネル更新
    const cur = tour.getCurrent();
    ui.renderHouse(
      cur,
      withCuspHint(housesData[cur] || housesData[0], cur),
      enrichBodies(bodiesByHouse[cur] || []),
      { silent: true }
    );

    if (opts.status) setYamlStatus(opts.status, opts.statusOk ? "ok" : "err");
  }

  function withCuspHint(h, num) {
    if (!h || !num || !chart.cusps || !chart.cusps[num]) return h;
    // 浅いコピーでカスプを補足（元データは壊さない）
    const cusp = chart.cusps[num];
    return Object.assign({}, h, {
      subtitle: (h.subtitle || "") + (cusp.sign_ja ? " · カスプ " + cusp.sign_ja : ""),
    });
  }

  function openPlanetDetail(id, house) {
    const extra =
      (chart.bodyDetails && chart.bodyDetails[id]) ||
      bodies.find((b) => b.id === id) ||
      {};
    ui.showPlanetPanel(planetDetail(id, house, housesData[house], extra));
  }

  function handleNext() {
    if (tour.getMode() === "guide" && tour.getPhase() === "playing") {
      // ショット送り。最後なら onDone
      cine.skipShot();
      return;
    }
    tour.next();
  }

  function handlePrev() {
    if (tour.getMode() === "guide" && tour.getPhase() === "playing") {
      cine.skipAll();
      tour.setPhase("waiting");
      return;
    }
    tour.prev();
  }

  // buttons
  if (ui.el.startGuide) {
    ui.el.startGuide.addEventListener("click", () => {
      begin("cinematic");
      tour.startGuide();
      ui.toast(t("toast_guide_start"), 3200);
    });
  }
  if (ui.el.startFree) {
    ui.el.startFree.addEventListener("click", () => {
      cine.stop();
      tour.setPhase("idle");
      begin("walk");
      tour.startFree();
      ui.hideCaption();
      ui.setCaption(t("caption_free_title"), t("caption_free_body"), t("caption_ops"));
      ui.toast(t("toast_free"), 3500);
    });
  }
  if (ui.el.startOrbit) {
    ui.el.startOrbit.addEventListener("click", () => {
      cine.stop();
      tour.setPhase("idle");
      begin("orbit");
      tour.startFree();
      ui.hideCaption();
      ui.toast(t("toast_orbit"), 2600);
    });
  }
  if (ui.el.btnNext) ui.el.btnNext.addEventListener("click", () => handleNext());
  if (ui.el.btnPrev) ui.el.btnPrev.addEventListener("click", () => handlePrev());
  if (ui.el.btnMap) {
    ui.el.btnMap.addEventListener("click", () => {
      mapOpen = !mapOpen;
      ui.setMapOpen(mapOpen);
    });
  }
  if (ui.el.btnMode) {
    ui.el.btnMode.addEventListener("click", () => {
      const m = controls.getMode() === "walk" ? "orbit" : "walk";
      controls.setMode(m);
      controls.teleport(tour.getCurrent());
      ui.el.btnMode.textContent =
        m === "walk" ? t("btn_mode_orbit") : t("btn_mode_walk");
    });
  }
  if (ui.el.btnSound) ui.el.btnSound.addEventListener("click", toggleSound);
  if (ui.el.btnQuality) {
    ui.el.btnQuality.addEventListener("click", () => {
      quality = quality === "high" ? "low" : "high";
      localStorage.setItem("ht-quality", quality);
      ui.setQualityLabel(quality);
      ui.toast(
        t("toast_quality", {
          q: quality === "low" ? t("quality_low") : t("quality_high"),
        }),
        3500
      );
    });
  }
  if (ui.el.btnHelp) {
    ui.el.btnHelp.addEventListener("click", () => {
      ui.toast(controls.isMobile() ? t("help_mobile") : t("help_desktop"), 4000);
    });
  }

  const mapClose = document.getElementById("ht-map-close");
  if (mapClose) {
    mapClose.addEventListener("click", () => {
      mapOpen = false;
      ui.setMapOpen(false);
    });
  }
  if (ui.el.btnMenu) {
    ui.el.btnMenu.addEventListener("click", () => {
      const open = ui.el.menuOverlay && ui.el.menuOverlay.hidden;
      ui.setMenuOpen(open);
    });
  }
  if (ui.el.planetClose) {
    ui.el.planetClose.addEventListener("click", () => ui.hidePlanetPanel());
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest && e.target.closest(".ht-p-btn");
    if (!btn) return;
    const id = btn.getAttribute("data-planet");
    const house = tour.getCurrent();
    if (!id || house < 1) return;
    openPlanetDetail(id, house);
  });

  if (ui.el.mapOverlay) {
    ui.el.mapOverlay.addEventListener("click", (e) => {
      if (e.target === ui.el.mapOverlay) {
        mapOpen = false;
        ui.setMapOpen(false);
      }
    });
  }
  const menuClose = document.getElementById("ht-menu-close");
  if (menuClose) menuClose.addEventListener("click", () => ui.setMenuOpen(false));
  const menuTitle = document.getElementById("ht-menu-title");
  if (menuTitle) {
    menuTitle.addEventListener("click", () => {
      ui.setMenuOpen(false);
      started = false;
      ui.showTitle();
    });
  }

  function begin(controlMode) {
    started = true;
    ui.startHud();
    controls.setMode(controlMode || "walk");
    ui.showMobileStick(controls.isMobile() && controlMode === "walk");
    if (ui.el.btnMode) {
      ui.el.btnMode.textContent =
        controlMode === "orbit"
          ? t("btn_mode_walk")
          : controlMode === "cinematic"
            ? t("btn_mode_guide")
            : t("btn_mode_orbit");
    }
  }

  function enrichBodies(list) {
    return list.map((b) => {
      const pt = getPlanetTexts()[b.id];
      return {
        ...b,
        name_ja: pt ? pt.name : b.id,
        name: pt ? pt.name : b.id,
      };
    });
  }

  function emptyBodiesByHouse() {
    const m = {};
    for (let i = 1; i <= 12; i++) m[i] = [];
    return m;
  }

  // audio
  function ensureAudio() {
    if (audioCtx) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    audioCtx = new AC();
    masterGain = audioCtx.createGain();
    masterGain.gain.value = 0.0001;
    masterGain.connect(audioCtx.destination);
  }

  function stopOscs() {
    oscNodes.forEach((n) => {
      try {
        n.osc.stop();
        n.osc.disconnect();
        n.gain.disconnect();
      } catch (e) { /* */ }
    });
    oscNodes = [];
  }

  function toggleSound() {
    soundOn = !soundOn;
    ui.setSoundLabel(soundOn);
    if (soundOn) {
      ensureAudio();
      if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
      retuneAudio(tour.getCurrent());
      if (masterGain) {
        masterGain.gain.cancelScheduledValues(audioCtx.currentTime);
        masterGain.gain.linearRampToValueAtTime(0.045, audioCtx.currentTime + 0.8);
      }
      ui.toast(t("toast_sound_on"));
    } else {
      if (masterGain && audioCtx) {
        masterGain.gain.linearRampToValueAtTime(0.0001, audioCtx.currentTime + 0.4);
      }
      stopOscs();
      ui.toast(t("toast_sound_off"));
    }
  }

  function retuneAudio(num) {
    if (!soundOn || !audioCtx) return;
    stopOscs();
    const h = housesData[num] || housesData[0];
    const base = (h.sound && h.sound.baseHz) || 110;
    const mood = (h.sound && h.sound.mood) || "warm";
    let intervals = [1, 5 / 4, 3 / 2];
    let types = ["sine", "triangle", "sine"];
    let filterFreq = 1200;
    if (mood === "deep" || mood === "mist" || mood === "hearth") {
      intervals = [1, 6 / 5, 3 / 2];
      filterFreq = 600;
    }
    if (mood === "playful" || mood === "chatter") {
      intervals = [1, 9 / 8, 5 / 4];
      filterFreq = 2200;
    }
    if (mood === "open" || mood === "grand") {
      intervals = [1, 5 / 4, 2];
      filterFreq = 2600;
    }
    if (mood === "playful") filterFreq = 2400;
    const filter = audioCtx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = filterFreq;
    filter.connect(masterGain);
    intervals.forEach((ratio, i) => {
      const osc = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      osc.type = types[i] || "sine";
      osc.frequency.value = base * ratio;
      g.gain.value = 0.0001;
      osc.connect(g);
      g.connect(filter);
      osc.start();
      g.gain.linearRampToValueAtTime(0.18 / (i + 1), audioCtx.currentTime + 1);
      oscNodes.push({ osc, gain: g });
    });
    if (mood === "playful") {
      try {
        const bufferSize = audioCtx.sampleRate * 2;
        const noiseBuf = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        const data = noiseBuf.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
          const burst = Math.sin(i * 0.001) > 0.92 ? 1 : 0.15;
          data[i] = (Math.random() * 2 - 1) * burst * 0.4;
        }
        const noise = audioCtx.createBufferSource();
        noise.buffer = noiseBuf;
        noise.loop = true;
        const ng = audioCtx.createGain();
        const nf = audioCtx.createBiquadFilter();
        nf.type = "bandpass";
        nf.frequency.value = 1800;
        nf.Q.value = 0.6;
        ng.gain.value = 0.0001;
        noise.connect(nf);
        nf.connect(ng);
        ng.connect(masterGain);
        noise.start();
        ng.gain.linearRampToValueAtTime(0.02, audioCtx.currentTime + 1.2);
        oscNodes.push({ osc: noise, gain: ng });
      } catch (e) { /* ignore */ }
    }
  }

  function isProbablyMobile() {
    return window.matchMedia("(max-width: 720px), (pointer: coarse)").matches;
  }

  ui.renderHouse(0, housesData[0], [], { silent: true });
  ui.updateNavActive(0, housesData);
  ui.hideLoading();

  function frame() {
    requestAnimationFrame(frame);
    const dt = Math.min(ctx.clock.getDelta(), 0.05);
    const t = ctx.clock.elapsedTime;
    animatePlanets(planetMeshes, t, dt, reducedMotion);
    animateSymbolics(animatables, houseGroups, tour.getCurrent(), t, dt, reducedMotion);
    if (started) cine.update(dt);
    controls.update(dt, started);
    ctx.renderer.render(ctx.scene, ctx.camera);
  }
  frame();
})();
