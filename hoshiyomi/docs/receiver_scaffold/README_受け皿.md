# アプリ側「受け皿」スキャフォールド（星読みの暦）

生成側（§10 の nanami-astro / Python）の成果物と、ユーザー/日記イベントを**受け取るためのアプリ側配線**です。既存プロトタイプ（`星読みの暦_プロトタイプ.jsx`）を Vite + TS へ移植する際、`src/` にそのまま置けます。生成側がまだ無くても動くよう、**欠損に寛容**に作っています。

## 含まれるファイル

| ファイル | 役割 | 引き継ぎ参照 |
|---|---|---|
| `src/types/artifacts.ts` | readings.yaml / life_events.yaml のスキーマ契約＋最小トランジット型 | §6.2 / §10.1 / §10.2 |
| `src/lib/timeline.ts` | 共通イベント型 `TimelineEvent`＋アダプタ（transit/major）＋マージ/グループ/スケール絞り | §9.1 / §9.4 |
| `src/lib/loadArtifacts.ts` | readings.yaml / life_events.yaml の js-yaml 読み込み（欠損寛容） | §10.3 |
| `src/lib/storage.ts` | localStorage 安全ラッパー＋profileキー規約 | §9.3 |
| `src/lib/userEvents.ts` | ユーザーイベント/日記の CRUD（`nanami:{profile_id}:userEvents`） | §9.3 / §11.3 |
| `src/components/ReadingsView.tsx` | 焼き込み鑑定の表示＋**モデル注釈**（必須） | §6.2 |
| `src/components/timeline/TimelineView.tsx` | ズーム切替（日/月/年/人生）。日・月は既存へ委譲、年・人生を描画 | §9.2 / §9.6 |

## データ契約（生成側 §10 はこの形で出力する）

**readings.yaml**
```yaml
version: nanami-readings-v1
model: gemini-2.5-flash-lite      # 注釈に表示（§6.2 必須）
profile_id: profile_xxx
generated_at: 2026-07-10T00:00:00+09:00
note: 本鑑定は Gemini 2.5 Flash-Lite により、計算済みデータのみを根拠に生成しています。
sections:
  - { id: overview, title: 全体像,   body: "..." }
  - { id: talent,   title: 才能・強み, body: "..." }
```

**life_events.yaml**（トップレベル配列でも `events:` 配下でも可）
```yaml
version: nanami-life-events-v1
profile_id: profile_xxx
events:
  - { type: return,   date: 2005-08-01, title: サターンリターン, description: 節目, meta: { orb: 0.3 } }
  - { type: aspect,   date: 2026-08-06, title: 木星 合 土星,    meta: { bodies: [Jupiter, Saturn], aspect: conjunction, orb: 0.01 } }
  - { type: ingress,  date: 2027-04-01, title: 天王星 双子座入り }
```

## 既存プロトタイプへの差し込み

1. `npm i js-yaml @types/js-yaml`
2. `parseYaml.ts`（Phase1）の正規化型に合わせ、`types/artifacts.ts` の `TransitDay` / `NormalizedAspect` を微調整（フィールド名の単一の真実はパーサ側）
3. スタイル: 各コンポーネント冒頭の仮 `C` を、プロトタイプのデザイントークン（§5）へ置換
4. タブ構成に「鑑定（ReadingsView）」を追加し、既存の「38日カレンダー」を `TimelineView` の月スケールへ接続:
   ```tsx
   <TimelineView
     events={mergeEvents(fromTransitDaily(days), lifeEvents, listUserEvents(profileId))}
     todayISO={today}
     renderDay={() => <DayDetail .../>}
     renderMonth={() => <CalendarView .../>}
     onOpenEvent={(e) => openDetail(e)}   // 解説/AI用YAML/Googleカレンダー（§9.5）
   />
   ```
5. 日記入力（`upsertDiary`）を日別詳細に足す

## 注意

- **localStorage は Vite の実機/実ビルドで動作**。claude.ai のアーティファクトプレビューでは動かないため、この受け皿の実挙動確認は Claude Code / ローカルで行うこと。
- 年/人生ビューは `life_events.yaml` が来るまで空（ユーザーイベント＋38日窓のみ）。**イベントを推測・捏造しない**（§10.2 / §1）。
- Git: 大規模UI改修の前にチェックポイントコミット（§9.8）。

## この受け皿でカバーしていない（＝次の実装）

- 詳細モーダル（解説/AI用YAML/Googleカレンダーリンク生成）の中身
- レーンA（コピー/自分のAIへ送る）の送信UI（`buildPayload()` は移植で流用）
- horoscope_svg 表示（§11.2）、月次マージの取り込みUI（§11.3）
- 実データ差分の正規化（§3.1）を parseYaml.ts に実装
