# nanami-products

nanami-astro の計算エンジンを利用した、占星術・四柱推命データ生成サービスです。

## API連携デモアプリ

`/api-sandbox` では、western / shichusuimei / transit / combined のレスポンスを
JSON・YAML・AI貼り付け用プロンプトで確認できます。

- 無料サンプル: APIキー不要。固定レスポンスで表示と連携方法を確認します。
- APIキー版: 入力した出生情報から実際に計算します。`X-API-Key` は送信時だけ使用し、ブラウザには保存しません。

### ローカル起動

Python 3.10 以降を使用してください。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn routes:app --reload
```

起動後、`http://127.0.0.1:8000/api-sandbox` を開きます。無料サンプルは追加設定なしで利用できます。

### 環境変数

APIキーは画面で都度入力し、環境変数やソースコードには保存しません。本番計算APIをローカルで動かす場合は、
既存サービスと同じデータベース接続設定が必要です。デプロイ設定の詳細は `README_DEPLOY.md` を参照してください。

### 使い方

1. 無料サンプルまたはAPIキー版を選びます。
2. API種別と出生情報を入力し、「占術データを作成する」を押します。
3. JSON・YAMLを確認するか、「AIに貼るプロンプト」をコピーしてChatGPT / Claudeへ貼り付けます。

API仕様は `/manual/api`、APIキー発行画面は `/api-key/start` で確認できます。

## License

This project is licensed under AGPL-3.0.
This project uses [nanami-astro](https://github.com/haserisa0810-gif/nanami-astro) 
as its calculation engine, which uses Swiss Ephemeris (pyswisseph).
