# 検証範囲・商品・依存関係

## 実在する商品と生成経路

商品設定は `routes.py::PRODUCT_CONFIG` をASTから抽出し、[product_catalog.json](product_catalog.json)に保存しました。収録フラグと生成関数を確認し、価格や販売設定は変更していません。

| 商品／機能 | 実在する構成 | 新規試験 | 状態・限界 |
|---|---|---|---|
| `western_basic` | 出生図、主要天体。小惑星・四柱・トランジットなし | 実YAML・AIテキスト生成、解析 | PASS；実モデル鑑定はFull側のみ |
| `western_full` | 出生図＋小惑星＋初回31日トランジット | 実YAML、Light、AI、SVG | PASS（形式）；AI精度表現にFAIL |
| `western_asteroids` | 基本＋小惑星、トランジットなし | 実YAML・AIテキスト | PASS；外部API fallback未実施 |
| `western_transit` | 基本＋トランジット、小惑星なし | 実YAML・AIテキスト | PASS（形式・分岐） |
| `acg_bundle` | 小惑星・トランジット＋ACG利用 | 実YAML・AIテキスト、既存ACGテスト | PASS（契約）；地図の独立位置精度・目視未実施 |
| `western_asteroids_addon` | 基本鑑定への後付け小惑星 | 既存専用生成関数 | PASS（形式・分岐） |
| `western_31days_transit_addon` | 名前は31days、現行既定38日 | 専用生成関数、38日サンプル | PASS（形式）；初回Full31日と区別 |
| `western_long_term_transits_addon` | 365日、週次sample、イベント要約 | 実計算・専用Full/AI YAML | PASS（解析）；正確なピーク時刻の独立検証未実施 |
| `shichu` | 四柱推命単独。保存Full＋AI送信モード | 実YAML・年選択・SVG・実AI | 出力PASS／計算FAILあり |
| 四柱推命「基本版／Full版」 | 別々のSKUは見つからない。現行`shichu`と基本鑑定・選択年・完全原本の送信モード | モードを個別検証 | 独立した基本SKU：対象外 |
| `shichu_fortune_cycles_addon` | 専用追加生成経路・商品識別 | 実YAML・AIテキスト | PASS（形式）；再購入・実決済未実施 |
| `transit_yaml` | 出生図を含まないイベント時空の天体配置 | 専用関数・YAML・AIテキスト | 解析PASS／内部診断情報FAIL |
| 複合 | 管理者生成フラグ／APIで西洋＋四柱 | 複合YAML・指示分岐 | PASS（形式）；専用販売SKU：対象外 |
| 5/10/20年流年試作 | ローカル試作・抽出モジュール | 保存データの出所確認・既存テスト | 販売済み商品としては対象外。独立した全年度精度は未実施 |
| ZIP・raw YAML・prompt.txt | チャートページの保存・取得経路 | 既存TestClientテスト | PASS（架空fixture）；実購入済みデータ未実施 |
| 年選択 | basic／selected／complete | 新規実生成＋既存Python/JS | PASS；非連続・交運年・旧形式を含む |
| SVG | 西洋・四柱の実生成 | XML解析 | PASS（形式）；表示目視未実施 |
| PDF・画像レンダリング・ACG地図 | 関連実装／既存テストあり | 既存テスト範囲のみ | 全商品でのレンダリング品質は未実施 |

## 主な計算・出力ファイル

| 領域 | 実装 |
|---|---|
| 四柱・節入り・日柱・時柱・大運・空亡・神殺 | `services/shichusuimei_calc.py` |
| 通根・透干・十神強度・流通・格局／用神候補 | `services/shichusuimei_structure.py` |
| 西洋天体・ハウス・ASC/MC・アスペクト | `services/western_core.py`、`services/western_calc.py` |
| 小惑星fallback | `services/asteroid_provider.py` |
| 商品組立・大運追加・短期／長期トランジット | `services/yaml_exporter.py`、`services/transit_yaml.py`、`services/long_term_transit_yaml.py` |
| 年選択／保存済み原本の抽出 | `services/shichusuimei_year_selection.py`、`services/shichusuimei_year_extract_prototype.py` |
| 指示文・占術分岐・メタデータ | `services/prompt_builder.py`、各locale、`services/output_metadata.py`、`services/shichusuimei_prompt_rules.py` |
| 商品UI・ZIP・購入／発行 | `routes.py`、`templates/` |

`nanami-astro`との関係は西洋コア・goldenテスト・fixtureの同期です。実行時に別リポジトリの全四柱計算をimportする構成は確認していません。同期対象3ファイルは改行正規化後に内容一致（PASS）。rawハッシュの同期チェックはCRLF/LF差により失敗するため、実ロジックの相違と区別しました。`nanami-astro`側の別用途全モジュールの総合監査は未実施です。

## 入力・境界のカバレッジ

| 項目 | 状態 | 実施範囲 |
|---|---|---|
| 出生時刻あり／不明／推定 | PASS（出力契約） | 四柱のexact/unknown/approximate、時柱の暫定・除外と用神保留 |
| 0時／23時設定 | FAIL | 0:30、1:30、22:30、23:30とUIの不一致 |
| 立春／節入り | PASS | 2026年12節、±2分、年・月の切替 |
| うるう年／日付境界 | PASS／FAIL | 2024-02-29の日干支独立照合。海外日柱はFAIL |
| 海外／南半球 | PASS／FAIL | 東京・UTC・London・New York・Sydney、ASC等にReykjavikも使用 |
| DST切替 | FAIL | New Yorkの2024春不存在／秋重複時刻 |
| 高緯度 | FAIL | 緯度69.65、-75のPlacidus例外 |
| 交運・年の重複 | PASS（近似期間整合性） | 2033年は大運2候補、2032/34年は各1候補 |
| 未収録年・不正入力 | PASS／FAIL | 年選択は拒否PASS。西洋APIの日付・24時・緯度不正は500でFAIL |
| 全年代／全節気／全時刻 | 未実施 | 有限の反例と代表例に限定 |
| イベント商品のJulian/Gregorian切替 | 未実施（独立暦照合） | 機能の存在とGregorianサンプル生成は確認。Julian歴史日付全経路の独立検証はしていない |
| 旧実購入者データ | 未実施 | 本番DB・購入履歴は読まず、架空旧形式fixtureで代替契約検証 |
| 真太陽時／標準時など流派変更 | 未実施 | 本サービス採用方式の確認と差異指摘のみ。正解として置換しない |
