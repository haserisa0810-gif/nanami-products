# 旧Personal Edition 引換コード運用（Legacy／手動発行）

既存のSTORES・Payhip・Etsy注文番号による通常引換とは独立した、Etsy／ココナラ等の旧・サポート用手動納品フローです。ココナラでの新規販売は終了しています。既存発行済みコードとURLの互換維持、および過去購入者のサポートのため機能は残しますが、新規商品には使用しません。

## 初回セットアップ

デプロイ後、既存の `POST /internal/init-db` を一度実行します。
`nanami_products.personal_edition_codes` が追加されます。

Personal Editionのビルド材料をCloud Runへ含める必要があります。`personal-edition/dist/` は不要で、
初回ZIP生成時にサーバー上でテンプレートZIPを生成します。

## コードと納品用ZIPの事前発行

環境変数 `DATABASE_URL` を設定した端末で実行します。

ココナラ過去購入者への例外的な再発行・サポート用（通常運用では使用しない）:

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

FULL版のダウンロードZIPには、計算済みYAML、AI相談文、言語別README、専用鑑定ページURLを含めます。Birth Chart Museumは含めません。ACG用コードでは、これらに加えて現行の `START-ACG.html` 方式を使用します。無料Museumアプリは別機能・別配布物として既存URLを維持します。

## 対応状況

- `western_full`: 対応済み
- `acg_bundle`: 対応済み（現行ACG注文も無期限Personal Editionの配布方式を内部利用）
- `western_basic`: 将来追加
- `shichu`: 将来追加

テーブルと管理APIは `product_type` を保持するため、後続商品を同じコード基盤へ追加できます。

## 注意

- EtsyのInstant Downloadでは全購入者へ同じファイルが渡るため、個別コードZIPを再利用する場合はMade-to-order納品に限定します。
- 平文アクセスコードはDBへ保存せず、SHA-256ハッシュだけを保存します。生成後の無期限鑑定URLを提供するため、出生情報と生成YAMLは通常のチャート保存先へ保存します。
- コード入力からZIP生成まではオンライン接続が必要です。ダウンロード後のPersonal Editionはオフライン利用できます。
