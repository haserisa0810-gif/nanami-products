# 配布PDF・ZIP・README UI/UX仕様書

## 1. 目的

購入直後から鑑定発行、保存、再利用まで、購入者が「どのファイルを開けばよいか」「何が商品に含まれるか」を迷わない配布体験を定める。

正規ファイルの配置は `docs/DISTRIBUTION_PDF_INDEX.md`、ACG成果物は `docs/ACG_DISTRIBUTION_ARTIFACTS.md` を参照する。

## 2. 成果物の区別

| 成果物 | 役割 |
|---|---|
| Etsy等のアクセスPDF | 購入直後にダウンロードし、注文番号入力ページを開く案内書 |
| 鑑定ページ | 購入者ごとの生成結果、AI操作、保存・追加機能への入口 |
| Planner PDF | 購入者データから生成した1年手帳 |
| 保存用ZIP | YAML、プロンプト、README、鑑定URL等の手元保存 |
| Personal Edition ZIP | 現行の無期限利用向け成果物。ACG対象ではSTART-ACG方式を含む |
| サンプルPDF／画像 | 購入前確認・販売素材。購入者個人の結果ではない |
| 旧Activation／旧Final／fixed | legacyまたはQA。現行配布物として使用しない |

## 3. アクセスPDF

- JA / EN / ES / DEを別成果物として生成する。
- 該当言語の正規引換URLと `provider` を含む。
- URLは可視テキスト、クリック可能リンク、QRの3経路で開ける。
- PDF内で、注文番号を入力して鑑定を発行する流れを簡潔に説明する。
- 商品内容を正確に記載する。
  - FULL版: 1年Plannerを含む。ACGとMuseumを含まない。
  - ACG bundle: ACGと1年Plannerを含む。Museumを含まない。
- 旧Activationコード方式を現行注文方式として案内しない。
- 顧客情報、実注文番号、秘密情報を埋め込まない。

## 4. ZIPとREADME

- READMEは購入者の言語で、最初に開くファイル、鑑定URL、YAML、AIプロンプト、期限後の利用方法を説明する。
- READMEとファイル名から、商品に含まれない機能を誤認させない。
- 全有料商品からBirth Chart Museumの名称、同梱案内、起動案内を除外する。
- 無料Museumを残す場合も有料ZIPと分離し、任意の無料アプリであることを明示する。
- ZIP内パスは相対パスのみとし、`..` や絶対パスを許可しない。
- 購入者がOS標準機能で展開できる形式にする。
- ファイル名は商品、言語、用途を識別でき、`Final`、`fixed`、`sample`だけで現行版を判断させない。

## 5. ACG配布

- ACGの現行案内はSTART-ACG方式を正規とする。
- ACG bundle購入者へ、YAMLを手作業で貼り直すことを通常手順として要求しない。
- Personal ACG成果物は正確な出生時刻を持つ対象商品だけに含める。
- 一般FULL版にPersonal ACGが含まれるように見せない。

## 6. currentとlegacy

- 現行配布物は言語とcurrent用途が分かる管理場所に置く。
- 古い `Final`、`fixed`、旧EN ZIP、旧Access ZIP、旧Museum同梱版はlegacy/QAとして隔離する。
- 既存ユーザーの手元成果物を勝手に削除・無効化しない。
- Etsy等へアップロードする前に、正規配置から選んだことを二者またはチェックリストで確認する。
- 同名差替えを行う場合も、内容ハッシュと生成日時を作業記録へ残す。

## 7. 受入テスト

### PDF

- ページ数、A4寸法、埋込フォント、主要テキストを機械検査する。
- Museum表記0、旧Activation表記0、正しい商品内容を確認する。
- URL注釈、可視URL、QRが同じ正規URLを指す。
- 4言語で誤言語混入を検出する。
- 全ページを画像化し、文字切れ、重なり、QR欠けを目視する。

### ZIP／README

- ZIPを安全に展開でき、必須ファイルが存在する。
- README、ファイル名、内部リンクが同じ商品・言語を示す。
- Museum、休止中商品、旧方式の誤案内がない。
- YAMLとプロンプトの文字コードがUTF-8で、OS間で文字化けしない。
- 鑑定URLと自動読込URLが対象トークンを指す。

主なテスト: `tests/test_etsy_full_access_guides.py`, `tests/test_chart_download_zip.py`, `tests/test_personal_edition_activation.py`, `tests/test_personal_edition_macos_ci.py`, `tests/test_planner_delivery.py`。

## 8. 手動配布チェック

1. Listingの商品名、SKU、言語とアップロード対象PDFを照合する。
2. PDFを購入者と同じ方法でダウンロードし、リンクとQRを開く。
3. 引換後のZIPを展開し、READMEの上から順に操作する。
4. 価格、数量、SKU、画像、動画、公開状態を変更しない限定差替えでは、保存前後の差分を記録する。
5. Etsy編集画面に未保存変更が残っていないことを確認する。
