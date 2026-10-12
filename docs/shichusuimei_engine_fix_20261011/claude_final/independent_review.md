# Opus 5.5 最終保護差分レビュー

**前提:** ツールは無効のため、コードの実行、テストの実行、外部照合はしていません。以下の判定はすべて、提示されたコードと差分を読んだ結果です。未提示のコード（`yaml_exporter`、`pillars4`、`day_kanshi_from_birth`、フォーム変換部、fixture の中身）に依存する項目は「未検証」とし、実在する反例とは分けて扱います。

## 1. 対応ごとの判定

| # | 対応 | 判定 | 根拠 |
|---|---|---|---|
| 1 | N1: 非文字列の timezone（false/0/[]/{}）を400にする | **PASS** | `api_calc.py:156` で `isinstance(raw, str)` を確認し、`:160` で raw を strip した値を `ZoneInfo` で検証しています。`_normalize_timezone` への委譲もなくなりました |
| 2 | timezone=null のとき tz_name を使う | **PASS** | `:152-154` は `None` の場合だけ tz_name に移ります。false や 0 は移らずに400です |
| 3 | 国内で空文字の timezone を指定した場合 | **FAIL（軽微）** | 反例Cを参照。変更履歴の「国内JST既定値は維持」と食い違います |
| 4 | エンジンで文字列の bool を拒否する | **PASS（関数単体）／呼出元は未検証** | `resolve_day_boundary_hour` が bool 以外を拒否します。ただし `yaml_exporter` が `None` などをそのまま渡す経路がないかは未提示です |
| 5 | API の day_boundary（false→1、0→0、0.0→400） | **PASS** | `str(False)` は `"false"` なので1、`str(0)` は `"0"` なので0、`"0.0"` は選択肢にないので400になります |
| 6 | 四柱と複合APIの版を1.1にする | **PASS** | `_success:78` |
| 7 | 西洋とトランジットAPIの版を1.0のまま維持する | **未検証** | 追加テストは `_success(endpoint, {}, {"systems":{}})` を呼ぶだけで、`calc_western_api` や `calc_transit_api` を通っていません。`build_product_yaml(include_shichusuimei=False)` が `systems.shichusuimei` に `{}` やスタブの dict を置く実装だと、版は1.1になります。テストの `endpoint` 引数も判定に効いていません |
| 8 | 旧年レポートで日柱の疑義を flag にする | **PASS（条件付き）** | offset が0以下、または不明のときに flag が付き、interpretation_flags にも反映されます。原本は変更していません（新しい dict と deepcopy のみ）。ただし反例Dと条件付き項目を参照してください |
| 9 | 旧原本の女性補完 flag | **一部FAIL** | 反例Aを参照 |
| 10 | 旧addonの日柱を normalized → top-level → summary の順に照合し、無ければ拒否する | **PASS** | `routes` に提示されたとおりの順序です。照合できない場合と不一致の場合はどちらも ValueError になり、注文の使用登録より前に失敗します |
| 11 | 旧addonで保存済み offset を引き継ぐ | **PASS（JSTのfixture）** | 実際の生成関数を使った統合テストがあります。旧LA原本が日柱不一致で拒否される経路にはテストがありません |
| 12 | 国内でも fold を指定でき、1949年日本の重複時刻を検出する | **PASS（推論）** | tzdata の規則では、1949-09-10（土）25:00 JDT に JST へ戻るため、09-11 00:30 は重複します。fold=0 が +10、fold=1 が +9 で、テストの期待値と一致します。Windows では PyPI の `tzdata` のバージョンに依存します |
| 13 | 時干の規則を明記する | **ラベルはPASS／挙動は未検証** | テストは文字列が存在するかを見ているだけです。`pillars4` が実際に有効日の日干から五鼠遁で時干を出しているかは未提示です |
| 14 | 生成後に注文を使用済みにする | **PASS** | 生成で例外が出れば `_redeem_addon_order_or_raise` に到達しません |
| 15 | 日本語の告知 | **PASS（ja のみ）** | `lang == 'ja'` の場合だけ表示されます。外国語版は既知の未解決事項として扱われています |
| 16 | 旧原本の欠落 gender を補完済みと断定しない | **テストが弱い** | 反例Aの後半を参照 |

## 2. 実在する反例（提示コードだけで成立するもの）

### A. 性別キーが欠落した旧原本で、大運の順逆が「確定」と出力される

**入力:**
- `engine_version="0.4.0"`
- `input` に `gender` キーがない
- `systems.shichusuimei.input.raw.gender="female"`
- 保存済みの大運 items がある

**結果:**
- `legacy_imputed` は False になります（`:155` が `"gender" in base_input` を要求するため）。
- `direction_unknown` も False です。
- そのため `daiun.status` は `"overlapping_periods"`、`interpretation_flags.daiun_direction_confirmed` は **True** になります。

補完されたかどうかを原本から判断できない、と決めたのに、確定とは断定してしまっています。

追加テスト `test_old_report_missing_gender_...` にも穴があります。このテストは `engine_version` も `raw.gender` も設定していません。fixture が 0.5.0、または raw の性別が female 以外であれば、修正前のコードでも通ってしまいます。さらに `daiun_direction_confirmed` を検査していません。

**最小修正（三値にする）:**
```python
gender_unverified = legacy and "gender" not in base_input and raw_gender == "female"
if gender_unverified:
    legacy_notes.append("旧原本に性別指定の記録がなく、保存済み大運の順逆が入力由来か補完由来か確認できません。参照用として扱ってください。")
...
"daiun_direction_confirmed": False if (direction_unknown or legacy_imputed) else None if gender_unverified else True,
```
テスト側では、`engine_version="0.4.0"` と `raw.gender="female"` を明示的に設定し、`daiun_direction_confirmed is None` を検査してください。

### B. `birth_utc_offset_hours` に JSON の true/false を渡すと、+1/0 として受理される

`birth_datetime.py:43` は `float(True)` を計算して 1.0 にします。

**入力:** `Europe/London`、`1990-10-28 01:30`（BST終了による重複時刻）、`birth_utc_offset_hours=true`

**結果:** 400 にならず、BST（+1）が選ばれます。timezone や day_boundary で塞いだのと同じ種類の型の穴です。

**最小修正:**
```python
if type(utc_offset_hours) is bool:
    raise BirthDatetimeError("出生当時のUTCオフセットを数値で指定してください。")
```

### C. 国内出生で `timezone: ""` を送ると400になる

**入力:** `{"birth_place":"東京都","timezone":""}`

**結果:** `:156` で400になります。変更履歴は「空なら400」を海外出生の条件として書き、国内は「JST既定値を維持」としています。フォーム系のクライアントは空文字を送ることが多いので、実装と文書が食い違っています。

**推奨する修正:** 空白だけの文字列を省略として扱います。海外出生の場合は `resolve_prefecture` が失敗するので、従来どおり400のままです。
```python
raw = payload.get("timezone")
if raw is None or (isinstance(raw, str) and not raw.strip()):
    raw = payload.get("tz_name")
if raw is not None and not (isinstance(raw, str) and not raw.strip()):
    ...  # 既存の型・ZoneInfo検証
```
もう一つの選択肢は、変更履歴に「空文字の timezone は国内でも400」と追記することです。

### D. offset を保存していない旧JST原本に、全件「未確認」の疑義注記が付く

`timezone_offset_hours` も `time_context` もない旧原本では、tz が `Asia/Tokyo` であっても `day_suspect=None` になり、注記が付きます。Asia/Tokyo のオフセットは常に正（+9 または +10）なので、これは誤警告です。誤った値を出すわけではないため、FAIL ではなく改善点として扱います。

**推奨する修正:** offset が不明な場合、tz_name と保存済みの出生時刻（`daiun.debug.birth_local` または raw）から `ZoneInfo` でオフセットを導出し、それもできないときだけ None にします。

## 3. 条件付きリスク（未提示コードに依存し、反例としては未確定）

1. **新しい 0.5.0 チャートへの誤った疑義 flag:** `engine_version` が `systems.shichusuimei.engine_version` 以外の場所にあると、新しいチャートもすべて旧原本と判定されます。その場合、LA などの新しいチャートに `base_day_pillar_suspect=True` が付きます。「0.5.0 の LA チャートで年レポートを作ると suspect が False になる」テストがありません。追加を推奨します。
2. **版文字列の解析:** `"0.5"` は `(0,5) < (0,5,0)` で旧原本と判定されます。`"0.5.0rc1"` は ValueError になり、やはり旧原本と判定されます。実際にこうした形式の版文字列を出力しているかによります。
3. **addon の照合が日柱だけ:** 0.5.0 で節入りの基準（`UTC_for_solar_terms`）が変わっている場合、節入り付近の旧原本では月柱や年柱が食い違っても addon が統合されてしまいます。年・月・日柱（exact の場合は時柱も）の照合を推奨します。
4. **features 形式の旧原本:** 年レポートは `shichu.features` 形式の旧原本を受け付けますが、addon は `_validate_addon_base_doc` で `normalized_data` を必須にしているため拒否します。安全側に失敗する問題（購入済みの addon が使えない）で、誤った値は出しません。
5. **出生時刻不明の旧原本での addon:** `reference.day_kanshi` が時刻不明の経路でも出力されるかは未提示です。出力されない場合、時刻不明の原本はすべて「照合できない」で拒否されます。統合テストは exact の fixture しか使っていません。
6. **フォームから渡る `birth_fold`:** select の値は `"0"` や `"1"` という文字列です。route が int に変換していなければ、`type(fold) is not int` で常に400になります。変換部が未提示です。
7. **旧原本の tz の既定値:** `tz_name` が欠落した旧原本の海外チャートでは、年レポートが Asia/Tokyo を使って立春の境界を計算します。これは既存の挙動で、今回の差分の範囲外です。
8. **大運の参照用表示が出力全体に及ばない:** `legacy_female_imputed` のとき、`interactions.natal_daiun` / `combined` と `five_elements.daiun` / `combined_reference` には参照用であることを示す印が付きません。status と flags だけで十分かは運用判断になります。

## 4. 公開条件（すべて満たすまで公開保留を推奨）

- 反例Aの三値化と、そのためのテスト修正
- 反例Bの bool 拒否
- 反例Cの実装修正、または変更履歴への追記
- 西洋とトランジットの 1.0 維持を、実際の `calc_western_api` / `calc_transit_api` を通して検証し、`systems.shichusuimei` が `None` または存在しないことも確認する
- 0.5.0 の負オフセットのチャートで `base_day_pillar_suspect=False` になるテスト
- 旧LA原本の addon が日柱不一致で拒否され、注文が未使用のまま残るテスト
- すべてのテストを実環境で実行し、結果を確認する（このレビューは実行していません）
- 既知の未解決事項として以下を引き続き公開しない: 外部販売ページ、外国語の告知、旧原本の救済・返金・再発行、Windows の1970年以前（Q06）

なお `birth_datetime.py` は aware な `astimezone(tz)` しか使っておらず、OS の timestamp には依存しないと読めます。このため、Q06 がこのファイルに及ばない可能性は高いと考えます。ただし推論のみで、Windows 上での実行確認はしていません。