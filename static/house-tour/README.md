# Birth Chart Museum — House Tour (Abstract Edition)

出生図の12ハウスを、**ミュージアムとして巡る**インタラクティブ展示デモです。

> ホロスコープを読むのではなく、自分の出生図の中を歩く。

## Edition

| 名前 | 説明 | ルート |
|------|------|--------|
| **Abstract Museum (v1)** | 現行。象徴・低ポリ・ガイドツアー・YAML・JA/EN | `/house-tour` |
| Architecture Museum | 実験予定。建築・素材寄りの博物館品質 | 別ルートで追加予定（本版を上書きしない） |

**チェックポイント（退避済み）**

- Git tag: `checkpoint/house-tour-abstract-museum-v1`
- 詳細: [CHECKPOINT.md](./CHECKPOINT.md)
- リアル寄り検討: [REALISM.md](./REALISM.md)

## アクセス

```text
GET /house-tour
GET /house-tour?lang=en
GET /house-tour?chart=neko
```

## 機能

- ガイドツアー（シネマティックカメラ）
- 自由歩行（クリックで近づく / ドラッグで見回す）
- YAML 出生図のクライアント読込
- 日本語 / English 切替
- サンプル「ねこ編集長」ワンクリック

## 構成

```text
static/house-tour/
├─ house-tour.css
├─ sample-data.json
├─ README.md
├─ CHECKPOINT.md
├─ REALISM.md
└─ js/
   ├─ main.js
   ├─ scene.js / controls.js / cinematic.js / museum-shots.js
   ├─ house-builder.js / planet-builder.js
   ├─ tour-controller.js / ui.js / i18n.js / parse-yaml.js
   └─ data/
      ├─ sample-chart.js / neko-chart.js
      ├─ houses-ja.js / houses-en.js
      ├─ planets-ja.js / planets-en.js
      └─ ui-strings.js
```

テンプレート: `templates/house_tour.html`  
ルート: `GET /house-tour`（鑑定・注文・YAML生成には非接続）

## 操作

| 環境 | 操作 |
|------|------|
| PC | クリックで近づく / ドラッグで見回す / ホイール前後 / 次へ |
| スマホ | 中央タップで近づく / 右ドラッグ視点 / 左スティック |

## 非対象（このデモ）

- サーバー側での再計算
- フォトリアル AAA レンダリング
- 既存鑑定・注文フローの改変
