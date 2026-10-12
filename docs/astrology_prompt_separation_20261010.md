# 占術別AI指示文の分離・整理（2026-10-10）

四柱推命・ホロスコープ・複合商品のAI向け指示を、実際に収録されている占術データに応じて分離した。計算エンジン・計算済み鑑定データ・保存済み原本を変更せず、ローカルで確認した。本番・候補環境へのデプロイは実施していない。

## 調査結果と適用経路

- 主な生成箇所は `services/prompt_builder.py` と `services/yaml_exporter.py`。英語・スペイン語・ドイツ語は `prompt_locales.py` と `companion_locales.py` を使用する。
- 旧共通処理が四柱推命単独にもハウス・ASC/MCの注意事項とACG相談案内を付加していた。試験APIのAI向けラッパー、相談モード、追加商品の指示にも対応が必要だった。
- 原則として `systems.western` / `systems.shichusuimei` の実データから判定する。文書を持たない旧呼び出しについては、既存の引数との互換性を保つ。
- 新規発行、購入者ページの指示、AI向けコピー・保存、基本・年選択・完全原本モードの付随指示、試験API、MCPの指示取得に適用する。追加商品固有の既存経路も維持する。
- 保存済み購入データには、表示時に現在の指示を生成する。DB内の原本YAML・旧指示文を上書きしない。

## 共通部分と占術別部分

共通部分は「計算値を再計算しない」「未収録情報を補完しない」「計算結果・占術的解釈・本人が話した事実を区別する」という制約。占術ごとに必要な時間精度の制約を保持する。

四柱推命側は日干・月令・四柱・蔵干・十神・十二運・五行・空亡を参照し、通根・透干・十神強度・日主の支持材料を優先する。格局・用神・喜忌は方式別の試験的候補として扱い、根拠・信頼度・競合規則・限界を読む。合や三合の存在だけで合化を確定せず、神殺は補助材料とする。時刻不明・推定では仮置き時柱を確定根拠にしない。

ホロスコープ側は既存の天体・アスペクト・ハウス・ASC/MC・時刻不明時の制約と、利用可能なACG連携手順を維持する。四柱推命専用の構造分析規則を含めない。複合商品には両方の占術別規則を組み合わせる。

### 変更・除外した指示

- 四柱推命単独から、西洋出生図・ハウス・ASC/MC・アスペクト・トランジット・ACGを前提とする指示を除外。
- 「今年の流年」を「原本作成時の流年、または指定した収録年」に変更。
- 年選択では選択年と `year_selection.included_years` を参照し、未選択・未収録の年を推測・再計算しない。立春基準、大運の近似交運時期・境界候補を維持。
- 新規四柱推命単独の出生時刻説明と継続利用案内も、占術に合う表現に変更。保存済み文書内の説明文と利用者が指定した説明文は改変しない。
- 試験APIの `interpreted_tags` は補助とし、計算済み `raw_data` と構造分析を優先する指示へ変更。タグの生成方法や計算値は変更していない。

## 内部診断メタデータ

新規発行と基本・年選択の派生YAMLから、`ephemeris` 内の次の既知の内部診断項目だけを除く。

`ephe_dir`、`ephe_dir_exists`、`ephe_files`、`resolved_ephe_dir`、`searched_ephe_dirs`、`env_sweph_ephe_path`

`has_se1`、計算エンジンの識別、計算方式・前提、未知の来歴情報は保持する。出力用コピーを処理するため、元の計算オブジェクトを変更しない。

**完全原本モード・raw YAML・ZIP内の完全原本は保存済み原本をそのまま返す。** 過去の原本に内部パスや旧説明文が含まれていても、原本不変の仕様を優先して保持する。新しいAI指示は別テキストとして提供する。

## 変更ファイル

| ファイル | 変更内容 |
| --- | --- |
| `services/prompt_builder.py` | 日本語の鑑定・相談指示の占術別分岐、流年表現、四柱推命用共通制約 |
| `services/prompt_locales.py` | 英・西・独の鑑定指示を分離、複合商品対応 |
| `services/companion_locales.py` | 英・西・独の相談指示を分離 |
| `services/shichusuimei_prompt_rules.py`（新規） | 英・西・独の四柱推命構造・不確実性規則を共通化 |
| `services/yaml_exporter.py` | 実データに基づく指示生成、新規出力の診断情報除外、説明文整理 |
| `services/output_metadata.py`（新規） | 元データを変更しない出力用診断情報フィルター |
| `services/shichusuimei_year_selection.py` | 各モードの指示を補強、派生出力だけ診断情報除外 |
| `routes.py` | 購入者ページ・コピー・保存用指示の更新、保存済み商品の読み込み対応 |
| `services/addon_prompt_locales.py` | 四柱推命大運・流年追加商品の指示整理 |
| `services/api_yaml.py` | 試験APIの占術別AI指示とデータ参照対応 |
| `services/api_calc.py` | 試験APIで共通の占術別指示を使用 |
| `services/api_demo.py` | デモも同じ指示を使用 |
| `services/mcp_chart_service.py` | 四柱推命商品の指示・推奨セクションを分離 |
| `tests/test_astrology_prompt_separation.py`（新規） | 占術・言語・時間精度・来歴保持・計算データ不変の検証 |
| `tests/test_shichusuimei_year_selection.py` | 旧購入データ・年選択・原本・ZIP・保存文書不変の検証追加 |
| `tests/test_yaml_integrity.py` | ACG指示の適用条件を検証 |
| `docs/astrology_prompt_separation_20261010.md`（新規） | 本報告 |

## 検証結果

- 対象テスト：**165件成功、サブテスト10件成功**。
- 既存テスト全体：**891件成功、サブテスト160件成功**（138.58秒）。
- 年選択UIのNodeテスト：**6件成功**。
- `git diff --check`：成功。
- 計算エンジン・構造分析・DB保存処理・デプロイスクリプト・購入者HTML・年選択JavaScriptに差分なし。
- 架空の保存済みFullを使い、診断メタデータ以外の計算データを型も含めて比較し一致を確認。新規出力でも元の計算オブジェクトが不変であることを確認。
- 旧購入データからの指示生成後も、保存済みYAML・旧指示文字列は不変。完全原本の改行を含むテキスト・SHA256・rawダウンロード・ZIP原本の一致を確認。
- 四柱推命単独に西洋用語がないこと、ホロスコープ単独に四柱推命構造規則がないこと、複合商品に両者があることを日本語・英語・スペイン語・ドイツ語で確認。
- 年選択・コピー・保存の対応、未選択年の禁止、推定・不明時刻の制約、試験APIとMCPの指示を確認。

全体テストの警告5611件には既存の `datetime.utcnow()` 等の非推奨警告が含まれる。テスト失敗はない。今回のテストは出力・互換性・不変性の確認であり、占術の計算ロジック全体の正しさや、実際のAI鑑定の深さを保証するものではない。

### 再実行コマンド

作業ディレクトリ：`C:/Users/haser/nanami-products/tmp/prompt-separation`

```powershell
C:/Users/haser/nanami-products/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=C:/Users/haser/AppData/Local/Temp/nanami-prompt-separation-full
node --test tests/test_shichusuimei_year_selection_ui.cjs
git diff --check
```

全体ログ：`C:/Users/haser/nanami-products/tmp/prompt-separation-full-tests.log`

対象ログ：`C:/Users/haser/nanami-products/tmp/prompt-separation-targeted.log`

## Git・環境・未確認事項

- 既存の未コミット変更を保持するため、独立worktreeで実装。
- ブランチ：`codex/astrology-prompt-separation`、開始コミット：`cb92cfffa2dc8889bc9be7f789589bea91d8d8c8`。
- 今回の変更は**未コミット・未push**。既存ブランチの履歴変更・本番DB操作・デプロイ・トラフィック変更は実施していない。
- 既存候補URLに今回の修正は反映されていない。確認したのはローカルの試験API・購入者ページ・ファイル生成経路。
- 基本版とFull版の計算済み収録データ、全大運・年別構造分析、年選択機能、購入・発行・保存・価格には変更を加えていない。
- 次の品質評価として、同じ架空YAMLと修正済み指示を用いた実際のAI鑑定比較が可能。今回は外部AIへの送信・鑑定評価は実施していない。
