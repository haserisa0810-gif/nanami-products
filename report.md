# nanami-products 調査レポート

> 調査のみ。コード・ファイルは一切変更していません。
> 「コード上の懸念（未再現）」と「要確認」を明示的に分けています。実機・本番設定での再現確認は行っていません。

## 総評

決済・購入者フロー・トークン・課金まわりの**基礎設計は概ね堅実**です。特に以下は良くできています。

- 購入者チャートのトークンは `secrets.token_urlsafe(18)`（推測困難）。
- 公開チャートは有効期限（発行から90日、期限切れは 410）・`X-Robots-Tag: noindex`・期限切れ時 `no-store` を付与。
- 注文番号の二重使用は `redemptions.order_code` の `INSERT ... ON CONFLICT DO NOTHING` で原子的に防止。チャート保存と同一トランザクション。
- APIキーは平文保存せず **SHA-256 ハッシュ**保存（表示は `key_prefix` のみ）。生成は `np_` + `token_urlsafe(32)`。
- APIクレジット消費は条件付き `UPDATE ... WHERE credits_remaining >= %s` で原子的（多重消費・マイナス残高を防止）。
- SQLは全て psycopg のプレースホルダ（`%s`）でパラメータ化。ユーザー入力のSQL連結は見当たらず。
- テンプレートのJS埋め込みは `| tojson`、HTMLはJinja2オートエスケープ。`|safe` はi18n定型文のみで、YAML/氏名など可変値には未使用 → XSS面は低い。
- サーバー側での生成AI（Claude/OpenAI/Gemini）呼び出しは**無し**。YAMLは決定的計算。→ 指示項目11「AI生成（timeout/token超過/truncation）」は本サービスには基本該当しません。

**特に危ない領域は「Secret管理」と「認証境界」**です。gitに管理者トークンが平文で残っており、かつ有料商品の生成が認証なしの管理エンドポイントから叩ける状態です。ここは早急な対応を推奨します。

---

## Critical

### C-1: gitに管理者トークンが平文でコミットされている
- **重大度:** Critical
- **該当ファイル:** `backups/secret-migration-20260516/nanami-products-before.yaml`（**git管理下**）
- **該当箇所:** L59-66。`API_KEY_ADMIN_TOKEN: 7f2c9d4b8a1e4f0a9d6b3c1e5f7a2b8c4d1e6f9a0c3b7d5e8f1a4c6b9d2e5f0`、および `ADDON_KEY_WESTERN_ASTEROIDS` / `ADDON_KEY_WESTERN_31DAYS_TRANSIT` / `ADDON_KEY_SHICHU_FORTUNE_CYCLES` の各値。
- **内容:** Cloud Run 設定のスナップショットがバックアップとしてコミットされており、その中に管理者トークンとアドオンキーが平文で入っている。`DATABASE_URL` は `secretKeyRef` 化されているが、トークン類は素の値。
- **なぜ問題か:** `API_KEY_ADMIN_TOKEN` は `/internal/api-keys`（APIキー発行）・`/internal/api-keys/reissue`・`/internal/redemptions/reset`（注文の再利用解放）・`/internal/charts/expired/cleanup` の認可に使われる（`_admin_access_error` → `_admin_token_from_env`）。このトークンを知る者は、**任意クレジットのAPIキーを無制限に発行**（＝API課金の踏み倒し）、**注文番号のリセットによる有料商品の再取得**、期限切れチャートの削除が可能。現行 `deploy.env.yaml` の値と一致していれば即座に悪用可能。
- **確認方法:** `git log -p -- backups/` でコミット履歴に値が残っていることを確認。現行本番の `API_KEY_ADMIN_TOKEN` と一致するか照合。
- **修正する場合の方向性:** 当該ファイルを履歴から除去（git filter-repo等）＋ `API_KEY_ADMIN_TOKEN` と全 `ADDON_KEY_*` を**ローテーション**。以後はコミット前提のバックアップに平文シークレットを含めない。
- **修正優先度:** 最優先
- **様子見可能か:** 不可。

### C-2: 有料商品生成が認証なしの管理エンドポイントから可能
- **重大度:** Critical（ビジネスロジック迂回）
- **該当ファイル:** `routes.py`
- **該当箇所:** `POST /admin/yaml/generate`（4230行）、`POST /admin/post-chart/generate`（4190行）、`GET /admin/yaml/new`（3797行）。いずれも `_admin_access_error` 等の認可を**呼んでいない**。ミドルウェア（387行）もキャッシュ制御のみで認証しない。
- **内容:** `/admin/yaml/generate` は注文番号の検証を一切せずに `build_product_yaml()` を実行し、チャートを `order_code=NULL` で保存してトークンURLを返す。購入者フロー（`/redeem`）が行うSTORES/Payhip照合を完全に迂回する。
- **なぜ問題か:** (1) 有料商品（西洋・四柱・トランジットYAML）を**無料で無制限に生成**できる。(2) 認証なしで Swiss Ephemeris 計算＋DB書き込みを誘発でき、**計算リソース枯渇・DB肥大の DoS 面**になる。トークンは乱数なので他人のデータ閲覧はできないが、商品価値と可用性に直接影響。
- **確認方法:** 認証ヘッダなしで `POST /admin/yaml/generate`（`birth_date` のみ必須）→ 303 で `/admin/yaml/result/{token}` に到達しチャートが生成されることを確認。
- **修正する場合の方向性:** `/admin/*` の生成・フォーム系に `_admin_access_error` 相当のトークン認可を付与（`/internal/*` と同じ仕組みを流用）。少なくとも本番では `X-Admin-Token` 必須に。
- **修正優先度:** 最優先
- **様子見可能か:** 不可。

---

## High

### H-1: `deploy.env.yaml` にローカル平文シークレットが集中
- **重大度:** High
- **該当ファイル:** `deploy.env.yaml`（`.gitignore` 対象・git未追跡）
- **該当箇所:** `STORES_MAIL_PASSWORD`（Gmail アプリパスワード）、`API_KEY_ADMIN_TOKEN`、`ADDON_KEY_*`、`STORES_MAIL_SYNC_TOKEN`、`DATABASE_URL` 等。
- **内容:** git未追跡なのは適切だが、実ファイルが平文で存在し、C-1で同種トークンが既に流出圏内。IMAPパスワードはメール本文（購入者の個人情報を含む）への全アクセス権を意味する。
- **なぜ問題か:** 端末・バックアップ経由の流出で決済照合メール（購入者氏名・メール）を含む Gmail 全体、DB、管理操作が同時に危険化。
- **確認方法:** `git ls-files | grep deploy.env`（未追跡＝OK）を確認しつつ、Secret Manager 移行状況を確認。
- **修正する場合の方向性:** Secret Manager へ全面移行。少なくとも `STORES_MAIL_PASSWORD` / `API_KEY_ADMIN_TOKEN` は環境変数直書きをやめる。
- **修正優先度:** 高
- **様子見可能か:** 不可（C-1と併せて対応）。

### H-2: `/internal/*` 系のフェイルオープン認可
- **重大度:** High
- **該当ファイル:** `routes.py`
- **該当箇所:** `internal_init_db`（1971行）・`internal_mail_sync`（2995行）は `STORES_MAIL_SYNC_TOKEN` が未設定だと**認証をスキップ**して実行。`_admin_access_error`（2015行）は `_admin_token_from_env()` が空のとき、リモートは401だが**ローカル判定のみ**にフォールバック。
- **内容:** トークン環境変数の設定漏れ・空文字で、認証が丸ごと無効化される設計（fail-open）。
- **なぜ問題か:** デプロイ事故・環境変数欠落時に、DB初期化・メール同期・（`_admin_access_error`側は）管理操作が無防備化。
- **確認方法:** トークン env を空にした状態で各エンドポイントへアクセスし、認証なしで通ることを確認。
- **修正する場合の方向性:** トークン未設定時は 500 で停止（fail-close）。
- **修正優先度:** 高（**要確認:** 本番で各トークンが確実に設定されているか）
- **様子見可能か:** 本番で必ず設定されているなら実害は低いが、設計として要修正。

### H-3: 管理トークンの用途兼用・単一シークレット
- **重大度:** High
- **該当ファイル:** `routes.py:1986-1990`（`_admin_token_from_env`）
- **内容:** `API_KEY_ADMIN_TOKEN` が無ければ `STORES_MAIL_SYNC_TOKEN` を管理トークンとして流用。1つのシークレットが「メール同期」「APIキー発行」「注文リセット」「管理テストサイトのパス生成」を兼ねる。
- **なぜ問題か:** 1つ漏れると全権限が漏れる。最小権限・分離ができていない（C-1の被害範囲を拡大させる）。
- **修正する場合の方向性:** 用途別トークンに分離。
- **修正優先度:** 中〜高
- **様子見可能か:** 可（ただしC-1対応時に合わせて見直し推奨）。

### H-4: デモAPIが認証・レート制限なし
- **重大度:** High（コスト/可用性）
- **該当ファイル:** `routes.py:2763-2778`（`/api/demo/western|shichu|transit|combined`）、`_demo_response`（2462行）
- **内容:** デモ計算エンドポイントはAPIキー不要・レート制限なしで Swiss Ephemeris 計算を実行。
- **なぜ問題か:** 無認証で重い計算を無制限に叩ける → 計算リソース枯渇の DoS 面、有料APIのタダ使い。
- **確認方法:** 認証なしで `/api/demo/combined` を連打し、200が返り続けることを確認。
- **修正する場合の方向性:** デモにIPベースのレート制限、または入力サイズ・回数制限を導入。
- **修正優先度:** 中
- **様子見可能か:** 現状トラフィックが小さいなら可。

### H-5: マンデン管理が「秘匿パス頼み」で既定値がソース内
- **重大度:** High
- **該当ファイル:** `routes.py:3822`
- **該当箇所:** `MUNDANE_ADMIN_PREFIX = os.getenv("MUNDANE_ADMIN_PREFIX", "/admin/7d4c2f8b91a64e0d/mundane")`
- **内容:** マンデン記事の作成・編集（公開 `/mundane/{slug}` に反映）は認証ではなく**推測困難パス**で保護。既定値がコードにハードコードされており、env未設定ならこの既定パスで誰でも投稿・編集可能。
- **なぜ問題か:** セキュリティ・バイ・オブスキュリティ。パスが知られれば公開ページの改ざん（デファンス）が可能。
- **確認方法:** `MUNDANE_ADMIN_PREFIX` env の設定有無を確認。未設定なら既定パスでPOSTが通る。
- **修正する場合の方向性:** トークン認可へ変更、または最低限 env 必須化。
- **修正優先度:** 中
- **様子見可能か:** env で上書き済みなら可（**要確認**）。

---

## Medium

### M-1: 例外ログに購入者メールが出力される
- **重大度:** Medium（個人情報）
- **該当ファイル:** `routes.py`（`_resolve_payhip_order_from_metadata` 内）
- **該当箇所:** `logger.exception("payhip_order_check_failed email=%s product_code=%s ...", email_clean, ...)`
- **内容:** Payhip照合の例外時に購入時メールアドレスを Cloud Run ログへ出力。
- **なぜ問題か:** 個人情報がログに残留。他の大半のログは `token[:8]` / `order_id` 止まりで良好なだけに、この経路が例外。
- **修正する場合の方向性:** メールをマスキング（例：先頭数文字＋ドメイン）またはログから除外。
- **修正優先度:** 中
- **様子見可能か:** 可（早めに対応推奨）。

### M-2: DATABASE_URL 未設定時に注文照合が "ok" を返す
- **重大度:** Medium
- **該当ファイル:** `routes.py`（`_check_order_for_redeem`）
- **該当箇所:** `if not os.environ.get("DATABASE_URL"): ... return "ok", None, None, 200`（stores系）
- **内容:** DB未設定だと STORES 注文の厳格照合をスキップして "ok"。実際には直後の保存でDB無しなら失敗するため実害は限定的だが、照合ロジックとしては fail-open。
- **なぜ問題か:** 「DB未設定＝検証通過」は危険側の初期値。将来の分岐変更で穴になりうる。
- **修正する場合の方向性:** DB未設定は 503 で停止に統一。
- **修正優先度:** 低〜中
- **様子見可能か:** 可。

### M-3: レート制限判定に TOCTOU の隙
- **重大度:** Medium（コード上の懸念・未再現）
- **該当ファイル:** `routes.py`（`_check_api_rate_limit` 2448行）
- **内容:** レート制限は `count_api_usage_since` の読み取り→判定で、同時多発リクエスト時に上限を僅かに超える可能性。**クレジット消費自体は原子的**なので課金の過剰請求は起きない。
- **なぜ問題か:** レート上限がバースト時に厳密に守られない可能性。
- **修正する場合の方向性:** 厳密性が必要なら消費と同一トランザクションでのカウント、または原子的インクリメント。
- **修正優先度:** 低
- **様子見可能か:** 可。

### M-4: 起動時にDB初期化せず、手動 `/internal/init-db` 依存
- **重大度:** Medium（運用）
- **該当ファイル:** `routes.py:1963`（`startup` は初期化スキップ）
- **内容:** テーブル作成は `/internal/init-db` を手動で叩く運用。新規デプロイ・スキーマ追加直後は、叩くまでエラーを返しうる。
- **なぜ問題か:** 手順漏れで本番が一時的に機能しない運用リスク。
- **修正する場合の方向性:** 起動後の非同期初期化、またはデプロイ手順の自動化・チェックリスト化。
- **修正優先度:** 低〜中
- **様子見可能か:** 可（**要確認:** デプロイ手順に組み込まれているか）。

### M-5: 課金APIは「生成後にクレジット消費」— 失敗生成の計算浪費
- **重大度:** Medium（コード上の懸念）
- **該当ファイル:** `routes.py:2560-2645`（`_handle_calc_api`）
- **内容:** 事前チェック（残高スナップショット）→生成→原子的 `consume_api_credits`。二重課金・過剰消費は起きないが、同時実行で残高が枯渇していた場合、**計算実行後に402**となり計算リソースを浪費する。逆に生成失敗時はクレジット未消費（返金扱いで妥当）。
- **なぜ問題か:** 課金の正しさは保たれるが、無駄計算の余地。設計上の許容範囲だが記録。
- **修正する場合の方向性:** 先行して原子的に「予約消費」し、失敗時に返金する方式も選択肢。
- **修正優先度:** 低
- **様子見可能か:** 可。

---

## Low

- **L-1:** `ADMIN_PASSWORD`（既定 `"admin"`）は CLAUDE.md 記載どおり未使用の予約設定。誤解を招くため削除候補。（`config.py` / ドキュメント）
- **L-2:** `/admin/addon/generate` と `/addon/generate`（5536-5537行）、addonのYAML/HTML系が二重デコレータで同一ハンドラ。命名上の重複で「admin」側が特権的でない点が紛らわしい。
- **L-3:** `routes.py` が単一 6077 行。ルーティング・検証・整形・DB呼び出しが密結合で保守性が低い（分割候補）。
- **L-4:** `backups/` ディレクトリ自体を git 管理下に置く運用（C-1の温床）。バックアップは別管理を推奨。
- **L-5:** `.gitignore` に `.git` エントリがある（無害だが不要）。

---

## 要確認（コードだけでは判断できないもの）

1. **C-1:** バックアップ内 `API_KEY_ADMIN_TOKEN` の値が**現行本番と一致**するか。一致していれば即ローテーション必須。
2. **H-1 / C-1:** Cloud Run へのシークレット注入が Secret Manager 化されているか、`deploy.env.yaml` 直投入か。
3. **H-2:** 本番で `STORES_MAIL_SYNC_TOKEN` / `API_KEY_ADMIN_TOKEN` が確実に設定されているか（未設定だと認可が無効化）。
4. **H-5:** `MUNDANE_ADMIN_PREFIX` を env で上書きしているか、既定パスのままか。
5. **C-2:** `/admin/*` 生成系を Cloud Run のイングレス制御やIAPなど**アプリ外**で保護している運用か（コード上は無防備）。
6. **M-4:** 新規デプロイ時に `/internal/init-db` を確実に実行する手順になっているか。
7. STORESメール照合（IMAP）が購入者本人性をどこまで担保しているか（注文番号のみで本人確認しているか）。

---

## 将来的な改善案

- **Secret運用の刷新:** 全シークレットを Secret Manager へ。バックアップに平文値を含めない。トークンは用途別に分離（H-3）。
- **認証境界の一元化:** `/admin/*`・`/internal/*`・デモAPIを共通の認可依存（FastAPI `Depends`）で束ね、fail-close をデフォルトに。
- **レート制限の共通基盤:** デモ/課金/公開redeemに横断的なIP・キー単位レート制限を導入（H-4/M-3）。
- **`routes.py` の分割:** 購入者フロー / API販売 / 管理 / ACG / アドオン を APIRouter で分割し、認可をルーター単位で付与。
- **ログのPIIポリシー統一:** 「識別子は先頭数文字のみ」を全ログに徹底（M-1）。

## 監査で見えた「共通ライブラリ化」提案

- **`auth_guard`（認可共通化）:** `_admin_access_error` / `_admin_token_from_env` / `_is_local_request` を1モジュールにまとめ、`Depends(require_admin)` として全 admin/internal ルートへ強制適用。fail-close を既定に。これで C-2・H-2・H-5 を構造的に一掃できる。
- **`order_verification`（注文照合共通化）:** STORES / Payhip / Gumroad の照合と `redeem_and_save` 呼び出しを1つのサービスに集約。redeem・addon・transit_yaml で重複している検証分岐を統一（現状 `routes.py` に散在）。
- **`chart_response`（公開レスポンス共通化）:** `_apply_public_chart_headers`（noindex / expiry / cache）を全 `/chart` `/addon` `/mundane` レスポンスで必ず通す薄いラッパ。ヘッダ付与漏れを防ぐ。
- **`secret_config`（設定・シークレット読取）:** env 読取とトークン取得を集約し、「未設定時 fail-close」を1箇所で保証。
- **`pii_logging`（ロギング）:** メール・トークン等を自動マスキングするロガーラッパ。

---

## 修正優先順位（今回は実装しません）

1. **C-1:** バックアップ平文トークンの履歴除去 ＋ `API_KEY_ADMIN_TOKEN`・`ADDON_KEY_*` のローテーション。
2. **C-2:** `/admin/*` 生成・フォーム系に認可を付与（無料生成・DoS面の封鎖）。
3. **H-1 / H-2 / H-3:** Secret Manager 移行、`/internal/*` の fail-close 化、トークン用途分離。
4. **H-4:** デモAPIのレート制限。
5. **H-5:** マンデン管理の認可化。
6. **M-1:** Payhip例外ログのメールマスキング。
7. 以降、M-2〜M-5・Low を保守サイクルで対応。
