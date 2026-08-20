# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A FastAPI web service that generates structured YAML data for AI-driven astrology readings. It computes Western natal charts (via Swiss Ephemeris / pyswisseph) and optionally Four Pillars of Destiny (四柱推命), then stores results in SQLite keyed by a URL-safe token. The output YAML is intended to be fed verbatim into Claude for interpretation — the AI must not re-derive positions from the birth date.

## Running Locally

```bash
pip install -r requirements.txt
DATABASE_URL=postgresql://user:pass@host/db python -m uvicorn routes:app --reload --port 8080
```

`DATABASE_URL` は必須。Neon の接続文字列（`postgresql://...?sslmode=require`）または `postgres://` スキームどちらでも可（自動変換）。

Key endpoints — 購入者フロー:
- `GET /start` — 注意事項ページ
- `GET /redeem` — 注文番号＋出生情報入力フォーム
- `POST /redeem` — 注文番号検証・YAML生成・リダイレクト
- `GET /chart/{token}` — 購入者専用ページ（YAML・プロンプト全文・コピーボタン）
- `GET /chart/{token}.yaml` — raw YAML
- `GET /chart/{token}/prompt.txt` — AI プロンプトテキスト

Key endpoints — ACG（アストロカートグラフィ）:
- `GET /acg` — 天空線マップページ（マンデン＋YAML貼り付けパーソナル、Leaflet + Natural Earth + turf.js すべて自前ホスティング）
- `GET /api/acg/mundane?date=YYYY-MM-DD` — マンデン線 GeoJSON（認証なし・日次メモリキャッシュ・当該日 03:00 UTC = JST正午固定・日付範囲 1800〜2399）
- `POST /api/acg/personal` — JSON `{"yaml_text": "..."}` → ネイタル線 GeoJSON（ステートレス、保存もログ出力もしない。抽出は subject.datetime 優先 → input フォールバック。過去日は弾かない = Moshier 自動フォールバック）

計算コアは `services/acg_core.py`（`lines_to_geojson(dt_utc, natal=False)`）、API層は `services/acg_api.py`、CLI は `acg.py`。
1 Feature = 1 LineString。経度180度またぎは RFC 7946 準拠で複数 Feature に分割し `properties.line_group`（例 `Venus_MC`）で束ねる。
ASC/DSC は緯度1度刻み（±85）。地点逆引き（500km以内・上位5件・strength判定）と「AIに渡す用YAML」コピーはフロント側 turf.js で実装。
解釈は固定辞書 `static/acg_interpretations.json`（`Venus_MC` 形式キー、label/meaning/meaning_hint、生成AIなし）。

Key endpoints — 管理者フロー:
- `GET /admin/yaml/new` — 管理者用生成フォーム
- `POST /admin/yaml/generate` — YAML 生成・保存
- `GET /admin/yaml/result/{token}` — 管理者結果ページ（購入者 URL 発行）
- `GET /health` — ヘルスチェック（外部からの死活監視はこちら）
- `GET /healthz` — 同内容。ただし Google Front End が `/healthz` を横取りするため、
  Cloud Run の外部URLでは 404 になる。コンテナ直アクセス用。

## Deploy

本番操作は `AGENTS.md` の「Production safety and deploy」に従う。直接 `gcloud run deploy`
を実行せず、clean・commit・push 済みの状態から候補版を 0% 配信で作成し、スモーク
テストと別の明示承認を経てから本番トラフィックを切り替える。

## Architecture

### Data Flow

1. Admin submits birth info via `POST /admin/yaml/generate` (`routes.py`)
2. `services/yaml_exporter.py::build_product_yaml()` orchestrates all calculations
3. `services/western_calc.py::calc_western_from_payload()` runs Swiss Ephemeris for natal chart
4. Optionally `services/shichusuimei_calc.py::calc_shichusuimei_from_payload()` computes Four Pillars
5. Result serialized to YAML + a static prompt string → saved to SQLite via `services/token_store.py`
6. Public URLs serve the stored YAML/prompt by token

### Ephemeris Resolution (`western_calc.py`)

Swiss Ephemeris files (`*.se1`) are looked up in this order:
1. `SWEPH_EPHE_PATH` env var
2. `ephe/` directory adjacent to the project root
3. `/app/ephe` (Docker)

If no `.se1` files are found, it falls back to Moshier ephemeris (`FLG_MOSEPH`). Chiron requires swieph; asteroids can fall back to the FreeAstro external API (see below).

### Asteroid Fallback (`services/asteroid_provider.py`)

When running without `.se1` files, Ceres/Pallas/Juno/Vesta are fetched from an external API:
- `FREEASTRO_BASE` — base URL (set in `config.py`, read from env)
- `FREEASTRO_API_URL` — full URL override (auto-appends `/api/v1/western/natal` if root given)
- `FREEASTRO_API_KEY` — required for the API to be considered "configured"

### Storage (`services/pg_store.py`)

Neon/PostgreSQL。`DATABASE_URL` 環境変数から接続。スキーマ `nanami_products` に 2 テーブル。

- `nanami_products.redemptions` — 注文番号の使用状況を管理。`order_code` PRIMARY KEY で同一注文番号の重複を防ぐ。`redeem_and_save()` は redemptions と charts の INSERT を同一トランザクションで実行する。
- `nanami_products.charts` — 生成済み YAML・プロンプト・出生情報を保存。管理者フロー（`order_code=NULL`）と購入者フロー両方が使う。

`init_db()` はアプリ起動時（`@app.on_event("startup")`）に呼ばれ、スキーマ・テーブルを `IF NOT EXISTS` で作成する。

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | **必須**。Neon/PostgreSQL 接続文字列 |
| `PUBLIC_BASE_URL` | `""` | Override base URL in generated links (important behind proxies) |
| `ADMIN_PASSWORD` | `"admin"` | Unused in current code; reserved |
| `FREEASTRO_BASE` | `""` | FreeAstro service base URL |
| `FREEASTRO_API_URL` | derived | Full asteroid API endpoint |
| `FREEASTRO_API_KEY` | `""` | Enables asteroid fallback |
| `SWEPH_EPHE_PATH` | `""` | Override ephemeris directory |
| `FREEASTRO_API_TIMEOUT` | `12` | Seconds for asteroid API calls |
| `HOSHIYOMI_APP_URL` | `""` | 星読みの暦アプリ（hoshiyomi/）のベースURL。設定すると `/chart/{token}` に「アプリで開く（自動読み込み）」ボタンが出る（`?load=` にYAML/SVGのURLを渡す。公開チャートのYAML/SVGはCORS許可済み） |
| `MUSEUM_SHOP_URL_EN` | `""` | Birth Chart Museum Demo の海外向け販売URL（Etsy）。未設定なら購入ボタンは「近日発売」表示 |
| `MUSEUM_SHOP_URL_JA` | `""` | 同・日本向け販売URL（STORES） |

### 四柱推命 Calculation Notes (`shichusuimei_calc.py`)

- Year/month pillars use solar longitude (立春 = 315°, then 30° steps)
- Day pillar uses `int((JD + 0.5 + 50) % 60)` against `KANSHI_60`
- `day_change_at_23=True` shifts 00:00–00:59 births to the previous calendar day
- 大運 (major luck cycles) direction: yang year stem + male = forward; all other combos follow the standard table
- Gender normalization defaults to `"female"` for any unrecognized input

### Birth Chart Museum Personal Edition (`personal-edition/`) と Web Demo

販売用ローカル版（Etsy=英語 / STORES=日本語）。`python personal-edition/build.py` が Web 版
（`templates/birth_chart_museum.html`・`house_tour*.html`・`static/house-tour*`・`static/dream-sky`）
から静的化した ZIP を EN / JA の2バリアントで `personal-edition/dist/` に生成する。
CDN（three.js r128 / js-yaml 4.1.0 / OrbitControls / Cinzel フォント）は
`personal-edition/vendor/` に同梱済み。Web 版は変更しない。
テンプレート構造を変えると build.py の置換アサーションが失敗するので、その際は build.py も更新する。
詳細は `personal-edition/README.md`。

無料デモ: `GET /birth-chart-museum/demo`（抽象版）・`/birth-chart-museum/demo/architecture`（建築版）。
サンプル出生図（ねこ編集長）固定・YAML/sessionStorage 読込なし・英語デフォルト
（日本向けは `?lang=ja` を配布）。demo UI は `templates/_museum_demo.html` を
`{% if demo %}` で include し、Personal Edition ビルドでは丸ごと除去される。
初期言語の優先順位: URL `?lang` → localStorage → `window.HT_DEFAULT_LANG`（配布設定）→ ブラウザ言語 → en。

### Prompt (`services/prompt_builder.py`)

`build_prompt()` returns a static Japanese-language system prompt instructing the AI to interpret the YAML without re-calculating positions. Modify `BASE_PROMPT` here to change all generated prompt files.
