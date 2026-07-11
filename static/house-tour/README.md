# House Tour — ホロスコープ・ハウスツアー 3D デモ

出生図の12ハウスを、空間・建築・光・色・音・オブジェクト・天体として歩いて体験する独立デモです。

> ホロスコープを読むのではなく、自分の出生図の中を歩く。

## アクセス

アプリ経由:

```text
GET /house-tour
```

## 構成

```text
static/house-tour/
├─ house-tour.css
├─ sample-data.json          # テスト用ミラー（正本は js/data）
├─ README.md
└─ js/
   ├─ main.js
   ├─ scene.js
   ├─ controls.js
   ├─ house-builder.js
   ├─ planet-builder.js
   ├─ tour-controller.js
   ├─ ui.js
   └─ data/
      ├─ sample-chart.js
      ├─ houses-ja.js
      ├─ houses-en.js
      └─ planets-ja.js
```

テンプレート: `templates/house_tour.html`  
ルート: `routes.py` の `GET /house-tour` のみ（鑑定・注文・YAML 非接続）

## 技術

- Three.js r128（CDN、このページのみ）
- ES modules（ビルド不要）
- 外部APIなし・固定サンプルのみ
- 音声は既定 OFF

## 操作

| 環境 | 操作 |
|------|------|
| PC | WASD 移動 / クリックで視点ロック / N・P 次前 / M マップ |
| スマホ | 左スティック移動 / 右ドラッグ視点 / 「次へ」「前」ボタン |

## 非対象（今回）

- 占星術計算、YAML貼り付け、ユーザー出生図、注文・課金、既存鑑定フロー改変
