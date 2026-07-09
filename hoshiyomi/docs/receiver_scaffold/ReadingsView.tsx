// src/components/ReadingsView.tsx
// 焼き込み鑑定（readings.yaml）の表示（§6.2）。モデル注釈を必ず出す。
// スタイルは仮。既存プロトタイプの C トークン（テーマ）に置き換えること。
import type { Readings } from "../types/artifacts";

const C = { text: "#E8E4D8", sub: "#9BA0B2", faint: "#6C7183", panel: "#1C2030", line: "#2E3348" };

export function ReadingsView({ readings }: { readings: Readings | null }) {
  if (!readings) {
    return (
      <p style={{ color: C.faint, fontSize: 13 }}>
        この profile には焼き込み鑑定（readings.yaml）がまだありません。生成側（§10.1）で作成・同梱してください。
      </p>
    );
  }
  return (
    <div>
      {readings.sections.map((s) => (
        <section
          key={s.id}
          style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: 18, marginBottom: 14 }}
        >
          <h3 style={{ color: C.text, margin: "0 0 8px", fontWeight: 600 }}>{s.title}</h3>
          <div style={{ color: C.text, lineHeight: 2, whiteSpace: "pre-wrap" }}>{s.body}</div>
        </section>
      ))}
      {/* モデル注釈（§6.2 必須）。note があれば優先、無ければ model から自動生成 */}
      <p style={{ color: C.faint, fontSize: 12, marginTop: 4 }}>
        {readings.note ?? `本鑑定は ${readings.model} により、計算済みデータのみを根拠に生成しています。`}
      </p>
    </div>
  );
}
