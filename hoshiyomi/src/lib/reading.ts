/* AI鑑定 — buildPayload とプロンプト（引き継ぎ§6準拠、ルール変更禁止）。
   レーンA（既定・§6.1）: プロンプト全文を組み立ててコピー／各AIへ受け渡す。実行時APIなし。
   ライブ生成（§6.5）: VITE_ANTHROPIC_API_KEY がある場合のみの開発検証用。配布ビルドには含めない。 */

import type { ChartData } from "./parseYaml";

export const MODEL = "claude-sonnet-4-6";

export const AI_SECTIONS = [
  { id: "overview", label: "全体像" },
  { id: "talent", label: "才能・強み" },
  { id: "pitfall", label: "つまずきやすいパターン" },
  { id: "work", label: "仕事・活動の向き" },
  { id: "relation", label: "人間関係の傾向" },
  { id: "flow38", label: "今後38日間の流れ" },
  { id: "selectedDay", label: "選択日の使い方（朝・昼・夜）" },
] as const;

export type SectionId = (typeof AI_SECTIONS)[number]["id"];

export function buildPayload(data: ChartData, sectionId: SectionId, selectedDate: string) {
  const natal = data.natal;
  const compactBodies = Object.fromEntries(
    Object.entries(natal.bodies).map(([k, b]) => [
      k,
      { sign: b.sign_ja, deg: +b.degree.toFixed(1), house: b.house, r: b.retrograde },
    ]),
  );
  const compactAst = Object.fromEntries(
    Object.entries(data.asteroids).map(([k, b]) => [
      k,
      { sign: b.sign_ja, deg: +b.degree.toFixed(1), house: b.house },
    ]),
  );
  const tightNatal = natal.aspects.filter((a) => a.orb <= 2.2);
  const base: Record<string, unknown> = {
    出生図: { 天体: compactBodies, 小惑星: compactAst, アスペクト: tightNatal, バランス: natal.summary },
  };
  if (sectionId === "flow38") {
    base.期間サマリー = data.transit.summary;
    base.日別タイトアスペクト = data.transit.daily.map((d) => ({
      date: d.date,
      aspects: d.natal_aspects.filter((a) => a.orb <= 0.8),
    }));
  }
  if (sectionId === "selectedDay") {
    const day = data.transit.daily.find((d) => d.date === selectedDate);
    if (day) {
      base.対象日 = { date: day.date, アスペクト: day.natal_aspects, 朝昼夜の月: day.moon_timepoints };
    }
  }
  return base;
}

export function buildInstruction(data: ChartData, sectionId: SectionId, selectedDate: string): string {
  const today = data.transit.todayDate;
  const AI_INSTRUCTIONS: Record<SectionId, string> = {
    overview: "このホロスコープの全体像を、性質の傾向として400字程度でまとめてください。",
    talent: "才能・強みを3点、根拠となる配置を添えて説明してください。",
    pitfall: "つまずきやすいパターンを2〜3点、「どう使うとズレにくいか」の視点で説明してください。",
    work: "仕事・活動の向きを、具体的な活かし方とともに説明してください。",
    relation: "人間関係の傾向を、出生図の配置を根拠に説明してください。",
    flow38: `期間サマリーと日別タイトアスペクトをもとに、38日間の流れと「動きやすい日・注意したい日」を説明してください。基準日(${today})以降を未来として扱ってください。`,
    selectedDay: "対象日のデータをもとに、朝・昼・夜それぞれの使い方を具体的な行動ヒントとして説明してください。",
  };
  return AI_INSTRUCTIONS[sectionId] + (sectionId === "selectedDay" ? `（対象日: ${selectedDate}）` : "");
}

export function buildSystemPrompt(data: ChartData): string {
  return `あなたは西洋占星術の鑑定者です。ユーザーから渡されるJSONは計算済みデータです。
ルール:
1. 計算結果を変更・再計算しない。JSON内の値のみを根拠にする。
2. 断定しすぎず「傾向・使い方・活かし方」として表現する。
3. 「良い・悪い」ではなく「どう使うとズレにくいか」を優先する。
4. 「ラッキー」等の軽い表現は避け、具体的な行動ヒントに置き換える。
5. 基準日は ${data.transit.todayDate}。それより前の日付は「振り返り」、以降を「今後」として扱う。
6. 月の朝・昼・夜データは日内の使い方の根拠として使う。
見出しや箇条書きを適度に使い、日本語で読みやすく書いてください。`;
}

/* レーンA用: 自分のAIに貼り付けるプロンプト全文（ルール＋依頼＋データ） */
export function buildFullPrompt(
  data: ChartData,
  sectionId: SectionId,
  selectedDate: string,
): string {
  const payload = buildPayload(data, sectionId, selectedDate);
  return `${buildSystemPrompt(data)}

依頼: ${buildInstruction(data, sectionId, selectedDate)}

データ:
${JSON.stringify(payload)}`;
}

/* コピー後に開く受け渡し先（レーンA） */
export const AI_DESTINATIONS = [
  { id: "chatgpt", label: "ChatGPT", url: "https://chatgpt.com/" },
  { id: "claude", label: "Claude", url: "https://claude.ai/new" },
  { id: "gemini", label: "Gemini", url: "https://gemini.google.com/app" },
] as const;

/* ライブ生成は開発検証専用（§6.5）。キーが無ければ UI 自体を出さない */
export const devApiKeyAvailable = (): boolean =>
  Boolean(import.meta.env.VITE_ANTHROPIC_API_KEY);

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function generateReading(
  data: ChartData,
  sectionId: SectionId,
  selectedDate: string,
): Promise<string> {
  const apiKey = import.meta.env.VITE_ANTHROPIC_API_KEY as string | undefined;
  if (!apiKey) {
    throw new Error(
      "APIキーが設定されていません。hoshiyomi/.env に VITE_ANTHROPIC_API_KEY を設定して dev サーバーを再起動してください。",
    );
  }
  const payload = buildPayload(data, sectionId, selectedDate);
  const body = JSON.stringify({
    model: MODEL,
    max_tokens: 1500,
    system: buildSystemPrompt(data),
    messages: [
      {
        role: "user",
        content: `依頼: ${buildInstruction(data, sectionId, selectedDate)}\n\nデータ:\n${JSON.stringify(payload)}`,
      },
    ],
  });

  // overloaded(529) は指数バックオフで再試行（§6）
  const maxRetries = 3;
  for (let attempt = 0; ; attempt++) {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body,
    });
    if (res.status === 529 && attempt < maxRetries) {
      await sleep(1000 * 2 ** attempt);
      continue;
    }
    const json = await res.json().catch(() => null);
    if (!res.ok || json?.error) {
      const msg = json?.error?.message || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return (json.content || [])
      .map((c: { type: string; text?: string }) => (c.type === "text" ? c.text : ""))
      .join("\n");
  }
}
