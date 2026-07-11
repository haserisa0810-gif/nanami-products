/**
 * Birth Chart Museum entrance — JA/EN, YAML handoff, no auto-start tour
 */
(function () {
  "use strict";

  var STR = {
    ja: {
      eyebrow: "INTERACTIVE EXHIBITION",
      lead: "ホロスコープを読むのではなく、出生図の中を歩く。\n体験の入り口を選んでください。",
      yaml_title: "出生図 YAML（任意）",
      yaml_help:
        "ここで貼って「この図を使う」と、入館後の各版に引き継がれます。ツアーは自動では始まりません。",
      yaml_save: "この図を使う",
      yaml_neko: "ねこ編集長",
      yaml_clear: "クリア",
      yaml_ok: "保存しました。入館先で使われます。",
      yaml_neko_ok: "ねこ編集長をセットしました。",
      yaml_cleared: "クリアしました。",
      yaml_empty: "YAMLを貼るか、「ねこ編集長」を選んでください。",
      abs_kicker: "本線 · Abstract",
      abs_title: "象徴ミュージアム",
      abs_body:
        "低ポリの象徴空間。ガイドツアー・YAML読込・日英対応が揃った、コンセプトの中心版です。",
      abs_f1: "ガイドが「何を見るか」を案内",
      abs_f2: "クリック歩行 · YAML出生図",
      abs_f3: "日本語 / English",
      abs_cta_guide: "入館（ガイド推奨）",
      abs_cta_free: "入館（自由）",
      arch_kicker: "実験 · Architecture",
      arch_title: "建築ミュージアム",
      arch_body:
        "邸宅・劇場・天文台など、現実にありそうな棟として歩ける試作です。素材とスケールを寄せています。",
      arch_f1: "全12棟の建築ボリューム",
      arch_f2: "4 / 5 / 9 を特に厚く",
      arch_f3: "入館後にガイド開始（ボタン）",
      arch_cta_guide: "入館（ガイド推奨）",
      arch_cta_free: "入館（自由）",
      dream_kicker: "実験 · Dream",
      dream_title: "Dream Sky",
      dream_body:
        "建物のない象徴空間。第4・5・12を光と粒子で体験。上のYAMLがそのまま使えます。",
      dream_f1: "自分の YAML / ねこ編集長",
      dream_f2: "第4 湖 · 第5 舞台 · 第12 霧",
      dream_f3: "配置天体で光と粒子が変化",
      dream_cta: "Dream に入る",
      note: "鑑定・注文には接続しません。YAMLはブラウザ内のみ。入口の図は各版（Dream含む）に引き継がれます。",
      back: "← nanami-products へ戻る",
    },
    en: {
      eyebrow: "INTERACTIVE EXHIBITION",
      lead: "Don’t read the chart — walk inside it.\nChoose your entrance.",
      yaml_title: "Natal YAML (optional)",
      yaml_help:
        "Paste and save here to carry the chart into each edition. Tours never auto-start.",
      yaml_save: "Use this chart",
      yaml_neko: "Neko sample",
      yaml_clear: "Clear",
      yaml_ok: "Saved — editions will pick this up.",
      yaml_neko_ok: "Neko sample set.",
      yaml_cleared: "Cleared.",
      yaml_empty: "Paste YAML or choose the Neko sample.",
      abs_kicker: "Main · Abstract",
      abs_title: "Symbolic Museum",
      abs_body:
        "Low-poly symbolic spaces. Guided tour, YAML load, and JA/EN — the core concept edition.",
      abs_f1: "Camera guide shows what to look at",
      abs_f2: "Click-to-walk · YAML natal charts",
      abs_f3: "Japanese / English",
      abs_cta_guide: "Enter (guide recommended)",
      abs_cta_free: "Enter freely",
      arch_kicker: "Experiment · Architecture",
      arch_title: "Architecture Museum",
      arch_body:
        "Walkable buildings that could exist — home, theater, observatory. Materials and scale first.",
      arch_f1: "All 12 architectural wings",
      arch_f2: "Houses 4 / 5 / 9 in depth",
      arch_f3: "Start guide with a button after entry",
      arch_cta_guide: "Enter (guide recommended)",
      arch_cta_free: "Enter freely",
      dream_kicker: "Experiment · Dream",
      dream_title: "Dream Sky",
      dream_body:
        "No buildings — houses 4 / 5 / 12 as light and particles. Uses the YAML saved above.",
      dream_f1: "Your YAML or Neko sample",
      dream_f2: "H4 lake · H5 stage · H12 mist",
      dream_f3: "Bodies change light & particles",
      dream_cta: "Enter Dream",
      note: "No order/billing. YAML stays in-browser and carries into each edition including Dream.",
      back: "← Back to nanami-products",
    },
  };

  // Marker only — editions treat "neko" pref without needing full YAML text
  var NEKO_MARKER = "__neko__";

  function detectLang() {
    try {
      var q = new URLSearchParams(location.search).get("lang");
      if (q === "en" || q === "ja") return q;
      var s = localStorage.getItem("ht-lang");
      if (s === "en" || s === "ja") return s;
    } catch (e) {}
    return (navigator.language || "en").toLowerCase().indexOf("ja") === 0 ? "ja" : "en";
  }

  var lang = detectLang();

  function t(key) {
    var pack = STR[lang] || STR.en;
    return pack[key] != null ? pack[key] : key;
  }

  function setStatus(msg, ok) {
    var el = document.getElementById("me-yaml-status");
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("is-ok", !!ok);
    el.classList.toggle("is-err", msg && !ok);
  }

  function applyI18n() {
    var pack = STR[lang] || STR.en;
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (!key || pack[key] == null) return;
      var text = pack[key];
      if (text.indexOf("\n") >= 0) {
        el.innerHTML = text.split("\n").join("<br>");
      } else {
        el.textContent = text;
      }
    });
    document.querySelectorAll(".me-lang-btn").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-lang") === lang);
    });
    ["me-abs-guide", "me-abs-free", "me-arch-guide", "me-arch-free", "me-dream-enter"].forEach(function (id) {
      var a = document.getElementById(id);
      if (!a) return;
      try {
        var u = new URL(a.getAttribute("href"), location.origin);
        u.searchParams.set("lang", lang);
        a.setAttribute("href", u.pathname + u.search);
      } catch (e) {}
    });
    try {
      localStorage.setItem("ht-lang", lang);
      var u = new URL(location.href);
      u.searchParams.set("lang", lang);
      history.replaceState({}, "", u.pathname + u.search);
    } catch (e) {}
  }

  function restoreYamlField() {
    var ta = document.getElementById("me-yaml-input");
    if (!ta) return;
    try {
      var pref = sessionStorage.getItem("ht-chart-pref");
      var saved = sessionStorage.getItem("ht-last-yaml");
      if (pref === "neko") {
        setStatus(t("yaml_neko_ok"), true);
        return;
      }
      if (saved && saved !== NEKO_MARKER) {
        ta.value = saved;
        setStatus(t("yaml_ok"), true);
      }
    } catch (e) {}
  }

  function saveYamlText(text) {
    try {
      sessionStorage.setItem("ht-last-yaml", text);
      sessionStorage.setItem("ht-chart-pref", "yaml");
      return true;
    } catch (e) {
      return false;
    }
  }

  function saveNeko() {
    try {
      sessionStorage.setItem("ht-chart-pref", "neko");
      // keep last yaml if any; pref wins for loaders that respect it
      return true;
    } catch (e) {
      return false;
    }
  }

  function clearChart() {
    try {
      sessionStorage.removeItem("ht-last-yaml");
      sessionStorage.removeItem("ht-chart-pref");
    } catch (e) {}
    var ta = document.getElementById("me-yaml-input");
    if (ta) ta.value = "";
  }

  document.querySelectorAll(".me-lang-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      lang = btn.getAttribute("data-lang") || "ja";
      applyI18n();
    });
  });

  var saveBtn = document.getElementById("me-yaml-save");
  if (saveBtn) {
    saveBtn.addEventListener("click", function () {
      var ta = document.getElementById("me-yaml-input");
      var text = ta ? ta.value.trim() : "";
      if (!text) {
        setStatus(t("yaml_empty"), false);
        return;
      }
      if (saveYamlText(text)) setStatus(t("yaml_ok"), true);
      else setStatus(t("yaml_empty"), false);
    });
  }

  var nekoBtn = document.getElementById("me-yaml-neko");
  if (nekoBtn) {
    nekoBtn.addEventListener("click", function () {
      if (saveNeko()) setStatus(t("yaml_neko_ok"), true);
    });
  }

  var clearBtn = document.getElementById("me-yaml-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      clearChart();
      setStatus(t("yaml_cleared"), true);
    });
  }

  // Before navigating into an edition, persist textarea if non-empty
  ["me-abs-guide", "me-abs-free", "me-arch-guide", "me-arch-free", "me-dream-enter"].forEach(function (id) {
    var a = document.getElementById(id);
    if (!a) return;
    a.addEventListener("click", function () {
      var ta = document.getElementById("me-yaml-input");
      var text = ta ? ta.value.trim() : "";
      if (text) {
        saveYamlText(text);
        try {
          sessionStorage.setItem("ds-last-yaml", text);
          sessionStorage.setItem("ds-chart-pref", "yaml");
        } catch (e) {}
      }
    });
  });

  applyI18n();
  restoreYamlField();
})();
