// src/lib/storage.ts
// localStorage 安全ラッパー。実プロジェクト（Vite）で動作する。
// 注意: claude.ai のアーティファクトプレビューでは localStorage が使えない。
//       実機/実ビルド（Vite dev/prod）で動くコードとして書いている。

export function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJSON(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false; // 容量超過・プライベートモード等でも落ちない
  }
}

export function removeKey(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* noop */
  }
}

// profile 単位のキー規約（§9.3 / §11.3）: nanami:{profile_id}:{suffix}
export const profileKey = (profileId: string, suffix: string) =>
  `nanami:${profileId}:${suffix}`;
