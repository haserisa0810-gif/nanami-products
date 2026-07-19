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
  localizeSign,
} from "./i18n.js";
import { createAmbientSound } from "./ambient-sound.js";

(function boot() {
  if (typeof THREE === "undefined") {
    console.error("[HouseTour] Three.js missing");
    const load = document.getElementById("ht-loading");
    if (load) {
      load.innerHTML =
        '<p style="color:#c4788a;text-align:center;line-height:1.7">Three.js の読み込みに失敗しました。<br>再読み込みしてください。</p>';
    }
    return;
  }

  initLang();
  applyDomI18n(document);

  let housesData = getHousesData();
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let quality = localStorage.getItem("ht-quality") || (isProbablyMobile() ? "low" : "high");
  const ambient = createAmbientSound();
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
      ambient.onHouse(h);
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
        ambient.onHouse(h);
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

  // YAML 入力 UI は入口 /birth-chart-museum のみ。ここでは sessionStorage から読む。
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
    return loaded;
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
    ui.setSoundLabel(ambient.isOn());
    refreshInfoPanelLabel();
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

  // 初回: URL ?chart= / 入口 sessionStorage / ねこ編集長デフォルト
  (function initialChart() {
    // Demo モード（/birth-chart-museum/demo）はサンプル固定。
    // ?chart= も入口 sessionStorage も読まない（購入者YAML読込は有料側の価値）。
    if (window.HT_DEMO) {
      applyChart(nekoChart, {
        status: t("status_neko"),
        statusOk: true,
      });
      return;
    }
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
      if (pref === "neko") {
        applyChart(nekoChart, {
          status: t("status_neko"),
          statusOk: true,
        });
        return;
      }
      if (saved && (pref === "yaml" || !pref)) {
        try {
          loadYamlText(saved, { silentToast: true });
          return;
        } catch (e) {
          ui.toast(t("status_yaml_fail") || t("toast_yaml_err"), 3200);
        }
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
    // ステータス表示は入口ポータル側。タイトルは profile のみ更新。
  }

  function withCuspHint(h, num) {
    if (!h || !num || !chart.cusps || !chart.cusps[num]) return h;
    // 浅いコピーでカスプを補足（元データは壊さない）
    const cusp = chart.cusps[num];
    return Object.assign({}, h, {
      subtitle:
        (h.subtitle || "") +
        (cusp.sign_ja
          ? " · " + t("cusp_label", { sign: localizeSign(cusp.sign_ja) })
          : ""),
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
  // 解説パネルの表示/非表示（純粋に画面だけ見たいとき用・状態は記憶）
  let infoVisible = true;
  try {
    infoVisible = localStorage.getItem("ht-info-visible") !== "0";
  } catch (e) { /* ignore */ }
  function setInfoVisible(next, opts) {
    infoVisible = next;
    try {
      localStorage.setItem("ht-info-visible", next ? "1" : "0");
    } catch (e) { /* ignore */ }
    ui.setInfoOpen(next);
    if (!next && !(opts && opts.silent)) ui.toast(t("toast_panel_off"), 2600);
  }
  function refreshInfoPanelLabel() {
    ui.setInfoOpen(infoVisible);
  }
  if (ui.el.btnPanel) {
    ui.el.btnPanel.addEventListener("click", () => setInfoVisible(!infoVisible));
  }
  if (ui.el.infoClose) {
    ui.el.infoClose.addEventListener("click", () => setInfoVisible(false));
  }
  setInfoVisible(infoVisible, { silent: true });
  if (ui.el.btnMode) {
    ui.el.btnMode.addEventListener("click", () => {
      const m = controls.getMode() === "walk" ? "orbit" : "walk";
      controls.setMode(m);
      controls.teleport(tour.getCurrent());
      ui.el.btnMode.textContent =
        m === "walk" ? t("btn_mode_orbit") : t("btn_mode_walk");
    });
  }
  if (ui.el.btnSound) {
    ui.el.btnSound.addEventListener("click", () => {
      const h = housesData[tour.getCurrent()] || housesData[0];
      ambient.toggle(h).then((on) => {
        ui.setSoundLabel(on);
        ui.toast(on ? t("toast_sound_on") : t("toast_sound_off"), 2200);
      });
    });
  }
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
  function returnToTitle() {
    try {
      if (cine.isPlaying()) cine.stop();
    } catch (e) { /* */ }
    tour.setPhase("idle");
    tour.startFree();
    ui.setMenuOpen(false);
    mapOpen = false;
    ui.setMapOpen(false);
    ui.hideCaption();
    ui.hidePlanetPanel();
    started = false;
    controls.setMode("orbit");
    ui.showMobileStick(false);
    ui.showTitle();
    ui.toast(t("toast_back_title"), 2200);
  }

  if (ui.el.btnMenu) {
    ui.el.btnMenu.addEventListener("click", () => {
      const open = ui.el.menuOverlay && ui.el.menuOverlay.hidden;
      ui.setMenuOpen(open);
    });
  }
  const btnTitle = document.getElementById("ht-btn-title");
  if (btnTitle) btnTitle.addEventListener("click", returnToTitle);

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
  if (menuTitle) menuTitle.addEventListener("click", returnToTitle);

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

  function isProbablyMobile() {
    return window.matchMedia("(max-width: 720px), (pointer: coarse)").matches;
  }

  try {
    ui.renderHouse(0, housesData[0], [], { silent: true });
    ui.updateNavActive(0, housesData);
  } catch (e) {
    console.error("[HouseTour] initial UI", e);
  }
  ui.hideLoading();

  // 自動開始はしない。prefer_guide=1 はタイトルでガイド開始を促すだけ。
  if (wantsPreferGuide()) {
    requestAnimationFrame(() => {
      setTimeout(() => {
        if (started) return;
        ui.toast(t("toast_guide_hint") || "準備ができたら「ガイドツアーで巡る」を押してください", 4200);
      }, 500);
    });
  }

  function wantsPreferGuide() {
    try {
      const p = new URLSearchParams(window.location.search || "");
      const v = (p.get("prefer_guide") || p.get("auto_guide") || p.get("guide") || "").toLowerCase();
      return v === "1" || v === "true" || v === "yes" || v === "on";
    } catch (e) {
      return false;
    }
  }

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
