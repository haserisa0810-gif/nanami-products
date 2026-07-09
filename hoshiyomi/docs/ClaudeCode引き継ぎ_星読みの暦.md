# 星読みの暦 — Claude Code 引き継ぎドキュメント

作成日: 2026-07-09 ／ 対象: Claude Code での本実装
このドキュメントと同梱ファイルをリポジトリに置き、そのまま Claude Code に読ませて実装を開始できる構成にしています。

---

## 0. 同梱ファイル

| ファイル | 役割 |
|---|---|
| `星読みの暦_プロトタイプ.jsx` | Claude(claude.ai)で作成した動作するUIプロトタイプ。**デザイン・画面構成・AI鑑定プロンプトの正**。本実装はこれを分割・移植する |
| `sample_data_compact.yaml` | プロトタイプに埋め込んだ圧縮版サンプルデータ。テストフィクスチャとして使用 |
| 元YAML（nanami-products-yaml-v1） | 本番でパースする完全スキーマ。ユーザーが別途リポジトリに配置する（noteで配布している実データ） |

---

## 1. プロダクト概要

**何を作るか**: 西洋占星術の計算済みYAML（出生図＋小惑星＋38日トランジット）を読み込み、
①出生図ビューア ②38日カレンダー ③日別詳細（朝・昼・夜の月） ④AI鑑定生成 を提供するWebアプリ。

**誰が使うか**:
- 制作者本人（データ検証・鑑定文の下書き生成）
- noteの購入者（配布されたYAMLを読み込んで自分で閲覧・鑑定生成）

**絶対ルール（占星データの扱い）**:
- 天体位置・ハウス・アスペクト・トランジットは**YAML内の値をそのまま表示**する。再計算・補正は一切しない
- AI鑑定もYAML内の値のみを根拠にさせる（プロンプトで強制。§6参照）
- `today.selected_date` を基準日とし、それより前の日付は「振り返り」、以降を「今後」として扱う

---

## 2. 推奨アーキテクチャ

```
Phase 1（自分用・ローカル）        Phase 2（顧客配布）
┌─────────────────┐   ┌──────────────────────────┐
│ Vite + React + TS │   │ Next.js (App Router) + TS   │
│ js-yaml でパース   │   │ /api/reading → Anthropic API │
│ APIキーは .env     │→ │  （キーはサーバ側、レート制限）│
│ localStorage保存   │   │ Vercel / Cloudflare にデプロイ│
└─────────────────┘   └──────────────────────────┘
```

- **Phase 1**: Vite + React + TypeScript。最速で動くものを作る。AI鑑定は `VITE_ANTHROPIC_API_KEY` を使いクライアントから直接叩く（自分専用なので許容）
- **Phase 2**: 顧客に配る段階で Next.js の API Route（または Cloudflare Workers）を挟む。**APIキーをクライアントに絶対に置かない**。IP/セッション単位のレート制限（例: 1日20リクエスト）を入れる。代替案として「購入者が自分のAPIキーを入力する（BYOK）」方式も可 — この場合キーはlocalStorageに保存しサーバへ送らない
- YAMLパース: `js-yaml`（アンカー/エイリアス `&id001` `*id001` を含むため自作パーサ禁止）
- 状態管理: React state + localStorage で十分。外部ストアは不要
- スタイリング: プロトタイプはインラインstyle。移植時は CSS Modules か vanilla-extract に整理（Tailwindを使う場合はデザイントークン§7をthemeに登録）

---

## 3. データ仕様（YAMLスキーマ要点）

パース後にアプリが参照するパス:

```
input.title / birth_date / birth_time / birth_place        … ヘッダー表示
birth_time.accuracy, interpretation_flags.*                 … ハウス解釈可否の判定
systems.western.natal.bodies.{天体名}                        … sign_ja, degree, house, retrograde
systems.western.natal.houses.{1..12}                        … カスプ
systems.western.natal.aspects[]                             … body1, body2, aspect, orb
systems.western.natal.summary.elements / modes / dominant_signs
systems.western.asteroids.{Lilith,Chiron,Ceres,Pallas,Juno,Vesta,Vertex}
systems.western.transit.period                              … start_date, days, timezone
systems.western.transit.daily[]                             … date, transiting_bodies, natal_aspects, moon_timepoints[]
systems.western.transit.today.selected_date                 … 基準日
systems.western.transit.next_31_days_summary                … overall_theme, key_dates, caution_dates,
                                                              easy_to_move_days, key_periods, action_hints
assets.horoscope_svg                                        … ホロスコープ図SVGの有無（Phase 2で表示）
```

TypeScript型（正規化後の内部モデル）:

```ts
type Body = { sign: string; signJa: string; degree: number; house: number; retrograde: boolean };
type Aspect = { transitBody?: string; body1?: string; body2?: string; natalBody?: string;
                aspect: "conjunction"|"opposition"|"square"|"trine"|"sextile"; orb: number };
type MoonTimepoint = { label: "morning"|"noon"|"night"; signJa: string; degree: number;
                       house: number; aspects: Aspect[] };
type TransitDay = { date: string; bodies: Record<string, Body>;
                    natalAspects: Aspect[]; moonTimepoints: MoonTimepoint[] };
```

正規化レイヤー `src/lib/parseYaml.ts` を作り、YAMLの生構造と画面を分離すること。
バリデーション: `version: nanami-products-yaml-v1` と `meta.schema_version` をチェックし、不一致なら「このYAMLは対応バージョンではありません」を表示。

### 3.1 実データで確認したスキーマ差分（重要）

プロトタイプは圧縮版データで作成。フル実データを受領して以下の差分を確認した。**parseYaml.ts の正規化層で必ず吸収すること**（プロトタイプのコードは圧縮版前提のため、実データを素通しすると動かない箇所がある）:

1. サマリーのキー名: 圧縮版 `transit.summary` → 実データ `transit.next_31_days_summary`。両方を見て存在する方を採用する
2. `caution_dates` / `easy_to_move_days` の型: 圧縮版は文字列配列 `['2026-07-01', ...]`。実データは**オブジェクト配列** `[{date, reason, source_aspects}]`。日付は `x => x.date` で取り出す。両型を受ける正規化を書く
3. `key_dates`: 実データは `[{date, theme, reason, source_aspects}]`（theme は取得可）
4. `today.moon_timepoints` の型: `daily[].moon_timepoints` は**配列**（`[{label:'morning', body:{...}}]`）だが、`today.moon_timepoints` は**オブジェクト**（`{morning:{moon:{...}}, noon, night}`）。月データのキーも daily は `body`、today は `moon` で非対称。today を日別詳細へ流用するなら配列へ変換する
5. YAMLアンカー/エイリアス: 実データに `&id001`〜`&id006` と `*id001` 等が実在（`key_aspects` と `caution_dates` が `natal_aspects` を参照）。js-yaml は解決するが、**解決後は同一オブジェクト参照**になる。正規化時にコピーして破壊的変更を避ける
6. 実データにあり圧縮版に無い補助フィールド: `key_periods` / `next_few_days` / `key_aspects` / `active_periods` / `caution_days` / `assets.horoscope_svg`。`next_few_days` は「今後数日」パネルにそのまま使える

テストフィクスチャ: 受領したフル実データ（アンカー付き）を `tests/fixtures/real_data_full.yaml` として保存し、圧縮版 `sample_data_compact.yaml` と両方でパーサテストを回すこと。アンカー解決の検証は実データ側でしか行えない。

---

## 4. 画面仕様

プロトタイプ実装済み（そのまま移植）:

1. **出生図ビューア** — 天体テーブル（グリフ・サイン・度数・ハウス・逆行R）、エレメント/モードのバーチャート、小惑星リスト、主要アスペクト（orb≤2.2のチップ表示）
2. **38日カレンダー** — 曜日始まりの実カレンダー配置。各セル: 日付、正午の月サイン、調和/緊張アスペクトのドット（orb≤1）、キーデート◆、「注意」「動」バッジ、今日ハイライト。上部に overall_theme、下部に action_hints
3. **日別詳細** — シグネチャ要素「朝・昼・夜の三連パネル」（曙色/浅葱/藤紫のトーン、月のサイン・度数・ハウス・アスペクト）。前後日ナビ、トランジット→ネイタルのアスペクト一覧（orb昇順）、運行天体テーブル、「この日をAIに読ませる→」ボタン
4. **AI鑑定** — セクション別生成ボタン（全体像／才能・強み／つまずきやすいパターン／仕事／人間関係／今後38日間／選択日の使い方）。生成結果をカードで蓄積表示

Phase 1 で追加する機能:

- **YAML読み込みUI**: ファイルドロップ＋テキスト貼り付け。パース成功でプロファイル切替、失敗時はエラー理由を表示（プロトタイプはデータ埋め込みのため未実装）
- **localStorage永続化**: 読み込んだYAML（複数プロファイル）とAI鑑定結果をキー `nanami:{profile_id}` で保存
- **鑑定結果のコピー/Markdownエクスポート**

Phase 2 で追加する機能:

- `assets.horoscope_svg` のSVGホロスコープ図表示（出生図タブ）
- 月ごとのトランジット追加YAMLのマージ（`data_role: base_chart` + addon の結合。usage_note.continuous_use 参照）
- 印刷用レイアウト／PDF出力
- 鑑定文の全セクション一括生成（キュー実行）

---

## 5. デザイントークン（プロトタイプ準拠）

```
コンセプト: 「夜の暦」。藍鉄の地に月白の文字。朝→昼→夜のグラデーションを全体の軸にする。
シグネチャ: ヘッダー下のホライズンライン(dawn→day→night) と 日別詳細の三連パネル。

色:
  bg      #14161E   panel  #1C2030   panel2 #232840   line #2E3348
  text    #E8E4D8   sub    #9BA0B2   faint  #6C7183
  dawn(朝) #E8A87C   day(昼) #86BFCB   night(夜) #A79BD4
  good(調和) #8FBF9F  hard(緊張) #D98A93  conj(合) #D4B475

タイポグラフィ:
  見出し: Shippori Mincho → Hiragino Mincho ProN → Yu Mincho（明朝・letter-spacing広め）
  本文:   Hiragino Kaku Gothic ProN → Yu Gothic → system-ui
  ※Web配信時は Google Fonts の Shippori Mincho を読み込む

アスペクト記号と色:
  ☌合=conj  ☍オポ=hard  □スクエア=hard  △トライン=good  ⚹セクスタイル=good

品質基準: 720px以下で1カラムに折返し / focus-visible リング / prefers-reduced-motion 対応（プロトタイプ実装済み）
```

---

## 6. AI鑑定仕様

- モデル: `claude-sonnet-4-6`（Phase 2でコスト調整するなら haiku 系に差し替え可能な設計に）
- 生成単位: セクション別（1リクエスト1セクション、max_tokens 1000〜2000）
- ペイロード圧縮: 全YAMLは送らない。プロトタイプの `buildPayload()` を正とする
  - 共通: 出生図天体（sign_ja/度数1桁/ハウス/逆行）、小惑星、natal aspects orb≤2.2、elements/modes
  - 「今後38日間」: 期間サマリー + 日別アスペクト orb≤0.8 のみ
  - 「選択日」: 対象日の natal_aspects 全件 + moon_timepoints
- プロンプトの必須ルール（元の鑑定プロンプトから継承。システムプロンプトに固定すること）:
  1. 計算結果を変更・再計算しない。JSON内の値のみを根拠にする
  2. 断定しすぎず「傾向・使い方・活かし方」として表現する
  3. 「良い・悪い」ではなく「どう使うとズレにくいか」を優先する
  4. 「ラッキー」等の軽い表現は避け、具体的な行動ヒントに置き換える
  5. `today.selected_date` 基準で過去日は振り返り、以降を今後として扱う
  6. 月の朝・昼・夜データは日内の使い方の根拠として使う
- エラー処理: API失敗時は理由を表示し再試行可能に。overloaded(529)は指数バックオフ

---

## 7. 実装タスクリスト（Claude Codeへの指示に使う）

Phase 1:
- [x] Vite + React + TS 雛形作成、デザイントークンを theme 化
- [x] `src/lib/parseYaml.ts`: js-yaml でパース → 内部モデルへ正規化 + バージョン検証 + 単体テスト（sample_data_compact.yaml をフィクスチャに）
- [x] プロトタイプJSXを components/ に分割移植（NatalView / CalendarView / DayDetail / AIView / AspectChip）
- [x] YAML読み込みUI（ドロップ＋貼り付け）と localStorage プロファイル管理
- [x] AI鑑定: `src/lib/reading.ts` に buildPayload とプロンプトを移植、.env のキーで呼び出し
- [x] 鑑定結果の保存・コピー・Markdownエクスポート

Phase 2:
- [ ] Next.js 化 or API プロキシ追加（キー秘匿＋レート制限）
- [ ] horoscope_svg 表示、月次アドオンYAMLマージ、印刷レイアウト

Phase 2.5（タイムライン拡張。§9 参照）:
- [ ] 共通イベント型 `TimelineEvent` と各ソースのアダプタ
- [ ] ズーム切替（日→月→年→人生）、既存の月カレンダーを「月」スケールに接続
- [ ] ユーザーイベントの localStorage CRUD、占術イベントとのマージ表示
- [ ] 人生ビュー（Time River）とGoogleカレンダー追加リンク

受け入れ基準:
- sample_data_compact.yaml と本番フルYAMLの両方が読み込め、38日全日がカレンダーに出る
- 表示される度数・orb・ハウスがYAMLの値と一致する（テストで担保）
- AI鑑定の出力にYAMLに存在しない天体配置への言及がない（目視レビュー項目）

---

## 8. Claude Code への最初の依頼文（コピペ用）

```
このリポジトリの「ClaudeCode引き継ぎ_星読みの暦.md」を読んでください。
同梱の 星読みの暦_プロトタイプ.jsx がUIとロジックの正です。
まず Phase 1 のタスクリスト順に、Vite + React + TypeScript で実装してください。
デザイントークン(§5)とAI鑑定ルール(§6)は変更しないでください。
最初に parseYaml.ts とそのテストから着手し、テストが通ってからUI移植に進んでください。
```

---

## 9. タイムライン拡張（人生ズーム / Time River）

**目的**: 新規アプリではなく、既存の月トランジットカレンダーを土台に「日→月→年→人生」とズームアウトできる占星術タイムラインへ発展させる。Googleマップの「街→県→国」のように縮尺だけが変わるイメージ。**既存機能（出生図・38日カレンダー・日別詳細・AI鑑定）は壊さず、その上に載せる。**

### 9.0 データ供給の前提（先に読む）

現行YAMLの占術イベントは **38日分のみ**。年・人生ビューが必要とする遠い年のイベント（例: 2008「転機」、2027「木星・天王星」）は**このデータに存在しない**。したがって:

- タイムラインの器（ズーム、共通イベント型、ユーザーイベント、Googleカレンダー）は**今すぐ実装してよい**
- 年/人生の**占術イベントの中身**は、(a) 月次追加YAMLを積む、または (b) 外惑星の主要トランジット（イングレス、木星合土星など）を別途計算する、というデータ供給が前提
- **供給が無い年のイベントを推測・捏造しない**（§1の絶対ルールと同じ）。データが無い期間は「ユーザーイベント＋38日窓」だけを表示し、占術イベントは空でよい

### 9.1 共通イベント構造

すべてのビューはこの単一型の配列を消費する。将来ソースが増えても型は変えない。

```ts
type TimelineScale = "day" | "month" | "year" | "life";

type TimelineSource =
  | "transit"        // 既存 daily / natal_aspects 由来
  | "transit_major"  // 外惑星の主要イベント（木星合土星・イングレス等。将来のデータ供給）
  | "user"           // ユーザー入力
  // 将来: "shichusuimei" | "acg" | "solar_return" | "progression" | "note" | "ai_archive"
  ;

type TimelineEvent = {
  id: string;
  type: string;            // "aspect" | "ingress" | "milestone" | "custom" など
  date: string;            // 'YYYY-MM-DD'（時刻は任意で 'YYYY-MM-DDTHH:mm'）
  endDate?: string;        // 期間イベント用（任意）
  title: string;           // 例: "木星 合 土星"
  description?: string;
  source: TimelineSource;
  meta?: Record<string, unknown>;  // orb, bodies, aspect など source 別の追加情報
};
```

アダプタで既存データを吸収する: `fromTransitDaily(daily) => TimelineEvent[]`（natal_aspects の orb 閾値で「重要」を抽出）、`fromUserEvent(input) => TimelineEvent`。ビューはソースを区別せず `TimelineEvent[]` を受ける。

### 9.2 ズーム4段

画面上部に `[日] [月] [年] [人生]` の切替を置く。

- **日**: 既存の日別詳細（朝・昼・夜）をそのまま接続
- **月**: 既存の38日カレンダーをそのまま接続
- **年**: その年の重要イベントのみを月ごとに区切って一覧。占術イベントは「タイトなアスペクト（orb 小）・イングレス・外惑星の合」に絞る＋ユーザーイベントは全件。行クリックで従来の月カレンダーへ遷移
- **人生**: 出生（1976）から未来までを縦タイムライン表示。1年1区切り、年境界に細い区切り線。現在の年に `現在` バッジ（dawn アクセント）

### 9.3 ユーザーイベント（localStorage）

占術イベントとは別に、ユーザーが自由に追加・編集・削除できる。

- 保存キー: `nanami:{profile_id}:userEvents` → `TimelineEvent[]`（`source:"user"`）
- 入力: 日付・タイトル・説明。例「2026-07-09 AI占い公開」「2027-03-01 引越し」「2028-04-10 転職」
- サーバ保存は不要。まず localStorage で十分

### 9.4 マージ表示

年・人生ビューは占術イベントとユーザーイベントを日付でマージして時系列表示する。例:

```
2026
 7/9  AI占い公開（user）
 7/15 満月（transit）
 8/6  木星 合 土星（transit）
 9/22 木星 合 太陽（transit_major）
```

### 9.5 詳細画面とGoogleカレンダー

イベントクリックで従来の詳細（解説／AI用YAML／Googleカレンダー登録）を表示。人生タイムラインからも登録できる。

Googleカレンダー追加は**APIを使わずリンクで実装**（ユーザーがクリックして開くだけ。認証・権限不要）:

```
https://calendar.google.com/calendar/render?action=TEMPLATE
  &text={encodeURIComponent(title)}
  &dates={YYYYMMDD}/{YYYYMMDD}      // 終日。時刻付きは {YYYYMMDDTHHMMSS}/{...}
  &details={encodeURIComponent(description)}
```

### 9.6 デザイン（Time River）

静かに人生をスクロールする縦リバー。§5のトークンを流用し、新色は足さない。年境界に `line` の細い区切り、現在位置のみ `dawn` で強調。装飾とモーションは最小限（`prefers-reduced-motion` 尊重）。既存カレンダーの配色・タイポと地続きに。

### 9.7 将来拡張

四柱推命 / ACG / ソーラーリターン / プログレス / ノート / AI Conversation Archive も、すべて §9.1 の `TimelineEvent`（`source` を増やすだけ）として同じタイムラインに載る構造を保つ。ビュー側はソース非依存に書く。

### 9.8 Git運用

- 作業開始前に現在状態を確認し、必要ならチェックポイントコミット
- この拡張は大規模UI改修に当たるため、**着手前のチェックポイントコミットを推奨**（例: `git commit -m "checkpoint: before timeline zoom"`）
- 既存機能を壊さないこと。まず器（型・ズーム切替・ユーザーイベント）を薄く通し、占術イベントの充実は後段で足す
