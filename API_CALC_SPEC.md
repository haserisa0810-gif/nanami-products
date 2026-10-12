# nanami-products 計算結果API 仕様書（四柱・複合 v1.1／西洋・トランジット v1.0）

## 2026-10-11 四柱API v1.1の変更

`shichu`・`combined`の`meta.api_version`は1.1。四柱エンジンは0.5.0。省略／falseの日替わりは1時、true／23は23時に統一したため、0時台・23時台では旧APIの実計算と結果が変わる。明示的な0時方式は`day_boundary: "00:00"`を使用する。旧保存YAMLや購入IDを読み替えない。西洋・トランジット単独のAPI版は1.0を維持する。

- UTCオフセットが0以下の出生地では、境界時刻以外も旧日柱の1日進みを修正する（例：LA 2000-01-07 12:00、旧乙丑→新甲子）。時干・十神などの派生値も変わる。
- `gender`省略／unknownは女性に補完しない。大運の順逆・起運を未確定としitemsは空、命式と原局×流年は維持する。
- 海外出生でIANAタイムゾーンが省略・空・不正な型なら400 `INVALID_TIMEZONE`。国内都道府県のJST既定値は維持する。
- 不正な日替わりは400 `INVALID_DAY_BOUNDARY`、不存在／未解決の重複日時は400 `INVALID_BIRTH_DATETIME`。重複は`birth_fold: 0/1`または`birth_utc_offset_hours`で指定する。
- `day_boundary`のJSON falseは1時、数値0は0時として区別する。時刻を文字列`"01:00"`・`"00:00"`・`"23:00"`で指定すると意味が明確になる。

## 概要

`nanami-products` に追加された計算結果APIの運用仕様です。
この仕様書は現時点の実装に合わせた実務用ドキュメントです。

対象API:

- `POST /api/calc/western`
- `POST /api/calc/shichu`
- `POST /api/calc/transit`
- `POST /api/calc/combined`

購入前の接続確認用デモAPI:

- `POST /api/demo/western`
- `POST /api/demo/shichu`
- `POST /api/demo/transit`
- `POST /api/demo/combined`

共通方針:

- 既存UI、既存URL、既存管理画面、既存注文機能は変更しない
- APIはJSONを返すだけ
- DB保存はしない
- `build_product_yaml()` を経由して、既存の計算結果を再利用する
- `interpreted_tags` は初期実装では簡易判定
- `X-API-Key` ヘッダーによるAPIキー認証が必須
- 成功時のみクレジットを消費する

## デモAPI

`/api/demo/*` は購入前の接続確認用です。

- `X-API-Key` 不要
- クレジット消費なし
- 本番計算なし
- 必須項目チェックのみ実施
- レスポンスは固定サンプル

必須項目:

- `western`: `birth_date`, `birth_place`
- `shichu`: `birth_date`, `birth_place`
- `transit`: `birth_date`, `birth_place`, `target_date`
- `combined`: `birth_date`, `birth_place`, `target_date`

画面確認:

```text
/api-sandbox
```

## APIキー認証・クレジット

全APIで以下のヘッダーが必須です。

```text
X-API-Key: np_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

APIキーはDBに平文保存せず、`nanami_products.api_keys.key_hash` にSHA-256ハッシュで保存します。

消費クレジット:

- `western`: 1 credit
- `shichu`: 1 credit
- `transit`: 1 credit
- `combined`: 3 credits

利用条件:

- `status = 'active'` のキーのみ利用可能
- `credits_remaining` が必要消費数未満の場合は `402` 相当のJSONエラーを返す
- 計算成功時のみ `credits_remaining` を減算する
- `nanami_products.api_usage_logs` に `endpoint / credits_used / status / error_code` を保存する

初期APIキー発行:

```bash
DATABASE_URL=postgresql://... python scripts/create_api_key.py --label test --credits 100
```

テストサイトから発行する場合は `/test-site` の「テスト用APIキー発行」を使います。本番環境では `API_KEY_ADMIN_TOKEN` または `STORES_MAIL_SYNC_TOKEN` が必要です。

購入者自身に発行させる場合は `/api-key/start` を使います。STORESの商品名に `[NP-API]` を入れておくと、購入完了メール同期でAPIキー商品として判定されます。

商品名と付与クレジット:

- `[NP-API] お試しAPIクレジット`: `API_KEY_ISSUE_CREDITS_TRIAL`、未設定時 `5`
- `[NP-API] APIクレジット`: `API_KEY_ISSUE_CREDITS_STANDARD`、未設定時 `20`
- 判定不能なAPIキー商品: `API_KEY_ISSUE_CREDITS`、未設定時 `20`

---

## 共通レスポンス

成功時は以下の形です。

```json
{
  "ok": true,
  "meta": {
    "api_version": "1.0",
    "engine": "nanami-products",
    "endpoint": "combined"
  },
  "input": {},
  "raw_data": {
    "western": {},
    "shichu": {},
    "transit": {}
  },
  "interpreted_tags": {
    "western": [],
    "shichu": [],
    "transit": [],
    "integration": []
  },
  "writing_hints": {
    "tone": {
      "sharpness": 50,
      "warmth": 50,
      "mystical": 50
    },
    "focus_areas": [],
    "key_concepts": []
  },
  "ai_prompt_context": {
    "role": "構造分析型の占星術鑑定",
    "instruction": "raw_dataを直接断定せず、interpreted_tagsを主軸に鑑定文を作成してください。",
    "caution": [
      "運命断定を避ける",
      "不安を煽らない",
      "basisがあるタグを優先する",
      "strengthが高いタグを優先する"
    ]
  },
  "handoff_yaml": "..."
}
```

エラー時は以下です。

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "birth_date is required"
  }
}
```

主なエラーコード:

- `INVALID_INPUT`
- `UNSUPPORTED_ENDPOINT`
- `UNSUPPORTED_PERIOD`
- `CALCULATION_FAILED`
- `INTERNAL_ERROR`

---

## 1. Western API

`POST /api/calc/western`

### 役割

西洋占星術専用の計算結果を返します。

### 入力

```json
{
  "name": "テスト太郎",
  "birth_date": "1990-01-01",
  "birth_time": "12:00",
  "birth_place": "東京都",
  "lat": 35.6812,
  "lon": 139.7671,
  "writing": {
    "tone": {
      "sharpness": 40,
      "warmth": 80,
      "mystical": 30
    },
    "focus_areas": ["career", "love"]
  }
}
```

### 実装上の扱い

- 小惑星、リリス、キロンは含める
- 四柱推命は含めない
- トランジットは含めない

### 主な `raw_data`

- `western.natal`
- `western.asteroids`

---

## 2. Shichu API

`POST /api/calc/shichu`

### 役割

四柱推命専用の計算結果を返します。

### 入力

```json
{
  "name": "テスト太郎",
  "birth_date": "1990-01-01",
  "birth_time": "12:00",
  "birth_place": "東京都",
  "gender": "female",
  "day_boundary": "23:00",
  "writing": {
    "tone": {
      "sharpness": 40,
      "warmth": 80,
      "mystical": 20
    },
    "focus_areas": ["career", "money"]
  }
}
```

### 実装上の扱い

- `day_boundary` は出生地の現地暦日の切替規則。省略／`"01:00"` は1時（0時台は前日）、`"23:00"` は23時（23時台は翌日）、`"00:00"` は暦日0時。UTC日付・真太陽時は使わない。新規四柱エンジンは0.5.0、旧保存YAMLは再計算しない。
- 夏時間の重複時刻には `birth_fold: 0 | 1` または `birth_utc_offset_hours` を指定する。不存在時刻・未選択の重複時刻は拒否する。ホロスコープ単独の従来日時仕様は今回変更しない。
- `gender: "unknown"` は大運未確定。命式と原局×流年は計算し、大運は `status: undetermined_gender`、`direction: null`、`items: []` とする。
- それ以外は `false`
- 西洋占星術は含めない
- トランジットは含めない

### 主な `raw_data`

- `shichu.normalized_data`
- `shichu.structure_report`
- `shichu.summary`

---

## 3. Transit API

`POST /api/calc/transit`

### 役割

現在または指定日の星回りを返します。

### 入力

```json
{
  "name": "テスト太郎",
  "birth_date": "1990-01-01",
  "birth_time": "12:00",
  "birth_place": "東京都",
  "lat": 35.6812,
  "lon": 139.7671,
  "target_date": "2026-05-01",
  "period": "day",
  "writing": {
    "tone": {
      "sharpness": 30,
      "warmth": 80,
      "mystical": 30
    },
    "focus_areas": ["career", "love"]
  }
}
```

### 実装上の扱い

- `period = day`
  - `target_date` を起点に 1日分を返す
- `period = month`
  - `target_date` を起点に 31日分を返す
- 各日について `moon_timepoints` を返す
- `moon_timepoints` は朝・昼・夜の使い方の材料

### 主な `raw_data`

- `western.transit`

---

## 4. Combined API

`POST /api/calc/combined`

### 役割

西洋占星術、四柱推命、トランジットを統合して返す本命APIです。

### 入力

```json
{
  "name": "テスト太郎",
  "birth_date": "1990-01-01",
  "birth_time": "12:00",
  "birth_place": "東京都",
  "lat": 35.6812,
  "lon": 139.7671,
  "gender": "female",
  "target_date": "2026-05-01",
  "day_boundary": "23:00",
  "period": "day",
  "writing": {
    "tone": {
      "sharpness": 40,
      "warmth": 80,
      "mystical": 30
    },
    "focus_areas": ["career", "love", "money"]
  }
}
```

### 実装上の扱い

- `western`
  - `include_asteroids = true`
  - `include_shichusuimei = false`
  - `include_transit = true`
- `shichu`
  - `include_asteroids = false`
  - `include_shichusuimei = true`
  - `include_transit = true`
- `transit`
  - `target_date`
  - `period`

### 主な `raw_data`

- `western`
- `shichu`
- `transit`

---

## interpreted_tags の考え方

`interpreted_tags` は、AIにそのまま鑑定文を書かせるための中間層です。
初期実装では、厳密な判定よりも「読みに使える形を固定する」ことを優先しています。

### タグ構造

```json
{
  "id": "saturn_pressure",
  "label": "責任・制限・継続課題",
  "strength": 2,
  "category": "timing",
  "basis": ["Saturn square orb=1.2"],
  "writing_hint": "焦らず整える必要性として扱う"
}
```

### ルール

- `strength` が高いタグを優先する
- 根拠が薄いものは `strength: 0`
- 判定が難しいものは `basis: []`
- 断定ではなく、使い方のヒントとして返す

---

## handoff_yaml

`handoff_yaml` は、APIレスポンス全体をそのまま AI に渡しやすくするための YAML 文字列です。

用途:

- 鑑定文生成の中間データ
- 別システムへの受け渡し
- 手作業での検証

---

## 確認方法

### OpenAPI

```text
http://127.0.0.1:8000/docs
```

### curl

```bash
curl -sS http://127.0.0.1:8000/api/calc/combined \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"テスト太郎",
    "birth_date":"1990-01-01",
    "birth_time":"12:00",
    "birth_place":"東京都",
    "lat":35.6812,
    "lon":139.7671,
    "gender":"female",
    "target_date":"2026-05-01",
    "day_boundary":"23:00",
    "period":"day",
    "writing":{"tone":{"sharpness":40,"warmth":80,"mystical":30},"focus_areas":["career","love","money"]}
  }'
```

---

## 運用メモ

- 既存の購入者フローはそのまま使う
- APIは購入・保存を行わない
- 仕様変更時は `routes.py` と `services/api_calc.py` と `services/api_tags.py` を先に確認する
- `transit` の日別解釈は `moon_timepoints` を前提にする
