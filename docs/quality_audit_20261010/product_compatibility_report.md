# 商品出力・年選択・購入済み互換性

## 商品データ

`build_product_yaml`と各専用addon／イベント生成関数を実行し、架空の保存YAMLとAI向けテキストを作成しました。[sample_shichu_full.yaml](sample_shichu_full.yaml)、[sample_western_basic.yaml](sample_western_basic.yaml)、[sample_western_full.yaml](sample_western_full.yaml)などです。これらは発行・決済・DB保存を伴う商品購入ではありません。

| 項目 | 状態 | 確認内容 |
|---|---|---|
| 11構成のYAML解析 | PASS | safe_load結果が生成関数の返却docと一致。アンカー／参照も解決 |
| 365日長期Full／AI YAML | PASS | 既存計算関数で53週次sampleを生成、両exporter出力を解析 |
| 西洋Light YAML | PASS（形式） | 実Fullから既存Light生成。Lightは完全原本の代わりではない |
| 計算値と保存値 | PASS（シリアライズ整合性） | doc→YAML→docの等価性。計算正確性は別報告の独立照合 |
| 西洋基本／Full差 | PASS | 基本は主要出生図、Fullに小惑星／短期transit。初回Fullは31日 |
| 四柱基本／Full差 | PASS（送信モード） | 同じ保存Fullから基本鑑定の共通情報を切り出す。別のSKU／別の計算を発見したものではない |
| 全大運・命式の保持 | PASS | 基本／選択年の`common`に原本のdaiunブロックと同じ値 |
| 原局と年別の出所 | PASS（抽出契約） | `selected_base_forecasts`は保存annual_forecastsから取得。追加試作の年別資料を勝手に統合しない |
| 四柱単独のAI指示 | PASS（既存テスト＋実生成） | ハウス・ASC/MC・西洋transit・西洋ACGを前提にしない。構造分析／不確実性を扱う |
| 西洋単独のAI指示 | PASS（既存テスト＋実生成） | 四柱構造分析規則を混在させない。unknownハウス制約を維持 |
| 複合指示 | PASS（既存テスト＋実生成） | 収録された両占術の指示。専用販売商品の存在までは意味しない |
| 年の表現 | PASS（新規指示） | 原本単年＝原本作成時、選択年のみ対象、立春期間、交運近似。旧保存promptはraw原本と区別 |
| 不要メタデータ | FAIL（イベントtransit） | 通常10構成は検索パス診断なし。独立したtransit_onlyにresolved/searched等が残る |
| 計算条件・不確実性 | PASS（確認範囲） | 候補・approx_*・time_sensitive等が残る。省略される全形式の完全性を包括認定しない |
| YAML・AIコピー／保存・ZIP | PASS（既存ローカル契約） | raw原本、最新指示、AI送信モードを既存モックテストで区別。実ブラウザ全商品操作は未実施 |
| SVG生成 | PASS（西洋・四柱XML） | 実商品データから生成してXML解析。視覚的正しさは未実施 |
| PDF／ZIP内全画像の目視 | 未実施 | 機能テストを全出力の表示品質と混同しない |

## 年選択の実データ試験

架空1990-05-15 12:30 JST女性から生成したFullの収録年は2026～2035年。年選択は再計算せず保存値を抽出します。

| 操作 | 状態 | 結果 |
|---|---|---|
| 基本鑑定 | PASS | 年別一覧を送信範囲から外し、命式・全大運等を保持 |
| 単年2026 | PASS | 元の2026レコードと完全に値一致 |
| 連続2年2026/2027 | PASS | 該当する元レコードと一致 |
| 非連続2026/2035 | PASS | 指定2年だけ。元レコードと一致 |
| 交運前後2032/2033/2034 | PASS | 元レコードと一致、2033年には大運2context、前後は各1context |
| 完全原本 | PASS | CRLFを含む元文字列をそのまま返す。元YAMLを新指示のために再serializeしない |
| 範囲外2036 | PASS | years_not_savedで拒否。推定・再計算しない |
| 同一年の別出所 | PASS（既存試作テスト） | 基本10年と追加流年の別出所を維持。商品UIでの両者一括統合は対象外 |

実スキーマは提案された`annual_fortune_report`そのものではありません。年選択結果に`year_selection`、共通の`common`、該当年の`selected_base_forecasts`を持ちます。原本・基本・選択でどの形をAI／アプリへ渡すかを区別し、送信抽出版は原本としてのアプリimport用途ではない旨の情報もあります。

## 旧保存データの互換性

**PASSは架空fixtureに対してのみ**です。`tests/test_shichusuimei_year_selection.py`等で、古い共通prompt／内部metadataがある原本、annual_forecastsなし、保存forecast不整合、不正YAML、再帰参照、誤商品、型違い、未収録年を確認しました。

- raw `.yaml`とZIPの`full.yaml`は保存文字列を保持し、新しい占術別指示は表示・prompt.txt・AIテキストへ適用（PASS）。保存済み原本／promptのDBを書き換えません。
- 年別データがない旧原本は基本・完全原本の利用を維持し、年選択は利用不可／拒否（PASS）。存在しない年を生成しません。
- 内部パスを含む旧原本の完全保存と、新規購入者向けの診断情報抑制は別契約です。古い完全原本の診断情報が残ることを新規除去の失敗とはしていません。
- 購入履歴・既存購入者の全実データ・現在の認証・共有URL期限・実決済連携は**未実施**。本番DBを検証のために参照していません。

## 見つかった案内の不整合

初回western_full生成は`transit_days=31`。追加専用商品は38日です。ZIP README生成の`full_like_western`分岐は日数を調べず「transit.yaml: 38日分」と記載するため、31日Fullにも38日案内が付くコード経路があります（P3、表示）。31日データが38日へ欠落した計算問題とは扱いません。AIの通常Full出力は31日として再試験しました。

検証途中でFullの試作パラメータを38日にして実AIへ送った追加応答は `supplemental38_readings/` に区別して保存しました。これは初回販売SKUの標準データではありません。通常promptの固定31日説明との一致は未保証であり、商品設定に応じて日数を統一する改善候補です。中間コピーは `archived_intermediate_outputs/` に残し、最終評価は現在の31日入力・応答に基づきます。
