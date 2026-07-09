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

## 6. AI鑑定仕様（コスト設計込み）

買い手ぶんの実行時課金を発生させないため、鑑定は次の2レーンで提供する。**アプリが買い手の端末でAPIを叩く常時ライブ生成は採用しない**（採用すると買い手×回数ぶん課金が積み上がるため）。

### 6.1 レーンA: 買い手が自分のAIへ受け渡し（無料・既定）

既存 nanami-astro の「AIに送る／コピー」導線と同じ。アプリは圧縮ペイロード＋鑑定プロンプトを組み立てて**コピー / 各AIへ送るボタン**を出すだけ。買い手は自分の ChatGPT / Claude / Gemini（無料枠可）に貼って読む。**あなたの課金ゼロ、買い手の鍵も不要。** プロトタイプのAI鑑定タブは、この方式へ差し替える（`fetch` を「プロンプト生成＋コピー」に置き換え、`buildPayload()` はそのまま流用）。

### 6.2 レーンB: 基本版鑑定を生成時に焼き込み（Gemini 2.5 Flash-Lite）

清書済みの「基本版鑑定」を、**nanami-astro のチャート生成時に一度だけ**生成してZIPに同梱する（§10.1）。買い手のアプリは表示するだけ＝**実行時APIゼロ**。

- モデル: **Gemini 2.5 Flash-Lite**（最安ティア。入力 $0.10 / 出力 $0.40 per 1M。1鑑定 約0.2円）。将来の差し替えを考え、モデル名は生成設定の1箇所に定数化する
- 読ませる範囲（基本版）: **主要天体（Sun〜Pluto＋ASC/MC/North Node）＋（小惑星）＋鑑定プロンプト部分**。トランジットは基本版では送らない（38日/年/人生は別レーン・別データで扱う）
- 出力の**注釈にモデルを明記**（必須）。例: 「本鑑定は Gemini 2.5 Flash-Lite により、計算済みデータのみを根拠に生成しています。」
- 出力形式: セクション見出し付き Markdown。`readings.yaml`（or `readings.md`）としてZIP同梱

### 6.3 プロンプトの必須ルール（両レーン共通・システム側に固定）

1. 計算結果を変更・再計算しない。渡された値のみを根拠にする
2. 断定しすぎず「傾向・使い方・活かし方」として表現する
3. 「良い・悪い」ではなく「どう使うとズレにくいか」を優先する
4. 「ラッキー」等の軽い表現は避け、具体的な行動ヒントに置き換える
5. `today.selected_date` 基準で過去日は振り返り、以降を今後として扱う
6. 月の朝・昼・夜データは日内の使い方の根拠として使う

### 6.4 ペイロード圧縮（プロトタイプ `buildPayload()` を正とする）

- 基本版（レーンB）: 主要天体（sign_ja/度数1桁/ハウス/逆行）＋小惑星＋natal aspects orb≤2.2＋elements/modes
- 「今後38日間」（レーンAで任意生成）: 期間サマリー ＋ 日別アスペクト orb≤0.8 のみ
- 「選択日」（レーンAで任意生成）: 対象日の natal_aspects 全件 ＋ moon_timepoints

### 6.5 アプリ内ライブAPI（開発検証のみ）

プロトタイプのライブ `fetch` は**あなたの検証用途に限り**残してよい（`.env` のキー、Flash-Lite の無料枠可）。配布ビルドには含めない。将来どうしても買い手のアプリ内ライブ生成が必要になったら §11.1 のプロキシ＋レート制限を検討。

---

## 7. 実装タスクリスト（Claude Codeへの指示に使う）

Phase 1:
- [ ] Vite + React + TS 雛形作成、デザイントークンを theme 化
- [ ] `src/lib/parseYaml.ts`: js-yaml でパース → 内部モデルへ正規化 + バージョン検証 + 単体テスト（sample_data_compact.yaml をフィクスチャに）
- [ ] プロトタイプJSXを components/ に分割移植（NatalView / CalendarView / DayDetail / AIView / AspectChip）
- [ ] YAML読み込みUI（ドロップ＋貼り付け）と localStorage プロファイル管理
- [ ] AI鑑定: `src/lib/reading.ts` に buildPayload とプロンプトを移植、.env のキーで呼び出し
- [ ] 鑑定結果の保存・コピー・Markdownエクスポート

Phase 2 — アプリ側（§9・§11 参照）:
- [ ] AI鑑定タブをレーンA（コピー／自分のAIへ送る）へ差し替え（§6.1）
- [ ] 焼き込み `readings.yaml` を表示するビュー（§6.2 / §10.1）
- [ ] 共通イベント型 `TimelineEvent` と各ソースのアダプタ（§9.1）
- [ ] ズーム切替（日→月→年→人生）、既存の月カレンダーを「月」スケールに接続
- [ ] `life_events.yaml` を年/人生ビューへ流し込み（§10.2）
- [ ] ユーザーイベント／日記の localStorage CRUD、占術イベントとのマージ表示
- [ ] 人生ビュー（Time River）とGoogleカレンダー追加リンク（§9.5/9.6）
- [ ] horoscope_svg 表示（§11.2）、月次マージ（§11.3）、印刷レイアウト（§11.4）

Phase 2 — 生成側（nanami-astro / Python。§10 参照）:
- [ ] 基本版鑑定を Gemini 2.5 Flash-Lite で焼き込み → `readings.yaml`（§10.1）
- [ ] `life_events.yaml` 広域スキャン生成（Swiss Ephemeris・主要イベントのみ）（§10.2）
- [ ] profile 単位ZIPに readings / life_events / horoscope.svg を同梱（§10.3）

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

---

## 10. 生成側（nanami-astro バックエンド）の追加出力

ここは Vite アプリ（Claude Code）ではなく、**既存の nanami-astro 生成パイプライン（Swiss Ephemeris / Python）側のタスク**。アプリは常に「計算済みデータを表示するだけ」を保ち、計算は必ず生成側で行う（§1の絶対ルール）。

### 10.1 基本版鑑定の焼き込み（§6.2 の生成ステップ）

チャート/ZIP生成の最後に1ステップ足す:

1. 主要天体＋（小惑星）＋natal aspects(orb≤2.2)＋elements/modes を圧縮ペイロード化
2. §6.3 のルールをシステムプロンプトに固定し、**Gemini 2.5 Flash-Lite** を1回呼ぶ
3. 返ってきた Markdown に**モデル注釈**（§6.2）を付け、`readings.yaml`（or `readings.md`）としてZIPに同梱
4. コストは1商品あたり約0.2円。低ボリュームなら Flash-Lite 無料枠でも可

### 10.2 年/人生ビューのデータ供給（`life_events.yaml`）

年/人生スケールが必要とする「遠い年の占術イベント」は38日YAMLに無い。**nanami-astro の Swiss Ephemeris で広域スキャンした専用ファイルを生成**して供給する（アプリ側では絶対に計算しない）。

- 出力: `life_events.yaml`。中身は §9.1 `TimelineEvent` 互換の配列（`source: "transit_major"`）
- 生成エンジン: 既存と同一（Swiss Ephemeris / tropical / Placidus / Asia/Tokyo）
- スキャン範囲: `birth_date` 〜 `today + N年`（N は設定。例: +10年）。過去（出生〜現在）も含めて人生タイムラインを埋める
- **人生スケール向けに「主要イベントだけ」に絞る**（ノイズ回避）:
  - 外惑星（Jupiter/Saturn/Uranus/Neptune/Pluto/Chiron）→ natal の Sun/Moon/ASC/MC/Saturn/Node への major aspect（conj/opp/square/trine）、タイトorb（例 ≤1°）、**ピーク日**を出力
  - リターン: Saturn return（約29.5年・59年）、Jupiter return（約12年ごと）、Nodal return（約18.6年）、Chiron return（約50年）
  - 外惑星のサイン・イングレス（世代の節目）、木星–土星コンジャンクション等の主要ムンダン（任意）
- 各イベント → `{ id, type:"aspect"|"return"|"ingress", date:ピーク日, title:"木星 合 土星" 等, description:meaning_hint, source:"transit_major", meta:{bodies, aspect, orb} }`
- 粒度: 「年」ビューは月解像度、「人生」ビューは年ごとに最重要イベントへ集約（アプリ側でフィルタしてもよいが、集約済みの `granularity` フィールドを持たせると軽い）

これでアプリは `life_events.yaml` を読み込むだけで年/人生ビューが埋まる。ファイルが無い期間は「ユーザーイベント＋38日窓」だけを表示（捏造しない）。

### 10.3 生成物の受け渡し

profile 単位で `{natal.yaml, transit(38d).yaml, readings.yaml, life_events.yaml, horoscope.svg}` をZIP同梱。アプリの読み込みUI（§4 Phase1）はこれらを一括で取り込む。将来の月次追加（§11.3）も同じ profile_id に束ねる。

---

## 11. Phase 2 実装詳細（アプリ側 / Claude Code）

### 11.1 APIプロキシ（焼き込み採用なら“任意”）

§6のレーンA＋Bを採用する限り**買い手のアプリはAPIを叩かないので、プロキシは不要**。将来「買い手がアプリ内でライブ生成」を出したくなった場合にのみ、Next.js API Route か Cloudflare Workers でキーを秘匿し、IP/セッション単位のレート制限（例: 1日20回）を掛ける。代替は BYOK（買い手が自分の鍵を入力、localStorage保存・サーバ非送信）。

### 11.2 horoscope_svg 表示

`assets.horoscope_svg`（nanami-astro が既に出力している `horoscope.svg`）を出生図タブに表示。ZIP内のSVGをそのまま `<img>` か inline SVG で描画するだけ。無ければ天体テーブルのみ表示にフォールバック。

### 11.3 月次トランジットのマージ（＋日記レイヤーの土台）

毎月の「次のトランジット」YAML（`data_role` addon）を取り込み、既存 `daily[]` に**日付キーでマージ**して連続タイムライン化する:

- マージキー: `date`（'YYYY-MM-DD'）。重複日は新しい addon を優先
- `period` は全体の最小 start 〜 最大 end に拡張。今日ハイライトは `today.selected_date`
- 保存: `nanami:{profile_id}` に統合済みトランジットをキャッシュ（localStorage）
- **日記レイヤー**: 各日付に一言メモを紐付け、`TimelineEvent`（`source:"diary"`）として `nanami:{profile_id}:userEvents` に保存（§9.3と同型）。別アプリにする場合も同じキー/型を共有すれば相互に開ける

### 11.4 印刷 / PDF レイアウト

出生図・鑑定・選択期間を1枚に流す印刷用CSS（`@media print`）。まずはブラウザ印刷→PDFで十分。
