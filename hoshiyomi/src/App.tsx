import { useEffect, useMemo, useState } from "react";
import { C, SANS, SERIF } from "./theme";
import { parseYamlText, YamlParseError, type ChartData } from "./lib/parseYaml";
import { detectPayload } from "./lib/detect";
import { chartFromStored } from "./lib/merge";
import {
  listProfiles, getProfile, saveProfile, getLastProfileId, setLastProfileId,
  updateProfileExtras, appendAddonYaml, saveLifeEvents,
  type StoredProfile,
} from "./lib/storage";
import { Eyebrow } from "./components/common";
import NatalView from "./components/NatalView";
import TimelineView from "./components/TimelineView";
import AIView from "./components/AIView";
import YamlLoader from "./components/YamlLoader";

type Tab = "natal" | "timeline" | "ai" | "load";

export default function App() {
  const [data, setData] = useState<ChartData | null>(null);
  const [tab, setTab] = useState<Tab>("timeline");
  const [selected, setSelected] = useState<string>("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadNotice, setLoadNotice] = useState<string | null>(null);
  const [profilesVersion, setProfilesVersion] = useState(0);

  const applyStored = (stored: StoredProfile): ChartData => {
    const merged = chartFromStored(stored.yamlText, stored.addonYamls);
    setData(merged);
    setSelected(merged.transit.todayDate);
    setLastProfileId(stored.profileId);
    setProfilesVersion((v) => v + 1);
    return merged;
  };

  // 起動時: 前回のプロファイルを復元
  useEffect(() => {
    const last = getLastProfileId();
    const stored = last ? getProfile(last) : listProfiles()[0];
    if (stored) {
      try {
        applyStored(stored);
        return;
      } catch {
        /* 保存データが壊れていたら読み込み画面へ */
      }
    }
    setTab("load");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const profiles = useMemo(() => listProfiles(), [data, profilesVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  // 読み込みUI: チャート / 月次アドオン / life_events / readings / horoscope.svg を自動判別（§10.3）
  const loadYaml = (text: string) => {
    setLoadError(null);
    setLoadNotice(null);
    try {
      const det = detectPayload(text);

      if (det.kind === "chart") {
        const parsed = parseYamlText(text);
        if (parsed.dataRole !== "base_chart") {
          // 月次トランジット追加YAML（§11.3）— 同一 profile_id のベースにマージ
          const target = getProfile(parsed.profileId);
          if (!target) {
            throw new YamlParseError(
              `アドオンYAML（data_role: ${parsed.dataRole}）です。先に同じプロファイルのベースチャートを読み込んでください。`,
            );
          }
          const updated = appendAddonYaml(parsed.profileId, text)!;
          applyStored(updated);
          setLoadNotice(`月次データをマージしました（期間 ${parsed.transit.period.start_date} 〜）。`);
          setTab("timeline");
          return;
        }
        const stored = saveProfile({
          profileId: parsed.profileId,
          title: parsed.title,
          birthDate: parsed.birthDate,
          yamlText: text,
        });
        applyStored(stored);
        setTab("timeline");
        return;
      }

      // 以降はチャート以外の同梱物 — 読み込み先プロファイルが必要
      if (!data) {
        throw new YamlParseError("先にチャートYAMLを読み込んでから、同梱ファイルを追加してください。");
      }
      if (det.kind === "life_events") {
        saveLifeEvents(data.profileId, det.events);
        setLoadNotice(`life_events を ${det.events.length} 件読み込みました。年・人生ビューに表示されます。`);
        setTab("timeline");
      } else if (det.kind === "readings") {
        updateProfileExtras(data.profileId, {
          baked: { text: det.text, loadedAt: new Date().toISOString() },
        });
        setLoadNotice("同梱の基本版鑑定を読み込みました。AI鑑定タブに表示されます。");
        setTab("ai");
      } else if (det.kind === "svg") {
        updateProfileExtras(data.profileId, { horoscopeSvg: det.svg });
        setLoadNotice("ホロスコープ図を読み込みました。出生図タブに表示されます。");
        setTab("natal");
      }
    } catch (e) {
      setLoadError(
        e instanceof YamlParseError ? e.message : `読み込みに失敗しました: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  };

  const switchProfile = (profileId: string) => {
    const stored = getProfile(profileId);
    if (!stored) return;
    try {
      applyStored(stored);
      if (tab === "load") setTab("timeline");
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setTab("load");
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: "natal", label: "出生図" },
    { id: "timeline", label: "タイムライン" },
    { id: "ai", label: "AI鑑定" },
    { id: "load", label: "YAML読み込み" },
  ];

  const accuracyJa: Record<string, string> = {
    exact: "正確", approximate: "推定", unknown: "不明",
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: SANS }}>
      <style>{`
        @media (max-width: 720px){ .grid-collapse{ grid-template-columns: 1fr !important; } }
        button:focus-visible{ outline: 2px solid ${C.dawn}; outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce){ *{ transition: none !important; } }
        @media print {
          nav, footer, select, .no-print { display: none !important; }
          body, #root > div { background: #fff !important; }
          * { color: #1a1a1a !important; border-color: #bbb !important;
              background: transparent !important; text-shadow: none !important; }
          main { max-width: 100% !important; padding: 0 !important; }
        }
      `}</style>
      {/* ヘッダー */}
      <header style={{ borderBottom: `1px solid ${C.line}`, padding: "22px 24px 0", maxWidth: 1080, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 10 }}>
          <div>
            <Eyebrow>Nanami Products — Western 38days Transit</Eyebrow>
            <h1 style={{ fontFamily: SERIF, fontSize: 30, fontWeight: 600, margin: 0, letterSpacing: "0.1em" }}>星読みの暦</h1>
            {data && (
              <div style={{ fontSize: 12.5, color: C.sub, margin: "8px 0 0" }}>
                {data.title} ／ {data.birthDate} {data.birthTime} 生・{data.birthPlace}
                （出生時刻: {accuracyJa[data.birthTimeAccuracy] ?? data.birthTimeAccuracy}）
              </div>
            )}
          </div>
          <div style={{ fontSize: 11.5, color: C.faint, textAlign: "right" }}>
            {data && (
              <>
                期間 {data.transit.period.start_date} — {data.transit.period.end_date}
                <br />
                Swiss Ephemeris / Placidus / {data.transit.period.timezone || "Asia/Tokyo"}
              </>
            )}
            {profiles.length > 0 && (
              <div style={{ marginTop: 6 }}>
                <select
                  value={data?.profileId ?? ""}
                  onChange={(e) => switchProfile(e.target.value)}
                  style={{
                    background: C.panel, color: C.sub, border: `1px solid ${C.line}`,
                    borderRadius: 6, padding: "4px 8px", fontSize: 11.5, fontFamily: SANS,
                  }}
                >
                  {!data && <option value="">プロファイル選択</option>}
                  {profiles.map((p) => (
                    <option key={p.profileId} value={p.profileId}>
                      {p.title || p.profileId}（{p.birthDate}）
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>
        {/* 朝→昼→夜のホライズンライン（シグネチャ） */}
        <div style={{ height: 3, margin: "16px 0 0", borderRadius: 2, background: `linear-gradient(90deg,${C.dawn},${C.day} 45%,${C.night})` }} />
        <nav style={{ display: "flex", gap: 4, marginTop: 0, flexWrap: "wrap" }}>
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              disabled={t.id !== "load" && !data}
              style={{
                background: "transparent", border: "none",
                borderBottom: `2px solid ${tab === t.id ? C.dawn : "transparent"}`,
                color: tab === t.id ? C.text : !data && t.id !== "load" ? C.faint : C.sub,
                padding: "14px 14px 12px", fontSize: 14,
                cursor: t.id !== "load" && !data ? "default" : "pointer",
                fontFamily: SANS, letterSpacing: "0.05em",
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main style={{ maxWidth: 1080, margin: "0 auto", padding: "24px" }}>
        {tab === "load" && (
          <>
            {loadNotice && (
              <div style={{ marginBottom: 12, fontSize: 13, color: C.good, lineHeight: 1.7 }}>{loadNotice}</div>
            )}
            <YamlLoader onLoad={loadYaml} error={loadError} />
          </>
        )}
        {loadNotice && tab !== "load" && (
          <div style={{ marginBottom: 14, fontSize: 12.5, color: C.good }}>{loadNotice}</div>
        )}
        {data && tab === "natal" && (
          <NatalView data={data} horoscopeSvg={getProfile(data.profileId)?.horoscopeSvg} />
        )}
        {data && tab === "timeline" && (
          <TimelineView
            key={data.profileId}
            data={data}
            selected={selected}
            onSelectDate={setSelected}
            onAskAI={(d) => { setSelected(d); setTab("ai"); }}
          />
        )}
        {data && tab === "ai" && (
          <AIView
            key={data.profileId}
            data={data}
            selectedDate={selected}
            initialReadings={getProfile(data.profileId)?.readings ?? []}
          />
        )}
      </main>
      <footer style={{ maxWidth: 1080, margin: "0 auto", padding: "0 24px 28px", fontSize: 11, color: C.faint, lineHeight: 1.8 }}>
        天体位置・アスペクトはYAML内の計算済みデータをそのまま表示しています(再計算なし)。AI鑑定は傾向・使い方の参考情報であり、断定的な予言ではありません。
      </footer>
    </div>
  );
}
