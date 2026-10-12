# 四柱推命0.5.0 修正の独立再レビュー
実モデルはclaude-opus-5-5のみ。別モデルに切替えない。
この固定ソースと修正前差分をレビューし、既存テスト合格を計算正確性の根拠にしない。
前回P0=UTC offset<=0の日柱+1、P1=1時/23時のUIと実装不一致、P1=unknownの女性補完。
新仕様は現地時計時刻: 1時(標準)は0時台前日、23時は23時台翌日、0時は明示指定のみ暦日。
年/月柱はUTC天文時刻、日/時柱は現地暦日/時計時刻。真太陽時と流派変更は対象外。
UTC±、DST重複/不存在、日付変更線、子刻、年末を独立した式・表・手計算で検証し、反例を具体化する。
unknownは大運未確定(items空)、命式・原局×流年は保持。確定性別の全大運・構造分析の互換性も確認。
旧保存原本は再計算・書換えない。旧booleanの実規則でaddonを作る。日柱が変わる旧海外原本は統合拒否。
日柱アンカーや節気を記憶のみで確定しない。渡された独立参照手法の独立性と限界を批判的に確認する。
模擬でコード実行/外部照合したと書かない。今回ツールは無効。未検証を明記。
出力: 対象、独立検証した式/条件、各P0/P1の解決判定、追加P0-P3、根拠・行・最小反例、方式差、未検証、公開判断。
ローカルのみ。DB・顧客資料・認証キーは渡していない。修正案のみでソース編集はしない。


## 修正前からの差分 services/shichusuimei_calc.py
```diff
--- before/services/shichusuimei_calc.py
+++ after/services/shichusuimei_calc.py
@@ -24,6 +24,9 @@
 import os
 from zoneinfo import ZoneInfo
 from typing import Any
+from services.birth_datetime import resolve_birth_datetime
+
+ENGINE_VERSION = "0.5.0"
 
 from pathlib import Path
 import swisseph as swe
@@ -420,59 +423,50 @@
     local_dt: datetime,
     *,
     day_change_at_23: bool,
+    day_boundary_hour: int | None = None,
 ) -> tuple[datetime.date, str]:
-    """日柱判定に使うローカル日付を返す。
-
-    現在のWeb UI上のオプションは、利用者の期待値に合わせて
-    「子刻後半（00:00-00:59）を前日扱いにする」挙動に寄せる。
-
-    - OFF: 暦日どおり（00:00切替）
-    - ON : 00:00-00:59 は前日の日柱を使う
-
-    これにより 1975-09-15 00:02 は
-    - OFF -> 1975-09-15 扱い（甲子）
-    - ON  -> 1975-09-14 扱い（癸亥）
-    となる。
+    """Civil-calendar modes: 01:00 standard, 23:00 next day, explicit 00:00.
+
+    The boolean is a new-calculation UI adapter, never an old-YAML migration.
+    Version <=0.4.0 had different boolean behavior; stored results stay intact.
     """
+    boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
     local_date = local_dt.date()
-    rule_label = "00:00切替"
-
-    if day_change_at_23 and local_dt.hour == 0:
-        local_date = (datetime(local_date.year, local_date.month, local_date.day) - timedelta(days=1)).date()
-        rule_label = "子刻後半(00:00-00:59)を前日扱い"
-    elif day_change_at_23:
-        rule_label = "子刻考慮ON"
-
-    return local_date, rule_label
+    if boundary == 1 and local_dt.hour < 1:
+        local_date -= timedelta(days=1)
+    elif boundary == 23 and local_dt.hour >= 23:
+        local_date += timedelta(days=1)
+    return local_date, f"{boundary:02d}:00切替"
+
+
+def resolve_day_boundary_hour(day_change_at_23: bool = False, day_boundary_hour: int | None = None) -> int:
+    if day_boundary_hour is None:
+        return 23 if day_change_at_23 else 1
+    if type(day_boundary_hour) is not int or day_boundary_hour not in (0, 1, 23):
+        raise ValueError("day_boundary_hour must be 0, 1 or 23")
+    if day_change_at_23 and day_boundary_hour != 23:
+        raise ValueError("day_change_at_23 conflicts with day_boundary_hour")
+    return day_boundary_hour
 
 
 def day_kanshi_from_birth(
     birth_dt: datetime,
     tz_name: str = "Asia/Tokyo",
     day_change_at_23: bool = False,
+    *, day_boundary_hour: int | None = None,
 ) -> str:
-    """日干支（四柱推命NEXT式）
-
-    int((J + 0.5 + 50) % 60)
-    ここで J は「日柱判定に使う日の0:00(ローカル)をUTCに直したJD」を使う。
+    """Sexagenary day of the selected LOCAL civil date; UTC is not used.
+
+    Gregorian ordinal +14 == Gregorian noon JDN +49 (0 = 甲子).
+    Anchor: 2000-01-07 = 甲子. Astronomy continues to use UTC independently.
     """
-    tz = ZoneInfo(tz_name)
-    if birth_dt.tzinfo is None:
-        # 入力がnaiveなら tz を付与（ローカル入力想定）
-        local_dt = birth_dt.replace(tzinfo=tz)
-    else:
-        local_dt = birth_dt.astimezone(tz)
-
+    local_dt = resolve_birth_datetime(birth_dt, tz_name)
     local_date, _rule_label = _effective_local_date_for_day_pillar(
         local_dt,
         day_change_at_23=day_change_at_23,
+        day_boundary_hour=day_boundary_hour,
     )
-
-    local_midnight = datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0, tzinfo=tz)
-    utc_midnight = local_midnight.astimezone(timezone.utc)
-    J = julian_day(utc_midnight)
-
-    idx = int((J + 0.5 + 50) % 60)
+    idx = (local_date.toordinal() + 14) % 60
     return KANSHI_60[idx]
 
 
@@ -482,8 +476,7 @@
     tz_name: str = "Asia/Tokyo",
 ) -> str:
     """日干とローカル時刻から時柱（時干支）を算出。"""
-    tz = ZoneInfo(tz_name)
-    local_dt = birth_dt.replace(tzinfo=tz) if birth_dt.tzinfo is None else birth_dt.astimezone(tz)
+    local_dt = resolve_birth_datetime(birth_dt, tz_name)
 
     b_idx = _time_branch_index(local_dt)
     branch = BRANCHES[b_idx]
@@ -523,8 +516,9 @@
     birth_dt: datetime,
     tz_name: str = "Asia/Tokyo",
     day_change_at_23: bool = False,
+    *, day_boundary_hour: int | None = None,
 ) -> Pillars:
-    day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23)
+    day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=day_boundary_hour)
     day_stem = day[0]
     hour = hour_kanshi_from_day_stem_and_time(day_stem, birth_dt, tz_name=tz_name)
     return Pillars(day=day, hour=hour)
@@ -540,7 +534,7 @@
     debug には立春時刻や太陽黄経などの内部情報を入れる。
     """
     tz = ZoneInfo(tz_name)
-    local_dt = birth_dt.replace(tzinfo=tz) if birth_dt.tzinfo is None else birth_dt.astimezone(tz)
+    local_dt = resolve_birth_datetime(birth_dt, tz_name)
     utc_dt = local_dt.astimezone(timezone.utc)
 
     if swe is None:
@@ -574,10 +568,11 @@
     birth_dt: datetime,
     tz_name: str = "Asia/Tokyo",
     day_change_at_23: bool = False,
+    *, day_boundary_hour: int | None = None,
 ) -> Pillars4:
     """四柱（年/月/日/時）をまとめて算出。"""
     y, m, _dbg = year_month_pillars(birth_dt, tz_name=tz_name)
-    day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23)
+    day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=day_boundary_hour)
     hour = hour_kanshi_from_day_stem_and_time(day[0], birth_dt, tz_name=tz_name)
     return Pillars4(year=y, month=m, day=day, hour=hour)
 
@@ -685,13 +680,13 @@
 
 
 def _parse_gender(payload_gender: Any) -> str:
-    """性別表記を male / female に正規化する。未指定時は female。"""
+    """Keep unrecognized/unspecified gender unknown; never choose a direction."""
     g = (str(payload_gender) if payload_gender is not None else "").strip().lower()
     if g in ("male", "m", "man", "男性", "男"):
         return "male"
-    if g in ("female", "f", "woman", "女性", "女", "default"):
+    if g in ("female", "f", "woman", "女性", "女"):
         return "female"
-    return "female"
+    return "unknown"
 
 
 def _is_yang_stem(stem: str) -> bool:
@@ -699,8 +694,11 @@
     return stem in ("甲", "丙", "戊", "庚", "壬")
 
 
-def _daiun_direction_from_year_stem(year_stem: str, gender: str) -> str:
+def _daiun_direction_from_year_stem(year_stem: str, gender: str) -> str | None:
     """年干陰陽 × 出生時の性別で大運方向を返す。"""
+    gender = _parse_gender(gender)
+    if gender == "unknown":
+        return None
     is_yang = _is_yang_stem(year_stem)
     if is_yang:
         return "forward" if gender == "male" else "reverse"
@@ -981,6 +979,15 @@
     gender_norm = _parse_gender(gender)
     year_stem = p4.year[0]
     direction = _daiun_direction_from_year_stem(year_stem, gender_norm)
+    if direction is None:
+        return {
+            "status": "undetermined_gender", "direction": None, "gender": "unknown",
+            "start_age": None, "start_age_text": None, "items": [],
+            "timing_method": "birth_plus_approx_start_age_calendar_months",
+            "note": "性別未指定のため大運順逆・起運・交運を保留。命式と原局に対する流年は計算済み。",
+            "debug": {"gender": "unknown", "birth_local": local_birth.isoformat(),
+                      "direction_rule": "year_stem_yinyang_x_birth_gender"},
+        }
     forward = direction == "forward"
 
     prev_jieqi_utc, next_jieqi_utc = _jieqi_boundary_utc_for_birth_month(local_birth, tz_name)
@@ -1043,6 +1050,7 @@
     }
 
     return {
+        "status": "determined_direction_approx_timing",
         "direction": direction,
         "gender": gender_norm,
         "start_age": start_age,
@@ -1264,6 +1272,7 @@
         "ten_god_to_day_master": ten_god(p4.day[0], kanshi[0]),
         "twelve_fortune_to_day_master": twelve_fortune(p4.day[0], kanshi[1]),
         "current_daiun": daiun_item,
+        "daiun_direction_status": daiun.get("status"),
         "natal_time_basis": "four_pillars" if include_hour else "three_pillars_hour_excluded",
         "relations": {
             "branch_relations": branch_relations,
@@ -1384,16 +1393,16 @@
     }
 
 
-def _build_unknowns(payload: dict[str, Any], *, day_change_at_23: bool) -> list[str]:
+def _build_unknowns(payload: dict[str, Any], *, day_change_at_23: bool, day_boundary_hour: int | None = None) -> list[str]:
     unknowns: list[str] = []
     if payload.get("hour") in (None, "", "不明"):
         unknowns.append("出生時刻が未入力のため 12:00 を仮置きして計算")
     if payload.get("minute") in (None, "", "不明"):
         unknowns.append("出生分が未入力のため 00 分として計算")
-    if day_change_at_23:
-        unknowns.append("日替わり境界は 23:00 切替設定を使用")
-    else:
-        unknowns.append("日替わり境界は 00:00 切替設定を使用")
+    boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
+    unknowns.append(f"日替わり境界は {boundary:02d}:00 切替設定を使用（出生地の現地暦日）")
+    if _parse_gender(payload.get("gender")) == "unknown":
+        unknowns.append("性別未指定のため大運順逆・起運は未確定。大運を女性扱いで補完しない")
     unknowns.append("大運開始年齢は簡易換算（3日=1年, 1日=4ヶ月）")
     return unknowns
 
@@ -1451,7 +1460,7 @@
         dominant_features.append(f"visible五行で {top_elem} が相対的に多い ({top_count})")
         dominant_features.append(f"visible五行で {bottom_elem} が相対的に少ない ({bottom_count})")
     dominant_features.append(f"月支は {month_branch} ({month_element})")
-    dominant_features.append(f"大運方向は {daiun.get('direction')}")
+    dominant_features.append(f"大運方向は {daiun['direction']}" if daiun.get("direction") else "大運方向は未確定（性別未指定）")
 
     notes = [
         "年柱は立春基準、月柱は節入り基準で判定",
@@ -1488,6 +1497,7 @@
     day_change_at_23: bool = False,
     as_of: datetime | None = None,
     annual_years: int = 10,
+    day_boundary_hour: int | None = None,
 ) -> dict[str, Any]:
     """routes.py の payload から四柱推命結果を作る。
 
@@ -1496,6 +1506,8 @@
     """
     if not isinstance(annual_years, int) or isinstance(annual_years, bool) or not 1 <= annual_years <= 20:
         raise ValueError("annual_years must be an integer between 1 and 20")
+    boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
+    day_change_at_23 = boundary == 23
     current_dt = as_of or datetime.now(ZoneInfo(tz_name))
     if current_dt.tzinfo is None:
         raise ValueError("as_of must be timezone-aware")
@@ -1519,7 +1531,18 @@
         0,
     )
 
-    p4 = pillars4(dt, tz_name=tz_name, day_change_at_23=day_change_at_23)
+    dt = resolve_birth_datetime(dt, tz_name, fold=payload.get("birth_fold"), utc_offset_hours=payload.get("birth_utc_offset_hours"))
+    effective_date, boundary_label = _effective_local_date_for_day_pillar(dt, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
+    time_context = {
+        "local_datetime": dt.isoformat(), "timezone": tz_name,
+        "utc_offset_hours": dt.utcoffset().total_seconds() / 3600,
+        "utc_datetime": dt.astimezone(timezone.utc).isoformat(), "fold": dt.fold,
+        "day_pillar_reference_datetime": dt.isoformat(), "day_pillar_date": effective_date.isoformat(),
+        "day_boundary_hour": boundary, "day_boundary_rule": boundary_label,
+        "calendar_time_basis": "local_civil_time", "true_solar_time_applied": False,
+        "astronomical_time_basis": "UTC_for_solar_terms",
+    }
+    p4 = pillars4(dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
     _, _, ym_debug = year_month_pillars(dt, tz_name=tz_name)
 
     five = _five_elements_counts(p4)
@@ -1548,7 +1571,7 @@
     }
     hidden_main = {k: (v[0] if v else None) for k, v in hidden_all.items()}
     gender_norm = _parse_gender(payload.get("gender"))
-    unknowns = _build_unknowns(payload, day_change_at_23=day_change_at_23)
+    unknowns = _build_unknowns(payload, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
 
     from services.shichusuimei_structure import analyze_structure, analyze_luck, concurrent_luck_analysis
     if not time_reliable:
@@ -1579,6 +1602,7 @@
             "year_boundary_rule": "lichun(315deg)",
             "period_start": year_start.isoformat(), "period_end": year_end.isoformat(),
             "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
+            "daiun_direction_status": daiun["status"],
             "daiun_boundary_in_window": any(
                 year_start <= datetime.fromisoformat(item["approx_start_at"]) < year_end
                 or year_start < datetime.fromisoformat(item["approx_end_at"]) <= year_end for item in contexts
@@ -1600,6 +1624,7 @@
     annual_forecasts = {
         "start_effective_year": annual_fortune["effective_year"], "years": annual_years,
         "items": forecasts,
+        "daiun_direction_status": daiun["status"],
         "note": "流年は立春から翌立春まで。大運は出生日時に近似起運年齢の年月を加えた期間で対応付け。交運日時は近似であり確定しない",
     }
 
@@ -1651,7 +1676,7 @@
         "module": "shichusuimei",
         "system": "shichusuimei",
         "ephemeris": ephemeris_debug_info(),
-        "engine_version": "0.4.0",
+        "engine_version": ENGINE_VERSION,
         "generated_at": current_dt.isoformat(),
         "input": {
             "raw": {
@@ -1661,6 +1686,7 @@
                 "hour": hour,
                 "minute": minute,
                 "gender": gender_norm,
+                "gender_supplied": payload.get("gender"),
                 "city": payload.get("city"),
                 "lat": payload.get("lat"),
                 "lng": payload.get("lng"),
@@ -1668,13 +1694,15 @@
             "assumptions": {
                 "tz_name": tz_name,
                 "day_change_at_23": day_change_at_23,
-                "day_boundary_rule": "子刻後半(00:00-00:59)を前日扱い" if day_change_at_23 else "00:00切替",
+                "day_boundary_hour": boundary,
+                "day_boundary_rule": boundary_label,
                 "year_boundary_rule": "lichun(315deg)",
                 "month_boundary_rule": "solar_terms(315deg+30deg_step)",
                 "daiun_start_mode": "approx_days_to_years",
                 "birth_time_accuracy": time_accuracy,
                 "structural_time_basis": structural_analysis["methodology"]["time_basis"],
             },
+            "time_context": time_context,
         },
         "unknowns": unknowns,
         "normalized_data": normalized_data,
@@ -1691,7 +1719,8 @@
             "options": {
                 "tz_name": tz_name,
                 "day_change_at_23": day_change_at_23,
-                "day_boundary_rule": "子刻後半(00:00-00:59)を前日扱い" if day_change_at_23 else "00:00切替",
+                "day_boundary_hour": boundary,
+                "day_boundary_rule": boundary_label,
                 "year_boundary": "lichun(315deg)",
                 "month_boundary": "solar_terms(315deg+30deg_step)",
             },

```


## 修正前からの差分 services/shichusuimei_annual_report.py
```diff
--- before/services/shichusuimei_annual_report.py
+++ after/services/shichusuimei_annual_report.py
@@ -98,6 +98,8 @@
 
 def _daiun_periods(shichu: dict, data: dict, year: int, tz: ZoneInfo) -> list[dict]:
     daiun = data.get("daiun") or {}
+    if daiun.get("status") == "undetermined_gender":
+        return []
     saved = daiun.get("items") or []
     if not saved:
         raise ValueError("基礎命式に大運の計算結果がありません。基礎命式を再発行してください。")
@@ -186,7 +188,8 @@
         luck = _item("daiun", context["kanshi"])
         daiun_counts.append({"daiun_index": context["index"], **_counts([luck])})
         combined.append({"daiun_index": context["index"], **_counts(natal + [luck, annual])})
-    first = datetime.fromisoformat(periods[0]["approx_start_at"])
+    first = datetime.fromisoformat(periods[0]["approx_start_at"]) if periods else None
+    direction_unknown = (data.get("daiun") or {}).get("status") == "undetermined_gender"
     return {"annual_fortune_report": {
         "schema_version": "1.0", "base_chart_id": (base_doc.get("meta") or {}).get("chart_id"),
         "selected_year": selected_year,
@@ -202,10 +205,10 @@
                    "period_start": start.isoformat(), "period_end": end.isoformat(), "period_end_exclusive": True,
                    "ten_god_to_day_master": core.ten_god(day_master, annual["stem"]),
                    "twelve_fortune_to_day_master": core.twelve_fortune(day_master, annual["branch"])},
-        "daiun": {"status": "overlapping_periods" if contexts else "before_first_daiun",
+        "daiun": {"status": "undetermined_gender" if direction_unknown else "overlapping_periods" if contexts else "before_first_daiun",
                   "contexts": contexts, "boundary_in_selected_year": any(c["boundary_in_selected_year"] for c in contexts),
                   "uncovered_before_first_daiun": {"start": start.isoformat(), "end": min(first, end).isoformat()}
-                      if start < first else None,
+                      if first is not None and start < first else None,
                   "note": "起運・交運日時は既存の簡易換算による概算。境界付近の大運を確定値として扱わない。"},
         "interactions": interactions,
         "kubo": {"empty_branches": deepcopy(empty), "annual_hit": annual["branch"] in empty,

```


## 修正前からの差分 services/yaml_exporter.py
```diff
--- before/services/yaml_exporter.py
+++ after/services/yaml_exporter.py
@@ -12,6 +12,7 @@
 from services.western_calc import calc_western_from_payload, house_of
 from services.prompt_builder import build_prompt, ensure_shichusuimei_structure_guidance
 from services.output_metadata import customer_output_doc
+from services.birth_datetime import resolve_birth_datetime
 
 SIGN_JA = {
     "Ari": "牡羊座", "Tau": "牡牛座", "Gem": "双子座", "Can": "蟹座", "Leo": "獅子座", "Vir": "乙女座",
@@ -505,6 +506,9 @@
     transit_profile: str = "standard",
     day_change_at_23: bool = False,
     birth_time_accuracy: str = "auto",
+    day_boundary_hour: int | None = None,
+    birth_fold: int | None = None,
+    birth_utc_offset_hours: float | None = None,
     birth_time_range: dict[str, Any] | None = None,
     birth_time_note: str | None = None,
     data_role: str = "base_chart",
@@ -535,6 +539,12 @@
         pref_name, lat, lng = resolve_prefecture(prefecture)
     tz = ZoneInfo(tz_name)
     local_dt = datetime(y, m, d, hour, minute, tzinfo=tz)
+    if include_shichusuimei:
+        from services.shichusuimei_calc import resolve_day_boundary_hour
+        day_boundary_hour = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
+        day_change_at_23 = day_boundary_hour == 23
+        local_dt = resolve_birth_datetime(datetime(y, m, d, hour, minute), tz_name,
+                                          fold=birth_fold, utc_offset_hours=birth_utc_offset_hours)
     tz_offset = local_dt.utcoffset()
     tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
     generated_at = datetime.now(timezone.utc).astimezone()
@@ -659,9 +669,11 @@
         from services.shichusuimei_calc import calc_shichusuimei_from_payload
         systems["shichusuimei"] = calc_shichusuimei_from_payload(
             {"year": y, "month": m, "day": d, "hour": hour if birth_time else None, "minute": minute, "gender": gender,
-             "birth_time_accuracy": birth_time_accuracy},
+             "birth_time_accuracy": birth_time_accuracy, "birth_fold": local_dt.fold,
+             "birth_utc_offset_hours": tz_offset_hours},
             tz_name=tz_name,
             day_change_at_23=day_change_at_23,
+            day_boundary_hour=day_boundary_hour,
         )
     calculation_time = f"{hour:02d}:{minute:02d}"
     display_birth_time = birth_time if birth_time_accuracy == "exact" else birth_time_accuracy
@@ -687,6 +699,8 @@
         "transit_days": transit_days,
         "transit_profile": transit_profile,
         "day_change_at_23": day_change_at_23,
+        **({"day_boundary_hour": day_boundary_hour, "birth_fold": local_dt.fold,
+            "shichusuimei_engine_version": systems["shichusuimei"]["engine_version"]} if include_shichusuimei else {}),
     })
     birth_time_data = _birth_time_struct(
         input_value=birth_time,
@@ -1088,6 +1102,9 @@
     birth_time_range: dict[str, Any] | None = None,
     birth_time_note: str | None = None,
     day_change_at_23: bool = False,
+    day_boundary_hour: int | None = None,
+    birth_fold: int | None = None,
+    birth_utc_offset_hours: float | None = None,
 ) -> tuple[str, str, dict[str, Any]]:
     _full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
         title=title,
@@ -1103,6 +1120,9 @@
         include_shichusuimei=True,
         include_transit=False,
         day_change_at_23=day_change_at_23,
+        day_boundary_hour=day_boundary_hour,
+        birth_fold=birth_fold,
+        birth_utc_offset_hours=birth_utc_offset_hours,
         birth_time_accuracy=birth_time_accuracy,
         birth_time_range=birth_time_range,
         birth_time_note=birth_time_note,
@@ -1147,8 +1167,12 @@
         "generated_at": full_doc.get("generated_at"),
         "calculation": {
             "engine": "nanami-products shichusuimei",
+            "engine_version": shichu.get("engine_version"),
             "timezone": tz_name,
-            "day_change_at_23": day_change_at_23,
+            "day_change_at_23": assumptions.get("day_change_at_23"),
+            "day_boundary_hour": assumptions.get("day_boundary_hour"),
+            "day_boundary_rule": assumptions.get("day_boundary_rule"),
+            "time_context": shichu_input.get("time_context"),
             "year_boundary_rule": assumptions.get("year_boundary_rule"),
             "daiun_start_mode": assumptions.get("daiun_start_mode"),
         },
@@ -1179,9 +1203,11 @@
                 },
                 "reference": {
                     "day_master": shichu.get("day_master"),
+                    "day_kanshi": (normalized.get("pillars") or {}).get("day", {}).get("kanshi"),
                     "assumptions": {
                         "tz_name": assumptions.get("tz_name"),
                         "day_change_at_23": assumptions.get("day_change_at_23"),
+                        "day_boundary_hour": assumptions.get("day_boundary_hour"),
                         "day_boundary_rule": assumptions.get("day_boundary_rule"),
                         "year_boundary_rule": assumptions.get("year_boundary_rule"),
                         "daiun_start_mode": assumptions.get("daiun_start_mode"),

```


## 修正前からの差分 services/api_calc.py
```diff
--- before/services/api_calc.py
+++ after/services/api_calc.py
@@ -7,6 +7,7 @@
 from services.api_tags import integration_tags, shichu_tags, transit_tags, western_tags
 from services.api_yaml import build_handoff_yaml, build_ai_prompt_context
 from services.yaml_exporter import build_product_yaml
+from services.birth_datetime import BirthDatetimeError
 
 API_VERSION = "1.0"
 ENGINE_NAME = "nanami-products"
@@ -143,8 +144,34 @@
 
 
 def _normalize_day_boundary(payload: dict[str, Any]) -> bool:
-    value = str(payload.get("day_boundary") or "").strip().lower()
-    return value in {"23:00", "23", "true", "1", "on", "yes"}
+    return _normalize_day_boundary_hour(payload) == 23
+
+
+def _normalize_shichu_timezone(payload: dict[str, Any]) -> str:
+    raw = payload.get("timezone", payload.get("tz_name"))
+    if raw is not None:
+        if not str(raw).strip():
+            raise ApiCalcError("INVALID_TIMEZONE", "an IANA birth timezone is required", 400)
+        return _normalize_timezone(payload)
+    # Preserve the domestic prefecture API default; an overseas place cannot
+    # silently inherit that default or UTC.
+    from services.location import resolve_prefecture
+    try:
+        resolve_prefecture(_normalize_birth_place(payload))
+    except ValueError as exc:
+        raise ApiCalcError("INVALID_TIMEZONE", "specify the overseas IANA birth timezone", 400) from exc
+    return "Asia/Tokyo"
+
+
+def _normalize_day_boundary_hour(payload: dict[str, Any]) -> int:
+    raw = payload.get("day_boundary")
+    value = str(raw if raw is not None else "").strip().lower()
+    choices = {"": 1, "01:00": 1, "1": 1, "01": 1, "false": 1, "off": 1, "no": 1,
+               "00:00": 0, "0": 0, "midnight": 0,
+               "23:00": 23, "23": 23, "true": 23, "on": 23, "yes": 23}
+    if value not in choices:
+        raise ApiCalcError("INVALID_DAY_BOUNDARY", "day_boundary must be 00:00, 01:00 or 23:00", 400)
+    return choices[value]
 
 
 def _normalize_period(payload: dict[str, Any]) -> str:
@@ -199,6 +226,9 @@
     transit_start_date: datetime | None = None,
     transit_days: int = 31,
     day_change_at_23: bool = False,
+    day_boundary_hour: int | None = None,
+    birth_fold: int | None = None,
+    birth_utc_offset_hours: float | None = None,
 ) -> dict[str, Any]:
     yaml_text, _prompt_text, doc = build_product_yaml(
         title=title,
@@ -216,6 +246,8 @@
         transit_start_date=transit_start_date,
         transit_days=transit_days,
         day_change_at_23=day_change_at_23,
+        **({"day_boundary_hour": day_boundary_hour, "birth_fold": birth_fold,
+            "birth_utc_offset_hours": birth_utc_offset_hours} if include_shichusuimei else {}),
     )
     return {
         "doc": doc,
@@ -282,14 +314,19 @@
             birth_place=input_data["birth_place"],
             birth_lat=_optional_float(payload, "lat"),
             birth_lng=_optional_float(payload, "lon"),
-            tz_name=_normalize_timezone(payload),
+            tz_name=_normalize_shichu_timezone(payload),
             gender=str(payload.get("gender") or "unknown"),
             include_asteroids=False,
             include_shichusuimei=True,
             include_transit=False,
             day_change_at_23=_normalize_day_boundary(payload),
+            day_boundary_hour=_normalize_day_boundary_hour(payload),
+            birth_fold=payload.get("birth_fold"),
+            birth_utc_offset_hours=payload.get("birth_utc_offset_hours"),
         )
         return _success("shichu", input_data, result["doc"], yaml_text=result.get("yaml_text"))
+    except BirthDatetimeError as exc:
+        return _error("INVALID_BIRTH_DATETIME", str(exc), status_code=400)
     except ApiCalcError as exc:
         return _error(exc.code, exc.message, status_code=exc.status_code)
     except Exception as exc:
@@ -347,7 +384,7 @@
         if not birth_date:
             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
         period = _normalize_period(payload)
-        tz_name = _normalize_timezone(payload)
+        tz_name = _normalize_shichu_timezone(payload)
         writing = _normalize_writing(payload)
         target_date_value = payload.get("target_date") or birth_date
         target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
@@ -381,8 +418,13 @@
             transit_start_date=target_start,
             transit_days=transit_days,
             day_change_at_23=_normalize_day_boundary(payload),
+            day_boundary_hour=_normalize_day_boundary_hour(payload),
+            birth_fold=payload.get("birth_fold"),
+            birth_utc_offset_hours=payload.get("birth_utc_offset_hours"),
         )
         return _success("combined", input_data, result["doc"], yaml_text=result.get("yaml_text"))
+    except BirthDatetimeError as exc:
+        return _error("INVALID_BIRTH_DATETIME", str(exc), status_code=400)
     except ApiCalcError as exc:
         return _error(exc.code, exc.message, status_code=exc.status_code)
     except Exception as exc:

```


## 修正前からの差分 services/prompt_builder.py
```diff
--- before/services/prompt_builder.py
+++ after/services/prompt_builder.py
@@ -5,6 +5,8 @@
 from services.prompt_locales import SUPPORTED_PROMPT_LANGS, build_localized_prompt
 
 SHICHUSUIMEI_STRUCTURE_GUIDANCE = """【四柱推命構造分析の優先規則】
+- 新規計算の input.assumptions.day_boundary_rule と input.time_context を参照し、出生地の現地暦日と節入り用UTCを区別してください。日替わりは1時・23時・明示0時の方式差です。保存済み旧原本のbooleanを新方式へ読み替えず、計算済みの日柱・時柱を使ってください。
+- 大運の status が undetermined_gender、direction が null の場合、性別未指定による保留です。女性へ補完せず、大運・起運・交運や大運との相互作用を推測しないでください。計算済み命式と流年の natal_analysis は利用できます。
 - systems.shichusuimei.normalized_data.structural_analysis があれば、通根・透干・十神の配置と重みを単純個数より優先してください。日干自身は十神強度に含まれません。
 - pattern_analysis と useful_god_analysis は試験的な方式別候補です。confidence、reasons、conflicting_rules、methodology.limitations を参照し、格局・用神・喜忌を確定しないでください。五行の不足だけで用神を決めないでください。
 - ten_god_flow と element_flow の both_present は配置の併存です。食神・財星の個数や接続だけで、生財・制殺・金運の成立を断定しないでください。日主が財を扱う材料は day_master_support と財星の通根・透干を合わせて読んでください。

```


## 修正前からの差分 services/shichu_chart.py
```diff
--- before/services/shichu_chart.py
+++ after/services/shichu_chart.py
@@ -245,6 +245,8 @@
                 kanshi = _label(item.get("kanshi"), "")
                 chips.append(f"{age}歳 {kanshi}".strip())
         parts.append(_text(bar_x, daiun_y + 34, " / ".join(chips) or "不明", fill="#705235", class_="small"))
+    elif _nested(normalized, "daiun", "status") == "undetermined_gender":
+        parts.append(_text(bar_x, element_y + 5 * 45 + 40, "大運：未確定（性別未指定）", fill="#705235", class_="small"))
 
     if not compact:
         parts.append(_text(width / 2, height - 122, "nanami astro", fill="#8a6c45", text_anchor="middle", class_="meta"))

```


## 修正前からの差分 routes.py
```diff
--- before/routes.py
+++ after/routes.py
@@ -709,11 +709,11 @@
         "gender_unknown": "指定なし",
         "gender_female": "女性",
         "gender_male": "男性",
-        "gender_help": "四柱推命の大運計算に使用します。不明な場合は「指定なし」のまま送信できます。",
+        "gender_help": "大運の順逆に使用します。「指定なし」では命式・原局と流年を計算し、大運・起運は未確定として保留します。",
         "shichu_settings": "四柱推命設定",
         "day_change": "日替わり境界",
         "standard_1am": "1時（丑の刻）— 標準",
-        "day_change_help": "23時切替の流派で見る場合のみ「23時」を選択してください。",
+        "day_change_help": "現地時刻で判定。1時：0時台は前日、23時：23時台は翌日の日柱。真太陽時補正は行いません。",
         "final_check": "最終確認",
         "final_check_hint": "送信後は、この注文番号で再生成できません。入力内容に間違いがある場合も、購入者側では変更できません。",
         "final_agree": "入力内容を確認しました。送信後に変更できないことに同意します。",
@@ -1659,6 +1659,14 @@
     return str(value).strip().lower() in {"1", "true", "on", "yes", "23"}
 
 
+def _parse_birth_fold(value: str) -> int | None:
+    if not value.strip():
+        return None
+    if value.strip() not in {"0", "1"}:
+        raise ValueError("夏時間の重複時刻は未選択・1回目・2回目から指定してください。")
+    return int(value)
+
+
 ORDER_CODE_RE = re.compile(r"[A-Za-z0-9=_-]+")
 ORDER_PROVIDERS = {"stores", "gumroad", "payhip", "etsy", "coconala"}
 # Gumroad relaxed（サーバー照合なし）を許す商品。Gumroadで販売しているのは西洋2種のみで、
@@ -5191,6 +5199,7 @@
     gender: str = Form("unknown"),
     product_type: str = Form("western_basic"),
     day_change_at_23: str | None = Form(None),
+    birth_fold: str = Form(""),
     event_name: str = Form(""),
     event_date: str = Form(""),
     event_time: str = Form(""),
@@ -5220,6 +5229,7 @@
     # western_basic / western_full では日替わり境界UIを出さず、必ず False。
     # shichu は購入者が 23時 / 1時 を選択できます。未選択時は 1時（False）を標準にします。
     day_change_at_23_bool = _truthy(day_change_at_23) if product_type == "shichu" else False
+    birth_fold = birth_fold if isinstance(birth_fold, str) else ""
 
     def _form_err(msg: str, status: int = 400):
         return _mark_no_store(templates.TemplateResponse(
@@ -5252,6 +5262,7 @@
                     "gender": gender,
                     "product_type": product_type,
                     "day_change_at_23": day_change_at_23_bool,
+                    "birth_fold": birth_fold,
                     "event_name": event_name,
                     "event_date": event_date,
                     "event_time": event_time,
@@ -5571,6 +5582,7 @@
                 include_shichusuimei=include_shichusuimei,
                 include_transit=include_transit,
                 day_change_at_23=day_change_at_23_bool,
+                **({"birth_fold": _parse_birth_fold(birth_fold)} if include_shichusuimei and birth_place_kind == "overseas" else {}),
                 lang=lang,
             )
     except Exception as e:
@@ -7111,7 +7123,7 @@
             include_asteroids=bool(include_asteroids),
             include_shichusuimei=bool(include_shichusuimei),
             include_transit=effective_include_transit,
-            day_change_at_23=bool(day_change_at_23),
+            day_change_at_23=_truthy(day_change_at_23),
         )
     except Exception as e:
         return templates.TemplateResponse(
@@ -7533,8 +7545,28 @@
 
     shichu = ((doc.get("systems") or {}).get("shichusuimei") or {})
     assumptions = ((shichu.get("input") or {}).get("assumptions") or {})
-    args["day_change_at_23"] = bool(assumptions.get("day_change_at_23"))
+    # Respect the actual rule saved by the old engine, not the old UI label.
+    # This creates a separate add-on; never migrates the purchased base chart.
+    if "day_boundary_hour" in assumptions:
+        boundary = assumptions["day_boundary_hour"]
+    elif assumptions.get("day_boundary_rule") == "00:00切替":
+        boundary = 0
+    elif "子刻後半" in str(assumptions.get("day_boundary_rule") or ""):
+        boundary = 1
+    else:
+        boundary = 1 if assumptions.get("day_change_at_23") else 0
+    args["day_boundary_hour"] = boundary
+    args["day_change_at_23"] = boundary == 23
+    context = (shichu.get("input") or {}).get("time_context") or {}
+    if context:
+        args["birth_fold"] = context.get("fold")
+        args["birth_utc_offset_hours"] = context.get("utc_offset_hours")
     yaml_text, _prompt_text, _addon_doc = build_shichu_fortune_cycles_addon_yaml(**args)
+    original_day = ((shichu.get("normalized_data") or {}).get("pillars") or {}).get("day") or {}
+    original_day = original_day.get("kanshi") if isinstance(original_day, dict) else original_day
+    new_day = (((_addon_doc.get("systems") or {}).get("shichusuimei") or {}).get("reference") or {}).get("day_kanshi")
+    if original_day and original_day != new_day:
+        raise ValueError("保存済み命式の日柱と修正後の計算が異なるため、追加データを統合できません。完全原本はそのまま保存してください。")
     return yaml_text
 
 

```


## 修正前からの差分 templates/redeem_shichu.html
```diff
--- before/templates/redeem_shichu.html
+++ after/templates/redeem_shichu.html
@@ -108,7 +108,7 @@
               <option value="male"
                 {% if form and form.gender == 'male' %}selected{% endif %}>男性</option>
             </select>
-            <small>四柱推命の大運計算に使用します。不明な場合は「指定なし」のまま送信できます。</small>
+            <small>大運の順逆に使用します。「指定なし」では命式・原局と流年を計算し、大運・起運は未確定として保留します。</small>
           </label>
         </div>
 
@@ -159,6 +159,14 @@
                        placeholder="例：America/New_York">
                 <small>出生地に近い地域を選んでください。リストにない場合だけ「その他」を使います。</small>
               </label>
+              <label class="full-span overseas-only-field" {% if not form or form.birth_place_kind != 'overseas' %}hidden{% endif %}>夏時間終了時の重複時刻（任意）
+                <select name="birth_fold">
+                  <option value="">通常・未選択</option>
+                  <option value="0" {% if form and form.birth_fold == '0' %}selected{% endif %}>同じ現地時刻の1回目</option>
+                  <option value="1" {% if form and form.birth_fold == '1' %}selected{% endif %}>同じ現地時刻の2回目</option>
+                </select>
+                <small>夏時間終了で同じ時刻が2回存在する場合だけ指定します。不明なまま片方を推測しません。</small>
+              </label>
             </div>
           </div>
         </div>
@@ -170,7 +178,7 @@
               <option value="false" {% if not form or not form.day_change_at_23 %}selected{% endif %}>1時（丑の刻）— 標準</option>
               <option value="true"  {% if form and form.day_change_at_23 %}selected{% endif %}>23時</option>
             </select>
-            <small>23時切替の流派で見る場合のみ「23時」を選択してください。</small>
+            <small>出生地の現地時刻で判定します。1時：0時台は前日、23時：23時台は翌日の日柱。真太陽時補正は行いません。</small>
           </label>
         </div>
 
@@ -369,7 +377,11 @@
       if (coordinateWrap) coordinateWrap.hidden = !coordinateValue;
       if (coordinateValue) document.getElementById('confirm-coordinates').textContent = coordinateValue;
       if (timezoneWrap) timezoneWrap.hidden = !active;
-      if (active) document.getElementById('confirm-timezone').textContent = buildConfirmValue(timezone);
+      if (active) {
+        const fold = document.querySelector('[name="birth_fold"]');
+        document.getElementById('confirm-timezone').textContent = buildConfirmValue(timezone) +
+          (fold && fold.value !== '' ? ' / ' + fold.selectedOptions[0].textContent : '');
+      }
       document.getElementById('confirm-gender').textContent = buildConfirmValue(gender?.selectedOptions?.[0]?.textContent);
       document.getElementById('confirm-day-change').textContent = buildConfirmValue(dayChange?.selectedOptions?.[0]?.textContent);
 

```


## 独立参照fixtureのメタデータ
{"library": "lunar_python", "version": "1.4.8", "source": "https://github.com/6tail/lunar-python", "term_source": "https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html", "calendar": "Gregorian civil date, selected 00/01/23 boundary; no true solar time", "year_month": "Independent lunar-python EightChar at same instant in UTC+8; outside term boundary", "hour": "Five-mouse cyclic formula based on selected civil-date stem and local two-hour branch"}

## 独立参照の代表反例（生成器から、エンジン期待値のコピーではない）
[
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Asia/Tokyo",
    "offset_hours": 9,
    "utc": "2000-01-06T15:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Asia/Tokyo",
    "offset_hours": 9,
    "utc": "2000-01-06T15:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Asia/Tokyo",
    "offset_hours": 9,
    "utc": "2000-01-06T15:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Asia/Tokyo",
    "offset_hours": 9,
    "utc": "2000-01-07T14:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Asia/Tokyo",
    "offset_hours": 9,
    "utc": "2000-01-07T14:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Asia/Tokyo",
    "offset_hours": 9,
    "utc": "2000-01-07T14:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Asia/Seoul",
    "offset_hours": 9,
    "utc": "2000-01-06T15:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Asia/Seoul",
    "offset_hours": 9,
    "utc": "2000-01-06T15:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Asia/Seoul",
    "offset_hours": 9,
    "utc": "2000-01-06T15:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Asia/Seoul",
    "offset_hours": 9,
    "utc": "2000-01-07T14:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Asia/Seoul",
    "offset_hours": 9,
    "utc": "2000-01-07T14:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Asia/Seoul",
    "offset_hours": 9,
    "utc": "2000-01-07T14:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Europe/London",
    "offset_hours": 0,
    "utc": "2000-01-07T00:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Europe/London",
    "offset_hours": 0,
    "utc": "2000-01-07T00:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Europe/London",
    "offset_hours": 0,
    "utc": "2000-01-07T00:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Europe/London",
    "offset_hours": 0,
    "utc": "2000-01-07T23:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Europe/London",
    "offset_hours": 0,
    "utc": "2000-01-07T23:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Europe/London",
    "offset_hours": 0,
    "utc": "2000-01-07T23:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "America/New_York",
    "offset_hours": -5,
    "utc": "2000-01-07T05:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "America/New_York",
    "offset_hours": -5,
    "utc": "2000-01-07T05:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "America/New_York",
    "offset_hours": -5,
    "utc": "2000-01-07T05:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "America/New_York",
    "offset_hours": -5,
    "utc": "2000-01-08T04:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "America/New_York",
    "offset_hours": -5,
    "utc": "2000-01-08T04:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "America/New_York",
    "offset_hours": -5,
    "utc": "2000-01-08T04:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "America/Los_Angeles",
    "offset_hours": -8,
    "utc": "2000-01-07T08:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "America/Los_Angeles",
    "offset_hours": -8,
    "utc": "2000-01-07T08:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "America/Los_Angeles",
    "offset_hours": -8,
    "utc": "2000-01-07T08:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "America/Los_Angeles",
    "offset_hours": -8,
    "utc": "2000-01-08T07:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "America/Los_Angeles",
    "offset_hours": -8,
    "utc": "2000-01-08T07:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "America/Los_Angeles",
    "offset_hours": -8,
    "utc": "2000-01-08T07:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Honolulu",
    "offset_hours": -10,
    "utc": "2000-01-07T10:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Honolulu",
    "offset_hours": -10,
    "utc": "2000-01-07T10:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Honolulu",
    "offset_hours": -10,
    "utc": "2000-01-07T10:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Honolulu",
    "offset_hours": -10,
    "utc": "2000-01-08T09:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Honolulu",
    "offset_hours": -10,
    "utc": "2000-01-08T09:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Honolulu",
    "offset_hours": -10,
    "utc": "2000-01-08T09:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Australia/Sydney",
    "offset_hours": 11,
    "utc": "2000-01-06T13:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Australia/Sydney",
    "offset_hours": 11,
    "utc": "2000-01-06T13:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Australia/Sydney",
    "offset_hours": 11,
    "utc": "2000-01-06T13:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Australia/Sydney",
    "offset_hours": 11,
    "utc": "2000-01-07T12:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Australia/Sydney",
    "offset_hours": 11,
    "utc": "2000-01-07T12:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Australia/Sydney",
    "offset_hours": 11,
    "utc": "2000-01-07T12:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "UTC",
    "offset_hours": 0,
    "utc": "2000-01-07T00:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "UTC",
    "offset_hours": 0,
    "utc": "2000-01-07T00:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "UTC",
    "offset_hours": 0,
    "utc": "2000-01-07T00:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "UTC",
    "offset_hours": 0,
    "utc": "2000-01-07T23:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "UTC",
    "offset_hours": 0,
    "utc": "2000-01-07T23:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "UTC",
    "offset_hours": 0,
    "utc": "2000-01-07T23:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Kiritimati",
    "offset_hours": 14,
    "utc": "2000-01-06T10:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Kiritimati",
    "offset_hours": 14,
    "utc": "2000-01-06T10:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Kiritimati",
    "offset_hours": 14,
    "utc": "2000-01-06T10:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Kiritimati",
    "offset_hours": 14,
    "utc": "2000-01-07T09:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Kiritimati",
    "offset_hours": 14,
    "utc": "2000-01-07T09:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Kiritimati",
    "offset_hours": 14,
    "utc": "2000-01-07T09:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Pago_Pago",
    "offset_hours": -11,
    "utc": "2000-01-07T11:59:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Pago_Pago",
    "offset_hours": -11,
    "utc": "2000-01-07T11:59:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-06",
    "day": "癸亥",
    "hour": "壬子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T00:59:00",
    "timezone": "Pacific/Pago_Pago",
    "offset_hours": -11,
    "utc": "2000-01-07T11:59:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Pago_Pago",
    "offset_hours": -11,
    "utc": "2000-01-08T10:30:00+00:00",
    "day_boundary_hour": 0,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Pago_Pago",
    "offset_hours": -11,
    "utc": "2000-01-08T10:30:00+00:00",
    "day_boundary_hour": 1,
    "effective_date": "2000-01-07",
    "day": "甲子",
    "hour": "甲子",
    "year": "己卯",
    "month": "丁丑"
  },
  {
    "local": "2000-01-07T23:30:00",
    "timezone": "Pacific/Pago_Pago",
    "offset_hours": -11,
    "utc": "2000-01-08T10:30:00+00:00",
    "day_boundary_hour": 23,
    "effective_date": "2000-01-08",
    "day": "乙丑",
    "hour": "丙子",
    "year": "己卯",
    "month": "丁丑"
  }
]

## 立春独立資料
国立天文台2026暦要項: 2026-02-04 05:02 JST (2026-02-03 20:02 UTC)。年/月は2分前=乙巳/己丑、2分後=丙午/庚寅。掲載時刻は分丸め、厳密秒でない。
