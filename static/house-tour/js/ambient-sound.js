/**
 * House Tour 環境音（Web Audio）
 * クリック直後に AudioContext を resume し、聞こえる音量で基音を鳴らす。
 */
export function createAmbientSound() {
  let soundOn = false;
  let audioCtx = null;
  let masterGain = null;
  let oscNodes = [];
  let auxNodes = []; // filters etc. to disconnect on stop

  const MASTER_ON = 0.28;
  const MASTER_OFF = 0.0001;

  function ensure() {
    if (audioCtx) return audioCtx;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    audioCtx = new AC();
    masterGain = audioCtx.createGain();
    masterGain.gain.value = MASTER_OFF;
    masterGain.connect(audioCtx.destination);
    return audioCtx;
  }

  function stopOscs() {
    oscNodes.forEach((n) => {
      try {
        if (n.osc.stop) n.osc.stop();
        n.osc.disconnect();
        if (n.gain) n.gain.disconnect();
      } catch (e) { /* */ }
    });
    oscNodes = [];
    auxNodes.forEach((n) => {
      try {
        n.disconnect();
      } catch (e) { /* */ }
    });
    auxNodes = [];
  }

  function resumeIfNeeded() {
    const ctx = ensure();
    if (!ctx) return Promise.resolve(null);
    if (ctx.state === "suspended") {
      return ctx.resume().then(() => ctx).catch(() => ctx);
    }
    return Promise.resolve(ctx);
  }

  /**
   * @param {object|null} house  housesData[n] with optional sound: { baseHz, mood }
   */
  function retune(house) {
    if (!soundOn || !audioCtx || !masterGain) return;
    stopOscs();
    const h = house || {};
    const base = (h.sound && h.sound.baseHz) || 110;
    const mood = (h.sound && h.sound.mood) || "warm";
    let intervals = [1, 5 / 4, 3 / 2];
    let types = ["sine", "triangle", "sine"];
    let filterFreq = 1400;
    if (mood === "deep" || mood === "mist" || mood === "hearth") {
      intervals = [1, 6 / 5, 3 / 2];
      filterFreq = 700;
    }
    if (mood === "playful" || mood === "chatter") {
      intervals = [1, 9 / 8, 5 / 4];
      filterFreq = 2400;
      types = ["triangle", "sine", "triangle"];
    }
    if (mood === "open" || mood === "grand") {
      intervals = [1, 5 / 4, 2];
      filterFreq = 2800;
    }
    if (mood === "rising" || mood === "steady") {
      intervals = [1, 5 / 4, 3 / 2];
      filterFreq = 1600;
    }

    const t0 = audioCtx.currentTime;
    const filter = audioCtx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = filterFreq;
    filter.Q.value = 0.7;
    filter.connect(masterGain);
    auxNodes.push(filter);

    intervals.forEach((ratio, i) => {
      const osc = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      osc.type = types[i] || "sine";
      osc.frequency.value = base * ratio;
      g.gain.value = 0.0001;
      osc.connect(g);
      g.connect(filter);
      osc.start();
      // 十分聞こえるレベル（旧: 0.18 * master 0.045 ≈ 無音級）
      const peak = (0.42 / (i + 1)) * (mood === "deep" || mood === "mist" ? 0.85 : 1);
      g.gain.linearRampToValueAtTime(peak, t0 + 0.55);
      oscNodes.push({ osc, gain: g });
    });

    // 薄いノイズ床（全ムードで少し空気感）
    try {
      const bufferSize = Math.floor(audioCtx.sampleRate * 1.5);
      const noiseBuf = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
      const data = noiseBuf.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) {
        data[i] = (Math.random() * 2 - 1) * 0.35;
      }
      const noise = audioCtx.createBufferSource();
      noise.buffer = noiseBuf;
      noise.loop = true;
      const ng = audioCtx.createGain();
      const nf = audioCtx.createBiquadFilter();
      nf.type = mood === "playful" ? "bandpass" : "lowpass";
      nf.frequency.value = mood === "playful" ? 1800 : 400;
      nf.Q.value = mood === "playful" ? 0.6 : 0.5;
      ng.gain.value = 0.0001;
      noise.connect(nf);
      nf.connect(ng);
      ng.connect(masterGain);
      noise.start();
      const noisePeak = mood === "playful" ? 0.035 : 0.018;
      ng.gain.linearRampToValueAtTime(noisePeak, t0 + 0.8);
      oscNodes.push({ osc: noise, gain: ng });
      auxNodes.push(nf);
    } catch (e) { /* ignore */ }
  }

  /**
   * @param {boolean} on
   * @param {object|null} house
   * @returns {Promise<boolean>} soundOn after attempt
   */
  function setOn(on, house) {
    soundOn = !!on;
    if (!soundOn) {
      if (masterGain && audioCtx) {
        try {
          masterGain.gain.cancelScheduledValues(audioCtx.currentTime);
          masterGain.gain.linearRampToValueAtTime(MASTER_OFF, audioCtx.currentTime + 0.25);
        } catch (e) { /* */ }
      }
      setTimeout(stopOscs, 280);
      return Promise.resolve(false);
    }

    return resumeIfNeeded().then((ctx) => {
      if (!ctx || !masterGain) {
        soundOn = false;
        return false;
      }
      retune(house);
      try {
        masterGain.gain.cancelScheduledValues(ctx.currentTime);
        masterGain.gain.setValueAtTime(Math.max(masterGain.gain.value, MASTER_OFF), ctx.currentTime);
        masterGain.gain.linearRampToValueAtTime(MASTER_ON, ctx.currentTime + 0.35);
      } catch (e) { /* */ }
      return true;
    });
  }

  function toggle(house) {
    return setOn(!soundOn, house);
  }

  function isOn() {
    return soundOn;
  }

  /** ハウス移動時に基音を差し替え（ON のときだけ） */
  function onHouse(house) {
    if (!soundOn) return;
    resumeIfNeeded().then(() => {
      if (soundOn) retune(house);
    });
  }

  return {
    isOn,
    setOn,
    toggle,
    onHouse,
    retune,
  };
}
