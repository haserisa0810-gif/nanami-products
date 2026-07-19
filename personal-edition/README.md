# Birth Chart Museum — Personal Edition（販売用ローカル版）

Etsy / Payhip などで販売する、購入者のPCで動くローカル版 Birth Chart Museum。
**Web 公開版（`templates/` + `static/`、FastAPI 配信）はソース・オブ・トゥルースのまま一切変更しない。**
このディレクトリはビルド材料とビルドスクリプトだけを持ち、`build.py` が Web 版のソースから
販売用 ZIP を生成する。

## ビルド方法

```bash
python personal-edition/build.py
```

出力（`dist/` は git 管理外）。配布先ごとに初期言語が違う2バリアントを一度に生成する:

```
personal-edition/dist/
├─ BirthChartMuseum-PersonalEdition-EN/           ← 展開済み（英語デフォルト・Etsy用）
├─ BirthChartMuseum-PersonalEdition-EN-v1.0.0.zip
├─ BirthChartMuseum-PersonalEdition-JA/           ← 展開済み（日本語デフォルト・STORES用）
└─ BirthChartMuseum-PersonalEdition-JA-v1.0.0.zip
```

バリアントの違いは各 HTML に注入される `window.HT_DEFAULT_LANG`（"en" / "ja"）の1行だけ。
初期言語の優先順位は URL `?lang` → 本人の過去の切替（localStorage）→ この配布設定 →
ブラウザ言語 → en。画面内の日英切替は両バリアントに残る。

Web 版テンプレートの文言・構造が変わって置換が合わなくなると **AssertionError で停止**する
（黙って壊れた ZIP を作らない）。その場合は `build.py` の該当置換を更新すること。

## 購入者の使い方（ZIP の中身）

```
BirthChartMuseum-PersonalEdition/
├─ start.bat        ← Windows: ダブルクリック（PowerShell 内蔵サーバ、追加インストール不要）
├─ start.command    ← Mac: ダブルクリック（python3 / ruby の順で自動選択）
├─ README.txt       ← 購入者向け説明（日本語＋English）
├─ LICENSES.txt     ← 同梱 OSS ライセンス（three.js / js-yaml / Cinzel）
├─ tools/
│  ├─ server.ps1    ← Windows 用ローカルサーバ（HttpListener、localhost のみ）
│  └─ server.py     ← Mac / Python 環境用ローカルサーバ（127.0.0.1 のみ）
└─ app/
   ├─ index.html                      ← ミュージアム入口（/ で配信）
   ├─ house-tour/index.html           ← 象徴版
   ├─ house-tour-architecture/index.html ← 建築版
   ├─ dream-sky/index.html            ← Dream Sky
   ├─ static/…                        ← Web 版から複製した CSS / JS（*.md 除外）
   └─ vendor/…                        ← 同梱ライブラリとフォント
```

起動フロー: start をダブルクリック → localhost の空きポート（8787〜8796）でサーバ起動 →
ブラウザが自動で開く → 入口で出生図 YAML を貼り付け（sessionStorage で各版に引き継ぎ、
Web 版と同一のクライアント処理）。

### なぜローカルHTTPサーバ方式か

`house-tour` / `house-tour-architecture` は ES Modules（`<script type="module">` +
相対 import 約20ファイル）で構成されており、`file://` 直接オープンでは CORS 制約で
確実に動かない。よって `index.html` 直開き方式は不採用。サーバは
- Windows: OS 標準の PowerShell だけで動く（追加インストール不要）
- Mac: python3（開発者ツールあり）→ OS 同梱 ruby の順にフォールバック

## Web 版が使っている外部依存の一覧（調査結果）

| 依存 | 使用ページ | Personal Edition での扱い |
|---|---|---|
| cdnjs: three.js r128 `three.min.js` | house-tour / architecture / dream-sky | `vendor/three.min.js` に同梱 |
| cdnjs: js-yaml 4.1.0 | 同上 | `vendor/js-yaml.min.js` に同梱 |
| jsDelivr: three@0.128.0 OrbitControls.js | dream-sky のみ | `vendor/OrbitControls.js` に同梱 |
| Google Fonts: Cinzel 400/500 | 入口 / house-tour / architecture | woff2 を `vendor/fonts/` に同梱（OFL 1.1） |
| Google Fonts: Noto Sans JP / Noto Serif JP 300-500 | 同上 | **同梱しない**（数十MBになるため）。CSS 既存のフォールバック（Hiragino / Yu Gothic 系）で表示 |

外部 API は **なし**（fetch なし・テクスチャ/音声ファイルなし・YAML 処理は完全クライアントサイド）。
Personal Edition は実行時の外部リクエストがゼロ（完全オフライン動作）。ネットワーク検証済み。

## Web Demo との関係

無料デモは Web 側のルート `/birth-chart-museum/demo`（+ `/architecture`）。
テンプレートの `{% if demo %}` ブロック（`templates/_museum_demo.html` の include）で
サンプル固定・リボン・購入導線を足しているが、**build.py はこのブロックを丸ごと除去する**ので
Personal Edition に demo UI は入らない（ビルド後の検証アサーションあり）。

## Web 版との差分（build.py が行う変換）

- `{{ asset_url('…') }}` → `/static/…`、`{% include "_head_icons.html" %}` → インライン展開
- CDN `<script>` → `/vendor/…`、Google Fonts `<link>` → `/vendor/fonts/fonts.css`
- `href="/birth-chart-museum"` → `href="/"`（入口がルートになるため）
- 「← nanami-products へ戻る」「サイトTOPへ」リンクを削除（販売版に本体サイト導線は不要）
- 入口ロゴの文言を `BIRTH CHART MUSEUM · PERSONAL` に変更

## バージョンアップ手順

1. Web 版（`static/house-tour*`、テンプレート）を通常どおり更新
2. `build.py` の `VERSION` を上げる
3. `python personal-edition/build.py` → 動作確認（start.bat）→ ZIP を差し替え

## 注意

- `vendor/` はコミット対象（オフラインでもビルド再現できるように）
- `dist/` は `.gitignore` 済み。`personal-edition/` 全体を `.gcloudignore` / `.dockerignore`
  に追加済みで、Cloud Run デプロイには含まれない
- 日本語ファイル名は使わない（gcloud アーカイブの文字化け問題。メモリ参照）
