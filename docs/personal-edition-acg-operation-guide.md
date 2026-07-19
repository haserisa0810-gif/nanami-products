# Personal Edition / ACG Bundle 運用資料

## URL一覧

### 購入者がZIPを発行するページ

ローカル確認用：

```text
http://127.0.0.1:8092/personal-edition/activate?lang=ja
```

英語表示：

```text
http://127.0.0.1:8092/personal-edition/activate?lang=en
```

本番公開後の想定URL：

```text
https://chart.nanami-astro.com/personal-edition/activate?lang=ja
https://chart.nanami-astro.com/personal-edition/activate?lang=en
```

> 現在、Personal Edition関連はローカル運用です。本番へデプロイするまでは、購入者がインターネット経由で上記ページを利用することはできません。

### 管理者が引換コードを発行するページ

```text
http://127.0.0.1:8092/admin/personal-edition/codes
```

管理者Basic認証が必要です。

### ACG Web版

```text
http://127.0.0.1:8092/acg
```

## 商品の分け方

| 商品 | コード | 納品内容 |
|---|---|---|
| Personal Edition FULL | `PE-FULL-...` | 出生YAML組み込み済みミュージアムZIP |
| ACG Premium Bundle | `PE-ACG-...` | FULL内容＋計算済み個人ACG＋ローカルACG画面 |
| データのみ | 既存の注文番号・購入者URL | YAML・プロンプトなど。Personal Edition ZIPは取得不可 |

商品種別は管理画面でコード発行時に選択します。

## 販売者の作業手順

1. 管理者ページを開く。
2. 商品種別を選択する。
   - 通常版：`Personal Edition FULL`
   - ACGセット：`ACG Premium Bundle`
3. 販売先、初期言語、発行件数、有効日数を設定する。
4. コードを発行する。
5. 表示された平文コードを保存する。
6. 購入者へ「購入者用URL」と「引換コード」を納品する。

平文コードは管理画面を閉じたあとDBから再表示できません。

## 購入者の操作手順

1. 納品された購入者用URLを開く。
2. `PE-FULL-...`または`PE-ACG-...`の引換コードを入力する。
3. 生年月日、出生時刻、出生地を入力する。
4. 入力内容を確認してZIPを作成する。
5. ZIPを展開する。
6. Windowsは`start.bat`、Macは`start.command`を実行する。
7. ブラウザでPersonal Editionを利用する。

ACG Bundleでは、画面右下の「ACG・あなたの天空線」から個人ACGを開けます。YAMLの貼り付けは不要です。

## ACG Bundleの制限

ACG Bundleは以下をすべて満たす場合だけ発行できます。

- 正確な出生時刻が分かる
- タイムゾーンが確定している
- UTCオフセットが計算できる
- 出生地が入力されている
- 暫定時刻・推定時刻ではない

出生時刻が不明、推定、正午仮置きの場合は、コードを使用済みにする前に発行を停止します。

## 購入者への納品文面（日本語）

```text
このたびはご購入ありがとうございます。

以下のページから、あなた専用のPersonal Editionを作成してください。

発行ページ：＜購入者用URL＞
引換コード：＜PE-FULLまたはPE-ACGコード＞

生年月日・出生時刻・出生地を入力すると、専用ZIPを保存できます。
ZIPを展開し、Windowsは「start.bat」、Macは「start.command」を実行してください。

※引換コードはZIPの作成成功後に使用済みになります。
※ACG Bundleは正確な出生時刻が必要です。
```

## Etsy向け納品文面（英語）

```text
Thank you for your purchase.

Please create your personalized edition using the page and access code below.

Activation page: <BUYER URL>
Access code: <PE-FULL or PE-ACG code>

Enter your birth date, exact birth time, and birthplace to download your personalized ZIP file.
After extracting the ZIP, run “start.bat” on Windows or “start.command” on macOS.

The access code is marked as used only after the ZIP is created successfully.
An accurate, confirmed birth time is required for the ACG Bundle.
```

## セキュリティ上の分離

- 既存のデータ購入者URLにはPersonal Edition ZIP機能を追加しない。
- `PE-FULL`コードからACG Bundleを取得できない。
- `PE-ACG`コードだけが計算済みACGファイルを含むZIPを生成する。
- 購入者の出生YAMLはZIP内へ自動組み込みされる。
- ACG Bundle購入者にYAMLを貼り付けてもらう必要はない。

## ローカル版ACGについて

天体線と出生情報はZIP内のローカルファイルから読み込みます。背景地図にはOpenStreetMapの地図タイルを使用するため、地図背景の表示にはインターネット接続が必要です。出生YAML自体を地図サービスへ送信することはありません。
