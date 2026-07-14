# タスク: YAML v2 — 時刻依存値の隔離と時刻修正の案内導線（西洋深化ステップ2）

あなたはこのリポジトリ（nanami-products）の実装担当です。出生時刻が不確かな注文のYAMLで、時刻依存の値を `time_sensitive_provisional` セクションに隔離し、固定プロンプトに利用制約を追加し、時刻判明時の案内導線を敷きます。

## 背景・合意事項

- 現状は時刻不明でも12:00仮計算のハウス・ASC/MC数値が通常セクションに格納され、プロンプトで「参考値」と指示するのみ。**外部AIはフラグより具体値を優先しがち**で、モデル非依存設計として弱い（GPTレビューの指摘）
- 「具体値を見せて使うなと指示する」のではなく「隔離セクションに移して意味を構造で示す」に変える
- 商品価値のため値は**削除しない**（隔離して残す）。言及の全面禁止ではなく「断定禁止・可能性としての言及まで許容」
- 「出生時刻確定後のみ有効」ではなく「**確定後は再計算が必要**」が正確な表現
- 納品済みの旧YAML（保存済みチャート）は書き換えない。新規生成からの適用
- 時刻修正・再発行の方針は `docs/DESIGN_birth_time_reissue.md` 参照（今回実装するのは案内導線のみ。セルフサーブUIは作らない）

## 成果物

1. `services/yaml_exporter.py` — `time_sensitive_provisional` の導入、schema_version 更新
2. `services/prompt_builder.py` — 利用制約の追記
3. 社内消費者の互換対応: `services/chart_svg.py` / `services/light_yaml.py` / `services/acg_api.py`（または `acg_core.py` の入力抽出部）/ `services/mcp_chart_service.py` / アドオンフロー（routes.py の `_addon_args_from_base_doc` 等）
4. `/chart/{token}` ページに時刻判明時の案内文
5. 新規テスト `tests/test_yaml_v2_time_provisional.py`
6. `docs/DESIGN_birth_time_reissue.md` に管理者向け再生成手順の追記

---

## 1. `time_sensitive_provisional` セクション（yaml_exporter.py）

### 適用条件

`birth_time_accuracy in {"unknown", "approximate"}`（既存 `_interpretation_flags()` が house 解釈を禁止する条件と同一。この対応関係をコード上でも共有し、二重定義しない）。

### 構造

`systems.western.natal` 直下に追加:

```yaml
time_sensitive_provisional:
  status: assumed_birth_time            # unknown時。approximate時は approximate_birth_time
  assumed_time: "12:00"                 # 実際に計算へ使った時刻
  valid_for_assertive_interpretation: false
  recalculation_required_when_time_known: true
  reason: birth_time_unknown            # または birth_time_approximate
  angles: { asc: ..., mc: ..., vertex: ... }   # 通常セクションから移動
  houses: [...]                                # 通常セクションから移動
  body_house_placements: { Sun: 10, Moon: 3, ... }  # 各天体の house を集約
  angle_aspects: [...]                          # ASC/MC/Vertex が関与するアスペクトを移動
```

### 通常セクションからの除去（適用条件を満たす場合のみ）

- `natal.houses` → 出力しない（provisional 側へ）
- `natal.angles` → 出力しない（provisional 側へ）
- 各 body の `house` キー → 出力しない（provisional の `body_house_placements` へ集約）
- `natal.aspects` のうち ASC/MC/Vertex 関与のもの → provisional の `angle_aspects` へ移動
- `summary` は現状維持（サイン基準で時刻依存が小さいため。月サインの日内変動は将来課題）

**accuracy == "exact" の場合は一切変更しない**（provisional セクション自体を出さない）。

### schema_version

- `meta.schema_version` を `"2.0"` に更新（exact 含む全新規生成で）
- `version` キー（`nanami-products-yaml-v1`）は据え置き
- アドオンYAMLの `schema_version` はベースからの引き継ぎロジックを維持

## 2. 固定プロンプト（prompt_builder.py）

`BASE_PROMPT`（および出生時刻関連の既存文言がある場合はその近く）に追記。**キーごとの占術講義を積み上げず、禁止事項と優先順位を短く**:

```
【データ利用の優先規則】
- 計算済みの値を再計算・訂正しない
- interpretation_flags と time_sensitive_provisional の指示を最優先する
- time_sensitive_provisional 内の値（ハウス・ASC/MC・アングルとのアスペクト）は仮定時刻による参考計算である。本人の確定的特徴として断定に使わない。可能性として触れる場合は「出生時刻が不確かなため暫定」と明示する。出生時刻が判明した場合は再計算が必要である
- データに存在しないセクションを推測で補完しない
- 配置と出来事の因果関係を断定しない
```

プロンプト内に旧構造（natal.houses 等）を前提にした説明文があれば、両スキーマで通用する表現に調整する。

## 3. 社内消費者の互換対応（重要）

**方針: 読み取りヘルパーを1箇所に作り、全消費者がそれを使う。**

`services/yaml_exporter.py`（または新規 `services/natal_reader.py`）に:

```python
def read_natal_houses(natal: dict) -> list: ...      # 通常 → provisional の順で探す
def read_natal_angles(natal: dict) -> dict: ...
def read_body_house(natal: dict, body_name: str) -> int | None: ...
```

対応必須の消費者（それぞれ実際にどのキーを読んでいるか grep で確認してから直すこと）:

- **chart_svg.py**: ホイール描画にハウス・ASC/MC が必要。provisional からも読めるようにし、**描画は従来通り行う**（見た目の商品価値は保つ。SVG上の注記が既にあれば維持）
- **light_yaml.py**: 軽量版変換。provisional セクションの存在を維持したまま変換するか、同等の隔離を保つ
- **acg_api.py / acg_core.py**: パーソナルACGの入力抽出（subject.datetime 優先 → input フォールバック）が v2 YAML でも動くこと。加えて `birth_time_accuracy` が unknown/approximate の場合、ACG応答に `"time_sensitive_warning": true` を追加（角度線の非表示までは今回やらない。警告フラグのみ）
- **mcp_chart_service.py**: 参照キーが v2 で壊れないこと
- **routes.py のアドオンフロー**（`_load_addon_base_yaml` / `_addon_args_from_base_doc` / `_validate_addon_base_doc`）: v1 と v2 両方のベースYAMLを受け付けること（v1 = 顧客が過去に購入した納品物。**永続的にサポート**）

## 4. 案内導線（/chart/{token} ページ）

`birth_time_accuracy in {"unknown", "approximate"}` のチャートページにのみ、注意事項エリアへ1ブロック追加:

- 文言例: 「出生時刻が後から判明した場合、ハウス・ASC/MCを含む正確な再計算が必要です。時刻の修正・再発行（時刻のみ変更可）は公式LINEからお問い合わせください。」
- リンクは既存の問い合わせ導線（`LINE_ADD_FRIEND_URL` 等、テンプレートで既に使われているもの）を再利用。新しい外部リンクを発明しない
- exact のチャートには表示しない

## 5. テスト `tests/test_yaml_v2_time_provisional.py`

1. **unknown 時の隔離**: birth_time=None で `build_product_yaml` → YAML に `time_sensitive_provisional:` があり、必須キー（status/assumed_time/valid_for_assertive_interpretation/recalculation_required_when_time_known/reason）が揃う。通常セクションに `houses:` / `asc:` / 各 body の `house:` / ASC関与アスペクトが**無い**
2. **exact 時は不変**: birth_time="08:30" → provisional セクションが無く、houses/angles/body house が従来位置にある。schema_version のみ "2.0"
3. **approximate**: status と reason が approximate 系になる
4. **読み取りヘルパー**: v1形式 dict と v2形式 dict の両方から houses/angles/body house が取れる
5. **アドオン互換**: v1 ベースYAML（旧形式のfixtureを用意）と v2 unknown ベースYAML の両方で `_addon_args_from_base_doc` が出生情報を抽出できる
6. **SVG**: unknown 時でも chart SVG 生成が例外なく完了し、ハウス円が描かれる（出力に既存のハウス描画マーカーが含まれる）
7. **プロンプト**: 生成 prompt テキストに `time_sensitive_provisional` の制約文が含まれる（unknown時）。exact 時にも共通規則は含まれてよい
8. **ACG**: v2 unknown YAML を `/api/acg/personal` 相当の関数に渡して GeoJSON が返り、`time_sensitive_warning` が立つ
9. **チャートページ**: unknown トークンのページに案内文が表示され、exact には出ない（テストクライアント使用。既存のルートテストのパターンに倣う）

既存テスト（278件＋今回分）がすべて通ること。
実行: `python -m pytest tests/ -q`

## 6. 管理者向け手順の追記（docs/DESIGN_birth_time_reissue.md）

「段階2の実装状況」として、管理者が時刻修正の問い合わせを受けた際の再生成手順（管理者フローで同一出生日・修正時刻・同一出生地で再生成し、新トークンURLを顧客に案内。旧チャートは削除しない）を5行程度で追記。

## 制約・禁止事項

- 保存済みチャート（DB内の既存YAML）を変更・再生成するコードを書かない
- v1 YAML の読み込み互換を壊さない（アドオン・ACGは顧客の手元の旧納品物を受け付け続ける）
- exact 注文のYAML構造を変えない（schema_version の値以外）
- セルフサーブの時刻修正UI・再発行機能は実装しない（案内文とドキュメントのみ）
- 同期対象3ファイル（western_core.py 等）を編集しない
- 新規依存パッケージの追加禁止
- 全テストが通ることを確認してから完了報告すること
