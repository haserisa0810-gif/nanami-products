# nanami-products デプロイ手順

## 初回デプロイ

```bash
cd ~/dev/nanami-products

gcloud run deploy nanami-products \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated
```

## 動作確認

```text
/healthz
/admin/yaml/new
/api-sandbox
/manual/api
```

`/api-sandbox` は購入前の接続確認用です。`/api/demo/*` に実際にPOSTしますが、APIキー不要・クレジット消費なし・固定レスポンスです。

管理用の試験画面は、`/test-site` ではなく `ADMIN_TEST_SITE_PATH` で設定した非推測パスを使います。未設定時は管理トークンのハッシュから自動生成されます。

## STORESメール同期

STORESのコンテンツ販売には、商品ごとの入口URLを設定します。

```text
https://chart.nanami-astro.com/start?type=western_basic
https://chart.nanami-astro.com/start?type=western_full
https://chart.nanami-astro.com/start?type=shichu
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
STORES_MAIL_SYNC_ON_SUBMIT=1
```

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
