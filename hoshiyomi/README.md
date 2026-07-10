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

## AI鑑定（2レーン・引き継ぎ§6）

- **レーンA（既定・無料）**: セクションを選ぶと鑑定プロンプト全文を組み立てる。「プロンプトをコピー」または「ChatGPT / Claude / Gemini へ →」（コピーしてからサイトを開く）で自分のAIに貼り付けて読む。実行時APIなし
- **レーンB（同梱）**: 生成側（nanami-astro）が焼き込んだ `readings.yaml` / `readings.md` を読み込みタブから取り込むと、AI鑑定タブの先頭に表示される
- **開発検証用ライブ生成（§6.5）**: `.env` に `VITE_ANTHROPIC_API_KEY` を設定したときだけ「（開発用）このアプリで生成」ボタンが出る。配布ビルドにはキーを含めないこと

## 同梱ファイルの読み込み（§10.3）

「YAML読み込み」タブは種類を自動判別する:

| 入力 | 判別 | 行き先 |
|---|---|---|
| チャートYAML（`data_role: base_chart`） | chart | プロファイル新規/更新 |
| AI貼り付け用YAML（`nanami-products-yaml-detail-v1` 等の縮約版） | chart(縮約) | 当日1日分として表示。フル版読み込み済みなら上書きせず保護 |
| 月次追加YAML（`data_role` がアドオン） | chart(addon) | 既存プロファイルの `daily[]` に日付キーでマージ、期間拡張（§11.3） |
| `life_events.yaml`（`nanami-life-events-v1` / TimelineEvent互換配列） | life_events | 年・人生ビューに `transit_major` として表示（§10.2） |
| 焼き込み鑑定（`nanami-readings-v1` / Markdown / `{readings: ...}`） | readings | AI鑑定タブ先頭に表示（モデル注釈付き） |
| `horoscope.svg` | svg | 出生図タブに表示（§11.2） |

日別詳細の下に「日記」欄があり、一言メモが `source:"diary"` として userEvents と同じキーに保存され、年・人生ビューにも載る。
**日記・ユーザーイベント・鑑定結果はすべてブラウザの localStorage 保存**（その端末・そのブラウザ内のみ。サーバ送信なし）。

## 鑑定URLからの自動読み込み（`?load=`）

`{アプリURL}/?load=<YAMLのURL>&load=<SVGのURL>` の形で開くと、記載順に fetch して自動で読み込む
（1つ目はチャートYAML、以降は同梱物）。読み込み後はアドレスバーから token 入りURLを消す。

nanami-products サーバ側は環境変数 `HOSHIYOMI_APP_URL` を設定すると、購入者の
`/chart/{token}` ページに「星読みの暦アプリで開く（自動読み込み）」ボタンが出る
（チャートYAML＋horoscope.svg を `?load=` で渡す。YAML/SVG エンドポイントは CORS 許可済み）。
アプリを別オリジンにホスティングする場合もこの仕組みだけで動く。

生成側（nanami-astro）が出力すべき `readings.yaml` / `life_events.yaml` の契約は
[docs/receiver_scaffold/README_受け皿.md](docs/receiver_scaffold/README_受け皿.md) を参照
（claude.ai 製の受け皿スキャフォールド一式を参考として保管。アプリ本体はこの契約を取り込み済みで、
クォート無し日付（js-yaml が Date 化する）にも対応している）。

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
