/**
 * Transit Flight — 3D transit timeline flight experience
 *
 * Data contract (sample-data.json or future API/YAML adapter):
 * {
 *   profile: { name, birth_date, period_start, period_end },
 *   events: [{ date, transit_planet, natal_planet, aspect, orb, level, theme }]
 * }
 *
 * Data sources:
 *   - sample-data.json (default)
 *   - window.TRANSIT_FLIGHT_DATA inject
 *   - POST /api/transit-flight/from-yaml  (nanami western transit YAML)
 */
(function () {
  "use strict";

  var DATA_URL = "/static/transit-flight/sample-data.json";
  var YAML_API = "/api/transit-flight/from-yaml";
  var URL_API = "/api/transit-flight/from-url";
  var FLIGHT_DURATION_MS = 58000; // ~1 min total flight (after warp)
  var WARP_DURATION_MS = 2800;
  var EVENT_SHOW_MS = 4200;
  var TRACK_LENGTH = 420; // world units along -Z

  var PLANET_JA = {
    Sun: "太陽", Moon: "月", Mercury: "水星", Venus: "金星", Mars: "火星",
    Jupiter: "木星", Saturn: "土星", Uranus: "天王星", Neptune: "海王星", Pluto: "冥王星"
  };

  var ASPECT_JA = {
    conjunction: "コンジャンクション（合）",
    opposition: "オポジション（衝）",
    square: "スクエア（矩）",
    trine: "トライン（三分）",
    sextile: "セクスタイル（六分）"
  };

  var ASPECT_COLOR = {
    conjunction: 0xffd700,
    opposition: 0x88aaff,
    square: 0xff8866,
    trine: 0x66ddaa,
    sextile: 0xaaccff
  };

  var LEVEL_LABEL = {
    1: "LEVEL 1 · 小さな変化",
    2: "LEVEL 2 · 注目期間",
    3: "LEVEL 3 · 大きな転換点"
  };

  // ── DOM ──────────────────────────────────────────────
  var el = {
    root: document.getElementById("tf-root"),
    canvas: document.getElementById("tf-canvas"),
    loading: document.getElementById("tf-loading"),
    title: document.getElementById("tf-title"),
    startBtn: document.getElementById("tf-start"),
    profileName: document.getElementById("tf-profile-name"),
    profileBirth: document.getElementById("tf-profile-birth"),
    profilePeriod: document.getElementById("tf-profile-period"),
    hud: document.getElementById("tf-hud"),
    dateLabel: document.getElementById("tf-date"),
    progressFill: document.getElementById("tf-progress-fill"),
    pauseBadge: document.getElementById("tf-pause-badge"),
    eventCard: document.getElementById("tf-event-card"),
    eventLevel: document.getElementById("tf-event-level"),
    eventTitle: document.getElementById("tf-event-title"),
    eventJa: document.getElementById("tf-event-ja"),
    eventMeta: document.getElementById("tf-event-meta"),
    eventTheme: document.getElementById("tf-event-theme"),
    end: document.getElementById("tf-end"),
    summaryList: document.getElementById("tf-summary-list"),
    replayBtn: document.getElementById("tf-replay"),
    error: document.getElementById("tf-error"),
    errorMsg: document.getElementById("tf-error-msg"),
    errorRetry: document.getElementById("tf-error-retry"),
    controlsHint: document.getElementById("tf-controls-hint"),
    yamlInput: document.getElementById("tf-yaml-input"),
    urlInput: document.getElementById("tf-url-input"),
    yamlStatus: document.getElementById("tf-yaml-status"),
    loadYamlBtn: document.getElementById("tf-load-yaml"),
    loadUrlBtn: document.getElementById("tf-load-url"),
    useSampleBtn: document.getElementById("tf-use-sample"),
    copyDataBtn: document.getElementById("tf-copy-data"),
    copyStatus: document.getElementById("tf-copy-status")
  };

  // ── State ────────────────────────────────────────────
  var state = {
    phase: "loading", // loading | title | warp | flight | end
    paused: false,
    destroyed: false,
    data: null,
    flightT: 0, // 0..1
    warpT: 0,
    speedMul: 1,
    lastTs: 0,
    raf: 0,
    lookX: 0,
    lookY: 0,
    targetLookX: 0,
    targetLookY: 0,
    drag: null,
    touch: null,
    activeEventIdx: -1,
    eventHideTimer: 0,
    shownEvents: {},
    lowPower: false,
    reducedMotion: false,
    inputBound: false
  };

  // ── Three.js objects ─────────────────────────────────
  var renderer, scene, camera, clock;
  var starPoints, streakPoints, dustPoints;
  var eventGroup, eventNodes = [];
  var warpBoost = 0;
  var ambientNearColor = new THREE.Color(0x050810);
  var ambientFarColor = new THREE.Color(0x0a0e22);

  // ── Utils ────────────────────────────────────────────
  function parseDate(s) {
    var p = String(s).split("-");
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
  }

  function formatDate(d) {
    var y = d.getUTCFullYear();
    var m = String(d.getUTCMonth() + 1).padStart(2, "0");
    var day = String(d.getUTCDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function clamp(v, a, b) {
    return Math.max(a, Math.min(b, v));
  }

  function dateProgress(start, end, date) {
    var a = start.getTime();
    var b = end.getTime();
    if (b <= a) return 0;
    return clamp((date.getTime() - a) / (b - a), 0, 1);
  }

  function dateAtProgress(start, end, t) {
    var ms = lerp(start.getTime(), end.getTime(), clamp(t, 0, 1));
    return new Date(ms);
  }

  function detectLowPower() {
    var cores = navigator.hardwareConcurrency || 4;
    var mem = navigator.deviceMemory || 4;
    var mobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
    return cores <= 4 || mem <= 4 || mobile;
  }

  function planetLabel(en) {
    var ja = PLANET_JA[en];
    return ja ? en.toUpperCase() + "（" + ja + "）" : String(en).toUpperCase();
  }

  function aspectTitle(ev) {
    return (
      String(ev.transit_planet || "").toUpperCase() +
      " " +
      String(ev.aspect || "").toUpperCase() +
      " " +
      String(ev.natal_planet || "").toUpperCase()
    );
  }

  function aspectJaLine(ev) {
    var t = PLANET_JA[ev.transit_planet] || ev.transit_planet;
    var n = PLANET_JA[ev.natal_planet] || ev.natal_planet;
    var a = ASPECT_JA[ev.aspect] || ev.aspect;
    return "トランジット " + t + " × ネイタル " + n + " · " + a;
  }

  // ── Error UI ─────────────────────────────────────────
  function showError(msg) {
    if (el.errorMsg) el.errorMsg.textContent = msg || "読み込みに失敗しました。";
    if (el.error) el.error.hidden = false;
    if (el.loading) el.loading.classList.add("is-hidden");
  }

  function hideError() {
    if (el.error) el.error.hidden = true;
  }

  // ── Data ─────────────────────────────────────────────
  function setYamlStatus(msg, kind) {
    if (!el.yamlStatus) return;
    el.yamlStatus.textContent = msg || "";
    el.yamlStatus.classList.remove("is-error", "is-ok");
    if (kind === "error") el.yamlStatus.classList.add("is-error");
    if (kind === "ok") el.yamlStatus.classList.add("is-ok");
  }

  function setCopyStatus(msg, kind) {
    if (!el.copyStatus) return;
    el.copyStatus.textContent = msg || "";
    el.copyStatus.classList.remove("is-error", "is-ok");
    if (kind === "error") el.copyStatus.classList.add("is-error");
    if (kind === "ok") el.copyStatus.classList.add("is-ok");
  }

  function loadSampleData() {
    if (window.TRANSIT_FLIGHT_DATA) {
      return Promise.resolve(window.TRANSIT_FLIGHT_DATA);
    }
    return fetch(DATA_URL, { credentials: "same-origin" }).then(function (res) {
      if (!res.ok) throw new Error("データの取得に失敗しました（" + res.status + "）");
      return res.json();
    });
  }

  function parseApiData(res) {
    return res.json().then(function (body) {
      if (!res.ok || !body || !body.ok) {
        var msg = (body && body.error) || "データの変換に失敗しました（" + res.status + "）";
        throw new Error(msg);
      }
      return body.data;
    });
  }

  function loadYamlData(yamlText) {
    return fetch(YAML_API, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml_text: yamlText, max_events: 10 })
    }).then(parseApiData);
  }

  function loadChartUrlData(ref) {
    var q = encodeURIComponent(ref);
    // GET is cache-friendly for deep links; POST also works via YAML_API
    return fetch(URL_API + "?load=" + q + "&max_events=10", {
      credentials: "same-origin"
    }).then(parseApiData);
  }

  function queryLoadRef() {
    try {
      var params = new URLSearchParams(window.location.search || "");
      return (
        params.get("load") ||
        params.get("chart_url") ||
        params.get("url") ||
        params.get("yaml_url") ||
        params.get("chart") ||
        params.get("chart_id") ||
        ""
      ).trim();
    } catch (_) {
      return "";
    }
  }

  function applyData(raw) {
    state.data = normalizeData(raw);
    fillProfile(state.data);
    if (scene) {
      rebuildEvents(state.data);
    }
    return state.data;
  }

  function normalizeData(raw) {
    if (!raw || !raw.profile || !Array.isArray(raw.events)) {
      throw new Error("データ形式が不正です。");
    }
    var profile = raw.profile;
    var start = parseDate(profile.period_start);
    var end = parseDate(profile.period_end);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      throw new Error("期間の日付が不正です。");
    }
    var events = raw.events
      .map(function (e, i) {
        var d = parseDate(e.date);
        var level = clamp(Math.round(+e.level || 1), 1, 3);
        var aspect = String(e.aspect || "conjunction").toLowerCase();
        if (!ASPECT_COLOR[aspect]) aspect = "conjunction";
        return {
          id: i,
          date: d,
          dateStr: e.date,
          transit_planet: e.transit_planet || "Unknown",
          natal_planet: e.natal_planet || "Unknown",
          aspect: aspect,
          orb: typeof e.orb === "number" ? e.orb : parseFloat(e.orb) || 0,
          level: level,
          theme: e.theme || "",
          progress: dateProgress(start, end, d)
        };
      })
      .filter(function (e) {
        return !isNaN(e.date.getTime());
      })
      .sort(function (a, b) {
        return a.date - b.date;
      });

    // Place events along track (leave margin at start/end)
    events.forEach(function (e) {
      e.z = -lerp(18, TRACK_LENGTH - 12, e.progress);
    });

    return {
      profile: profile,
      periodStart: start,
      periodEnd: end,
      events: events
    };
  }

  function fillProfile(data) {
    if (el.profileName) el.profileName.textContent = data.profile.name || "Sample";
    if (el.profileBirth) el.profileBirth.textContent = data.profile.birth_date || "—";
    if (el.profilePeriod) {
      el.profilePeriod.textContent =
        (data.profile.period_start || "") + " 〜 " + (data.profile.period_end || "");
    }
  }

  // ── Scene build ──────────────────────────────────────
  function createStarField(count) {
    var geo = new THREE.BufferGeometry();
    var pos = new Float32Array(count * 3);
    var i, r, th, ph;
    for (i = 0; i < count; i++) {
      // cylinder-ish distribution ahead and around path
      r = 8 + Math.random() * 90;
      th = Math.random() * Math.PI * 2;
      ph = (Math.random() - 0.5) * 1.4;
      pos[i * 3] = Math.cos(th) * r * Math.cos(ph);
      pos[i * 3 + 1] = Math.sin(ph) * r * 0.7 + (Math.random() - 0.5) * 20;
      pos[i * 3 + 2] = -Math.random() * (TRACK_LENGTH + 80);
    }
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var mat = new THREE.PointsMaterial({
      color: 0xc8d4ff,
      size: state.lowPower ? 0.55 : 0.7,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.85,
      depthWrite: false
    });
    return new THREE.Points(geo, mat);
  }

  function createStreaks(count) {
    var geo = new THREE.BufferGeometry();
    var pos = new Float32Array(count * 3);
    var i;
    for (i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 40;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 24;
      pos[i * 3 + 2] = -Math.random() * 120;
    }
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var mat = new THREE.PointsMaterial({
      color: 0xaaccff,
      size: 0.15,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.35,
      depthWrite: false
    });
    return new THREE.Points(geo, mat);
  }

  function createDust(count) {
    var geo = new THREE.BufferGeometry();
    var pos = new Float32Array(count * 3);
    var i;
    for (i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 30;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 18;
      pos[i * 3 + 2] = -Math.random() * (TRACK_LENGTH + 40);
    }
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var mat = new THREE.PointsMaterial({
      color: 0x8866cc,
      size: 0.35,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.4,
      depthWrite: false
    });
    return new THREE.Points(geo, mat);
  }

  function glowSphere(radius, color, opacity) {
    return new THREE.Mesh(
      new THREE.SphereGeometry(radius, state.lowPower ? 12 : 20, state.lowPower ? 12 : 20),
      new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: opacity,
        depthWrite: false
      })
    );
  }

  function ringMesh(inner, outer, color, opacity) {
    var geo = new THREE.RingGeometry(inner, outer, state.lowPower ? 24 : 48);
    var mat = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: opacity,
      side: THREE.DoubleSide,
      depthWrite: false
    });
    var m = new THREE.Mesh(geo, mat);
    m.rotation.y = Math.PI / 2;
    return m;
  }

  function lineLoop(points, color, opacity) {
    var geo = new THREE.BufferGeometry().setFromPoints(points);
    var mat = new THREE.LineBasicMaterial({
      color: color,
      transparent: true,
      opacity: opacity
    });
    return new THREE.LineLoop(geo, mat);
  }

  function buildAspectVisual(aspect, level, color) {
    var g = new THREE.Group();
    var scale = level === 3 ? 1.35 : level === 2 ? 1.0 : 0.55;
    var coreR = 0.55 * scale;
    var c = new THREE.Color(color);

    if (aspect === "conjunction") {
      var a = glowSphere(coreR * 1.1, color, 0.55);
      var b = glowSphere(coreR * 0.9, 0xffffff, 0.35);
      a.position.x = -0.35 * scale;
      b.position.x = 0.35 * scale;
      g.add(a, b);
      g.add(ringMesh(coreR * 1.6, coreR * 1.85, color, 0.45));
      g.add(ringMesh(coreR * 2.2, coreR * 2.4, 0xffffff, 0.2));
    } else if (aspect === "opposition") {
      var left = glowSphere(coreR, color, 0.6);
      var right = glowSphere(coreR, 0xaaccff, 0.55);
      left.position.x = -2.4 * scale;
      right.position.x = 2.4 * scale;
      g.add(left, right);
      var pts = [
        new THREE.Vector3(-2.4 * scale, 0, 0),
        new THREE.Vector3(2.4 * scale, 0, 0)
      ];
      g.add(
        new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.7 })
        )
      );
      g.add(ringMesh(coreR * 3.2, coreR * 3.45, color, 0.3));
    } else if (aspect === "square") {
      // Cross walls
      var wallGeo = new THREE.PlaneGeometry(0.12 * scale, 5.5 * scale);
      var wallMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.35,
        side: THREE.DoubleSide,
        depthWrite: false
      });
      var w1 = new THREE.Mesh(wallGeo, wallMat);
      var w2 = new THREE.Mesh(wallGeo, wallMat.clone());
      w1.rotation.z = Math.PI / 4;
      w2.rotation.z = -Math.PI / 4;
      g.add(w1, w2);
      g.add(glowSphere(coreR * 0.7, color, 0.7));
      g.add(ringMesh(coreR * 2.0, coreR * 2.25, color, 0.5));
    } else if (aspect === "trine") {
      var tri = [];
      var i, ang;
      for (i = 0; i < 3; i++) {
        ang = (i / 3) * Math.PI * 2 - Math.PI / 2;
        tri.push(
          new THREE.Vector3(Math.cos(ang) * 2.2 * scale, Math.sin(ang) * 2.2 * scale, 0)
        );
      }
      g.add(lineLoop(tri, color, 0.85));
      g.add(glowSphere(coreR, color, 0.55));
      // soft trailing arcs (glow shells)
      g.add(glowSphere(coreR * 2.4, color, 0.12));
    } else {
      // sextile — hexagon
      var hex = [];
      for (i = 0; i < 6; i++) {
        ang = (i / 6) * Math.PI * 2;
        hex.push(
          new THREE.Vector3(Math.cos(ang) * 2.0 * scale, Math.sin(ang) * 2.0 * scale, 0)
        );
      }
      g.add(lineLoop(hex, color, 0.8));
      // crossing lines
      for (i = 0; i < 3; i++) {
        ang = (i / 3) * Math.PI;
        var p1 = new THREE.Vector3(Math.cos(ang) * 2.0 * scale, Math.sin(ang) * 2.0 * scale, 0);
        var p2 = new THREE.Vector3(
          Math.cos(ang + Math.PI) * 2.0 * scale,
          Math.sin(ang + Math.PI) * 2.0 * scale,
          0
        );
        g.add(
          new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([p1, p2]),
            new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.45 })
          )
        );
      }
      g.add(glowSphere(coreR * 0.8, color, 0.5));
    }

    // Level-3 outer gate frame
    if (level >= 3) {
      g.add(ringMesh(3.6 * scale, 3.85 * scale, 0xc9a96e, 0.4));
      g.add(ringMesh(4.3 * scale, 4.45 * scale, color, 0.22));
    } else if (level === 2) {
      g.add(ringMesh(2.8 * scale, 3.0 * scale, color, 0.28));
    }

    // Soft approach glow (large, faint)
    var halo = glowSphere(6 * scale, color, 0.04);
    g.add(halo);

    g.userData.color = c;
    g.userData.baseScale = 1;
    return g;
  }

  function disposeObject3D(obj) {
    if (!obj) return;
    obj.traverse(function (child) {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach(function (m) {
            m.dispose();
          });
        } else {
          child.material.dispose();
        }
      }
    });
  }

  function buildEvents(data) {
    eventGroup = new THREE.Group();
    eventNodes = [];
    data.events.forEach(function (ev) {
      var color = ASPECT_COLOR[ev.aspect] || 0xffffff;
      var visual = buildAspectVisual(ev.aspect, ev.level, color);
      // slight lateral offset by aspect type for variety
      var offsetX = 0;
      if (ev.aspect === "opposition") offsetX = 0;
      else if (ev.aspect === "square") offsetX = (ev.id % 2 === 0 ? -1.2 : 1.2);
      else offsetX = (Math.sin(ev.id * 1.7) * 1.5);
      visual.position.set(offsetX, Math.cos(ev.id) * 0.4, ev.z);
      visual.userData.event = ev;
      visual.userData.hitRadius = ev.level === 3 ? 8 : ev.level === 2 ? 5.5 : 3.5;
      eventGroup.add(visual);
      eventNodes.push(visual);
    });
    scene.add(eventGroup);
  }

  function rebuildEvents(data) {
    if (eventGroup && scene) {
      scene.remove(eventGroup);
      disposeObject3D(eventGroup);
    }
    eventGroup = null;
    eventNodes = [];
    buildEvents(data);
  }

  function initThree() {
    if (typeof THREE === "undefined") {
      throw new Error("Three.js の読み込みに失敗しました。ネットワークを確認してください。");
    }

    state.lowPower = detectLowPower();
    state.reducedMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    try {
      renderer = new THREE.WebGLRenderer({
        canvas: el.canvas,
        antialias: !state.lowPower,
        alpha: false,
        powerPreference: "default"
      });
    } catch (err) {
      throw new Error("この端末では3D表示（WebGL）を利用できません。");
    }
    if (!renderer || !renderer.getContext || !renderer.getContext()) {
      throw new Error("この端末では3D表示（WebGL）を利用できません。");
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, state.lowPower ? 1.25 : 1.75));
    renderer.setClearColor(0x050810, 1);

    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x050810, 0.012);

    camera = new THREE.PerspectiveCamera(62, 1, 0.1, 500);
    camera.position.set(0, 0.4, 6);

    scene.add(new THREE.AmbientLight(0x6688aa, 0.55));
    var dir = new THREE.DirectionalLight(0xffe8c8, 0.35);
    dir.position.set(4, 8, 2);
    scene.add(dir);

    var starCount = state.lowPower ? 900 : 2200;
    var streakCount = state.lowPower ? 120 : 280;
    var dustCount = state.lowPower ? 200 : 500;
    if (state.reducedMotion) {
      starCount = Math.floor(starCount * 0.5);
      streakCount = Math.floor(streakCount * 0.3);
      dustCount = Math.floor(dustCount * 0.4);
    }

    starPoints = createStarField(starCount);
    streakPoints = createStreaks(streakCount);
    dustPoints = createDust(dustCount);
    scene.add(starPoints, streakPoints, dustPoints);

    buildEvents(state.data);
    resize();
  }

  function resize() {
    if (!renderer || !camera || !el.root) return;
    var w = el.root.clientWidth || window.innerWidth;
    var h = el.root.clientHeight || window.innerHeight;
    if (w < 1 || h < 1) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  // ── Flight logic ─────────────────────────────────────
  function setPhase(phase) {
    state.phase = phase;
    if (phase === "title") {
      el.title.classList.remove("is-hidden");
      el.title.classList.add("is-interactive");
      el.hud.classList.remove("is-visible");
      el.end.classList.add("is-hidden");
      el.end.classList.remove("is-interactive");
      hideEventCard();
    } else if (phase === "warp" || phase === "flight") {
      el.title.classList.add("is-hidden");
      el.title.classList.remove("is-interactive");
      el.hud.classList.add("is-visible");
      el.end.classList.add("is-hidden");
      el.end.classList.remove("is-interactive");
    } else if (phase === "end") {
      el.hud.classList.remove("is-visible");
      hideEventCard();
      showEndScreen();
    }
  }

  function hideEventCard() {
    el.eventCard.classList.remove("is-visible");
    if (state.eventHideTimer) {
      clearTimeout(state.eventHideTimer);
      state.eventHideTimer = 0;
    }
  }

  function showEventCard(ev) {
    el.eventLevel.textContent = LEVEL_LABEL[ev.level] || LEVEL_LABEL[1];
    el.eventTitle.textContent = aspectTitle(ev);
    el.eventJa.textContent = aspectJaLine(ev);
    el.eventMeta.innerHTML =
      "<span>Peak: " +
      ev.dateStr +
      "</span><span>Orb: " +
      (typeof ev.orb === "number" ? ev.orb.toFixed(2) : ev.orb) +
      "°</span><span>強度: L" +
      ev.level +
      "</span>";
    el.eventTheme.textContent = ev.theme || "";
    el.eventCard.classList.add("is-visible");

    if (state.eventHideTimer) clearTimeout(state.eventHideTimer);
    state.eventHideTimer = setTimeout(function () {
      // keep major events a bit longer is already in EVENT_SHOW_MS; just hide
      if (state.activeEventIdx === ev.id) {
        el.eventCard.classList.remove("is-visible");
      }
    }, EVENT_SHOW_MS + (ev.level === 3 ? 1200 : 0));
  }

  function pickMajorEvents(events, n) {
    var sorted = events.slice().sort(function (a, b) {
      if (b.level !== a.level) return b.level - a.level;
      return a.orb - b.orb;
    });
    return sorted.slice(0, n);
  }

  function showEndScreen() {
    var majors = pickMajorEvents(state.data.events, 5);
    el.summaryList.innerHTML = "";
    majors.forEach(function (ev) {
      var li = document.createElement("li");
      li.innerHTML =
        '<div class="s-date">' +
        ev.dateStr +
        " · L" +
        ev.level +
        "</div>" +
        '<div class="s-title">' +
        aspectTitle(ev) +
        "</div>" +
        '<div class="s-theme">' +
        (ev.theme || "") +
        "</div>";
      el.summaryList.appendChild(li);
    });
    el.end.classList.remove("is-hidden");
    el.end.classList.add("is-interactive");
  }

  function startFlight() {
    state.flightT = 0;
    state.warpT = 0;
    state.paused = false;
    state.speedMul = 1;
    state.activeEventIdx = -1;
    state.shownEvents = {};
    state.lookX = 0;
    state.lookY = 0;
    state.targetLookX = 0;
    state.targetLookY = 0;
    hideEventCard();
    el.pauseBadge.classList.remove("is-on");
    camera.position.set(0, 0.4, 6);
    if (state.reducedMotion) {
      // Skip intense warp
      setPhase("flight");
    } else {
      setPhase("warp");
    }
  }

  function togglePause() {
    if (state.phase !== "flight" && state.phase !== "warp") return;
    if (state.phase === "warp") return; // no pause mid-warp
    state.paused = !state.paused;
    el.pauseBadge.classList.toggle("is-on", state.paused);
    el.pauseBadge.textContent = state.paused ? "PAUSED" : "";
  }

  function checkEvents(camZ) {
    var nearest = -1;
    var nearestDist = 999;
    var i, node, ev, dz, absDz;
    for (i = 0; i < eventNodes.length; i++) {
      node = eventNodes[i];
      ev = node.userData.event;
      dz = node.position.z - camZ;
      absDz = Math.abs(dz);
      // approaching or just passed
      if (absDz < node.userData.hitRadius && !state.shownEvents[ev.id]) {
        if (absDz < nearestDist) {
          nearestDist = absDz;
          nearest = i;
        }
      }
      // scale pulse when near
      var proximity = 1 - clamp(absDz / 25, 0, 1);
      var pulse = 1 + proximity * 0.18 * (ev.level * 0.35);
      node.scale.setScalar(pulse);
      node.rotation.z += 0.003 * (ev.level === 3 ? 1.2 : 0.6);
      // fade materials slightly by distance — skip for perf on low power
    }
    if (nearest >= 0) {
      var hit = eventNodes[nearest].userData.event;
      state.shownEvents[hit.id] = true;
      state.activeEventIdx = hit.id;
      showEventCard(hit);
    }
  }

  function ambientForProgress(t, nearEventLevel) {
    // Quiet vs tense atmosphere
    var base = ambientNearColor.clone().lerp(ambientFarColor, t);
    if (nearEventLevel >= 3) {
      base.lerp(new THREE.Color(0x1a1028), 0.25);
    } else if (nearEventLevel >= 2) {
      base.lerp(new THREE.Color(0x101828), 0.15);
    }
    return base;
  }

  function nearestEventLevel(camZ) {
    var best = 0;
    var bestD = 30;
    eventNodes.forEach(function (node) {
      var d = Math.abs(node.position.z - camZ);
      if (d < bestD) {
        bestD = d;
        best = node.userData.event.level;
      }
    });
    return bestD < 22 ? best : 0;
  }

  function updateWarp(dt) {
    state.warpT += dt / (WARP_DURATION_MS / 1000);
    var t = clamp(state.warpT, 0, 1);
    warpBoost = Math.sin(t * Math.PI) * 3.5;
    // streak stretch feel via material size
    if (streakPoints) {
      streakPoints.material.size = 0.15 + warpBoost * 0.35;
      streakPoints.material.opacity = 0.35 + warpBoost * 0.35;
    }
    // move camera slightly forward
    camera.position.z = 6 - t * 8;
    // swirl stars
    if (starPoints) starPoints.rotation.z += dt * 0.4;
    if (t >= 1) {
      warpBoost = 0;
      if (streakPoints) {
        streakPoints.material.size = 0.15;
        streakPoints.material.opacity = 0.35;
      }
      setPhase("flight");
    }
  }

  function updateFlight(dt) {
    if (state.paused) return;
    var nearLvl = nearestEventLevel(camera.position.z);
    // Slow slightly near major events for readability
    var approachFactor = nearLvl >= 3 ? 0.72 : nearLvl === 2 ? 0.85 : 1;
    var speed = state.speedMul * approachFactor;
    if (state.reducedMotion) speed *= 0.85;

    state.flightT += (dt * 1000 * speed) / FLIGHT_DURATION_MS;
    state.flightT = clamp(state.flightT, 0, 1);

    var z = lerp(6, -TRACK_LENGTH, state.flightT);
    camera.position.z = z;
    camera.position.x = state.lookX * 1.8;
    camera.position.y = 0.4 + state.lookY * 1.2;

    // look slightly ahead with mouse offset
    camera.lookAt(
      state.lookX * 2.5,
      0.2 + state.lookY * 1.5,
      z - 12
    );

    // date HUD
    var cur = dateAtProgress(state.data.periodStart, state.data.periodEnd, state.flightT);
    el.dateLabel.textContent = formatDate(cur);
    el.progressFill.style.width = (state.flightT * 100).toFixed(1) + "%";

    // ambient
    var amb = ambientForProgress(state.flightT, nearLvl);
    renderer.setClearColor(amb.getHex(), 1);
    if (scene.fog) scene.fog.color.copy(amb);

    // particle drift relative to motion
    if (streakPoints) {
      var arr = streakPoints.geometry.attributes.position.array;
      var i;
      for (i = 0; i < arr.length; i += 3) {
        arr[i + 2] += dt * (18 + speed * 40);
        if (arr[i + 2] > camera.position.z + 8) {
          arr[i] = (Math.random() - 0.5) * 40;
          arr[i + 1] = (Math.random() - 0.5) * 24;
          arr[i + 2] = camera.position.z - 40 - Math.random() * 80;
        }
      }
      streakPoints.geometry.attributes.position.needsUpdate = true;
    }

    checkEvents(camera.position.z);

    // end of track
    if (state.flightT >= 1) {
      // decelerate feel: brief hold then end
      setPhase("end");
    }
  }

  function tick(ts) {
    if (state.destroyed) return;
    state.raf = requestAnimationFrame(tick);
    if (!state.lastTs) state.lastTs = ts;
    var dt = Math.min(0.05, (ts - state.lastTs) / 1000);
    state.lastTs = ts;

    // smooth look
    state.lookX = lerp(state.lookX, state.targetLookX, 0.08);
    state.lookY = lerp(state.lookY, state.targetLookY, 0.08);

    if (state.phase === "warp") {
      updateWarp(dt);
      // keep looking forward during warp
      camera.lookAt(0, 0.2, camera.position.z - 20);
    } else if (state.phase === "flight") {
      updateFlight(dt);
    } else if (state.phase === "title") {
      // idle drift
      camera.position.z = 6 + Math.sin(ts * 0.0003) * 0.3;
      camera.position.y = 0.4 + Math.sin(ts * 0.0004) * 0.08;
      camera.lookAt(0, 0.2, camera.position.z - 12);
      if (starPoints) starPoints.rotation.z += dt * 0.02;
      if (dustPoints) dustPoints.rotation.y += dt * 0.01;
    } else if (state.phase === "end") {
      // slow drift at end
      camera.position.z = -TRACK_LENGTH + Math.sin(ts * 0.0002) * 0.5;
      camera.lookAt(0, 0.2, camera.position.z - 8);
    }

    // gentle event spin always
    if (eventNodes && (state.phase === "flight" || state.phase === "title" || state.phase === "end")) {
      var j;
      for (j = 0; j < eventNodes.length; j++) {
        eventNodes[j].rotation.y += dt * 0.15;
      }
    }

    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  }

  // ── Input ────────────────────────────────────────────
  function onPointerMove(e) {
    if (state.phase !== "flight" && state.phase !== "warp" && state.phase !== "title") return;
    if (state.drag) return; // drag handles look
    // subtle mouse-look on desktop
    if (e.pointerType === "mouse" || e.pointerType === "pen") {
      var nx = (e.clientX / window.innerWidth) * 2 - 1;
      var ny = (e.clientY / window.innerHeight) * 2 - 1;
      state.targetLookX = nx * 0.35;
      state.targetLookY = -ny * 0.22;
    }
  }

  function onPointerDown(e) {
    if (state.phase === "end" || state.phase === "title") return;
    state.drag = {
      id: e.pointerId,
      x: e.clientX,
      y: e.clientY,
      lookX: state.targetLookX,
      lookY: state.targetLookY
    };
    try {
      el.canvas.setPointerCapture(e.pointerId);
    } catch (_) {}
    el.canvas.classList.add("is-dragging");

    // Tap to re-show nearest event (mobile)
    if (e.pointerType === "touch") {
      state.touch = { t: performance.now(), x: e.clientX, y: e.clientY };
    }
  }

  function onPointerUp(e) {
    if (state.drag && state.drag.id === e.pointerId) {
      // tap detection for event detail
      if (state.touch && performance.now() - state.touch.t < 280) {
        var dx = Math.abs(e.clientX - state.touch.x);
        var dy = Math.abs(e.clientY - state.touch.y);
        if (dx < 12 && dy < 12) {
          showNearestEventDetail();
        }
      }
      state.drag = null;
      state.touch = null;
      el.canvas.classList.remove("is-dragging");
    }
  }

  function onPointerMoveDrag(e) {
    if (!state.drag || state.drag.id !== e.pointerId) {
      onPointerMove(e);
      return;
    }
    var dx = (e.clientX - state.drag.x) / window.innerWidth;
    var dy = (e.clientY - state.drag.y) / window.innerHeight;
    state.targetLookX = clamp(state.drag.lookX + dx * 1.8, -1, 1);
    state.targetLookY = clamp(state.drag.lookY - dy * 1.4, -0.7, 0.7);
  }

  function showNearestEventDetail() {
    if (state.phase !== "flight") return;
    var camZ = camera.position.z;
    var best = null;
    var bestD = 18;
    eventNodes.forEach(function (node) {
      var d = Math.abs(node.position.z - camZ);
      if (d < bestD) {
        bestD = d;
        best = node.userData.event;
      }
    });
    if (best) {
      state.activeEventIdx = best.id;
      showEventCard(best);
    }
  }

  function onWheel(e) {
    if (state.phase !== "flight") return;
    e.preventDefault();
    var delta = e.deltaY > 0 ? -0.08 : 0.08;
    state.speedMul = clamp(state.speedMul + delta, 0.4, 2.2);
  }

  function onKey(e) {
    if (e.code === "Space") {
      // don't steal space from buttons
      if (e.target && (e.target.tagName === "BUTTON" || e.target.tagName === "A")) return;
      e.preventDefault();
      togglePause();
    }
  }

  function setControlsHint() {
    if (!el.controlsHint) return;
    var mobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
    el.controlsHint.textContent = mobile
      ? "スワイプで視点 · タップで詳細 · 自動飛行"
      : "マウスで視点 · ドラッグ調整 · ホイールで速度 · Space 一時停止";
  }

  function reportLoadOk(raw) {
    applyData(raw);
    var n = state.data.events.length;
    setYamlStatus(
      "読み込み完了: " + n + "件のイベント（" +
        state.data.profile.period_start + " 〜 " +
        state.data.profile.period_end + "）",
      "ok"
    );
  }

  function onLoadYamlClick() {
    var text = el.yamlInput ? el.yamlInput.value : "";
    if (!text || !String(text).trim()) {
      setYamlStatus("YAMLを貼り付けてから読み込んでください。", "error");
      return;
    }
    if (el.loadYamlBtn) el.loadYamlBtn.disabled = true;
    setYamlStatus("YAMLを変換中…", null);
    loadYamlData(text)
      .then(reportLoadOk)
      .catch(function (err) {
        console.error("[TransitFlight] yaml", err);
        setYamlStatus(err && err.message ? err.message : "YAMLの読み込みに失敗しました。", "error");
      })
      .then(function () {
        if (el.loadYamlBtn) el.loadYamlBtn.disabled = false;
      });
  }

  function onLoadUrlClick() {
    var ref = el.urlInput ? String(el.urlInput.value || "").trim() : "";
    if (!ref) {
      setYamlStatus("Chart URL または chart_id を入力してください。", "error");
      return;
    }
    if (el.loadUrlBtn) el.loadUrlBtn.disabled = true;
    setYamlStatus("Chart URL を読み込み中…", null);
    loadChartUrlData(ref)
      .then(reportLoadOk)
      .catch(function (err) {
        console.error("[TransitFlight] url", err);
        setYamlStatus(err && err.message ? err.message : "URLの読み込みに失敗しました。", "error");
      })
      .then(function () {
        if (el.loadUrlBtn) el.loadUrlBtn.disabled = false;
      });
  }

  function onUseSampleClick() {
    if (el.useSampleBtn) el.useSampleBtn.disabled = true;
    setYamlStatus("サンプルを読み込み中…", null);
    loadSampleData()
      .then(function (raw) {
        applyData(raw);
        if (el.yamlInput) el.yamlInput.value = "";
        if (el.urlInput) el.urlInput.value = "";
        setYamlStatus("サンプルデータを読み込みました。", "ok");
      })
      .catch(function (err) {
        setYamlStatus(err && err.message ? err.message : "サンプルの読み込みに失敗しました。", "error");
      })
      .then(function () {
        if (el.useSampleBtn) el.useSampleBtn.disabled = false;
      });
  }

  function onCopyDataClick() {
    if (!state.data) return;
    var payload = {
      app: "transit_flight",
      profile: state.data.profile,
      events: state.data.events.map(function (e) {
        return {
          date: e.dateStr || formatDate(e.date),
          transit_planet: e.transit_planet,
          natal_planet: e.natal_planet,
          aspect: e.aspect,
          orb: e.orb,
          level: e.level,
          theme: e.theme
        };
      }),
      note: "計算済みトランジットの飛行用要約です。日付から再計算せず、この値を根拠にしてください。"
    };
    var text = JSON.stringify(payload, null, 2);
    function ok() {
      setCopyStatus("コピーしました。", "ok");
    }
    function fail() {
      setCopyStatus("コピーに失敗しました。手動で選択してください。", "error");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok).catch(fail);
    } else {
      try {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        ok();
      } catch (_) {
        fail();
      }
    }
  }

  function bindInput() {
    if (state.inputBound) return;
    state.inputBound = true;
    window.addEventListener("resize", resize);
    window.addEventListener("keydown", onKey);
    el.canvas.addEventListener("pointermove", onPointerMoveDrag);
    el.canvas.addEventListener("pointerdown", onPointerDown);
    el.canvas.addEventListener("pointerup", onPointerUp);
    el.canvas.addEventListener("pointercancel", onPointerUp);
    el.canvas.addEventListener("wheel", onWheel, { passive: false });

    el.startBtn.addEventListener("click", function () {
      if (!state.data || !state.data.events.length) {
        setYamlStatus("先にデータを読み込んでください。", "error");
        return;
      }
      startFlight();
    });
    el.replayBtn.addEventListener("click", function () {
      startFlight();
    });
    if (el.loadYamlBtn) el.loadYamlBtn.addEventListener("click", onLoadYamlClick);
    if (el.loadUrlBtn) el.loadUrlBtn.addEventListener("click", onLoadUrlClick);
    if (el.useSampleBtn) el.useSampleBtn.addEventListener("click", onUseSampleClick);
    if (el.copyDataBtn) el.copyDataBtn.addEventListener("click", onCopyDataClick);
    if (el.urlInput) {
      el.urlInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          onLoadUrlClick();
        }
      });
    }
    if (el.errorRetry) {
      el.errorRetry.addEventListener("click", function () {
        hideError();
        boot();
      });
    }

    // Pause when tab hidden
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", destroy);
  }

  function unbindInput() {
    if (!state.inputBound) return;
    state.inputBound = false;
    window.removeEventListener("resize", resize);
    window.removeEventListener("keydown", onKey);
    el.canvas.removeEventListener("pointermove", onPointerMoveDrag);
    el.canvas.removeEventListener("pointerdown", onPointerDown);
    el.canvas.removeEventListener("pointerup", onPointerUp);
    el.canvas.removeEventListener("pointercancel", onPointerUp);
    el.canvas.removeEventListener("wheel", onWheel);
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("pagehide", destroy);
  }

  function onVisibility() {
    if (document.hidden) {
      if (state.phase === "flight" && !state.paused) {
        state.paused = true;
        el.pauseBadge.classList.add("is-on");
        el.pauseBadge.textContent = "PAUSED";
      }
    }
  }

  // ── Lifecycle ────────────────────────────────────────
  function destroy() {
    if (state.destroyed) return;
    state.destroyed = true;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    if (state.eventHideTimer) clearTimeout(state.eventHideTimer);
    unbindInput();
    if (renderer) {
      try {
        renderer.dispose();
      } catch (_) {}
    }
    // dispose geometries/materials lightly
    if (scene) {
      scene.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach(function (m) {
              m.dispose();
            });
          } else {
            obj.material.dispose();
          }
        }
      });
    }
    renderer = null;
    scene = null;
    camera = null;
  }

  function boot() {
    state.destroyed = false;
    state.phase = "loading";
    hideError();
    if (el.loading) el.loading.classList.remove("is-hidden");

    var deepRef = queryLoadRef();
    var initial;
    if (deepRef) {
      if (el.urlInput) el.urlInput.value = deepRef;
      setYamlStatus("URLパラメータから読み込み中…", null);
      initial = loadChartUrlData(deepRef).then(function (raw) {
        return { raw: raw, mode: "url" };
      }).catch(function (err) {
        // fall back to sample so the page is still usable
        console.error("[TransitFlight] deep-link", err);
        return loadSampleData().then(function (raw) {
          return { raw: raw, mode: "sample", deepError: err && err.message ? err.message : "URL読み込みに失敗" };
        });
      });
    } else {
      initial = loadSampleData().then(function (raw) {
        return { raw: raw, mode: "sample" };
      });
    }

    initial
      .then(function (pack) {
        applyData(pack.raw);
        initThree();
        setControlsHint();
        bindInput();
        if (el.loading) el.loading.classList.add("is-hidden");
        setPhase("title");
        if (pack.mode === "url") {
          reportLoadOk(pack.raw);
        } else if (pack.deepError) {
          setYamlStatus(
            "URL読み込み失敗: " + pack.deepError + " — サンプルを表示中です。",
            "error"
          );
        } else {
          setYamlStatus("サンプル表示中。Chart URL または YAML で差し替えできます。", null);
        }
        state.lastTs = 0;
        state.raf = requestAnimationFrame(tick);
      })
      .catch(function (err) {
        console.error("[TransitFlight]", err);
        showError(err && err.message ? err.message : "初期化に失敗しました。");
      });
  }

  // Expose for debugging / future API inject
  window.TransitFlight = {
    restart: function () {
      if (state.phase === "flight" || state.phase === "end" || state.phase === "title") {
        startFlight();
      }
    },
    destroy: destroy,
    getState: function () {
      return { phase: state.phase, flightT: state.flightT, paused: state.paused };
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
