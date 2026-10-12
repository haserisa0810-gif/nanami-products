# 不具合・改善候補

ここでのseverityは親監査が実行証拠と到達経路を踏まえて付けたものです。Claude原文のseverityと異なる場合はレビュー報告に理由を示しています。**今回は未修正**です。変更案は別の実装作業で検討するための提案であり、既存保存データの自動修正・再発行を許可するものではありません。

## 一覧

| ID | 優先度 | 状態 | 原因分類 | 内容 |
|---|---|---|---|---|
| Q01 | P0 | FAIL | 計算エンジン | UTC offset≤0で日柱が1日進む |
| Q02 | P1 | FAIL | 計算エンジン／商品出力／UI | 日替わり選択の表示と動作が逆の意味になる |
| Q03 | P1 | FAIL | データ生成／UI | 性別「指定なし」が女性として大運と入力欄に保存される |
| Q04 | P1 | FAIL | データ生成／UI | DST不存在時刻の受入れ、重複時刻のfold未指定 |
| Q05 | P1 | FAIL | 商品出力 | 時刻不明の仮出生ハウスがtransit.natal_houseに残る |
| Q06 | P2 | FAIL | 計算エンジン（環境依存） | Windowsの1970年以前の日時変換が例外 |
| Q07 | P2 | FAIL | 計算エンジン／計算方式 | 旧身強参考指標が食傷月を中立と説明 |
| Q08 | P2 | FAIL | 商品出力 | イベントtransitのephemeris診断情報を公開出力に含める |
| Q09 | P2 | FAIL | UI・API入力 | 不正日付・24時・緯度範囲外がHTTP500 |
| Q10 | P2 | FAIL | 計算方式／UI | 高緯度Placidus例外の明確な商品対応が不足 |
| Q11 | P2 | FAIL（単一応答） | AI解釈 | 財のvisible_root_score=0から「根なし」を広く断定 |
| Q12 | P2 | FAIL（単一応答） | AI指示文／AI解釈 | 日次orbの最小値を厳密イベントの「正確化」と表現 |
| Q13 | P3 | FAIL（表示） | 商品出力 | 初回31日FullにもZIP READMEが38日と案内する経路 |
| Q14 | P3 | FAIL（ツール） | 開発用同期 | CRLF差で正本同期のraw hashチェックが失敗 |

P0/P1は解消または対象範囲の仕様対応が確認されるまで、新候補の公開保留の根拠とします。P2/P3をすべて同じ影響と見なしません。P0は計算誤りであり、DB破損が見つかったという意味ではありません。

## Q01：日柱のタイムゾーン依存

- 箇所：`services/shichusuimei_calc.py:451-476`。
- 再現：`day_kanshi_from_birth(datetime(2000,1,7,12), "UTC", False)` → **乙丑**。独立暦／現地暦日式では**甲子**。同じ日時と設定で`Asia/Tokyo`は甲子。
- 証跡：[主JSON](new_verification_results.json)の`day:2000-1-7:UTC`など15件、Claude F1。
- 原因：現地0時のUTC JDに`+0.5+50`を加えて切り捨てると、オフセット正の場合だけ基準日に合う。UTC／米州／英国冬時間で+1日。
- 影響：その入力の日柱、日主、時干、十神、十二運、空亡、神殺、構造分析など。国内JSTの代表例が合格しても海外出生を保証できない。どの実購入者が該当するかは未調査。
- 提案：採用する日替わり後の**現地暦日**から独立した干支通算日式を適用し、別実装・外部暦の回帰例を追加。原本書換えや既存購入者への対応は別途判断する。

## Q02：日替わりUIの契約違反

- 箇所：`services/shichusuimei_calc.py:419-476`、`templates/redeem_shichu.html:169-173`、計算結果の関連ラベル。
- UI：false＝1時（丑の刻）標準、true＝23時。内部：false＝0時、true＝0時台だけ前日扱い（結果として1時切替）。
- 再現：JST 2000-01-07 23:30、true →甲子。表示どおり23時切替なら翌日乙丑。同日0:30、true →癸亥、表示どおりなら甲子。
- 証跡：`day_boundary_23:00:30`／`:23:30` FAIL、Claude F2。
- 影響：日境界の利用者に日主からの派生値の違いを生む。0時／23時／1時の流派差そのものとは別に、選択表示と計算が矛盾することが問題。
- 提案：既存保存値との互換性を考慮し、採用規則を明示するモードと正しいラベルを決める。保存済みbooleanの意味を無断で読み替えない。

## Q03：性別未指定を女性へ変換

- 箇所：`services/shichusuimei_calc.py:687-707, 1550, 1663`、購入UI `templates/redeem_shichu.html:103-109`、`routes.py:712`。
- 再現：1990-05-15、gender=`unknown`で計算 →input.raw.gender=`female`、daiun.gender=`female`、direction=`reverse`。
- 証跡：`gender_unknown_female_default`。購入UIには「指定なし」があり、そのまま送信できる案内を確認。
- 影響：未指定でも一方の大運が確定し、元入力が女性だったように見える。男性だった場合は順逆が変わる。管理者・APIだけの問題とは言えない。
- 提案：原入力unknownを保持し、大運を保留／二方式候補とするか、必要入力として選択を求めるかを商品仕様で決める。既存原本を自動変更しない。

## Q04：DSTの不存在・重複時刻

- 箇所：`services/yaml_exporter.py::build_product_yaml`のZoneInfo付与・offset算出と関連出生日時入力。
- 再現1：America/New_York、2024-03-10 02:30を生成すると07:30 UTCに対応。現地へ戻すと03:30となり、入力時刻は実在しないのに受け入れる。
- 再現2：2024-11-03 01:30はfold=0で05:30 UTC、fold=1で06:30 UTC。入力にfold指定／選択がなく、片方へ固定。
- 証跡：`DST:2024-03-10T02:30:00`、`DST_ambiguous_fold`。
- 影響：海外の対象日に1時間以上の時刻誤差、ASC・ハウス・月・時柱などに影響。流派としてDSTを標準時へ戻すかとは別の入力の曖昧性。
- 提案：UTC往復で不存在を検出し、重複時刻はoffset等を明示して選択。既存のtimezone／出生地入力範囲を踏まえて実装する。

## Q05：時刻不明のtransitハウス

- 箇所：`services/yaml_exporter.py:216, 300-365, 604, 650`。
- 再現：birth_time=None、birth_time_accuracy=`unknown`、include_transit=Trueで生成。31日×10天体の310値すべてにnatal_houseが入る。
- 証跡：`unknown_transit_natal_house`、[時刻不明YAML](sample_western_unknown.yaml)。
- 影響：出生図のハウス・ASC/MCは暫定欄へ隔離／禁止flagがあるが、transit項目単位では通常値に見える。プロンプトを無視する別の消費者に誤用される余地。
- 留保：今回の実AIはそのハウス値を使わず制約を守った。全体の警告が全くないという指摘ではない。
- 提案：unknownではnatal_houseをnull／専用暫定欄とする、または参照元の仮定を項目に明示。収録データ契約変更は別途レビュー。

## Q06：Windows負timestamp例外

- 箇所：`services/shichusuimei_calc.py:904`。
- 再現：当Windows／Python3.14で1950-07-15 13:30 JST女性の実計算 →`[Errno 22] Invalid argument`。
- 証跡：`pre1970_windows_current_runtime`。起運・節気関連のJD→UTC変換。
- 影響：ローカルでの過去出生計算が完了しない。Linux本番の再現は未実施。同じ範囲の全出生が失敗するとまでは検査していない。
- 提案：epoch＋timedelta等のOS依存しない日時変換を検討し、全対象年代のWindows/Linux両検証を行う。

## Q07：旧身強参考指標の得令説明

- 箇所：`services/shichusuimei_calc.py:714-762`。
- 再現：`_calc_strength_score(Pillars4("庚午","壬午","甲子","甲子"))` →月支午=火と日干甲=木を「中立・直接関係が弱い」、delta0と説明。
- 証跡：`strength_output_month_neutral`。木生火は洩気側の関係がある。
- 影響：旧`features.strength`の説明が新しい構造分析と齟齬を持つ可能性。scoreの正解／全閾値の校正を検証していないため、一定点数が必ず誤りとはしない。
- 提案：説明に全相生相剋の関係を明示、独自係数・reference_onlyを徹底。係数変更は別の占術レビューを要する。

## Q08：イベントtransitの内部診断

- 箇所：`services/transit_yaml.py::build_transit_only_yaml`のmeta.ephemeris。
- 再現：Fictional event、2024-04-08 18:00 UTC、Tokyoで生成 →`resolved_ephe_dir`／`searched_ephe_dirs`等がYAMLに残る。
- 証跡：`no_internal_paths:transit_only`、[イベントYAML](sample_transit_only.yaml)。
- 影響：購入者向け新規出力に環境パス／探索情報を露出。通常商品のメタデータ抑制とは別生成経路。
- 提案：計算エンジン・使用条件を残して診断だけを共通出力adapterで除外。完全保存原本は変更しない。

## Q09：不正入力の500

- 箇所：`services/api_calc.py:226-260`、`services/western_calc.py`等。
- 再現：有効な基本payloadにbirth_date=`not-a-date`、`2023-02-29`、birth_time=`24:00`、lat=100を個別入力 →各500／INTERNAL_ERRORと内部例外メッセージ。
- 証跡：`api_invalid:*`4件。入力不備はクライアントエラーとして明示する期待で評価。
- 影響：API利用者が入力不備とサービス故障を区別できない。購入フォームの全経路を500と認定したものではない。
- 提案：日時／座標範囲を計算前に検証し、安定したエラーcode／400系応答にする。

## Q10：高緯度ハウスの例外

- 箇所：`services/western_core.py`／`services/western_calc.py`のPlacidus計算呼出。
- 再現：固定UTC日時で緯度69.65または-75 →`swisseph.houses: error`。
- 証跡：`high_latitude:*`2件。Swiss公式のPlacidus/Koch限界と一致。
- 影響：サポートする緯度の利用者へ、方式の適用不能を商品上で適切に説明する必要がある。Placidus数学自体のバグとは分類しない。
- 提案：入力範囲・エラー表示・別方式利用を商品仕様として決める。無断で別ハウスへ切替えることは避ける。

## Q11／Q12：実AI応答の限定的な不一致

根の意味の拡張とsample精度の過大表現です。原入力と実応答の箇所・根拠は[AI報告](ai_quality_report.md)にあります。全AI／全鑑定が同じ誤りをするという評価ではありません。修正候補は、visible_root_scoreの定義と日次／週次近似を指示で明示し、複数命式・複数モデルで再試験することです。

## Q13：ZIPの日数案内

- 箇所：`routes.py:9233-9238`付近、READMEの`full_like_western`分岐。
- 期待：初回Full31日なら31日、追加38日なら38日。実際：同分岐で38日固定。
- 影響：保存ファイルの説明と収録期間の不一致。YAMLの日次件数の欠落ではない。
- 提案：period.daysなど実収録期間から案内を生成。日本語READMEのコード経路を確認、全localeは未実施。

## Q14：同期ハッシュの改行差

- 再現：`scripts/sync_western_core.py --check --source C:/Users/haser/dev/nanami-astro`は3ファイルを不一致扱い。CRLF→LF正規化後の内容は3件すべて一致。
- 証跡：`source_sync_content:*`。
- 影響：同期確認の偽警告。実際の西洋計算ロジックの相違は確認されない。
- 提案：同期ツールとGit改行規則の整合を決める。正本・対象の既存変更は破棄しない。

## 未確認の懸念／流派差

| 項目 | 状態 | 必要な確認 |
|---|---|---|
| FreeAstroのtimezone契約 | 未実施 | リクエストにtzなし。受信側仕様・実結果とoffset付き入力の独立比較 |
| 実ephemeris fallbackと表示modeの不一致 | 未実施 | 部分ファイル欠損・天体別戻りflagの記録 |
| 真太陽時、夏時間の標準時換算、子刻二分法 | 未実施（方式妥当性） | 採用流派と商品説明を確定。方式差を計算誤りへ一律分類しない |
| 巳の中気／余気順序・季節係数・身強閾値 | 未実施（占術校正） | 蔵干集合は一致。固定重みの文献／専門家レビュー |
| 全刑・破・三刑・半会・三合の重複／活性化 | 未実施（全網羅） | 独立規則の全組合せ反例と参加要素追跡 |
| 全旧購入者・保存データ・購入履歴 | 未実施 | 別途権限下の読み取り影響調査。今回はDBへ接続しない |
| 画像・PDFの見た目／全ブラウザ導線 | 未実施 | ローカル架空商品でレンダリング確認 |

## 公開可否の判断材料

この候補の無条件な公開を推奨しません。まずQ01～Q05の計算／出力契約の対処方針を決め、独立反例で修正確認を行う必要があります。販売対象地域・入力仕様を限定する判断でも、既存データの意味と明示的な境界を確認する必要があります。現時点で本番全利用者への誤りの頻度・注文件数は不明です。
