# Claude Opus 5.5 独立レビューの実施記録

**実施済み**。要求したモデルIDは `claude-opus-5-5`、応答の `modelUsage` も同じIDでした。別モデルへの代用は行っていません。[実施メタデータ](independent_review_metadata.json)、[生応答](independent_review_response.json)。

## 実行条件

- Claude Codeの既存認証を利用。既存CLI 2.1.218では指定モデルのバージョン制約エラーがあったため、試作用ディレクトリに2.1.280を隔離導入。グローバルCLIは変更していません。
- オプション：`--safe-mode --no-session-persistence --model claude-opus-5-5 --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}' --output-format json`。
- 空の一時作業ディレクトリから実行。ClaudeへのDBアクセス・コード編集・shell・Webツールは許可していません。実データ・秘密情報は渡していません。
- 指示は[claude_review_request.md](claude_review_request.md)。資料は行番号付き11ソースの[固定スナップショット](independent_review_input.md)。[ファイル別SHA256](independent_review_hashes.json)を記録し、終了後の変更は0件です。
- モデルの利用可否だけを確認した[probe記録](model_probe_metadata.json)と、実コードレビューは別の呼出です。
- 実施時刻は応答メタデータのUTC時刻。モデル正式名称・IDは[Anthropic公式モデル資料](https://platform.claude.com/docs/en/models/overview)に合わせています。

## 対象ファイル

1. `services/shichusuimei_calc.py`
2. `services/shichusuimei_structure.py`
3. `services/western_calc.py`
4. `services/western_core.py`
5. `services/transit_builder.py`
6. `services/asteroid_provider.py`
7. `services/transit_yaml.py`
8. `services/long_term_transit_yaml.py`
9. `services/yaml_exporter.py`
10. `services/location.py`
11. `services/shichusuimei_year_selection.py`

命式・節気・干支・時刻・大運・流年、表の十神・十二運・空亡・神殺、構造分析・格局／用神・合化、天体・ハウス・アスペクト・小惑星・トランジットをレビュー対象にしました。全UI・全locale・年抽出prototypeはClaudeへの資料に含めていません。それらは親監査側の既存テストと追加試験で確認しました。

## 独立性と限界

Claudeには「既存テストの合格や実装コメントから正しいと認定しない」「独立した式・手計算・反例を用いる」「仮説／流派差／未検証を区別する」と指示しました。Claude自身が実行した内容は**読解・代数・表の手照合**で、外部資料検索やコード実行はしていません。記憶由来の干支基準日だけを確定証拠とは扱わず、親監査でlunar-pythonの実行照合を追加しました。

レビュー原文は[変更せず保存](independent_review.md)しています。そのseverityや「確認済み」はClaude自身の表現であり、以下の追確認結果が監査としての採否です。

## 主指摘の追確認

| Claude指摘 | 親監査の判定 | 根拠・扱い |
|---|---|---|
| F1 P0：UTC offset≤0で日柱+1 | FAIL、採用P0 | 日数式の代数と別暦30条件中15反例が一致。2000-01-07 UTC：甲子→乙丑 |
| F2 P1：23時設定の表示／動作不一致 | FAIL、採用P1 | 実行＋実際の購入UIを確認。falseは0時、trueは0時台前日扱い。UIはfalse=1時、true=23時 |
| F3 P2：子刻の時干不連続 | 未実施（流派の正誤） | 境界挙動は確認。子初・子正・晩子の採用方式を確定しないまま普遍的バグとしない |
| F4 P1：性別不明→女性 | FAIL、採用P1 | unknownからinput.raw.gender、daiun.genderともfemaleとなる。購入UIも「指定なし」を許可 |
| F5 P1：旧身強指標の洩気欠落 | FAIL（説明）、採用P2 | 甲×午の木生火が中立表示。全尺度／重みの校正は未実施のためP1の数値精度断定は採用しない |
| F6 P1：DST時計時刻を採用 | 未実施（方式差） | 現地時計時刻と標準時の扱いは流派・仕様判断が必要。DST不存在／重複入力の別P1は実行確認済み |
| F7 P1：時刻不明transitのnatal_house | FAIL、採用P1 | 日次310/310項目に仮出生ハウス値。出生図の暫定flag／プロンプトはあり、実AIは断定回避PASS |
| F8 P1：小惑星APIのtimezone不足 | 未実施（位置誤り）、要調査 | モック送信にoffset/tzなし。ただし受信側の時刻契約未確認、実小惑星の誤差は認定しない |
| F9 P2：Windows負timestamp例外 | FAIL、採用P2 | 当環境で1950出生の実関数がInvalid argument。Linux本番では未実施 |
| F10 P2：時刻不明の月／境界の確度 | 未実施（全日区間の精度） | unknown12時仮置きと制約は確認。日の最早最遅を全計算する仕様ではない。実AIは注意を付記 |
| F11 P2：高緯度Placidus | FAIL、採用P2 | 69.65/-75で例外。Swiss公式の方式限界に合致。商品としての案内・入力保護の改善候補 |
| F12 P2：出生地が都道府県代表のみ | 広い影響主張は不採用 | 実購入経路には市区町村座標解決がある。都道府県だけの入力の近似と真太陽時方式は別事項 |
| F13 P2：実使用ephemeris flagを無視 | 未実施（誤表示再現） | コード上の懸念は記録。部分的天文ファイル欠損時の実flag／出力不一致は未再現 |

他のP3候補（半会と拱合の名称、蔵干順序、unused transit_builderのキー、generated_atのtimezone、週次ピークの近似、360°浮動小数境界）は[原文](independent_review.md)に保持しています。全候補の実行反例・影響経路を検証したとはしません。親側の同期CRLF、ZIP日数説明、API不正入力、AI応答の限定的誤りは独立レビュー後に追加しました。

## 再レビュー用資料

原指示文・固定ソース・SHA256・モデルの生応答が揃っているため、同じモデルにそのまま渡せます。修正時はこの古いスナップショットを新コードと取り違えず、新しいcommit・dirty差分を固定してレビューする必要があります。今回は指摘の修正を行っていません。
