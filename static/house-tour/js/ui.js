/**
 * DOM UI バインディング
 */
import { t, getLang } from "./i18n.js";

export function createUI(root) {
  const $ = (id) => document.getElementById(id);

  const el = {
    loading: $("ht-loading"),
    title: $("ht-title"),
    hud: $("ht-hud"),
    info: $("ht-info"),
    infoNum: $("ht-info-num"),
    infoTitle: $("ht-info-title"),
    infoEn: $("ht-info-en"),
    infoShort: $("ht-info-short"),
    infoDetail: $("ht-info-detail"),
    infoKeywords: $("ht-info-keywords"),
    infoPlanets: $("ht-info-planets"),
    planetsLabel: $("ht-planets-label"),
    objectChips: $("ht-object-chips"),
    senseSpace: $("ht-sense-space"),
    senseLight: $("ht-sense-light"),
    senseSound: $("ht-sense-sound"),
    swatchA: $("ht-swatch-a"),
    swatchB: $("ht-swatch-b"),
    swatchC: $("ht-swatch-c"),
    infoArch: $("ht-info-arch"),
    navRing: $("ht-nav-ring"),
    navCenter: $("ht-nav-center"),
    strip: $("ht-strip"),
    modeLabel: $("ht-mode-label"),
    guideLabel: $("ht-guide-label"),
    btnMode: $("ht-btn-mode"),
    btnSound: $("ht-btn-sound"),
    btnQuality: $("ht-btn-quality"),
    btnHelp: $("ht-btn-help"),
    btnMenu: $("ht-btn-menu"),
    btnNext: $("ht-btn-next"),
    btnPrev: $("ht-btn-prev"),
    btnMap: $("ht-btn-map"),
    locTitle: $("ht-loc-title"),
    locSub: $("ht-loc-sub"),
    crosshair: $("ht-crosshair"),
    toast: $("ht-toast"),
    vignette: $("ht-vignette"),
    profileName: $("ht-profile-name"),
    profileBirth: $("ht-profile-birth"),
    profileSystem: $("ht-profile-system"),
    startGuide: $("ht-start-guide"),
    startFree: $("ht-start-free"),
    startOrbit: $("ht-start-orbit"),
    planetPanel: $("ht-planet-panel"),
    planetClose: $("ht-planet-close"),
    planetTitle: $("ht-planet-title"),
    planetBody: $("ht-planet-body"),
    stickBase: $("ht-stick-base"),
    stickKnob: $("ht-stick-knob"),
    mapOverlay: $("ht-map-overlay"),
    menuOverlay: $("ht-menu-overlay"),
    caption: $("ht-caption"),
    captionKicker: $("ht-caption-kicker"),
    captionTitle: $("ht-caption-title"),
    captionBody: $("ht-caption-body"),
  };

  function setAccent(hex) {
    document.documentElement.style.setProperty("--ht-accent", hex || "#c9a96e");
  }

  function toast(msg, ms) {
    if (!el.toast) return;
    el.toast.textContent = msg;
    el.toast.classList.add("is-show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.toast.classList.remove("is-show"), ms || 2200);
  }

  function flashVignette() {
    if (!el.vignette) return;
    el.vignette.classList.add("is-flash");
    clearTimeout(flashVignette._t);
    flashVignette._t = setTimeout(() => el.vignette.classList.remove("is-flash"), 180);
  }

  function hideLoading() {
    el.loading && el.loading.classList.add("is-hidden");
  }

  function showError(msg) {
    if (el.loading) {
      el.loading.innerHTML =
        '<p style="color:#c4788a;text-align:center;line-height:1.7;max-width:280px;letter-spacing:0.04em">' +
        msg +
        "</p>";
    }
  }

  function fillProfile(chart) {
    if (el.profileName) el.profileName.textContent = chart.name || "—";
    if (el.profileBirth) {
      el.profileBirth.textContent =
        (chart.birth_date || "") +
        (chart.birth_time ? " " + chart.birth_time : "") +
        (chart.birth_place ? " · " + chart.birth_place : "");
    }
    if (el.profileSystem) {
      const sys = chart.house_system || "Placidus";
      const tag =
        chart.source === "yaml" || chart.source === "yaml-sample-neko"
          ? t("system_yaml")
          : t("system_demo");
      el.profileSystem.textContent = sys + " · " + tag;
    }
  }

  function buildNav(bodiesByHouse, onJump) {
    const ring = el.navRing;
    const strip = el.strip;
    if (!ring) return;
    ring.querySelectorAll(".ht-nav-house").forEach((n) => n.remove());
    if (strip) strip.innerHTML = "";

    for (let n = 1; n <= 12; n++) {
      const a = ((n - 1) * 30 - 90) * (Math.PI / 180);
      const r = 58;
      const x = Math.cos(a) * r;
      const y = Math.sin(a) * r;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ht-nav-house";
      btn.textContent = String(n);
      btn.dataset.house = String(n);
      btn.style.transform = "translate(" + x + "px," + y + "px)";
      if ((bodiesByHouse[n] || []).length) btn.classList.add("has-planet");
      btn.addEventListener("click", () => onJump(n));
      ring.appendChild(btn);

      if (strip) {
        const s = document.createElement("button");
        s.type = "button";
        s.className = "ht-strip-btn";
        s.textContent = String(n);
        s.dataset.house = String(n);
        s.addEventListener("click", () => onJump(n));
        strip.appendChild(s);
      }
    }
    if (el.navCenter) {
      el.navCenter.onclick = () => onJump(0);
    }
  }

  function updateNavActive(current, housesData) {
    document.querySelectorAll(".ht-nav-house, .ht-strip-btn").forEach((b) => {
      const n = parseInt(b.dataset.house, 10);
      b.classList.toggle("is-active", n === current);
      if (b.classList.contains("ht-nav-house") && housesData[n]) {
        if (n === current) b.style.background = housesData[n].palette.primary;
        else b.style.background = "";
      }
    });
    if (el.navCenter) el.navCenter.classList.toggle("is-active", current === 0);
  }

  function renderHouse(num, h, bodies, opts) {
    opts = opts || {};
    el.info && el.info.classList.toggle("is-center", num === 0);
    setAccent(h.palette ? h.palette.primary : "#c9a96e");

    if (el.infoNum) {
      el.infoNum.textContent =
        num === 0 ? "CORE · CHART" : t("house_num", { n: num });
    }
    if (el.infoTitle) el.infoTitle.textContent = h.title || "";
    if (el.infoEn) {
      el.infoEn.textContent =
        (h.subtitle || h.title_en || "") + (num ? " · House " + num : "");
    }
    if (el.senseSpace) el.senseSpace.textContent = h.spaceLabel || "—";
    if (el.senseLight) el.senseLight.textContent = h.lightLabel || "—";
    if (el.senseSound) el.senseSound.textContent = h.soundLabel || "—";
    const pal = h.palette || {};
    if (el.swatchA) el.swatchA.style.background = pal.primary || "#c9a96e";
    if (el.swatchB) el.swatchB.style.background = pal.accent || "#e8d5b0";
    if (el.swatchC) el.swatchC.style.background = pal.secondary || "#12141e";

    if (el.objectChips) {
      el.objectChips.innerHTML = "";
      (h.objects || []).forEach((name) => {
        const chip = document.createElement("span");
        chip.className = "ht-obj-chip";
        chip.textContent = name;
        el.objectChips.appendChild(chip);
      });
    }

    if (el.infoKeywords) {
      el.infoKeywords.innerHTML = "";
      (h.keywords || []).forEach((k) => {
        const s = document.createElement("span");
        s.className = "ht-kw";
        s.textContent = k;
        el.infoKeywords.appendChild(s);
      });
    }

    if (el.infoShort) el.infoShort.textContent = h.short || "";
    if (el.infoDetail) el.infoDetail.textContent = h.detail || "";
    if (el.infoArch) el.infoArch.textContent = h.architecture || "";

    if (el.planetsLabel) {
      el.planetsLabel.textContent =
        num === 0 ? t("section_planets_core") : t("section_planets");
    }
    if (el.infoPlanets) {
      el.infoPlanets.innerHTML = "";
      if (num === 0) {
        const li = document.createElement("li");
        li.innerHTML =
          '<span class="ht-p-name">' + escapeHtml(t("core_hint")) + "</span>";
        el.infoPlanets.appendChild(li);
      } else if (!bodies || !bodies.length) {
        const li = document.createElement("li");
        li.innerHTML =
          '<span class="ht-p-name" style="color:var(--ht-dim)">' +
          escapeHtml(t("empty_planets")) +
          "</span>";
        el.infoPlanets.appendChild(li);
      } else {
        bodies.forEach((b) => {
          const li = document.createElement("li");
          li.className = "ht-planet-row";
          const label = b.name_ja || b.name || b.id;
          li.innerHTML =
            '<span class="ht-p-dot" style="background:' +
            (b.color || "#fff") +
            '"></span>' +
            '<button type="button" class="ht-p-btn" data-planet="' +
            b.id +
            '">' +
            (b.glyph || "") +
            " " +
            escapeHtml(label) +
            "</button>";
          el.infoPlanets.appendChild(li);
        });
      }
    }

    if (el.locTitle) {
      el.locTitle.textContent =
        num === 0 ? t("loc_core") : t("loc_house", { n: num });
    }
    if (el.locSub) el.locSub.textContent = h.spaceLabel || h.title_en || "";

    if (!opts.silent) flashVignette();
  }

  function showPlanetPanel(detail) {
    if (!el.planetPanel) return;
    el.planetPanel.hidden = false;
    if (el.planetTitle) {
      el.planetTitle.textContent =
        (detail.glyph || "") +
        " " +
        detail.name +
        " · " +
        t("house_num", { n: detail.house });
    }
    if (el.planetBody) {
      const pos = detail.position
        ? "<p class=\"ht-planet-pos\"><strong>" +
          escapeHtml(t("planet_position")) +
          "</strong> — " +
          escapeHtml(detail.position) +
          "</p>"
        : "";
      el.planetBody.innerHTML =
        pos +
        "<p class=\"ht-planet-fn\"><strong>" +
        escapeHtml(t("planet_function")) +
        "</strong> — " +
        escapeHtml(detail.function) +
        "</p>" +
        "<p class=\"ht-planet-house\"><strong>" +
        escapeHtml(detail.houseTitle) +
        "</strong> — " +
        escapeHtml(detail.houseTheme) +
        "</p>" +
        "<p class=\"ht-planet-combo\">" +
        escapeHtml(detail.combo) +
        "</p>" +
        "<p class=\"ht-planet-note\">" +
        escapeHtml(t("planet_note")) +
        "</p>";
    }
  }

  function hidePlanetPanel() {
    if (el.planetPanel) el.planetPanel.hidden = true;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function startHud() {
    el.title && el.title.classList.add("is-hidden");
    el.hud && el.hud.classList.remove("is-hidden");
    el.hud && el.hud.setAttribute("aria-hidden", "false");
  }

  function showTitle() {
    el.title && el.title.classList.remove("is-hidden");
    el.hud && el.hud.classList.add("is-hidden");
  }

  function setGuideLabel(text) {
    if (el.guideLabel) el.guideLabel.textContent = text || "";
  }

  /** ガイド中「いま見ているもの」 */
  function setCaption(title, body, kicker) {
    if (!el.caption) return;
    el.caption.hidden = false;
    if (el.captionKicker) {
      el.captionKicker.textContent = kicker || t("caption_viewing");
    }
    if (el.captionTitle) el.captionTitle.textContent = title || "";
    if (el.captionBody) el.captionBody.textContent = body || "";
  }

  function hideCaption() {
    if (el.caption) el.caption.hidden = true;
  }

  function setModeLabel(text) {
    if (el.modeLabel) el.modeLabel.textContent = text;
  }

  function setQualityLabel(q) {
    if (el.btnQuality) {
      el.btnQuality.textContent =
        q === "low" ? t("btn_quality_low") : t("btn_quality_high");
    }
  }

  function setSoundLabel(on) {
    if (el.btnSound) {
      el.btnSound.textContent = on ? t("btn_sound_on") : t("btn_sound_off");
      el.btnSound.classList.toggle("is-active", on);
    }
  }

  function setMapOpen(open) {
    if (el.mapOverlay) el.mapOverlay.hidden = !open;
  }

  function setMenuOpen(open) {
    if (el.menuOverlay) el.menuOverlay.hidden = !open;
  }

  function showMobileStick(show) {
    if (el.stickBase) el.stickBase.hidden = !show;
  }

  function updateStickKnob(dx, dy) {
    if (!el.stickKnob) return;
    el.stickKnob.style.transform =
      "translate(" + dx * 28 + "px," + dy * 28 + "px)";
  }

  function resetStickKnob() {
    if (el.stickKnob) el.stickKnob.style.transform = "translate(0,0)";
  }

  return {
    el,
    toast,
    flashVignette,
    hideLoading,
    showError,
    fillProfile,
    buildNav,
    updateNavActive,
    renderHouse,
    showPlanetPanel,
    hidePlanetPanel,
    startHud,
    showTitle,
    setGuideLabel,
    setCaption,
    hideCaption,
    setModeLabel,
    setSoundLabel,
    setQualityLabel,
    setMapOpen,
    setMenuOpen,
    showMobileStick,
    updateStickKnob,
    resetStickKnob,
    setAccent,
  };
}
