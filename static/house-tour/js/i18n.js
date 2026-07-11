/**
 * House Tour i18n — ja / en
 */
import { housesJa } from "./data/houses-ja.js";
import { housesEn } from "./data/houses-en.js";
import {
  planetTextsJa,
  comboText as comboTextJa,
} from "./data/planets-ja.js";
import { planetTextsEn, comboTextEn } from "./data/planets-en.js";
import { uiStrings, format } from "./data/ui-strings.js";

let lang = "ja";
const listeners = [];

export function detectLang() {
  try {
    const q = new URLSearchParams(window.location.search || "").get("lang");
    if (q === "en" || q === "ja") return q;
  } catch (e) { /* ignore */ }
  try {
    const saved = localStorage.getItem("ht-lang");
    if (saved === "en" || saved === "ja") return saved;
  } catch (e) { /* ignore */ }
  const nav = (navigator.language || "en").toLowerCase();
  return nav.startsWith("ja") ? "ja" : "en";
}

export function initLang(forced) {
  lang = forced === "en" || forced === "ja" ? forced : detectLang();
  applyDocumentLang();
  return lang;
}

export function getLang() {
  return lang;
}

export function setLang(next) {
  if (next !== "en" && next !== "ja") return lang;
  lang = next;
  try {
    localStorage.setItem("ht-lang", lang);
  } catch (e) { /* ignore */ }
  applyDocumentLang();
  // URL を静かに同期（履歴を汚しすぎない）
  try {
    const u = new URL(window.location.href);
    u.searchParams.set("lang", lang);
    window.history.replaceState({}, "", u.pathname + u.search + u.hash);
  } catch (e) { /* ignore */ }
  listeners.forEach((fn) => {
    try {
      fn(lang);
    } catch (err) {
      console.error(err);
    }
  });
  return lang;
}

export function onLangChange(fn) {
  listeners.push(fn);
}

function applyDocumentLang() {
  if (document.documentElement) document.documentElement.lang = lang;
  const title = t("page_title");
  if (title) document.title = title;
}

export function t(key, vars) {
  const pack = uiStrings[lang] || uiStrings.en;
  const fallback = uiStrings.en || {};
  const str = pack[key] != null ? pack[key] : fallback[key] != null ? fallback[key] : key;
  return vars ? format(str, vars) : str;
}

export function getHousesData() {
  return lang === "en" ? housesEn : housesJa;
}

export function getPlanetTexts() {
  return lang === "en" ? planetTextsEn : planetTextsJa;
}

export function getComboText(planetId, houseNumber) {
  return lang === "en"
    ? comboTextEn(planetId, houseNumber)
    : comboTextJa(planetId, houseNumber);
}

/** data-i18n / data-i18n-html / data-i18n-placeholder / data-i18n-title を反映 */
export function applyDomI18n(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!key) return;
    el.textContent = t(key);
  });
  scope.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const key = el.getAttribute("data-i18n-html");
    if (!key) return;
    el.innerHTML = t(key);
  });
  scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (!key) return;
    el.setAttribute("placeholder", t(key));
  });
  scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
    const key = el.getAttribute("data-i18n-title");
    if (!key) return;
    el.setAttribute("title", t(key));
  });
  // 言語トグルの見た目
  scope.querySelectorAll("[data-lang-set]").forEach((btn) => {
    const l = btn.getAttribute("data-lang-set");
    btn.classList.toggle("is-active", l === lang);
  });
}
