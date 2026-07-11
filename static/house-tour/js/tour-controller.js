/**
 * ガイドツアー（主役） / 自由探索（補助）
 * ガイド中はシネマティック案内 → ユーザーが「次へ」で進行
 */
export function createTourController(options) {
  let mode = "free"; // free | guide
  let current = 0; // 0 = core, 1-12
  let guideStep = 0; // 0 = intro at core, then 1..12
  let phase = "idle"; // idle | playing | waiting

  function getCurrent() {
    return current;
  }

  function getMode() {
    return mode;
  }

  function getPhase() {
    return phase;
  }

  function setPhase(p) {
    phase = p;
    options.onPhase && options.onPhase(p);
  }

  function setCurrent(n, opts) {
    opts = opts || {};
    current = Math.max(0, Math.min(12, n | 0));
    if (mode === "guide" && current >= 1) guideStep = current;
    options.onVisit && options.onVisit(current, opts);
  }

  function startGuide() {
    mode = "guide";
    guideStep = 0;
    current = 0;
    options.onMode && options.onMode("guide");
    options.onVisit && options.onVisit(0, { reason: "guide-start", playCinematic: true });
  }

  function startFree() {
    mode = "free";
    phase = "idle";
    options.onMode && options.onMode("free");
    setCurrent(0, { reason: "free-start", playCinematic: false });
  }

  /**
   * 「次へ」
   * - 案内再生中: ショット送り / 最後まで飛ばす
   * - 案内待ち: 次ハウスへ
   * - 自由: 次ハウスへ瞬間移動
   * @returns {'skip-shot'|'skip-all'|'advance'|'free-next'}
   */
  function next() {
    if (mode === "guide") {
      if (phase === "playing") {
        // シネマ側で処理（main が skip）
        return "skip-shot";
      }
      // waiting or idle after house
      if (guideStep < 12) {
        guideStep += 1;
        current = guideStep;
        options.onVisit &&
          options.onVisit(current, { reason: "guide-next", playCinematic: true });
        return "advance";
      }
      // 完了
      mode = "free";
      phase = "idle";
      options.onMode && options.onMode("free");
      options.onGuideComplete && options.onGuideComplete();
      setCurrent(0, { reason: "guide-done", playCinematic: false });
      return "advance";
    }
    // free
    if (current === 0) setCurrent(1, { reason: "next", playCinematic: false });
    else if (current >= 12) setCurrent(0, { reason: "next", playCinematic: false });
    else setCurrent(current + 1, { reason: "next", playCinematic: false });
    return "free-next";
  }

  function prev() {
    if (mode === "guide") {
      if (phase === "playing") return "skip-shot";
      if (guideStep > 0) {
        guideStep -= 1;
        current = guideStep;
        options.onVisit &&
          options.onVisit(current, { reason: "guide-prev", playCinematic: true });
      }
      return "advance";
    }
    if (current <= 0) setCurrent(12, { reason: "prev", playCinematic: false });
    else if (current === 1) setCurrent(0, { reason: "prev", playCinematic: false });
    else setCurrent(current - 1, { reason: "prev", playCinematic: false });
    return "free-next";
  }

  function onAutoEnter(n) {
    if (mode === "guide") return; // ガイド中は歩行で部屋を切り替えない
    if (phase === "playing") return;
    if (n !== current) {
      current = n;
      options.onVisit &&
        options.onVisit(current, { reason: "walk", silentTeleport: true, playCinematic: false });
    }
  }

  function guideLabel() {
    if (mode !== "guide") return "";
    if (phase === "playing") return "案内中…（次へでショット送り）";
    if (guideStep === 0) return "中庭 — 「次へ」で第1ハウス";
    if (guideStep >= 12) return "第12ハウス — 「次へ」でツアー完了";
    return "第" + guideStep + "ハウス / 12 — 「次へ」で次の展示室";
  }

  return {
    getCurrent,
    getMode,
    getPhase,
    setPhase,
    setCurrent,
    startGuide,
    startFree,
    next,
    prev,
    onAutoEnter,
    guideLabel,
  };
}
