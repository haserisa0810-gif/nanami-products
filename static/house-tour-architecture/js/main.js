/**
 * Birth Chart Museum — Architecture Edition
 * 抽象版 UX を再利用し、建築・素材を差し替え。
 */
import { sampleChart, bodiesFromChart } from "../../house-tour/js/data/sample-chart.js";
import { nekoChart } from "../../house-tour/js/data/neko-chart.js";
import { parseNatalYaml } from "../../house-tour/js/parse-yaml.js";
import { createSceneContext } from "../../house-tour/js/scene.js";
import {
  buildPlanets,
  clearPlanets,
  animatePlanets,
  planetDetail,
} from "../../house-tour/js/planet-builder.js";
import { createControls } from "../../house-tour/js/controls.js";
import { createTourController } from "../../house-tour/js/tour-controller.js";
import { createCinematicPlayer } from "../../house-tour/js/cinematic.js";
import { buildShotsForHouse } from "../../house-tour/js/museum-shots.js";
import { createUI } from "../../house-tour/js/ui.js";
import {
  initLang,
  getLang,
  setLang,
  onLangChange,
  t,
  getHousesData,
  getPlanetTexts,
  applyDomI18n,
} from "../../house-tour/js/i18n.js";
import {
  buildCampus,
  animateArch,
  applyArchAtmosphere,
  EYE_H,
} from "./arch-builder.js";
import { createAmbientSound } from "../../house-tour/js/ambient-sound.js";
import {
  isLivedInEnabled,
  setLivedInEnabled,
  setLivedInVisible,
} from "./life-props.js";

(function boot() {
  if (typeof THREE === "undefined") {
    console.error("[HouseTourArch] Three.js missing");
    return;
  }

  initLang();
  applyDomI18n(document);

  let housesData = getHousesData();
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let quality = localStorage.getItem("ht-quality") || "high";
  const ambient = createAmbientSound();
  let started = false;
  let mapOpen = false;
  let chart = nekoChart;
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
    // 建築版: やや明るい「屋外キャンパス」トーン
    ctx.scene.background.setHex(0x0c1018);
    ctx.fog.color.setHex(0x0c1018);
    ctx.fog.density = 0.007;
    ctx.ambient.intensity = 0.32;
  } catch (e) {
    ui.showError("3D init failed<br><small>" + e.message + "</small>");
    return;
  }

  const { houseGroups, animatables, entryWorld } = buildCampus(ctx, housesData);
  const cine = createCinematicPlayer(ctx.camera, THREE);

  function syncLivedInButton() {
    const btn = document.getElementById("ht-btn-lived-in");
    if (!btn) return;
    const on = isLivedInEnabled();
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.textContent = on
      ? t("btn_lived_in_on") || "生活感: ON"
      : t("btn_lived_in_off") || "生活感: OFF";
  }

  function toggleLivedIn() {
    const next = !isLivedInEnabled();
    setLivedInEnabled(next);
    setLivedInVisible(houseGroups, next);
    syncLivedInButton();
    ui.toast(
      next
        ? t("toast_lived_in_on") || "生活感ON — 机上の小物を表示"
        : t("toast_lived_in_off") || "生活感OFF — 建築のみ（すぐ戻せます）",
      2800
    );
  }

  const tour = createTourController({
    onVisit(num, opts) {
      opts = opts || {};
      const h = housesData[num] || housesData[0];
      ui.renderHouse(num, withCusp(h, num), enrich(bodiesByHouse[num] || []), {
        silent: opts.silentTeleport || opts.playCinematic,
      });
      ui.updateNavActive(num, housesData);
      applyArchAtmosphere(ctx, houseGroups, housesData, num);
      ui.hidePlanetPanel();

      if (opts.playCinematic) {
        playGuide(num);
        return;
      }
      if (!opts.silentTeleport) {
        controls.setMode(controls.getMode() === "orbit" ? "orbit" : "walk");
        controls.teleport(num);
        controls.syncLastHouse(num);
      }
      ambient.onHouse(h);
      ui.setGuideLabel(guideLabelText());
      if (!opts.silentTeleport && opts.reason !== "walk") {
        ui.toast(
          num === 0 ? t("loc_core") : t("loc_house", { n: num }) + " · " + (h.spaceLabel || "")
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

  function playGuide(num) {
    tour.setPhase("playing");
    controls.setMode("cinematic");
    ui.showMobileStick(false);
    const hg = num === 0 ? null : houseGroups[num];
    const shots = buildShotsForHouse(num, hg, THREE, housesData, getLang());
    cine.play(shots, {
      onShot(shot, i, total) {
        ui.setCaption(shot.label, shot.caption, t("caption_guide", { i: i + 1, total }));
        ui.setGuideLabel(guideLabelText());
      },
      onDone() {
        tour.setPhase("waiting");
        controls.syncEulerFromCamera();
        controls.setMode("walk");
        if (num === 0) controls.teleport(0);
        else if (entryWorld[num]) {
          const p = houseGroups[num].group.position;
          controls.setPose(entryWorld[num], { x: p.x, y: 2.2, z: p.z });
        } else controls.teleport(num);
        controls.syncLastHouse(num);
        ui.showMobileStick(controls.isMobile());
        const h = housesData[num] || housesData[0];
        ui.setCaption(h.title || t("loc_core"), t("caption_done_body"), t("caption_done"));
        ui.setGuideLabel(guideLabelText());
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
    onPick(data) {
      if (data.pickable === "planet") {
        const extra =
          (chart.bodyDetails && chart.bodyDetails[data.planetId]) ||
          bodies.find((b) => b.id === data.planetId) ||
          {};
        ui.showPlanetPanel(
          planetDetail(data.planetId, data.house, housesData[data.house], extra)
        );
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
      tour.setCurrent(0, { playCinematic: tour.getMode() === "guide" });
    },
    onJump(n) {
      tour.setCurrent(n, { playCinematic: tour.getMode() === "guide", reason: "jump" });
    },
    onToggleMap() {
      mapOpen = !mapOpen;
      ui.setMapOpen(mapOpen);
    },
    onMenu() {
      if (!started) return;
      ui.setMenuOpen(ui.el.menuOverlay && ui.el.menuOverlay.hidden);
    },
    onStickMove(dx, dy) {
      ui.updateStickKnob(dx, dy);
    },
    onStickEnd() {
      ui.resetStickKnob();
    },
  });
  if (controls.setEntryPoints) controls.setEntryPoints(entryWorld);

  function handleNext() {
    if (tour.getMode() === "guide" && tour.getPhase() === "playing") {
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

  function applyChart(next, opts) {
    opts = opts || {};
    chart = next;
    bodies = bodiesFromChart(chart).map((b) => {
      const pt = getPlanetTexts()[b.id];
      return { ...b, name_ja: pt ? pt.name : b.id, name: pt ? pt.name : b.id };
    });
    bodiesByHouse = emptyBodiesByHouse();
    bodies.forEach((b) => {
      if (b.house >= 1 && b.house <= 12) bodiesByHouse[b.house].push(b);
    });
    clearPlanets(planetMeshes);
    const built = buildPlanets(ctx, houseGroups, bodies);
    planetMeshes = built.planetMeshes;
    pickables = built.pickables;
    controls.setPickables(pickables);
    ui.fillProfile(chart);
    ui.buildNav(bodiesByHouse, (n) => {
      if (cine.isPlaying()) cine.stop();
      tour.setPhase("idle");
      tour.setCurrent(n, { playCinematic: tour.getMode() === "guide", reason: "jump" });
    });
    ui.updateNavActive(tour.getCurrent(), housesData);
    const cur = tour.getCurrent();
    ui.renderHouse(cur, withCusp(housesData[cur] || housesData[0], cur), enrich(bodiesByHouse[cur] || []), {
      silent: true,
    });
    // ステータス表示は入口ポータル側。タイトルは profile のみ更新。
  }

  function withCusp(h, num) {
    if (!h || !num || !chart.cusps || !chart.cusps[num]) return h;
    const cusp = chart.cusps[num];
    return Object.assign({}, h, {
      subtitle: (h.subtitle || "") + (cusp.sign_ja ? " · " + cusp.sign_ja : ""),
    });
  }

  function enrich(list) {
    return list.map((b) => {
      const pt = getPlanetTexts()[b.id];
      return { ...b, name_ja: pt ? pt.name : b.id, name: pt ? pt.name : b.id };
    });
  }

  function emptyBodiesByHouse() {
    const m = {};
    for (let i = 1; i <= 12; i++) m[i] = [];
    return m;
  }

  // YAML 入力 UI は入口のみ。ここでは sessionStorage から読む。

  document.querySelectorAll("[data-lang-set]").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.getAttribute("data-lang-set")));
  });
  onLangChange(() => {
    housesData = getHousesData();
    applyDomI18n(document);
    ui.setQualityLabel(quality);
    ui.setSoundLabel(ambient.isOn());
    syncLivedInButton();
    refreshInfoPanelLabel();
    applyChart(chart, { status: "", statusOk: true });
    ui.setGuideLabel(guideLabelText());
  });

  function begin(mode) {
    started = true;
    ui.startHud();
    controls.setMode(mode || "walk");
    ui.showMobileStick(controls.isMobile() && mode === "walk");
  }

  document.getElementById("ht-start-guide")?.addEventListener("click", () => {
    begin("cinematic");
    tour.startGuide();
    ui.toast(t("toast_guide_start"), 3200);
  });
  document.getElementById("ht-start-free")?.addEventListener("click", () => {
    cine.stop();
    tour.setPhase("idle");
    begin("walk");
    tour.startFree();
    ui.setCaption(t("caption_free_title"), t("caption_free_body"), t("caption_ops"));
    ui.toast(t("toast_free"), 3500);
  });
  document.getElementById("ht-start-orbit")?.addEventListener("click", () => {
    cine.stop();
    tour.setPhase("idle");
    begin("orbit");
    tour.startFree();
    ui.hideCaption();
    ui.toast(t("toast_orbit"), 2600);
  });

  ui.el.btnNext?.addEventListener("click", handleNext);
  ui.el.btnPrev?.addEventListener("click", handlePrev);
  ui.el.btnMap?.addEventListener("click", () => {
    mapOpen = !mapOpen;
    ui.setMapOpen(mapOpen);
  });
  // 解説パネルの表示/非表示（本館と共通の localStorage キーで記憶）
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
  ui.el.btnPanel?.addEventListener("click", () => setInfoVisible(!infoVisible));
  ui.el.infoClose?.addEventListener("click", () => setInfoVisible(false));
  setInfoVisible(infoVisible, { silent: true });
  ui.el.btnMode?.addEventListener("click", () => {
    const m = controls.getMode() === "walk" ? "orbit" : "walk";
    controls.setMode(m);
    controls.teleport(tour.getCurrent());
    ui.el.btnMode.textContent = m === "walk" ? t("btn_mode_orbit") : t("btn_mode_walk");
  });
  ui.el.btnSound?.addEventListener("click", () => {
    const h = housesData[tour.getCurrent()] || housesData[0];
    ambient.toggle(h).then((on) => {
      ui.setSoundLabel(on);
      ui.toast(on ? t("toast_sound_on") : t("toast_sound_off"), 2200);
    });
  });
  document.getElementById("ht-btn-lived-in")?.addEventListener("click", toggleLivedIn);
  document.getElementById("ht-menu-lived-in")?.addEventListener("click", () => {
    toggleLivedIn();
    ui.setMenuOpen(false);
  });
  syncLivedInButton();
  ui.el.btnQuality?.addEventListener("click", () => {
    quality = quality === "high" ? "low" : "high";
    localStorage.setItem("ht-quality", quality);
    ui.setQualityLabel(quality);
    ui.toast(t("toast_quality", { q: quality === "low" ? t("quality_low") : t("quality_high") }), 3200);
  });
  ui.el.btnHelp?.addEventListener("click", () => {
    ui.toast(controls.isMobile() ? t("help_mobile") : t("help_desktop"), 4000);
  });
  ui.el.btnMenu?.addEventListener("click", () => {
    ui.setMenuOpen(ui.el.menuOverlay && ui.el.menuOverlay.hidden);
  });
  ui.el.planetClose?.addEventListener("click", () => ui.hidePlanetPanel());
  document.getElementById("ht-map-close")?.addEventListener("click", () => {
    mapOpen = false;
    ui.setMapOpen(false);
  });
  document.getElementById("ht-menu-close")?.addEventListener("click", () => ui.setMenuOpen(false));
  document.getElementById("ht-menu-title")?.addEventListener("click", () => {
    ui.setMenuOpen(false);
    started = false;
    ui.showTitle();
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest && e.target.closest(".ht-p-btn");
    if (!btn) return;
    const id = btn.getAttribute("data-planet");
    const house = tour.getCurrent();
    if (!id || house < 1) return;
    const extra = (chart.bodyDetails && chart.bodyDetails[id]) || {};
    ui.showPlanetPanel(planetDetail(id, house, housesData[house], extra));
  });

  // 初期チャート（入口ポータルの sessionStorage を優先）
  (function initialFromPortal() {
    // Demo モードはサンプル固定（入口 sessionStorage を読まない）
    if (window.HT_DEMO) {
      applyChart(nekoChart, { status: t("status_neko"), statusOk: true });
      return;
    }
    try {
      const pref = sessionStorage.getItem("ht-chart-pref");
      const saved = sessionStorage.getItem("ht-last-yaml");
      if (pref === "neko") {
        applyChart(nekoChart, { status: t("status_neko"), statusOk: true });
        return;
      }
      if (saved && (pref === "yaml" || !pref)) {
        try {
          const { chart: loaded, bodyCount, warnings } = parseNatalYaml(saved);
          applyChart(loaded, {
            status:
              t("status_loaded", { name: loaded.name, n: bodyCount }) +
              (warnings && warnings.length ? t("status_warn", { n: warnings.length }) : ""),
            statusOk: true,
          });
          return;
        } catch (e) {
          ui.toast(t("toast_yaml_err"), 2800);
        }
      }
    } catch (e) { /* ignore */ }
    applyChart(nekoChart, { status: t("status_neko"), statusOk: true });
  })();
  try {
    ui.renderHouse(0, housesData[0], [], { silent: true });
  } catch (e) {
    console.error("[HouseTourArch] initial UI", e);
  }
  ui.hideLoading();

  // 自動開始はしない（タイトルで YAML / チャート確認してからボタンで開始）
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
    const tm = ctx.clock.elapsedTime;
    animatePlanets(planetMeshes, tm, dt, reducedMotion);
    animateArch(animatables, houseGroups, tour.getCurrent(), tm, dt, reducedMotion);
    if (started) cine.update(dt);
    controls.update(dt, started);
    ctx.renderer.render(ctx.scene, ctx.camera);
  }
  frame();
})();
