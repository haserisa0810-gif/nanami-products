# Personal Edition 引換コード運用（FULL版）

既存のSTORES・Payhip・`/redeem/western-full` とは独立した、Etsy／ココナラ向けの手動納品フローです。

## 初回セットアップ

デプロイ後、既存の `POST /internal/init-db` を一度実行します。
`nanami_products.personal_edition_codes` が追加されます。

Personal Editionのビルド材料をCloud Runへ含める必要があります。`personal-edition/dist/` は不要で、
初回ZIP生成時にサーバー上でテンプレートZIPを生成します。

## コードと納品用ZIPの事前発行

環境変数 `DATABASE_URL` を設定した端末で実行します。

ココナラ用・日本語・10件:

```powershell
.venv\Scripts\python scripts\issue_personal_edition_codes.py --count 10 --provider coconala --lang ja --delivery-dir deliveries\coconala
```

Etsy用・英語・10件:

```powershell
.venv\Scripts\python scripts\issue_personal_edition_codes.py --count 10 --provider etsy --lang en --delivery-dir deliveries\etsy
```

各ZIPには異なる `ACCESS-CODE.txt` が入ります。コードの平文は発行時にだけ出力され、DBには
正規化済みコードのSHA-256ハッシュだけが保存されます。

管理APIから発行する場合:

```http
POST /internal/personal-edition/codes
X-Admin-Token: <API_KEY_ADMIN_TOKEN>
Content-Type: application/json

{"count":10,"provider":"etsy","lang":"en","product_type":"western_full","expiration_days":30}
```

## 購入者の操作

- 日本語: `https://chart.nanami-astro.com/personal-edition/activate?lang=ja`
- 英語: `https://chart.nanami-astro.com/personal-edition/activate?lang=en`

購入者は引換コードと出生情報を入力します。FULL版YAMLと本人用ZIPの両方が正常に生成された後だけ、
コードが `used` になります。入力エラーや計算・ZIP生成エラーではコードを消費しません。

ダウンロードZIPには `app/birth-chart.yaml` が追加され、Personal Edition起動時に入口と各ミュージアムへ
自動的に読み込まれます。起動後の利用は従来どおりローカルです。

## 対応状況

- `western_full`: 対応済み
- `western_basic`: 将来追加
- `shichu`: 将来追加

テーブルと管理APIは `product_type` を保持するため、後続商品を同じコード基盤へ追加できます。

## 注意

- EtsyのInstant Downloadでは全購入者へ同じファイルが渡るため、個別コードZIPにはMade-to-order納品を使用します。
- 平文コード、出生情報、生成YAMLはDBへ保存しません。
- コード入力からZIP生成まではオンライン接続が必要です。ダウンロード後のPersonal Editionはオフライン利用できます。
