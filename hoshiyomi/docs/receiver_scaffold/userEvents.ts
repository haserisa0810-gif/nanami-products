// src/lib/userEvents.ts
// ユーザーイベント & 日記の localStorage CRUD（§9.3 / §11.3）。
// 日記は「別アプリ」でも同じキー規約・同じ型を共有すれば相互に開ける。
import type { TimelineEvent } from "./timeline";
import { readJSON, writeJSON, profileKey } from "./storage";

const SUFFIX = "userEvents";

export function listUserEvents(profileId: string): TimelineEvent[] {
  return readJSON<TimelineEvent[]>(profileKey(profileId, SUFFIX), []);
}

function save(profileId: string, events: TimelineEvent[]): boolean {
  return writeJSON(profileKey(profileId, SUFFIX), events);
}

// 自由イベント追加（例: "2027-03-01 引越し"）
export function addUserEvent(
  profileId: string,
  input: { date: string; title: string; description?: string }
): TimelineEvent {
  if (!/^\d{4}-\d{2}-\d{2}/.test(input.date)) throw new Error("date は 'YYYY-MM-DD' 形式で");
  if (!input.title.trim()) throw new Error("title は必須です");
  const ev: TimelineEvent = {
    id: `user:${input.date}:${crypto.randomUUID()}`,
    type: "custom",
    date: input.date,
    title: input.title.trim(),
    description: input.description?.trim() || undefined,
    source: "user",
  };
  save(profileId, [...listUserEvents(profileId), ev]);
  return ev;
}

export function updateUserEvent(profileId: string, id: string, patch: Partial<TimelineEvent>): void {
  const next = listUserEvents(profileId).map((e) =>
    e.id === id ? { ...e, ...patch, id: e.id } : e
  );
  save(profileId, next);
}

export function removeUserEvent(profileId: string, id: string): void {
  save(profileId, listUserEvents(profileId).filter((e) => e.id !== id));
}

// 日記: 1日1件を upsert（id を日付固定にして上書き。空文字なら削除）
export function upsertDiary(profileId: string, date: string, text: string): void {
  const id = `diary:${date}`;
  const others = listUserEvents(profileId).filter((e) => e.id !== id);
  if (!text.trim()) {
    save(profileId, others);
    return;
  }
  const ev: TimelineEvent = {
    id,
    type: "diary",
    date,
    title: text.trim().slice(0, 40),
    description: text.trim(),
    source: "diary",
  };
  save(profileId, [...others, ev]);
}

export function getDiary(profileId: string, date: string): string {
  const e = listUserEvents(profileId).find((x) => x.id === `diary:${date}`);
  return e?.description ?? "";
}
