# 四柱推命エンジン0.5.0：日柱・日替わり・性別未指定の修正

2026-10-11。対象はローカルworktree `tmp/prompt-separation`、ブランチ `codex/astrology-prompt-separation`。先行する指示文分離と品質監査の未コミット変更を保持したまま、監査Q01・Q02・Q03を修正した。ルートcheckoutの未コミット作業、本番DB、購入履歴、発行済み原本は変更していない。commit・push・デプロイ・価格変更・商品公開は未実施。

今回は国内・海外、基本版・Full版・複合商品の四柱推命に使う共通エンジンを修正した。新規生成にはどちらの版でも修正が適用される。Full専用の別エンジンを新設したものではない。保存済み基本版・Full版には適用しない。

## 原因と対処

| 監査項目 | 原因 | 対処 |
|---|---|---|
| Q01 P0 日柱が1日進む | 現地0時をUTCのJDに変換し、固定の補正値で日柱の通算日を切り捨てていた。UTCオフセットが0以下の地域で暦日がずれた | 日替わり適用後の現地Gregorian暦日から `(date.toordinal() + 14) % 60` を計算。2000-01-07甲子の独立暦を参照し、別実装と照合。年柱・月柱の節入りは従来どおりUTCの天文時刻を使用 |
| Q02 P1 日替わりの表示と処理が不一致 | UIのfalse=1時、true=23時に対し、実装はfalse=0時、true=1時だった | 新規計算はUIの契約に統一。明示的な `day_boundary_hour` と計算バージョンを保持。旧原本のbooleanを新規則に読み替えない |
| Q03 P1 unknownを女性へ補完 | 性別の正規化で認識できない値をfemaleにしていた | unknownを保持。大運は `status: undetermined_gender`、direction・起運年齢はnull、itemsは空配列。性別によらない命式と原局×流年は保持 |

## 日替わり方式と日時の責務

| 新規入力 | 規則 | 日柱に用いる現地暦日 |
|---|---|---|
| 通常UI／`day_change_at_23: false`／`day_boundary: "01:00"` | 1時標準 | 00:00–00:59は前日、01:00以降は当日 |
| 23時UI／`day_change_at_23: true`／`day_boundary: "23:00"` | 23時切替 | 23:00–23:59は翌日、それ以外は当日 |
| エンジン／APIの明示指定 `day_boundary_hour: 0`／`day_boundary: "00:00"` | 0時切替 | 現地暦日そのもの。通常購入UIに新しい選択肢は追加しない |

1時を0時へ変更したものではない。1時／23時／0時は採用方式の違いであり、今回は既存UIが約束していた方式と実装の不一致を直した。時支は現地時計時刻から従来の2時間区分で求め、時干は採用した日干に対応する五鼠遁を使用する。真太陽時補正は追加していない。

`input.time_context` に現地日時、IANAタイムゾーン、出生当時のUTCオフセット、UTC日時、fold、日柱用暦日、日替わり時刻、時計時刻方式を分離して記録する。節入りはUTC天文時刻、日柱・時柱は現地日時という責務を維持する。

四柱推命と四柱を含む複合商品の日時入力はUTC往復で検証する。夏時間の不存在時刻を拒否し、重複時刻は `birth_fold: 0/1`、出生当時のUTCオフセット、または確定済みaware日時が必要。四柱購入画面に任意の「同じ現地時刻の1回目／2回目」を追加した。日本の過去の夏時間にも指定できる。海外API入力ではIANAタイムゾーンを必須にし、国内都道府県の既存JST既定値は維持した。西洋占星術単独の日時入力経路は今回変更していない。時干方式も `hour_stem_rule: five_rat_from_effective_day_stem` と明示し、夜子時など別流派への変更は行っていない。

## 変更ファイル

以下は先行する指示文分離作業との差分ではなく、今回の修正対象。

- `services/birth_datetime.py`：現地日時の検証とDST重複解決（新規）。
- `services/shichusuimei_calc.py`：現地暦日日柱、明示日替わり、unknown大運、0.5.0と日時根拠。
- `services/yaml_exporter.py`：四柱／複合商品の日時検証、計算設定と版の識別、流年追加YAMLへの引継ぎ。
- `services/api_calc.py`：日替わり入力の0／1／23の区別、海外タイムゾーン必須、日時エラー400。
- `services/shichusuimei_annual_report.py`：未確定大運を年別出力で保持し、原局×流年は維持。
- `services/api_tags.py`、`services/shichu_chart.py`：未確定大運の表示・AI向けヒント。
- `services/prompt_builder.py`：旧設定の読み替え禁止、unknownの女性補完・大運断定禁止。
- `routes.py`：日替わり説明、管理画面boolean処理、夏時間fold入力、旧原本からの追加データ生成の照合。
- `templates/redeem_shichu.html`、`templates/redeem.html`：日替わり／性別未指定の説明。四柱専用画面のfold選択。
- `templates/addon_form.html`：日本語の大運・流年追加の未指定性別に関する告知。
- `templates/nanami_api_spec.html`、`API_CALC_SPEC.md`：新仕様の明文化。
- `tests/test_shichusuimei_overseas_engine.py`、`tests/fixtures/shichusuimei/overseas_calendar_reference.json`：独立期待値と境界・互換テスト。
- `scripts/build_shichusuimei_independent_cases.py`、`scripts/verify_shichusuimei_engine_fix.py`、`scripts/review_shichusuimei_engine_fix.py`：独立fixture生成、修正前後比較、指定Claudeモデルへの再レビュー。
- `scripts/review_shichusuimei_fix_followup.py`：初回レビューを保存したまま、追加保護差分を同じモデルで再確認。
- `scripts/finalize_shichusuimei_fix_evidence.py`：最終テストログ、今回のみのアプリ差分、開始時コピーと現在ソースの照合。

## 独立照合

期待値を修正後エンジンから転記していない。fixture生成器はアプリケーションをimportせず、隔離した `lunar_python 1.4.8` からGregorian日干支を取得した。時干は独立した五鼠遁の算式、UTC日時は日付別の固定オフセット表から導出する。年／月柱は同一UTC瞬間を独立実装が扱うUTC+8に変換して求める。これを出生地の時刻として日柱へ流用していない。本番requirementsには独立検証ライブラリを追加していない。

| 検証 | 件数・範囲 | 証跡／限界 |
|---|---|---|
| 現地日柱・時柱・UTC換算 | 960ケース。東京、ソウル、ロンドン、NY、LA、ホノルル、シドニー、UTC、キリバス、米領サモア × 4日付 × 8時刻 × 3方式 | fixtureと新規pytest。2000-01-07、2024-02-29、7/1、12/31。全歴史年代のタイムゾーン検証ではない |
| 年／月柱 | 40ケース。10地域×4日付 | 独立実装との同一瞬間の照合。節気境界外を選択 |
| 立春 | 20ケース。10地域×2026立春前後 | [国立天文台2026暦要項](https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html)の2月4日05:02 JSTを参照し、±2分で検証。掲載時刻は分単位であり、厳密秒の精度検証ではない |
| 夏時間 | London、NY、LA、Sydneyの不存在／重複時刻 | 不存在を拒否、重複は未指定拒否とfold／offset／aware日時による解決を検証 |
| P0を日替わり変更と分離 | 0時方式320ケースで旧・新を照合 | 修正前184不一致、修正後0不一致。詳細は `before_after_verification.json` |

独立実装にも誤りの可能性はある。全節気、全年代、全流派の正しさをこの検証だけで保証したものではない。

## 日本出生・西洋データ・旧購入データへの影響

日本の境界外の3出生例×2既存boolean設定を比較し、追加status情報を除くnormalized_dataの計算値が一致した。比較範囲には四柱、全大運、流年、構造分析を含む。Tokyo／LAの西洋単独・複合商品4例では、生成日時を除く西洋データが一致した。西洋計算コアと四柱構造分析のソース自体は変更していない。

境界値では次のように新規結果が変わる。これはQ02を修正するための意図した変更であり、日本出生の全入力が不変という意味ではない。

| 東京2000-01-07 | 選択 | 旧 日柱／時柱 | 新 日柱／時柱 |
|---|---|---|---|
| 00:30 | 1時標準（false） | 甲子／甲子 | 癸亥／壬子 |
| 00:30 | 23時切替（true） | 癸亥／壬子 | 甲子／甲子 |
| 23:30 | 23時切替（true） | 甲子／甲子 | 乙丑／丙子 |

海外のP0修正や日替わり境界で日干が変われば、時干・十神・十二運・空亡・構造分析などの従属値も正当に変わる。大運の順逆・干支列・起運近似の式は性別確定時に変更していないが、日主との十神などの派生表示は変わりうる。未知性別では従来の女性扱いを廃止するため、大運の確定出力がなくなる。

新規計算に `engine_version: "0.5.0"`、明示規則・日時根拠を付け、四柱を含む新規chart識別にも計算版・設定を含める。四柱／複合APIの版は1.1とし、西洋／トランジット単独APIは1.0を維持する。保存済みID・購入URL・権限は変更しない。旧Full fixtureの年選択は保存値そのまま、完全原本は入力文字列そのままで返すことを検証した。原本から新たに追加流年を作る経路では、旧計算が実際に採用した規則（旧false=0時、旧true=1時）と保存されたUTCオフセットを引き継ぐ。それでも旧海外原本と日柱が食い違う場合は追加データとの結合を拒否し、日柱照合に必要な保存値が欠ける場合も拒否する。旧原本の再計算・移行は行わない。

旧原本から作る別年のレポートでは、原本の計算版と保存UTCオフセットを確認する。旧計算＋offset≤0は `base_day_pillar_suspect: true`、offset未確認ならnullと注意事項を出す。旧原本でunknownがfemaleへ補完されたことを確認できる場合は `legacy_female_imputed` とし、大運は参照値で方向確定済みではないと明示する。原本の命式・大運を変更したものではなく、各年の派生レポートに来歴の制約を付けたもの。

旧原本にgenderキー自体が欠け、保存rawがfemaleの場合は `legacy_gender_unverified`、順逆確定flagはnullとする。補完があったとは断定せず、保存値が本人の指定由来かどうかを未確認として保持する。UTCオフセットは数値の0／1と真偽値false／trueを区別し、真偽値によるDST候補選択は拒否する。

性別unknownは候補両出力を採用せず大運を保留する。全大運・原局×大運・大運×流年は算出できない旨を示し、原局、流年、原局×流年、年選択、SVG、追加YAMLの経路で例外や女性への再補完を防いだ。AI指示にも未確定の大運や交運時期を断定しない制約を追加した。

運用コードの直接呼出元を検索し、四柱計算は `yaml_exporter.py` 経由であることを確認した。他の独立した相性／日運エンジンが旧booleanの意味で呼ぶ経路は見つからない。検証専用scriptsは別扱い。注文使用済み登録は既存どおり生成成功後であり、日時エラーや追加YAML照合エラーで注文を使用済みにする変更は加えていない。大運・流年追加の日本語フォームにも未指定性別では大運が空になることを告知した。外部販売ページや外国語告知の整備は未実施で、海外公開前の課題として残す。

## テストと再レビュー

最終差分でPython全回帰 **1971 PASS、160サブテストPASS、149.23秒**。既存891テストと今回追加1080テストを含む。5622 warningsは既存の非推奨API等の警告で、失敗・skipはない。JavaScriptは6 PASS。修正前後比較スクリプトもexit 0で完了した。購入DBはモック、データはローカルの架空fixtureを使用し、実際の購入済みDBや本番サービスへ接続したテストではない。旧JST追加YAML、旧LA拒否、西洋／transit実API版、修正後LA年レポートは計算関数のモックなしで検証した。

- Python全回帰：[`pytest_final.log`](pytest_final.log)（実行ログの保存コピー）。
- 件数・既存／新規の区別・コマンド：[`test_results.json`](test_results.json)。
- JavaScript年選択：`node --test tests/test_shichusuimei_year_selection_ui.cjs`、6 PASS。
- 修正前後：[`before_after_verification.json`](before_after_verification.json)。
- Claude：[`claude_review_request.md`](claude_review_request.md)、`independent_review_input.md`、`independent_review_hashes.json`、`independent_review_metadata.json`、`independent_review.md`。
- レビュー3回の指摘と親側の対応判断：[`claude_review_resolution.md`](claude_review_resolution.md)。第3回の後続保護差分は親側の実関数・回帰テストで確認し、Claudeによる追加再査読は未実施。
- 最終変更範囲と保護コピーの整合：[`source_manifest.json`](source_manifest.json)、[`fix_only_application.patch`](fix_only_application.patch)。先行作業を含むgit diffと、今回のみのアプリ差分を区別する。

Claudeへ送るデータは固定ソース、修正前差分、架空の独立参照ケースのみ。顧客データ・認証キー・DBは含めない。指定モデルは `claude-opus-5-5` のみで、別モデルを代用しない。ツールは無効なので、Claudeの手計算・コード査読と、こちらの実行検証は区別する。

3回とも実モデルIDが `claude-opus-5-5`、CLI exit 0、is_error false、レビュー中の対象ソース改変なしを確認した。元3件の新規計算は初回の手計算査読で解消判定。旧原本・入力型・告知などの追加指摘は実装・テストで対応し、販売・再発行に関わる未決定事項は公開課題として保持した。モデル原文のPASS／FAIL／未検証と、親側の実行結果を混同しない。

## 未解決事項と公開判断

この修正はQ01–Q03と、その正確な日時処理に必要な四柱／複合商品のDST検証まで。前回監査のQ04は西洋単独経路には残る。Q05（出生時刻不明時のtransitハウス）、Q06（Windowsで1970年以前のJD日時変換）、Q07–Q14などは今回未修正。真太陽時、全流派の時干、起運の厳密交運日時、既存購入者の再発行方針も今回確定していない。外国語指示文の翻訳変更と実AI鑑定品質の再測定は対象外。

したがって今回の3件が解消しても、全商品の海外公開を一律に承認できる状態とは判断しない。対象商品で残るP1、古い海外原本の扱い、公開先での検証を別途判断する必要がある。今回はローカル修正・テスト・報告までとし、リリース操作は行わない。

開始時の未コミット状態は [`before_git_status.txt`](before_git_status.txt)、主要12ファイルの保護コピーとSHA256は `before/` と [`before_hashes.json`](before_hashes.json)。今回の変更もすべて未コミット。先行作業の変更を破棄したり履歴を書き換えたりしていない。
