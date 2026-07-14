# タスクB: 西洋計算コアの同期とW0移植（nanami-products側）

あなたはこのリポジトリ（nanami-products）の実装担当です。姉妹リポジトリ nanami-astro（`C:\Users\haser\dev\nanami-astro`、読み取りのみ）で抽出済みの西洋計算コアを、このリポジトリへ「コピー同期」する体制を作り、W0（速度・applying/phase・calculation_rules・data_quality）を移植します。

**前提: タスクA（nanami-astro 側のコア抽出）が完了していること。** `C:\Users\haser\dev\nanami-astro\services\western_core.py` が存在しない場合は作業を中止して報告すること。

## 背景・合意事項

- **nanami-astro が正本。同期は一方向（astro → products）のみ**。products 側で計算コアを直接編集しない
- 同期対象は「両リポで完全同一のファイル」に限定。YAML exporter・商品ロジックは同期しない
- このフェーズでは**顧客向けYAMLの内容を変えない**（計算層の拡張のみ。YAML v2 は次フェーズ）
- 追加キーのみで後方互換維持

## 成果物

1. 新規 `scripts/sync_western_core.py` — 同期スクリプト（manifest＋checkモード付き）
2. 同期実行によるファイル取り込み: `services/western_core.py` / `tests/test_western_core_golden.py` / `tests/fixtures/western_core_golden.json`
3. `services/western_calc.py` — 重複定義を削除しコアを import、W0フィールドを出力に追加
4. 新規テスト `tests/test_western_w0_products.py`
5. `docs/western_core_sync_manifest.json` — 同期記録

---

## 1. 同期スクリプト `scripts/sync_western_core.py`

標準ライブラリのみで実装。

```
python scripts/sync_western_core.py            # 同期実行（コピー＋manifest更新）
python scripts/sync_western_core.py --check    # 差分検査のみ（コピーしない）
python scripts/sync_western_core.py --source <path>  # 正本の場所を上書き（既定 ../nanami-astro）
```

- 同期対象リスト（スクリプト内に定数で明示）:
  - `services/western_core.py`
  - `tests/test_western_core_golden.py`
  - `tests/fixtures/western_core_golden.json`
- 同期実行時: 各ファイルをコピーし、`docs/western_core_sync_manifest.json` に以下を記録:
  `{"synced_at": ISO8601, "source": <絶対パス>, "files": {<相対パス>: {"sha256": ...}}}`
- `--check`: ①ローカルファイルと manifest の sha256 一致（ローカル改変検出）、②ソースとローカルの一致（正本からの乖離検出）を検査し、乖離があれば exit code 1 と差分ファイル名を出力
- ソースが存在しない場合はエラーメッセージを出して exit 2（check がソース不在で黙って成功しないこと）

作成後、**同期を実行**して3ファイルを取り込み、manifest を生成すること。

## 2. `services/western_calc.py` の改修

- コアと重複する定義（`ASPECTS` / `ORB` / `norm360` / `sign_of` / `house_of` / `angle_diff` / `calc_aspects`）を削除し、`from services.western_core import ...` で再エクスポート（既存の import 元: `services/yaml_exporter.py`, `services/transit_builder.py` 等を壊さない。`grep -rn "from services.western_calc import\|from services import western_calc" services/ routes.py` で利用箇所を確認すること）
- W0フィールドの移植（nanami-astro の `services/western_calc.py` の W0 実装を参考にしてよい）:
  - 各 planet dict に `"speed"`（swe.calc_ut の xx[3]、小数4桁）。角度点（ASC/MC等）は `None`
  - **FreeAstro 外部API由来の小惑星は速度が取れないため `"speed": None`**（→ アスペクトの phase は "unknown" になる。推測で補完しない）
  - aspects はコアの `calc_aspects` 経由で自動的に `exact_angle` / `actual_angle` / `signed_deviation` / `orb_limit` / `applying` / `phase` を持つ
  - South Node 関与のアスペクトに `"axis_mirror": true`（astro 側と同じ規約）
  - 出力に追加: `calculation_rules`（コアの `build_calculation_rules()` を使用。`core_version` / `exact_threshold_deg` を含む）、`data_quality`、`engine_version_western: "w0.1.0"`
- `data_quality` の判定: `build_product_yaml`（services/yaml_exporter.py）は `birth_time` を直接知っているので、western 計算用 payload に `"birth_time"` キーを追加で渡し、calc 側は
  `birth_time` が非空 → `"known"` / それ以外 → `"unknown"` とする。`houses_available` は座標と時刻が揃っているか。既存の `birth_time_accuracy`（exact/approximate/unknown）とは独立の計算層メタデータとして持つ（変換・統合は次フェーズ）

## 3. 顧客向けYAMLが変わらないことの担保（重要）

`services/yaml_exporter.py` の `_format_body()` / `_format_aspect()` は出力フィールドを明示的に選んでいるため、計算層の追加キーは顧客YAMLに漏れないはずである。これをテストで固定する:

- 代表的な入力で `build_product_yaml()` を実行し、生成YAML文字列に `phase:` / `signed_deviation:` / `calculation_rules:` / `data_quality:` が**含まれない**ことを検証
- 既存のYAML関連テストがすべて通ること

## 4. テスト `tests/test_western_w0_products.py`

1. **ゴールデン一致**: 同期した `tests/test_western_core_golden.py` がそのまま通る（これが両リポ共通契約の本体）
2. **実データ smoke**: `calc_western_from_payload` で全 planet に speed が存在、aspects に phase が存在、`calculation_rules["core_version"]` が `western_core.WESTERN_CORE_VERSION` と一致
3. **小惑星の速度なし**: FreeAstro フォールバック経路（モックで可）で小惑星の speed が None、その関与アスペクトの phase が "unknown"
4. **data_quality**: birth_time あり→known / なし→unknown
5. **YAML不変**: §3 の検証
6. **同期スクリプト**: `--check` が一致時 exit 0、ローカルファイルを1バイト改変すると exit 1（tmp コピーで検証）、ソース不在パス指定で exit 2

実行: `python -m pytest tests/ -q`（このリポジトリの .venv を使用）

## 制約・禁止事項

- nanami-astro 側のファイルを変更しない（読み取りのみ）
- 同期対象3ファイルを手で編集しない（同期スクリプトの出力そのままにする）
- 顧客向けYAML・プロンプト・ルート層の変更禁止（payload への birth_time キー追加のみ例外）
- 既存キーの削除・改名・値変更の禁止（追加のみ）。検出されるアスペクト集合・orb 値の変更禁止
- 新規依存パッケージの追加禁止
- 全テストが通ることを確認してから完了報告すること
