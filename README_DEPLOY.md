# nanami-products デプロイ手順

## ライセンス

nanami-products は GNU Affero General Public License v3.0 or later
（AGPL-3.0-or-later）で公開します。

このプロジェクトは Swiss Ephemeris / pyswisseph を使用しています。Swiss
Ephemeris は Astrodienst AG によるデュアルライセンスで、AGPL または Swiss
Ephemeris Professional License のいずれかを選択する必要があります。本リポジトリ
では、Professional License を購入するまで AGPL の条件に従って公開運用します。

公開サービスとして動かす場合、利用者が対応するソースコードへアクセスできる必要が
あります。現在のソースコードURL:

```text
https://github.com/haserisa0810-gif/nanami-products
```

## デプロイ

直接 `gcloud run deploy` は実行しません。未コミット変更と未 push のコミットを検査し、
候補版を 0% 配信で作成してから、別の明示承認で本番へ切り替えます。詳しい手順は
`docs/PRODUCTION_SAFETY.md` を参照してください。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_candidate.ps1
```

## 動作確認

```text
/health
/admin/yaml/new
/api-sandbox
/manual/api
```

`/healthz` は Google Front End が横取りするため、Cloud Run の外部URLでは 404 になります。外部からの死活監視には `/health` を使ってください。

`/api-sandbox` は購入前の接続確認用です。`/api/demo/*` に実際にPOSTしますが、APIキー不要・クレジット消費なし・固定レスポンスです。

管理用の試験画面は、`/test-site` ではなく `ADMIN_TEST_SITE_PATH` で設定した非推測パスを使います。未設定時は管理トークンのハッシュから自動生成されます。

## STORESメール同期

STORESのコンテンツ販売には、商品ごとの入口URLを設定します。

```text
https://chart.nanami-astro.com/start/western-basic
https://chart.nanami-astro.com/start/western-full
https://chart.nanami-astro.com/start/shichu
https://chart.nanami-astro.com/api-key/start
```

STORESの商品名には、判定用コードを先頭に入れます。

```text
[NP-WB] ライト鑑定｜ホロスコープ基本版
[NP-WF] フル鑑定｜ホロスコープFULL版
[NP-SC] 四柱推命鑑定
[NP-API] お試しAPIクレジット
[NP-API] APIクレジット
```

購入者が入力した10桁のSTORESオーダー番号を、IMAPで取り込んだ購入完了メールの件名と突合します。購入メール本文の商品名コードも照合するため、低額商品のオーダー番号を高額商品のフォームでは使えません。金額は参考情報として保存するだけで、判定には使いません。Cloud Runの環境変数に以下を設定します。

```text
DATABASE_URL=postgresql://...
STORES_MAIL_USERNAME=<STORES通知を受けるメールアドレス>
STORES_MAIL_PASSWORD=<Gmailの場合はアプリパスワード>
STORES_MAIL_SYNC_TOKEN=<任意の長いランダム文字列>
STORES_MAIL_FROM_FILTER=hello@stores.jp
ETSY_MAIL_FROM_FILTER=emails@mail.etsy.com
STORES_MAIL_SYNC_ON_SUBMIT=1
```

### Zoho Mail API（OAuth 2.0）

本番ではIMAPパスワードの代わりに、Zoho Mail APIの読み取り専用OAuthを使用できる。
Zoho API ConsoleのSelf Clientで `ZohoMail.messages.READ,ZohoMail.accounts.READ` の
認可コードを発行し、Japanデータセンターのトークンエンドポイントでrefresh tokenへ交換する。

```text
STORES_MAIL_BACKEND=zoho_api
STORES_MAIL_USERNAME=support@nanami-astro.com
ZOHO_ACCOUNTS_BASE_URL=https://accounts.zoho.jp
ZOHO_MAIL_API_BASE_URL=https://mail.zoho.jp/api
ZOHO_MAIL_CLIENT_ID=<Secret Managerで管理>
ZOHO_MAIL_CLIENT_SECRET=<Secret Managerで管理>
ZOHO_MAIL_REFRESH_TOKEN=<Secret Managerで管理>
ZOHO_MAIL_ACCOUNT_ID=<取得後に固定。未設定時はaccounts.READで自動判定>
```

OAuthクライアントの秘密値とrefresh tokenはリポジトリや `deploy.env.yaml` に保存せず、
Secret ManagerからCloud Runへ渡す。同期処理は検索・Original Message取得のGETだけを使用し、
既読、移動、削除などのメール状態を変更しない。移行期間中は
`STORES_MAIL_BACKEND=imap` に戻せば従来方式へ切り戻せる。

### Gmail API（OAuth 2.0、推奨）

Gmailを受信先のまま維持し、IMAPアプリパスワードを廃止する場合に使用する。
OAuth scopeは `https://www.googleapis.com/auth/gmail.readonly` のみとし、
OAuth同意画面はrefresh tokenの7日失効を避けるため `In production` にする。

```text
STORES_MAIL_BACKEND=gmail_api
GMAIL_API_EXPECTED_EMAIL=nanami.hoshitsuki@gmail.com
GMAIL_API_CLIENT_ID=<Secret Managerで管理>
GMAIL_API_CLIENT_SECRET=<Secret Managerで管理>
GMAIL_API_REFRESH_TOKEN=<Secret Managerで管理>
GMAIL_API_TOKEN_URL=https://oauth2.googleapis.com/token
GMAIL_API_BASE_URL=https://gmail.googleapis.com/gmail/v1
```

同期処理はGmail APIの `users.messages.list` と `users.messages.get(format=raw)`、
および認証アカウント照合用の `users.getProfile` のGETだけを使用する。

Etsyも同じメール同期を使います。各リスティングの商品名またはSKUに、次の判定コードを入れ、対応する入力URLをデジタルダウンロード内で案内します。

```text
[NP-WB]  基本版                  → /redeem/western-basic?lang=en
[NP-WBA] 基本版＋小惑星          → /redeem/western-asteroids?lang=en
[NP-WBT] 基本版＋トランジット    → /redeem/western-transit?lang=en
[NP-WF]  FULL                    → /redeem/western-full?lang=en
[NP-ACG] ACGバンドル             → /redeem/acg-bundle?lang=en
```

購入者は入力画面で購入元に「Etsy」を選び、Etsy購入メールの10桁の注文番号を入力します。注文メールが同期済みで、商品コードと入力URLが一致した場合だけ発行されます。ACGパーソナルエディションのコード発行・有効化フローとは独立しています。

テスト用のオーダー番号は以下のように登録できます。

```sql
INSERT INTO nanami_products.stores_orders
  (stores_order_no, product_type, amount, payment_status, mail_subject, mail_received_at)
VALUES
  ('1000000001', 'western_basic', 3000, 'paid', 'test order', NOW()),
  ('1000000002', 'western_full', 5000, 'paid', 'test order', NOW()),
  ('1000000003', 'shichu', 3000, 'paid', 'test order', NOW())
ON CONFLICT (stores_order_no) DO UPDATE SET
  product_type = EXCLUDED.product_type,
  amount = EXCLUDED.amount,
  payment_status = 'paid',
  updated_at = NOW();
```

何度でも使える身内・テスト用番号は `payment_status='reusable'` にします。

```sql
INSERT INTO nanami_products.stores_orders
  (stores_order_no, product_type, amount, payment_status, mail_subject, mail_received_at)
VALUES
  ('9000000001', 'western_basic', 0, 'reusable', 'reusable [NP-WB] order', NOW()),
  ('9000000002', 'western_full',  0, 'reusable', 'reusable [NP-WF] order', NOW()),
  ('9000000003', 'shichu',        0, 'reusable', 'reusable [NP-SC] order', NOW()),
  ('9000000004', 'transit_yaml',  0, 'reusable', 'reusable [NP-TY] transit yaml order', NOW())
ON CONFLICT (stores_order_no) DO UPDATE SET
  product_type = EXCLUDED.product_type,
  amount = EXCLUDED.amount,
  payment_status = 'reusable',
  mail_subject = EXCLUDED.mail_subject,
  mail_received_at = EXCLUDED.mail_received_at,
  updated_at = NOW();
```

上記SQLを毎回打つ代わりに、以下でも同じ試験番号を投入できます（`DATABASE_URL` が必要です）:

```bash
python scripts/upsert_reusable_stores_orders.py
```

追加部品（addon）のテストには、登録済みの `payment_status='permanent'` 番号を使います。
addon の消込は `addon_redemptions` で行うため、通常商品用の reusable 番号とは別枠です。

| 番号 | product_type | 用途 |
|---|---|---|
| `9700000031` | `western_31days_transit_addon` | 38日トランジット追加 |
| `9700000032` | `western_long_term_transits_addon` | 長期トランジット（1年）追加 |
| `9700000007` | （未設定） | product_type 未設定のため全addon共通 |

初回だけDBを初期化します。

```bash
curl -X POST "https://chart.nanami-astro.com/internal/init-db" \
  -H "Authorization: Bearer $STORES_MAIL_SYNC_TOKEN"
```

## APIキー発行

計算結果API（`/api/calc/*`）は `X-API-Key` ヘッダーが必須です。APIキーは平文保存せず、DBにはSHA-256ハッシュだけを保存します。

```bash
DATABASE_URL=postgresql://... python scripts/create_api_key.py --label test-client --credits 100
```

出力されたAPIキーは再表示できません。クライアントは以下のように送信します。

```text
X-API-Key: np_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

テストサイトからも発行できます。管理画面のURLは固定の `/test-site` ではなく、`ADMIN_TEST_SITE_PATH` に合わせてください。

```text
/admin/<secret>/test-site
```

本番環境では `API_KEY_ADMIN_TOKEN` または `STORES_MAIL_SYNC_TOKEN` を設定し、画面の「管理トークン」に入力して発行します。どちらも未設定の場合、発行はローカルアクセスのみ許可されます。
保存忘れ対応は、同じ管理画面の「保存忘れ再発行」でSTORESオーダー番号を入れて行います。

購入者自身にAPIキーを発行させる場合は、STORESの商品に `[NP-API]` を入れ、購入後の案内URLを以下にします。

```text
https://chart.nanami-astro.com/api-key/start
```

購入者がSTORESオーダー番号を入力すると、注文照合後にAPIキーを一度だけ表示・ダウンロードできます。付与クレジット数は商品名ごとに環境変数で変更できます。

```text
API_KEY_ISSUE_CREDITS_TRIAL=5
API_KEY_ISSUE_CREDITS_STANDARD=20
API_KEY_ISSUE_CREDITS=20
```

`[NP-API] お試しAPIクレジット` は trial、`[NP-API] APIクレジット` は standard として判定します。商品名を判定できない場合は後方互換の `API_KEY_ISSUE_CREDITS` を使います。

Cloud Schedulerから5分おきに同期エンドポイントをPOSTします。

```bash
gcloud scheduler jobs create http nanami-products-mail-sync \
  --location asia-northeast1 \
  --schedule "*/5 * * * *" \
  --uri "https://chart.nanami-astro.com/internal/mail-sync" \
  --http-method POST \
  --headers "Authorization=Bearer $STORES_MAIL_SYNC_TOKEN"
```

## 注意

- 現状は管理者用フォームに認証なしです。URLを公開する前に、Cloud Run の URLを表に出さないか、簡易認証を追加してください。
- `STORES_MAIL_SYNC_TOKEN` が未設定だと内部エンドポイントのBearer認証が無効になります。本番では必ず設定してください。
