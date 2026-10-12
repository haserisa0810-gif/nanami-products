# Claude Opus 5.5再レビューの記録と対応

指定モデル `claude-opus-5-5` を認証済みCLIで実際に呼び出した。modelUsageからモデルIDを検証し、別モデルへの代用はしていない。レビュー入力は固定ソースと架空ケースのみ。ツール無効のため、モデルのPASSはコード査読・手計算の判定であり、実行確認ではない。実行確認は親側のpytest、独立fixture、修正前後比較と分離した。

## 証跡

- 初回：[原文](independent_review.md)、[モデル・対象ファイル・時刻・改変検査](independent_review_metadata.json)、[使用指示](claude_review_request.md)。
- 保護追加後：[原文](claude_followup/independent_review.md)、[モデル検証](claude_followup/independent_review_metadata.json)、[使用指示と差分](claude_followup/claude_review_request.md)。
- 第3回の追加保護：[原文](claude_final/independent_review.md)、[モデル検証](claude_final/independent_review_metadata.json)、[使用指示と差分](claude_final/claude_review_request.md)。`claude_final`というディレクトリ名だが、この査読後に下記A/B/Cを親側で修正した。各hashはそのレビュー時点のスナップショットを表す。

## 初回／2回目の指摘への対応

| 指摘 | 親側の判断・対応 | 検証 |
|---|---|---|
| 元P0 UTCオフセットによる日柱ずれ | 新規計算で解消。現地暦日の式に変更 | 960独立期待値、旧320比較で184→0、ClaudeのJD・ordinal手計算 |
| 元P1 日替わりUI不一致 | 新規1時／23時を表示と一致。旧原本の実規則は維持 | 全3方式の境界、日柱・時柱、API・YAML・UI |
| 元P1 unknown女性補完 | 大運を未確定にし、命式と原局×流年は維持 | unknown別入力、年選択・SVG・年レポート・追加YAML |
| P1-A 旧海外原本の年レポート | 原本を変えず、旧版と保存offsetに応じ疑義フラグ・注意事項を追加。解釈flagにも明示 | 旧offset−8／不明、元データ不変の比較 |
| P1-B API変更の識別と告知 | 四柱／複合だけAPI1.1にし、日替わり・日柱・省略gender・timezone必須・新エラーを変更履歴に明記 | 四柱API1.1／西洋・transit envelope1.0テスト |
| P1-C 別呼出元の影響 | rgで運用上の直接呼出元がyaml_exporterのみであることを確認。独立した日運／相性エンジン経路は見つからない | 全既存回帰、修正前後の西洋単独／複合比較 |
| P1-D 未指定性別のaddon告知 | 日本語基本／addonフォームに大運保留を告知。外国語・外部販売ページは未対応として公開判断に残す | テンプレートとunknown出力。外部販売ページは未実施 |
| P2-A 旧日柱照合ガードの抜け | normalized／top-level／summaryの順で照合。欠落は拒否 | 3旧形式、原本不変、不一致拒否 |
| P2-B 国内の過去DST | 国内もfold指定可。1949-09-11 00:30の重複をresolverで実確認 | +10／+9の2候補。全命式計算のWindows1970年以前問題は未修正 |
| P2-C 旧fold／offset | 原本の出生当時UTCオフセットを引継ぎ | モックの引数確認に加え、実生成関数による旧JST YAML連携 |
| P2-D 子刻時干の流派差 | 現在の五鼠遁方式を維持し、hour_stem_ruleに明示 | 0／1／23時方式の算式・表示整合。夜子時等への変更はしない |
| P2-E booleanの1と時間enumの1 | 別フィールド・別型である。UI valueはfalse／true、API day_boundaryは時刻enum | テンプレート確認。コアの文字列booleanは拒否 |
| P2-F 旧female補完の扱い | 元inputにgenderが記録されunknownで、旧rawがfemaleの場合のみ補完候補と表示。gender欠落を補完済みと断定しない | legacy flag／入力gender欠落テスト |
| timezone nullがaliasを無視 | nullと明示tz_nameを正しく使用 | LA timezone=null／tz_name指定 |
| N1 false／0／[]／{}が東京へ補完 | 実在する反例として修正。rawを文字列・IANAとして直接検証 | 4型とも400 INVALID_TIMEZONE |
| N2 long-term商品が四柱helperに落ちる | 条件付き指摘。購入routeは専用_build_long_term_transits_addon_from_baseで処理し返却しており、このhelperへ落ちない | routesの専用分岐を確認。既存長期商品回帰 |
| N3 モックだけで実signatureを検証できない | 実生成関数を使う旧JST連携テストを追加 | 保存offsetと旧0時設定を引継ぎ、日柱一致、元データ不変 |
| N4 古いLMT offset丸め | 今回未修正。丸めた手編集YAMLなどは厳格一致で拒否されうる。未知offsetを推測で補完しない | 年代全域の統合は未実施 |
| その他既存指摘 | Windows負timestamp、SVG年齢表示、立春秒単位、到達不能分岐などは元3件とは分離 | 未修正／未検証としてREADMEに記録 |

旧原本を持つ購入者の再発行・返金・サポート導線は未決定。原本自体を保護することと、旧計算を正しいと保証することを区別する。今回のレビューとローカル試験の合格を、全商品・全流派・全世界の販売承認に読み替えない。

## 第3回後の対応

- A：旧genderキー欠落＋raw femaleは `legacy_gender_unverified` とし、順逆確定フラグはnull。補完されたと断定せず、確定とも扱わない。旧版0.4.0・raw femaleをテスト内で明示して検証した。
- B：UTCオフセットのtrue／falseを数値として受理しない。Londonの重複時刻にboolを渡す反例を拒否テストに追加した。
- C：国内都道府県を確認できる場合の空timezoneは、従来どおりJST既定値を使用。海外は省略・空を拒否し、非文字列は国内でも拒否する。
- D：保存offset不足を未確認の注意として出す方針を維持した。既知のJST原本でも保存根拠が欠ける場合に注意を出す可能性があるが、原本を変更したり誤って補正したりはしない。
- モデルが未提示としていた経路を親側で実行した。西洋・transitの実APIは版1.0、修正後LA原本の年レポートは日柱疑義false、旧LA日柱乙丑の追加データ生成は実関数で拒否され原本は不変。

この後続差分は親側の全回帰と実関数テストで検証した。第3回レビューを最終ソースへの無条件のPASSと報告しない。Claudeによる後続A/B/Cの再査読は未実施。
