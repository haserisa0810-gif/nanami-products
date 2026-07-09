/* localStorage 永続化 — キー nanami:{profile_id} に YAML と鑑定結果を保存 */

export type StoredReading = {
  sectionId: string;
  label: string;
  date?: string; // selectedDay の対象日
  text: string;
  generatedAt: string;
};

export type StoredProfile = {
  profileId: string;
  title: string;
  birthDate: string;
  yamlText: string; // ベースチャート（data_role: base_chart）
  savedAt: string;
  readings: StoredReading[];
  addonYamls?: string[]; // 月次トランジット追加YAML（§11.3、daily を日付キーでマージ）
  baked?: { text: string; loadedAt: string }; // 焼き込み済み基本版鑑定（§6.2）
  horoscopeSvg?: string; // 同梱 horoscope.svg（§11.2）
};

const PREFIX = "nanami:";
const LAST_KEY = "nanami:last_profile";

const keyOf = (profileId: string) => `${PREFIX}${profileId}`;

export function listProfiles(): StoredProfile[] {
  const out: StoredProfile[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k || !k.startsWith(PREFIX) || k === LAST_KEY) continue;
    try {
      const v = JSON.parse(localStorage.getItem(k) || "");
      if (v && typeof v === "object" && v.profileId && v.yamlText) out.push(v);
    } catch {
      /* 壊れたエントリは無視 */
    }
  }
  return out.sort((a, b) => b.savedAt.localeCompare(a.savedAt));
}

export function getProfile(profileId: string): StoredProfile | null {
  try {
    const raw = localStorage.getItem(keyOf(profileId));
    return raw ? (JSON.parse(raw) as StoredProfile) : null;
  } catch {
    return null;
  }
}

export function saveProfile(
  p: Pick<StoredProfile, "profileId" | "title" | "birthDate" | "yamlText">,
): StoredProfile {
  const existing = getProfile(p.profileId);
  // ベース再読み込み時も鑑定結果・アドオン・同梱物は維持する
  const stored: StoredProfile = {
    ...existing,
    ...p,
    savedAt: new Date().toISOString(),
    readings: existing?.readings ?? [],
  };
  localStorage.setItem(keyOf(p.profileId), JSON.stringify(stored));
  setLastProfileId(p.profileId);
  return stored;
}

export function updateProfileExtras(
  profileId: string,
  patch: Partial<Pick<StoredProfile, "baked" | "horoscopeSvg" | "addonYamls">>,
): StoredProfile | null {
  const p = getProfile(profileId);
  if (!p) return null;
  const next = { ...p, ...patch };
  localStorage.setItem(keyOf(profileId), JSON.stringify(next));
  return next;
}

export function appendAddonYaml(profileId: string, yamlText: string): StoredProfile | null {
  const p = getProfile(profileId);
  if (!p) return null;
  return updateProfileExtras(profileId, { addonYamls: [...(p.addonYamls ?? []), yamlText] });
}

export function deleteProfile(profileId: string): void {
  localStorage.removeItem(keyOf(profileId));
  if (getLastProfileId() === profileId) localStorage.removeItem(LAST_KEY);
}

export function saveReading(profileId: string, reading: StoredReading): void {
  const p = getProfile(profileId);
  if (!p) return;
  // 同一セクション（selectedDay は同一対象日）の結果は置き換える
  p.readings = p.readings.filter(
    (r) => !(r.sectionId === reading.sectionId && r.date === reading.date),
  );
  p.readings.push(reading);
  localStorage.setItem(keyOf(profileId), JSON.stringify(p));
}

export function getLastProfileId(): string | null {
  return localStorage.getItem(LAST_KEY);
}

export function setLastProfileId(profileId: string): void {
  localStorage.setItem(LAST_KEY, profileId);
}

/* ユーザーイベント（§9.3）— キー nanami:{profile_id}:userEvents */

import type { TimelineEvent } from "./timeline";

const userEventsKey = (profileId: string) => `${PREFIX}${profileId}:userEvents`;

export function listUserEvents(profileId: string): TimelineEvent[] {
  try {
    const raw = localStorage.getItem(userEventsKey(profileId));
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveUserEvent(profileId: string, ev: TimelineEvent): TimelineEvent[] {
  const list = listUserEvents(profileId).filter((e) => e.id !== ev.id);
  list.push(ev);
  list.sort((a, b) => a.date.localeCompare(b.date));
  localStorage.setItem(userEventsKey(profileId), JSON.stringify(list));
  return list;
}

export function deleteUserEvent(profileId: string, id: string): TimelineEvent[] {
  const list = listUserEvents(profileId).filter((e) => e.id !== id);
  localStorage.setItem(userEventsKey(profileId), JSON.stringify(list));
  return list;
}

/* life_events.yaml（§10.2）— 生成側が広域スキャンした transit_major イベント */

const lifeEventsKey = (profileId: string) => `${PREFIX}${profileId}:lifeEvents`;

export function listLifeEvents(profileId: string): TimelineEvent[] {
  try {
    const raw = localStorage.getItem(lifeEventsKey(profileId));
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveLifeEvents(profileId: string, events: TimelineEvent[]): void {
  localStorage.setItem(lifeEventsKey(profileId), JSON.stringify(events));
}

export function readingsToMarkdown(p: StoredProfile): string {
  const lines = [
    `# 星読みの暦 — AI鑑定`,
    ``,
    `- プロファイル: ${p.title}（${p.birthDate}）`,
    `- 出力日時: ${new Date().toLocaleString("ja-JP")}`,
    ``,
  ];
  for (const r of p.readings) {
    lines.push(`## ${r.label}${r.date ? `（${r.date}）` : ""}`, ``, r.text.trim(), ``);
  }
  return lines.join("\n");
}
