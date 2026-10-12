# Opus 5.5最終保護差分の再確認
前回の実レビュー原文と、その後の対応差分を提示する。元の3件の新規計算判定は前回の固定ソースレビューを参照する。
今回は前回の指摘に対する保護の十分性を独立に確認し、追加の実在する反例だけを出す。
ツール無効。実行や外部照合をしたと主張しない。実モデルclaude-opus-5-5のみ。
変更: 旧原本の年レポートは保存日柱を変更せず、旧offset<=0/不明なら疑義flag。旧unknown->female大運はlegacy_female_imputedで参照用。
四柱/複合APIのみ1.1を識別し仕様変更を告知、西洋単独1.0維持。nullable timezoneと有効tz_nameのalias回帰保護。
旧addon日柱はnormalized/top-level/summaryの順に照合し、不足は拒否。旧offsetは保存値を引継ぐ。
foldは国内も指定可。日本1949重複時刻はresolverで確認。Windows負timestampの既存Q06は今回未修正として公開リスクに残す。
時干規則をtime_contextに明記。文字列のbooleanはエンジンでは拒否、UIはboolean、API day_boundaryは時間enumで別型である。
大運未確定の告知は日本語基本フォームと日本語addonフォームに明記。外部販売ページと外国語告知はこの修正で未確定、公開課題として残す。
呼出元をrgで確認: 運用上の直接呼出元はyaml_exporterのみ。API/admin/buyerはそこを通る。日運や相性の別エンジン呼出元は存在しない。scriptsは検証専用。
order使用済み登録は生成後に実行する既存順序。保存済み原本の自動修正はしない。
出力: 対応のPASS/FAIL/未検証、根拠と最小反例、残る公開条件。モデル単体でコード実行済みと言わない。

# 四柱推命 0.5.0 修正の独立再レビュー

**前提**: 今回ツールは使っていません。コードの実行や外部照合はしておらず、提示されたソースと差分を読み、手計算で確認した結果です。既存テストが合格していることは、計算が正しい根拠として扱っていません。節入りの時刻と日柱アンカーは、記憶だけでは確定させていません。

## 1. 対象

- 差分: `shichusuimei_calc.py`, `birth_datetime.py`, `api_calc.py`, `yaml_exporter.py`, `routes.py`, `shichusuimei_annual_report.py`, `shichu_chart.py`, `prompt_builder.py`, `redeem_shichu.html`
- 独立参照: fixture 生成スクリプト、代表行、NAOJ 2026 立春資料
- 対象外: 真太陽時、流派の変更。`routes.py` の `args` 構築部、`shichusuimei_year_selection`、他モジュールの呼出元は提示されていないため未確認です。

## 2. 独立に検証した式と条件

### 2.1 日柱の式 `(date.toordinal() + 14) % 60`(`shichusuimei_calc.py:469`)

- **アンカー**: 2000-01-01 の ordinal は `1999*365 + 499 - 19 + 4 + 1 = 730120` です。2000-01-07 は 730126、+14 で 730140 となり、60 で割り切れるので 0=甲子です。
- **JDN との一致**: JDN = ordinal + 1721425 です。1721474 ≡ 14 (mod 60) なので、JDN+49 ≡ ordinal+14 が恒等的に成り立ちます。docstring の主張は算術上正しいです。
- **アンカー自体の値**: 2000-01-07=甲子 は、記憶ではなく lunar_python の 4 日付と一致していることを根拠にしています。外部の暦表との突合せは未実施です。

### 2.2 旧式の誤りの再導出(P0 の原因確認)

出生地の UTC オフセットを f 時間とします。

- 現地 D 日 0:00 の JD は J = JDN(D) − 0.5 − f/24 です。
- 旧 idx = ⌊J + 50.5⌋ = ⌊JDN + 50 − f/24⌋ となります。
- 0 < f < 24 なら JDN+49 で正しく、新式と一致します。
- −24 < f ≤ 0 なら JDN+50 となり、+1 ずれます。
- 帰結:
  - 前回の P0「UTC offset≤0 で日柱+1」と一致します。
  - 同じ実効日であれば、日本(+9)の旧原本の日柱は新式でも変わりません。

### 2.3 手計算表(現地暦日 → 干支)

| ケース | 実効日 | idx | 日柱 | 時柱(五鼠遁) |
|---|---|---|---|---|
| UTC 2000-01-07 12:00(旧式) | 01-07 | 1 | 乙丑(誤り) | — |
| UTC/Pago Pago 2000-01-07 12:00(新式) | 01-07 | 0 | 甲子 | 甲午 |
| Kiritimati 2000-01-07 12:00(=01-06 22:00Z) | 01-07 | 0 | 甲子 | — |
| Pago Pago 2000-01-06 11:00(**同一瞬間**) | 01-06 | 59 | 癸亥 | — |
| 2024-02-29 23:30、23時切替 | 03-01 | 0 | 甲子 | 甲子 |
| 2024-02-29 00:30、1時切替 | 02-28 | 58 | 壬戌 | 庚子 |
| 2024-12-31 23:30、0時/1時切替 | 12-31 | 5 | 己巳 | 甲子 |
| 2024-12-31 23:30、23時切替 | 2025-01-01 | 6 | 庚午 | 丙子 |
| NY 2024-11-03 01:30、fold 0 / fold 1 | 11-03 | 7 | 辛未 | 己丑(両 fold 同一) |

確認できた条件は次のとおりです。

- **日付変更線**: Kiritimati と Pago Pago の同一瞬間でも、日柱は異なります(甲子 / 癸亥)。年柱・月柱は同一です。新仕様どおりの帰結です。
- **年末**: 23時切替では 2025-01-01 の日柱になりますが、年柱は立春基準なので 甲辰 [(2024−4)%60=40] のままです。月柱は「大雪〜小寒の間なら丙子」という条件付きで、節入り時刻は手計算では確定していません。
- **境界判定**: `hour < 1` と `hour >= 23` は分以下を見ないため、00:59→前日、01:00→当日、22:59→当日、23:00→翌日 で、境界の欠落も重複もありません(`:435-438`)。
- **DST**: 時計時刻で判定するため、重複時刻の fold は日柱・時柱に影響しません。影響するのは UTC、節入りまでの差、起運です。1時間差は起運換算で約5日分にあたります。
- **DST 判定**(`birth_datetime.py:29-36`): 往復変換で検出しています。fold=1 は非重複時刻では除外され、gap は両候補とも壁時計が一致しないため例外になります。Apia の 2011-12-30(24時間 gap)も同じ理屈で拒否されると読めます(実行はしていません)。
- **五鼠遁の表**(`:485-491`)と fixture の算術式 `idx%5*2+branch`: 甲→甲、乙→丙、丙→戊、丁→庚、戊→壬 で一致しました。
- **年柱と月柱の組合せ**: 己卯/丁丑、乙巳/己丑、丙午/庚寅 は、年干から月干を求める表(`:376-382`)と整合します。

### 2.4 独立参照の独立性と限界

| 項目 | 独立性 | 限界 |
|---|---|---|
| 日柱 | 本番コードを import しない lunar_python | 日付は 4 つのみ。境界の規則(`:34-36`)は仕様の再記述なので、検証できるのは仕様への適合だけで、流派の妥当性は検証していない |
| 時柱 | コードとしては別実装 | **方法は本番と同一**(実効日の日干から五鼠遁)。下記 M1 の差は原理的に検出できない |
| 年柱・月柱 | 同一瞬間を UTC+8 に変換して lunar_python で計算 | 「節入りから遠い」ことの余裕幅が記録されていない。Kiritimati/Sydney の 2000-01-07 未明は UTC では 01-06 で小寒に近い可能性があり、余裕幅は要記録 |
| オフセット | 手書きの値を zoneinfo と相互に照合 | DST 切替日は fixture に含まれていない |
| 立春 | NAOJ 資料(分単位で丸め)±2分 | 2026年の1回のみ |
| 再現性 | — | `sys.path` に `C:/Users/haser/...` が直書きされており(`script:12`)、CI では再生成できない |

## 3. 前回指摘の解決判定

### P0: UTC offset≤0 で日柱が+1 → **新規計算では解決**(条件付き)

UTC、Pago Pago、London、NY の各ケースで、手計算上 甲子 になります。

残る問題:

- 旧原本の救済範囲が経路によって不一致です(下記 P1-A)。
- 統合拒否のガードに抜けがあります(P2-A)。

### P1: 1時/23時の UI と実装の不一致 → **新規計算では解決**

- UI の選択値 false/true は、`resolve_day_boundary_hour` で 1/23 に変換されます(`calc:442-449`)。ヘルプ文と実装は一致しています。
- 旧原本の addon は、保存済みの実際の規則に従って作られます。旧 OFF→0、旧 ON→1 と正しく対応しています(`routes.py` 概算 7550-7559)。

残る問題:

- 旧 UI で「1時」を選んだ購入者は、実際には 0時の規則で計算されていました。保存された原本と本人の選択が食い違う事実は、仕様上も是正されません。影響対象(旧エンジン × 出生 00:xx/23:xx)の抽出を推奨します。
- `_truthy("1")` と API の `"1"` で意味が異なります(P2-E)。

### P1: unknown を女性で補完 → **エンジンでは解決**

- `_parse_gender` は unknown を unknown のまま保持し、`_calc_daiun` は status・空の items・direction None を返します(`calc:682-705, 982-990`)。
- 流年の natal_analysis は維持され、structural_analysis は大運に依存しません。
- 性別が確定している場合の順逆表(陽男陰女=順)は `:702-705` で変わっていません。

残る問題: P1-D(addon 商品)と P2-F(旧原本に入っている女性補完の大運)。

## 4. 追加指摘

### P0

なし。新規計算の正確性を直接壊す反例は、今回は見つけていません。

### P1

**P1-A: 旧原本で日柱誤りがあり得るものを、年報告が警告なしで使う**

- 箇所: `shichusuimei_annual_report.py:132-158`
- addon は日柱の不一致を拒否しますが、`build_annual_fortune_report` は `engine_version` もオフセットも見ずに、保存された日柱を日主として使います。
- 最小反例: 旧 0.4.0、America/Los_Angeles、2000-01-07 12:00 の原本。
  - 保存値は 乙丑(誤り)で、正しくは 甲子 です。
  - 年報告の十神・十二運・空亡は 乙 を日主として新たに出力されます。
- 修正案:
  - `base_engine_version < 0.5.0` かつ出生時オフセット ≤ 0 の場合は、`day_pillar_suspect: true` を付けるか生成を拒否します。
  - 原本自体は書き換えません。

**P1-B: API の既定値と意味の変更が、API_VERSION 据え置きのまま行われている**

- 箇所: `api_calc.py:12, 166-174`
- 変更内容:
  - 旧 `""`/false は 00:00 暦日でしたが、新では 01:00 になります。
  - 旧 `"true"/"23"/"on"` は「0時台を前日」でしたが、新では「23時台を翌日」になります。
- 最小反例(Asia/Tokyo):
  - day_boundary 未指定、2000-01-07 00:30: 旧 甲子 → 新 癸亥
  - `"true"`、00:30: 旧 癸亥 → 新 甲子
  - `"true"`、23:30: 旧 甲子 → 新 乙丑
- 修正案: 次のいずれかを選びます。
  - API_VERSION を上げ、変更履歴を出す
  - 旧の値を受けたときに `deprecated_day_boundary` の警告を返す

**P1-C(条件付き): 他の呼出元で位置引数 `day_change_at_23` の意味が変わっている**

- 箇所: `calc:452-457, 567-572`
- シグネチャは同じですが、True の意味が「0時台を前日」から「23時台を翌日」に変わりました。
- 相性診断や日運など、提示されていないモジュールが旧の意味で呼んでいると、結果が黙って変わります。また、naive な重複時刻を渡すと新たに例外になります。
- 呼出元の grep が必要です(未検証)。

**P1-D(条件付き): 性別未指定の購入者が大運・流年 addon を買うと、大運が空になる**

- 箇所: `yaml_exporter.py:1090-1222`、`routes` の args 構築部(提示なし)
- 商品の中核である大運が空になるため、購入前の告知、性別入力の必須化、返金導線のいずれかが必要です。
- 旧原本の addon で、`args["gender"]` を `doc.input.gender`(未指定)から取るのか、`shichu.input.raw.gender`(旧エンジンの female)から取るのかが不明です。
  - 前者の場合、原本にある女性補完の大運と矛盾します。
  - 後者の場合、新方針(女性で補完しない)に反します。

### P2

**P2-A: 統合拒否ガードの抜け**

- 箇所: `routes.py` 概算 7565-7568
- `normalized_data.pillars.day` がない旧形式(トップレベルの `pillars.day` が文字列のもの)では、`original_day` が `{}` になって偽と評価され、比較そのものが飛ばされます。
- 修正案: `shichu["pillars"]["day"]` と `summary.day_kanshi` にフォールバックし、どちらも取れなければ拒否します。

**P2-B: 日本の 1948–1951 年の夏時間**

- 箇所: `routes.py` 概算 5585、テンプレートの fold 欄が海外のみ
- 国内の購入者には fold の UI がないため、重複時刻は解決できない例外になり、エラー文も「birth_fold を指定」と出ます。存在しない時刻も同様に拒否されます。
- 候補反例(要確認): Asia/Tokyo 1949-09-11 00:30
  - tzdata の Japan 規則「Sep Sat>=8 25:00」は記憶に基づくので、zoneinfo で確認してください。
- 修正案: 国内でも過去の DST を検出したときだけ fold 欄を表示します。
- 未検証: 注文番号が計算例外の前に消費されないかどうか。

**P2-C: 旧原本の addon で `time_context` がない場合**

- 箇所: `routes.py` 概算 7560-7563
- 旧エンジンは暗黙に fold=0 で計算していましたが、addon は fold を渡さないため、重複時刻の出生は失敗します。
- 修正案: `doc.input.timezone_offset_hours`(旧エンジンが fold=0 で記録した値)を `birth_utc_offset_hours` に使います。存在しない時刻は明示的なメッセージで拒否します。

**P2-D: 子刻の時干規則が出力に明示されていない**

- 箇所: `calc:473-498, 1536-1544`
- 詳細は §5 の M1。
- 修正案: `time_context.hour_stem_rule = "five_rat_from_effective_day_stem"` を追加します。

**P2-E: 内部フォームの "1" の解釈が API と矛盾**

- 箇所: `routes.py:1659`
- `_truthy` は `"1"` を 23時 と解釈しますが、API の `"1"` は 01:00 です。管理画面のフォームが `"1"` を送ると 23時切替になります。
- 修正案: フォームの値を `"01:00"/"23:00"` に統一します。

**P2-F: 旧原本の unknown 補完大運が、新しい年報告で確定値として出る**

- 箇所: `annual_report.py:99-129`
- `input.gender ∈ {unknown, "", default}` かつ `raw.gender == female` の場合は、`status: legacy_female_imputed` を付けることを推奨します。原本は書き換えません。

### P3

- **立春前後1秒の不整合(既存)**: `calc:544-553`。年は二分探索の結果、月は瞬間の黄経で判定するため、立春の±1秒以内では年月の組合せが矛盾し得ます。例えば 丙午年で月 index 11 なら 辛丑 という誤った組合せになります。
- **到達不能な分岐の KeyError**: `calc:1014-1021`。`m_idx<0` の分岐は `status` を返さないため、`:1605` で KeyError になります。実際には到達しません。
- **SVG の大運表示(既存)**: `shichu_chart.py:244`。`item["start_age"]` というキーは存在しないため、「歳 庚辰」のように年齢が空で表示されます。
- **timezone の明示 null**: `api_calc.py:151`。`"timezone": null` を明示すると、`tz_name` が無視されます。
- **真偽値の緩い判定**: `resolve_day_boundary_hour` は `day_change_at_23` が文字列 `"false"` でも真として扱います(`calc:443-444`)。
- **fixture の記録不足**: 節入りまでの余裕幅が記録されておらず、生成スクリプトのパスが直書きです。

## 5. 方式差(バグではないが、明示が必要)

**M1. 子刻の時干**

- 実装は、実効日の日干から五鼠遁で時干を求めます。
- 0時切替の 23:30(甲子日)は 甲子時になります。夜子時流の 丙子 とは異なり、同じ暦日に 甲子時が2回現れます。
- 1時切替の 00:59(実効日 癸亥)は 壬子 です。直前の 癸亥時から連続する六十干支の時刻なら 甲子 になるはずで、01:00 の 乙丑 とも不連続です。
- 23時切替だけが連続になります。fixture は同じ方法で作られているため、この差は検出できません。

**M2. 現地暦日による日柱**

日付変更線をまたぐ同一瞬間で日柱が異なり、Apia の 2011-12-30 のように欠けた暦日が生じます。新仕様どおりの帰結です。

**M3. DST 重複時刻**

fold は日柱・時柱に影響せず、UTC と起運だけが変わります。

**M4. 1時切替の位置づけ**

1時切替(0時台を前日扱い)は製品仕様です。外部の流派との一致は今回は検証していません。

## 6. 未検証

- すべてのコード実行。テストの成否も、私自身は確認していません。
- 外部暦表との日柱照合、小寒/大雪/立春の厳密な時刻、lunar_python の EightChar の年が立春で厳密に切り替わるかどうか。
- tzdata の Japan 1948–51 規則と Apia の挙動(記憶と推論のみ)。
- `routes` の args 構築部、`year_selection`、他の呼出元(P1-C)、注文番号を消費するタイミング、`resolve_prefecture` が受け付ける表記の範囲。

## 7. 公開判断

**現状のままでは公開を保留します。** エンジンの新規計算(P0 と P1×2)は、手計算上は解決しています。公開の前に、次を対応または確認してください。

1. **P1-A**: 年報告で旧原本の日柱が疑わしい場合のフラグ付けか拒否。
2. **P1-B**: API のバージョンを上げるか、互換性の告知を出す。
3. **P1-C**: grep で他の呼出元を確認。
4. **P1-D**: 性別未指定での addon 販売の扱いを決める。
5. 実環境での実行確認: テスト全件に加え、§2.3 の 9 ケースと、Asia/Tokyo 1949-09 の DST 確認。

P2 は公開直後の修正でも許容範囲です。ただし P2-A は統合拒否の仕様そのものの穴なので、P1 と同時に直すことを推奨します。

## 前回からの差分 services/shichusuimei_calc.py
```diff
--- round1/services/shichusuimei_calc.py
+++ final/services/shichusuimei_calc.py
@@ -440,6 +440,8 @@
 
 
 def resolve_day_boundary_hour(day_change_at_23: bool = False, day_boundary_hour: int | None = None) -> int:
+    if type(day_change_at_23) is not bool:
+        raise ValueError("day_change_at_23 must be a boolean; use day_boundary_hour for 0, 1 or 23")
     if day_boundary_hour is None:
         return 23 if day_change_at_23 else 1
     if type(day_boundary_hour) is not int or day_boundary_hour not in (0, 1, 23):
@@ -1540,6 +1542,7 @@
         "day_pillar_reference_datetime": dt.isoformat(), "day_pillar_date": effective_date.isoformat(),
         "day_boundary_hour": boundary, "day_boundary_rule": boundary_label,
         "calendar_time_basis": "local_civil_time", "true_solar_time_applied": False,
+        "hour_stem_rule": "five_rat_from_effective_day_stem",
         "astronomical_time_basis": "UTC_for_solar_terms",
     }
     p4 = pillars4(dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
@@ -1745,4 +1748,4 @@
             "day_kanshi": p4.day,
             "hour_kanshi": p4.hour,
         },
-    }+    }

```


## 前回からの差分 services/api_calc.py
```diff
--- round1/services/api_calc.py
+++ final/services/api_calc.py
@@ -10,6 +10,7 @@
 from services.birth_datetime import BirthDatetimeError
 
 API_VERSION = "1.0"
+SHICHU_API_VERSION = "1.1"
 ENGINE_NAME = "nanami-products"
 
 
@@ -74,7 +75,7 @@
 
     response_doc = {
         "meta": {
-            "api_version": API_VERSION,
+            "api_version": SHICHU_API_VERSION if raw_shichu is not None else API_VERSION,
             "engine": ENGINE_NAME,
             "endpoint": endpoint,
         },
@@ -148,7 +149,9 @@
 
 
 def _normalize_shichu_timezone(payload: dict[str, Any]) -> str:
-    raw = payload.get("timezone", payload.get("tz_name"))
+    raw = payload.get("timezone")
+    if raw is None:
+        raw = payload.get("tz_name")
     if raw is not None:
         if not str(raw).strip():
             raise ApiCalcError("INVALID_TIMEZONE", "an IANA birth timezone is required", 400)
@@ -428,4 +431,4 @@
     except ApiCalcError as exc:
         return _error(exc.code, exc.message, status_code=exc.status_code)
     except Exception as exc:
-        return _error("INTERNAL_ERROR", str(exc), status_code=500)+        return _error("INTERNAL_ERROR", str(exc), status_code=500)

```


## 前回からの差分 services/shichusuimei_annual_report.py
```diff
--- round1/services/shichusuimei_annual_report.py
+++ final/services/shichusuimei_annual_report.py
@@ -138,6 +138,26 @@
         raise ValueError("四柱推命の基礎命式が含まれていません。")
     assumptions = (shichu.get("input") or {}).get("assumptions") or {}
     base_input = base_doc.get("input") or {}
+    base_version = str(shichu.get("engine_version") or "")
+    try:
+        legacy = tuple(int(n) for n in base_version.split(".")) < (0, 5, 0)
+    except ValueError:
+        legacy = True
+    offset = base_input.get("timezone_offset_hours")
+    if offset is None:
+        offset = ((shichu.get("input") or {}).get("time_context") or {}).get("utc_offset_hours")
+    try:
+        day_suspect = float(offset) <= 0 if offset is not None else None
+    except (TypeError, ValueError):
+        day_suspect = None
+    day_suspect = day_suspect if legacy else False
+    raw_gender = ((shichu.get("input") or {}).get("raw") or {}).get("gender")
+    legacy_imputed = legacy and core._parse_gender(base_input.get("gender")) == "unknown" and raw_gender == "female"
+    legacy_notes = []
+    if legacy and day_suspect is not False:
+        legacy_notes.append("旧計算の原本です。出生時UTCオフセットが0以下または未確認のため、日柱に旧不具合の疑義があります。原本の保存値を参照しており、再計算・修正済みの命式ではありません。")
+    if legacy_imputed:
+        legacy_notes.append("旧原本の性別未指定が女性に補完されています。保存済み大運は参照用で、順逆の確定結果として扱わないでください。")
     tz_name = assumptions.get("tz_name") or base_input.get("timezone") or "Asia/Tokyo"
     tz = ZoneInfo(tz_name)
     accuracy = assumptions.get("birth_time_accuracy") or base_input.get("birth_time_accuracy")
@@ -197,6 +217,9 @@
                         "year_boundary_rule": "lichun(315deg)", "daiun_calc_mode": "approx_days_to_years",
                         "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
                         "timezone": tz_name, "supported_years": {"min": MIN_YEAR, "max": MAX_YEAR},
+                        "base_day_pillar_suspect": day_suspect,
+                        "legacy_female_imputed": legacy_imputed,
+                        "legacy_reference_notes": legacy_notes,
                         "natal_time_basis": "four_pillars" if reliable else "three_pillars_hour_excluded"},
         "base_chart_usage": {"full_yaml_required": True,
                              "note": "同じbase_chart_idのFull YAMLと併用。出生四柱は照合用。格局・用神などは基礎命式を参照。"},
@@ -205,7 +228,7 @@
                    "period_start": start.isoformat(), "period_end": end.isoformat(), "period_end_exclusive": True,
                    "ten_god_to_day_master": core.ten_god(day_master, annual["stem"]),
                    "twelve_fortune_to_day_master": core.twelve_fortune(day_master, annual["branch"])},
-        "daiun": {"status": "undetermined_gender" if direction_unknown else "overlapping_periods" if contexts else "before_first_daiun",
+        "daiun": {"status": "undetermined_gender" if direction_unknown else "legacy_female_imputed" if legacy_imputed else "overlapping_periods" if contexts else "before_first_daiun",
                   "contexts": contexts, "boundary_in_selected_year": any(c["boundary_in_selected_year"] for c in contexts),
                   "uncovered_before_first_daiun": {"start": start.isoformat(), "end": min(first, end).isoformat()}
                       if first is not None and start < first else None,
@@ -221,9 +244,11 @@
                           "method": "existing_visible_stem_plus_branch_and_additive_hidden_stem_counts",
                           "note": "合算は参考個数。強弱・吉凶・合化の成立を示さない。時刻不明・推定の場合、合算から時柱を除外。"},
         "interpretation_flags": {"calculation_only": True, "automatic_good_bad_judgment": False,
+                                 "daiun_direction_confirmed": not direction_unknown and not legacy_imputed,
+                                 "natal_day_pillar_verified_by_this_report": False,
                                  "automatic_element_transformation": False},
     }}
 
 
 def build_annual_fortune_yaml(base_doc: dict, selected_year: int) -> str:
-    return yaml.safe_dump(build_annual_fortune_report(base_doc, selected_year), allow_unicode=True, sort_keys=False, width=120)+    return yaml.safe_dump(build_annual_fortune_report(base_doc, selected_year), allow_unicode=True, sort_keys=False, width=120)

```


## 前回からの差分 tests/test_shichusuimei_overseas_engine.py
```diff
--- round1/tests/test_shichusuimei_overseas_engine.py
+++ final/tests/test_shichusuimei_overseas_engine.py
@@ -115,6 +115,7 @@
 def test_time_context_rule_and_api_output_agree(boundary):
     response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="23:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone="America/Los_Angeles",gender="female",day_boundary=f"{boundary:02}:00"))
     assert status==200
+    assert response["meta"]["api_version"]=="1.1"
     # Find the actual raw module rather than relying on API envelope naming.
     text=json.dumps(response,ensure_ascii=False)
     assert '"engine_version": "0.5.0"' in text
@@ -214,4 +215,63 @@
         assert build_year_selection(original,{"mode":"complete"})["yaml_text"]==original
         selected=yaml.safe_load(build_year_selection(original,{"mode":"selected","years":[year]})["yaml_text"])
     assert selected["common"]["systems"]["shichusuimei"]["normalized_data"]["daiun"]==doc["systems"]["shichusuimei"]["normalized_data"]["daiun"]
-    assert path.read_text(encoding="utf-8")==original+    assert path.read_text(encoding="utf-8")==original
+
+
+@pytest.mark.parametrize("flag",["false","true"])
+def test_engine_boolean_is_not_an_hour_or_truthy_string(flag):
+    with pytest.raises(ValueError):
+        core.day_kanshi_from_birth(datetime(2000,1,7,12),day_change_at_23=flag)
+
+
+def test_api_timezone_null_preserves_explicit_alias():
+    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone=None,tz_name="America/Los_Angeles"))
+    assert status==200 and response["raw_data"]["shichu"]["input"]["time_context"]["timezone"]=="America/Los_Angeles"
+
+
+@pytest.mark.parametrize("offset",[-8,None])
+def test_legacy_annual_report_flags_suspect_day_and_imputed_gender_without_changing_original(offset):
+    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
+    doc["input"]["gender"]="unknown"
+    doc["input"]["timezone_offset_hours"]=offset
+    doc["systems"]["shichusuimei"]["input"]["raw"]["gender"]="female"
+    snapshot=deepcopy(doc)
+    result=build_annual_fortune_report(doc,2028)["annual_fortune_report"]
+    assert result["calculation"]["base_day_pillar_suspect"] is (True if offset is not None else None)
+    assert result["calculation"]["legacy_female_imputed"] is True
+    assert result["daiun"]["status"]=="legacy_female_imputed"
+    assert result["interpretation_flags"]["daiun_direction_confirmed"] is False
+    assert result["natal_reference"]["pillars"]["day"]==doc["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]
+    assert doc==snapshot
+
+
+@pytest.mark.parametrize("kind",["top_level","summary","missing"])
+def test_legacy_addon_alternative_day_locations_and_saved_offset(monkeypatch,kind):
+    import routes
+    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
+    shichu=doc["systems"]["shichusuimei"]
+    day=shichu["normalized_data"]["pillars"].pop("day")["kanshi"]
+    shichu.pop("pillars",None)
+    shichu.pop("summary",None)
+    if kind=="top_level":shichu["pillars"]={"day":day}
+    if kind=="summary":shichu["summary"]={"day_kanshi":day}
+    snapshot=deepcopy(doc)
+    def fake(**args):
+        assert args["birth_utc_offset_hours"]==9.0
+        return "fictional","",{"systems":{"shichusuimei":{"reference":{"day_kanshi":day}}}}
+    monkeypatch.setattr(routes,"build_shichu_fortune_cycles_addon_yaml",fake)
+    if kind=="missing":
+        with pytest.raises(ValueError,match="照合できない"):routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon")
+    else:assert routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon")=="fictional"
+    assert doc==snapshot
+
+
+def test_japan_historic_dst_and_hour_stem_rule_are_explicit():
+    wall=datetime(1949,9,11,0,30)
+    with pytest.raises(BirthDatetimeError,match="重複"):resolve_birth_datetime(wall,"Asia/Tokyo")
+    a=resolve_birth_datetime(wall,"Asia/Tokyo",fold=0)
+    b=resolve_birth_datetime(wall,"Asia/Tokyo",fold=1)
+    assert a.utcoffset()==timedelta(hours=10) and b.utcoffset()==timedelta(hours=9)
+    assert b.astimezone(timezone.utc)-a.astimezone(timezone.utc)==timedelta(hours=1)
+    result=core.calc_shichusuimei_from_payload(PAYLOAD,as_of=NOW)
+    assert result["input"]["time_context"]["hour_stem_rule"]=="five_rat_from_effective_day_stem"

```


## routes：旧原本の引数と検証・生成
def _addon_args_from_base_doc(doc: dict, lang: str = "ja") -> dict[str, object]:
    input_block = doc.get("input") or {}
    if not isinstance(input_block, dict):
        raise ValueError(redeem_error(lang, "addon_yaml_input_invalid"))

    birth_date = str(input_block.get("birth_date") or "").strip()
    if not birth_date:
        raise ValueError(redeem_error(lang, "addon_yaml_birth_date_missing"))

    calculation_time = str(input_block.get("calculation_time") or "").strip()
    birth_time_value = input_block.get("birth_time")
    birth_time = calculation_time or (str(birth_time_value).strip() if birth_time_value else None)
    if birth_time in {"unknown", "approximate", "morning", "afternoon", "night"}:
        birth_time = calculation_time or None

    birth_place = str(input_block.get("birth_place") or input_block.get("prefecture") or "").strip()
    lat = _float_or_none(input_block.get("birth_lat"))
    lng = _float_or_none(input_block.get("birth_lng"))
    prefecture = str(input_block.get("prefecture") or "").strip()
    birth_place_kind = str(input_block.get("birth_place_kind") or "").strip()
    if birth_place_kind == "overseas":
        prefecture = ""
    if not prefecture and (lat is None or lng is None):
        raise ValueError(redeem_error(lang, "addon_yaml_coordinates_missing"))

    birth_time_block = doc.get("birth_time") or {}
    if not isinstance(birth_time_block, dict):
        birth_time_block = {}

    return {
        "title": input_block.get("title"),
        "birth_date": birth_date,
        "birth_time": birth_time,
        "prefecture": prefecture,
        "birth_place_label": birth_place or None,
        "birth_lat": lat,
        "birth_lng": lng,
        "tz_name": str(input_block.get("timezone") or "Asia/Tokyo"),
        "gender": str(input_block.get("gender") or "unknown"),
        "birth_time_accuracy": str(input_block.get("birth_time_accuracy") or birth_time_block.get("accuracy") or "auto"),
        "birth_time_range": input_block.get("birth_time_range") if isinstance(input_block.get("birth_time_range"), dict) else None,
        "birth_time_note": str(input_block.get("birth_time_note") or birth_time_block.get("note") or "") or None,
    }


def _validate_addon_base_doc(doc: dict, addon_type: str, lang: str = "ja") -> None:
    systems = doc.get("systems") or {}
    if not isinstance(systems, dict):
        raise ValueError(redeem_error(lang, "addon_yaml_systems_invalid"))
    western = systems.get("western") or {}
    shichu = systems.get("shichusuimei") or {}

    if addon_type in {"western_asteroids_addon", "western_31days_transit_addon", "western_long_term_transits_addon"}:
        if not isinstance(western, dict) or not isinstance(western.get("natal"), dict):
            raise ValueError(redeem_error(lang, "addon_yaml_western_required"))
        return

    if addon_type == "shichu_fortune_cycles_addon":
        if not isinstance(shichu, dict) or not isinstance(shichu.get("normalized_data"), dict):
            raise ValueError(redeem_error(lang, "addon_yaml_shichu_required"))
        return

    raise ValueError(redeem_error(lang, "addon_unsupported"))


def _build_addon_yaml_from_base(
    doc: dict,
    addon_type: str,
    *,
    transit_start_date: datetime | None = None,
    lang: str = "ja",
) -> str:
    _validate_addon_base_doc(doc, addon_type, lang)
    args = _addon_args_from_base_doc(doc, lang)
    if addon_type == "western_asteroids_addon":
        yaml_text, _prompt_text, _addon_doc = build_asteroid_addon_yaml(**args)
        return yaml_text
    if addon_type == "western_31days_transit_addon":
        yaml_text, _prompt_text, _addon_doc = build_31days_transit_addon_yaml(
            **args,
            transit_start_date=transit_start_date,
        )
        return yaml_text

    shichu = ((doc.get("systems") or {}).get("shichusuimei") or {})
    assumptions = ((shichu.get("input") or {}).get("assumptions") or {})
    # Respect the actual rule saved by the old engine, not the old UI label.
    # This creates a separate add-on; never migrates the purchased base chart.
    if "day_boundary_hour" in assumptions:
        boundary = assumptions["day_boundary_hour"]
    elif assumptions.get("day_boundary_rule") == "00:00切替":
        boundary = 0
    elif "子刻後半" in str(assumptions.get("day_boundary_rule") or ""):
        boundary = 1
    else:
        boundary = 1 if assumptions.get("day_change_at_23") else 0
    args["day_boundary_hour"] = boundary
    args["day_change_at_23"] = boundary == 23
    context = (shichu.get("input") or {}).get("time_context") or {}
    if context:
        args["birth_fold"] = context.get("fold")
        args["birth_utc_offset_hours"] = context.get("utc_offset_hours")
    elif (doc.get("input") or {}).get("timezone_offset_hours") is not None:
        args["birth_utc_offset_hours"] = doc["input"]["timezone_offset_hours"]
    yaml_text, _prompt_text, _addon_doc = build_shichu_fortune_cycles_addon_yaml(**args)
    original_day = ((shichu.get("normalized_data") or {}).get("pillars") or {}).get("day") or {}
    original_day = original_day.get("kanshi") if isinstance(original_day, dict) else original_day
    if not original_day:
        original_day = (shichu.get("pillars") or {}).get("day") or (shichu.get("summary") or {}).get("day_kanshi")
        original_day = original_day.get("kanshi") if isinstance(original_day, dict) else original_day
    new_day = (((_addon_doc.get("systems") or {}).get("shichusuimei") or {}).get("reference") or {}).get("day_kanshi")
    if not original_day or not new_day:
        raise ValueError("保存済み命式の日柱を照合できないため、追加データを統合できません。完全原本はそのまま保存してください。")
    if original_day != new_day:
        raise ValueError("保存済み命式の日柱と修正後の計算が異なるため、追加データを統合できません。完全原本はそのまま保存してください。")
    return yaml_text




## 生成成功後の注文使用登録
            )
            return RedirectResponse(_chart_redirect_url(token, lang=lang), status_code=303)
        if not base_yaml.strip():
            return _addon_form_response(
                request, form=form, error=redeem_error(lang, "addon_yaml_required"), status_code=400
            )
        doc = _load_addon_base_yaml(base_yaml, lang)
        result_yaml = _build_addon_yaml_from_base(doc, addon_type, lang=lang)
        _redeem_addon_order_or_raise(
            order_code_for_redeem,
            order_provider_for_redeem,
            addon_type,
            lang=lang,
        )
    except Exception as exc:
        return _addon_form_response(request, form=form, error=str(exc), status_code=400)
    return _addon_form_response(request, form=form, result_yaml=result_yaml)


def _load_transit_addon_link(token: str) -> tuple[dict | None, bool]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token):
        raise HTTPException(status_code=404, detail="transit addon not found")
    link = pg_store.get_transit_addon_link(token)
    if not link:
        raise HTTPException(status_code=404, detail="transit addon not found")

## 日本語addon告知
        <a href="{{ lang_urls.en }}" class="{% if lang == 'en' %}is-active{% endif %}">{{ t.lang_en }}</a>
        <a href="{{ lang_urls.es }}" class="{% if lang == 'es' %}is-active{% endif %}">{{ t.lang_es }}</a>
        <a href="{{ lang_urls.de }}" class="{% if lang == 'de' %}is-active{% endif %}">{{ t.lang_de }}</a>
      </div>
      <h1>{{ t.addon_title }}</h1>
      <p class="lead">{{ t.addon_lead }}</p>
      {% if lang == 'ja' %}
      <p class="note">四柱推命の大運・流年追加：基本命式の性別が「指定なし」の場合、大運・起運は未確定です。原局と流年のみを計算します。大運が必要な場合は、性別が指定された基本命式を使用してください。旧原本の女性補完を確定値として引き継ぎません。</p>
      {% endif %}
      <section class="notice-box">
        <h2>{{ t.addon_usage_title }}</h2>
        <ul class="plain-list">
          {# 1行目は注文番号の案内なので購入元で出し分ける。2行目以降は共通。 #}

## API変更履歴
# nanami-products 計算結果API 仕様書（四柱・複合 v1.1／西洋・トランジット v1.0）

## 2026-10-11 四柱API v1.1の変更

`shichu`・`combined`の`meta.api_version`は1.1。四柱エンジンは0.5.0。省略／falseの日替わりは1時、true／23は23時に統一したため、0時台・23時台では旧APIの実計算と結果が変わる。明示的な0時方式は`day_boundary: "00:00"`を使用する。旧保存YAMLや購入IDを読み替えない。西洋・トランジット単独のAPI版は1.0を維持する。

## 概要

`nanami-products` に追加された計算結果APIの運用仕様です。