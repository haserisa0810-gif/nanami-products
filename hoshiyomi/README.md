# 星読みの暦（hoshiyomi）

計算済み YAML（nanami-products-yaml-v1）を読み込んで表示する Web アプリ。
出生図ビューア / 38日カレンダー / 日別詳細（朝・昼・夜の月） / AI鑑定生成。

仕様の正は [docs/ClaudeCode引き継ぎ_星読みの暦.md](docs/ClaudeCode引き継ぎ_星読みの暦.md)、
UI の正は [docs/星読みの暦_プロトタイプ.jsx](docs/星読みの暦_プロトタイプ.jsx)。

## 使い方（Phase 1 / ローカル）

```bash
cd hoshiyomi
npm install
npm run dev        # http://localhost:5180
```

- 「YAML読み込み」タブでファイルドロップまたはテキスト貼り付け
- 読み込んだ YAML と AI 鑑定結果は localStorage（キー `nanami:{profile_id}`）に保存され、複数プロファイルを切替可能
- 圧縮版（`transit.summary` / フラット moon_timepoints）とフル版（`next_31_days_summary` / `body:` ネスト）の両スキーマに対応

## AI鑑定

`.env` を作成（`.env.example` 参照）:

```
VITE_ANTHROPIC_API_KEY=sk-ant-...
```

Phase 1 はクライアントから直接 Anthropic API を叩く（自分専用の前提）。
**顧客に配布する場合はこのままデプロイしないこと** — Phase 2 で API プロキシ（キー秘匿＋レート制限）を挟む。

## タイムライン（Phase 2.5 / 引き継ぎ§9）

「タイムライン」タブに `[日] [月] [年] [人生]` のズーム切替がある。
日=日別詳細・月=38日カレンダー（既存画面を接続）、年=月ごとのイベント一覧、人生=出生年からの Time River。

- すべてのビューは共通型 `TimelineEvent`（[src/lib/timeline.ts](src/lib/timeline.ts)）を消費する。ソース追加は `TimelineSource` を増やすだけ
- 占術イベントは YAML にデータのある38日窓のみ（orb ≤ 0.5 のアスペクト＋key_dates）。**供給の無い年のイベントは生成しない**
- ユーザーイベントはキー `nanami:{profile_id}:userEvents` に保存。年・人生ビューの「＋ 予定を追加」から追加・編集・削除
- 各イベントの 📅 から Google カレンダーへ登録（APIなし・リンクのみ）

## テスト / ビルド

```bash
npm test           # vitest（parseYaml の正規化を検証）
npm run build      # 型チェック + production ビルド → dist/
```

## 構成

```
src/
  theme.ts               デザイントークン（夜の暦テーマ、引き継ぎ§5）
  lib/parseYaml.ts       YAML → 内部モデル正規化（値の再計算はしない）
  lib/reading.ts         AI鑑定 buildPayload・プロンプト（引き継ぎ§6）・API呼び出し
  lib/storage.ts         localStorage プロファイル・鑑定結果・ユーザーイベント永続化
  lib/timeline.ts        TimelineEvent 型・アダプタ・Googleカレンダーリンク（引き継ぎ§9）
  components/            NatalView / TimelineView（CalendarView / DayDetail / YearView / LifeView）/ AIView / YamlLoader
tests/fixtures/          sample_data_compact.yaml / real_data_full.yaml（テストフィクスチャ）
```

※ この配下は Cloud Run デプロイ対象外（リポジトリ直下の `.gcloudignore` で除外）。
