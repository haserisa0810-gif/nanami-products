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


## services/birth_datetime.py
```text
1: """Resolve a civil birth time without conflating it with a pillar calendar day.
2: 
3: No solar-time correction and no fallback to UTC. Ambiguous DST times require
4: an explicit fold/offset or an already aware instant; nonexistent times fail.
5: """
6: from datetime import datetime, timezone
7: from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
8: 
9: 
10: class BirthDatetimeError(ValueError):
11:     pass
12: 
13: 
14: def resolve_birth_datetime(
15:     birth: datetime, tz_name: str, *, fold: int | None = None,
16:     utc_offset_hours: float | None = None,
17: ) -> datetime:
18:     if not isinstance(tz_name, str) or not tz_name.strip():
19:         raise BirthDatetimeError("出生地のIANAタイムゾーンを指定してください。UTCへ自動補完しません。")
20:     try:
21:         tz = ZoneInfo(tz_name)
22:     except (ValueError, ZoneInfoNotFoundError) as exc:
23:         raise BirthDatetimeError("出生地のIANAタイムゾーンを確認してください。") from exc
24:     if fold is not None and (type(fold) is not int or fold not in (0, 1)):
25:         raise BirthDatetimeError("birth_foldは0または1で指定してください。")
26:     aware = birth.tzinfo is not None
27:     local = birth.astimezone(tz) if aware else birth.replace(tzinfo=tz)
28:     wall = local.replace(tzinfo=None)
29:     candidates = []
30:     for choice in (0, 1):
31:         candidate = wall.replace(tzinfo=tz, fold=choice)
32:         back = candidate.astimezone(timezone.utc).astimezone(tz)
33:         if back.replace(tzinfo=None) == wall and back.fold == choice:
34:             candidates.append(candidate)
35:     if not candidates:
36:         raise BirthDatetimeError("出生時刻が夏時間切替などにより存在しません。現地日時を確認してください。")
37:     if aware:
38:         candidates = [c for c in candidates if c.astimezone(timezone.utc) == local.astimezone(timezone.utc)]
39:     if fold is not None:
40:         candidates = [c for c in candidates if c.fold == fold]
41:     if utc_offset_hours is not None:
42:         try:
43:             offset = float(utc_offset_hours)
44:         except (ValueError, TypeError) as exc:
45:             raise BirthDatetimeError("出生当時のUTCオフセットを数値で指定してください。") from exc
46:         candidates = [c for c in candidates if abs(c.utcoffset().total_seconds() / 3600 - offset) < 1e-9]
47:     if not candidates:
48:         raise BirthDatetimeError("指定したUTCオフセット・foldと出生地の日時が一致しません。")
49:     if len(candidates) > 1:
50:         raise BirthDatetimeError("出生時刻が夏時間終了により重複します。birth_foldまたは出生当時のUTCオフセットを指定してください。")
51:     return candidates[0]
```


## services/shichusuimei_calc.py
```text
1: from __future__ import annotations
2: 
3: """四柱推命 計算（年/月/日/時） + 基本特徴量
4: 
5: 実装済み:
6: - 年柱 / 月柱（節入り）
7: - 日柱 / 時柱
8: - 蔵干
9: - 十神
10: - 五行カウント（表示用 / 蔵干込み）
11: - 空亡（旬空）
12: - 十二運
13: - 身強スコア目安
14: - 大運（年干陰陽 × 出生時の性別 で順逆判定）
15: 
16: 注意:
17: - 日替わり境界は流派差があるため option(day_change_at_23) で切替
18: - 性別は四柱推命の計算上は「出生時の性別」を使う
19: """
20: 
21: from dataclasses import dataclass, asdict
22: import calendar
23: from datetime import datetime, timezone, timedelta
24: import os
25: from zoneinfo import ZoneInfo
26: from typing import Any
27: from services.birth_datetime import resolve_birth_datetime
28: 
29: ENGINE_VERSION = "0.5.0"
30: 
31: from pathlib import Path
32: import swisseph as swe
33: 
34: def _ephe_candidates() -> list[Path]:
35:     candidates: list[Path] = []
36: 
37:     env_path = os.getenv("SWEPH_EPHE_PATH", "").strip()
38:     if env_path:
39:         candidates.append(Path(env_path))
40: 
41:     candidates.extend([
42:         Path(__file__).resolve().parents[1] / "ephe",
43:         Path("/app/ephe"),
44:     ])
45: 
46:     deduped: list[Path] = []
47:     seen: set[str] = set()
48:     for path in candidates:
49:         key = str(path.resolve()) if path.exists() else str(path)
50:         if key in seen:
51:             continue
52:         seen.add(key)
53:         deduped.append(path)
54:     return deduped
55: 
56: 
57: def _resolve_ephe_dir() -> Path | None:
58:     for ephe_dir in _ephe_candidates():
59:         if ephe_dir.exists() and any(ephe_dir.glob("*.se1")):
60:             return ephe_dir
61:     return None
62: 
63: 
64: def configure_ephemeris() -> int:
65:     ephe_dir = _resolve_ephe_dir()
66:     if ephe_dir is not None:
67:         swe.set_ephe_path(str(ephe_dir))
68:         return swe.FLG_SWIEPH
69:     return swe.FLG_MOSEPH
70: 
71: def ephemeris_debug_info() -> dict:
72:     resolved = _resolve_ephe_dir()
73:     candidates = _ephe_candidates()
74:     ephe_dir = resolved or candidates[0]
75:     files = sorted([p.name for p in ephe_dir.glob("*")]) if ephe_dir.exists() else []
76:     return {
77:         "ephe_dir": str(ephe_dir),
78:         "ephe_dir_exists": ephe_dir.exists(),
79:         "ephe_files": files,
80:         "has_se1": any(name.endswith(".se1") for name in files),
81:         "resolved_ephe_dir": str(resolved) if resolved is not None else None,
82:         "searched_ephe_dirs": [str(p) for p in candidates],
83:         "env_sweph_ephe_path": os.getenv("SWEPH_EPHE_PATH", "").strip() or None,
84:     }
85: 
86: # Swiss Ephemeris（節気計算に使用）
87: try:
88:     import swisseph as swe  # type: ignore
89: except Exception:  # pragma: no cover
90:     swe = None  # type: ignore
91: 
92: 
93: # 0=甲子 ... 59=癸亥
94: KANSHI_60 = [
95:     "甲子","乙丑","丙寅","丁卯","戊辰","己巳","庚午","辛未","壬申","癸酉",
96:     "甲戌","乙亥","丙子","丁丑","戊寅","己卯","庚辰","辛巳","壬午","癸未",
97:     "甲申","乙酉","丙戌","丁亥","戊子","己丑","庚寅","辛卯","壬辰","癸巳",
98:     "甲午","乙未","丙申","丁酉","戊戌","己亥","庚子","辛丑","壬寅","癸卯",
99:     "甲辰","乙巳","丙午","丁未","戊申","己酉","庚戌","辛亥","壬子","癸丑",
100:     "甲寅","乙卯","丙辰","丁巳","戊午","己未","庚申","辛酉","壬戌","癸亥",
101: ]
102: 
103: STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
104: BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
105: 
106: # 月支（節入り）順：立春=寅月スタート
107: MONTH_BRANCHES = ["寅","卯","辰","巳","午","未","申","酉","戌","亥","子","丑"]
108: 
109: # 干の五行
110: STEM_ELEMENT = {
111:     "甲": "木", "乙": "木",
112:     "丙": "火", "丁": "火",
113:     "戊": "土", "己": "土",
114:     "庚": "金", "辛": "金",
115:     "壬": "水", "癸": "水",
116: }
117: 
118: # 支の本気（代表五行）
119: BRANCH_ELEMENT = {
120:     "子": "水", "丑": "土", "寅": "木", "卯": "木",
121:     "辰": "土", "巳": "火", "午": "火", "未": "土",
122:     "申": "金", "酉": "金", "戌": "土", "亥": "水",
123: }
124: 
125: STEM_COMBINATIONS = {
126:     frozenset(("甲", "己")): "土",
127:     frozenset(("乙", "庚")): "金",
128:     frozenset(("丙", "辛")): "水",
129:     frozenset(("丁", "壬")): "木",
130:     frozenset(("戊", "癸")): "火",
131: }
132: 
133: BRANCH_CLASHES = {
134:     frozenset(("子", "午")),
135:     frozenset(("丑", "未")),
136:     frozenset(("寅", "申")),
137:     frozenset(("卯", "酉")),
138:     frozenset(("辰", "戌")),
139:     frozenset(("巳", "亥")),
140: }
141: 
142: BRANCH_SIX_HARMONIES = {
143:     frozenset(("子", "丑")): "土",
144:     frozenset(("寅", "亥")): "木",
145:     frozenset(("卯", "戌")): "火",
146:     frozenset(("辰", "酉")): "金",
147:     frozenset(("巳", "申")): "水",
148:     frozenset(("午", "未")): "火",
149: }
150: 
151: BRANCH_HARMS = {
152:     frozenset(("子", "未")),
153:     frozenset(("丑", "午")),
154:     frozenset(("寅", "巳")),
155:     frozenset(("卯", "辰")),
156:     frozenset(("申", "亥")),
157:     frozenset(("酉", "戌")),
158: }
159: 
160: # 六破（刑冲合害と独立して併記する）。巳申・寅亥は六合とも重なる。
161: BRANCH_DESTRUCTIONS = {
162:     frozenset(("子", "酉")), frozenset(("卯", "午")),
163:     frozenset(("辰", "丑")), frozenset(("未", "戌")),
164:     frozenset(("寅", "亥")), frozenset(("巳", "申")),
165: }
166: 
167: BRANCH_PUNISHMENTS = {
168:     frozenset(("子", "卯")): "無礼の刑",
169: }
170: 
171: BRANCH_SELF_PUNISHMENTS = {"辰", "午", "酉", "亥"}
172: 
173: BRANCH_THREE_PUNISHMENTS = {
174:     frozenset(("寅", "巳", "申")): "無恩の刑",
175:     frozenset(("丑", "戌", "未")): "持勢の刑",
176: }
177: 
178: BRANCH_TRIADS = {
179:     frozenset(("申", "子", "辰")): "水局",
180:     frozenset(("亥", "卯", "未")): "木局",
181:     frozenset(("寅", "午", "戌")): "火局",
182:     frozenset(("巳", "酉", "丑")): "金局",
183: }
184: 
185: # 神殺（代表的な表）。日干基準を基本に、天徳は月支基準。
186: TENOTSU_KIJIN_BY_DAY_STEM = {
187:     "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
188:     "乙": ["子", "申"], "己": ["子", "申"],
189:     "丙": ["亥", "酉"], "丁": ["亥", "酉"],
190:     "壬": ["卯", "巳"], "癸": ["卯", "巳"],
191:     "辛": ["寅", "午"],
192: }
193: 
194: BUNSHO_BY_DAY_STEM = {
195:     "甲": ["巳"], "乙": ["午"], "丙": ["申"], "丁": ["酉"], "戊": ["申"],
196:     "己": ["酉"], "庚": ["亥"], "辛": ["子"], "壬": ["寅"], "癸": ["卯"],
197: }
198: 
199: TENTOKU_BY_MONTH_BRANCH = {
200:     "寅": "丁", "卯": "申", "辰": "壬", "巳": "辛",
201:     "午": "亥", "未": "甲", "申": "癸", "酉": "寅",
202:     "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚",
203: }
204: 
205: # 蔵干（代表的な表）
206: HIDDEN_STEMS = {
207:     "子": ["癸"],
208:     "丑": ["己", "癸", "辛"],
209:     "寅": ["甲", "丙", "戊"],
210:     "卯": ["乙"],
211:     "辰": ["戊", "乙", "癸"],
212:     "巳": ["丙", "戊", "庚"],
213:     "午": ["丁", "己"],
214:     "未": ["己", "丁", "乙"],
215:     "申": ["庚", "壬", "戊"],
216:     "酉": ["辛"],
217:     "戌": ["戊", "辛", "丁"],
218:     "亥": ["壬", "甲"],
219: }
220: 
221: # 陰陽
222: YIN_YANG = {
223:     "甲": "陽", "乙": "陰",
224:     "丙": "陽", "丁": "陰",
225:     "戊": "陽", "己": "陰",
226:     "庚": "陽", "辛": "陰",
227:     "壬": "陽", "癸": "陰",
228: }
229: 
230: # 空亡（旬空）
231: KUBO_BY_JUN = [
232:     ["戌", "亥"],  # 甲子旬
233:     ["申", "酉"],  # 甲戌旬
234:     ["午", "未"],  # 甲申旬
235:     ["辰", "巳"],  # 甲午旬
236:     ["寅", "卯"],  # 甲辰旬
237:     ["子", "丑"],  # 甲寅旬
238: ]
239: 
240: JUN_LABELS = ["甲子旬", "甲戌旬", "甲申旬", "甲午旬", "甲辰旬", "甲寅旬"]
241: 
242: 
243: # 時支の境界（ローカル時刻）
244: # 子:23:00-00:59, 丑:01:00-02:59, ... 戌:19:00-20:59, 亥:21:00-22:59
245: def _time_branch_index(local_dt: datetime) -> int:
246:     h = local_dt.hour
247:     m = local_dt.minute
248:     minutes = h * 60 + m
249: 
250:     # 子だけ日跨ぎなので特別扱い
251:     if minutes >= 23 * 60 or minutes < 1 * 60:
252:         return 0  # 子
253:     # それ以外は 2時間刻み：1:00-2:59 が丑(1) ... 21:00-22:59 が亥(11)
254:     # 1:00 を起点に 120分ブロック
255:     return 1 + ((minutes - 60) // 120)
256: 
257: 
258: def julian_day(dt_utc: datetime) -> float:
259:     """グレゴリオ暦のUTC datetime -> JD
260: 
261:     dt_utc は timezone.utc の aware datetime を想定
262:     """
263:     if dt_utc.tzinfo is None:
264:         raise ValueError("dt_utc must be timezone-aware (UTC).")
265:     dt_utc = dt_utc.astimezone(timezone.utc)
266: 
267:     y = dt_utc.year
268:     m = dt_utc.month
269:     d = dt_utc.day
270:     frac_day = (dt_utc.hour + (dt_utc.minute + dt_utc.second / 60) / 60) / 24
271: 
272:     if m <= 2:
273:         y -= 1
274:         m += 12
275: 
276:     A = y // 100
277:     B = 2 - A + (A // 4)
278: 
279:     jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5
280:     return jd + frac_day
281: 
282: 
283: def _dt_utc_to_jdut(dt_utc: datetime) -> float:
284:     """UTC datetime -> Swiss Ephemeris 用の JD(UT)"""
285:     if swe is None:
286:         raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")
287:     dt_utc = dt_utc.astimezone(timezone.utc)
288:     hour = dt_utc.hour + (dt_utc.minute + dt_utc.second / 60) / 60
289:     return float(swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour))
290: 
291: 
292: def _sun_lon_deg(jd_ut: float) -> float:
293:     """太陽黄経（0-360）"""
294:     if swe is None:
295:         raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")
296:     flags = configure_ephemeris()
297:     xx, _ = swe.calc_ut(jd_ut, swe.SUN, flags)
298:     return float(xx[0]) % 360.0
299: 
300: 
301: def _angle_diff_deg(a: float, b: float) -> float:
302:     """角度差 a-b を [-180, 180) に正規化"""
303:     return ((a - b + 180.0) % 360.0) - 180.0
304: 
305: 
306: def _find_solar_longitude_crossing(
307:     *,
308:     target_lon_deg: float,
309:     approx_dt_utc: datetime,
310:     search_days: int = 7,
311: ) -> datetime:
312:     """太陽黄経が target_lon_deg を横切る瞬間を近傍探索して返す（UTC）。"""
313:     if swe is None:
314:         raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")
315: 
316:     target = target_lon_deg % 360.0
317:     approx = approx_dt_utc.astimezone(timezone.utc)
318: 
319:     step = timedelta(hours=6)
320:     start = approx - timedelta(days=search_days)
321:     end = approx + timedelta(days=search_days)
322: 
323:     t = start
324:     jd0 = _dt_utc_to_jdut(t)
325:     f0 = _angle_diff_deg(_sun_lon_deg(jd0), target)
326: 
327:     while t < end:
328:         t1 = t + step
329:         jd1 = _dt_utc_to_jdut(t1)
330:         f1 = _angle_diff_deg(_sun_lon_deg(jd1), target)
331: 
332:         if f0 == 0:
333:             return t
334: 
335:         if (f0 < 0 <= f1) or (f0 > 0 >= f1):
336:             lo_t, hi_t = t, t1
337:             lo_f, hi_f = f0, f1
338:             for _ in range(60):
339:                 mid_t = lo_t + (hi_t - lo_t) / 2
340:                 mid_jd = _dt_utc_to_jdut(mid_t)
341:                 mid_f = _angle_diff_deg(_sun_lon_deg(mid_jd), target)
342:                 if abs((hi_t - lo_t).total_seconds()) <= 1:
343:                     return mid_t
344:                 if (lo_f < 0 <= mid_f) or (lo_f > 0 >= mid_f):
345:                     hi_t, hi_f = mid_t, mid_f
346:                 else:
347:                     lo_t, lo_f = mid_t, mid_f
348:             return lo_t
349: 
350:         t, f0 = t1, f1
351: 
352:     raise RuntimeError("節気計算に失敗しました（探索範囲不足の可能性）")
353: 
354: 
355: def _lichun_utc_for_year(year: int, tz_name: str) -> datetime:
356:     """指定年の立春（太陽黄経315°）の瞬間を UTC で返す。"""
357:     tz = ZoneInfo(tz_name)
358:     approx_local = datetime(year, 2, 4, 12, 0, 0, tzinfo=tz)
359:     return _find_solar_longitude_crossing(
360:         target_lon_deg=315.0,
361:         approx_dt_utc=approx_local.astimezone(timezone.utc),
362:     )
363: 
364: 
365: def _month_index_from_sun_lon(sun_lon_deg: float) -> int:
366:     """太陽黄経から節入り月インデックス（0=寅月..11=丑月）"""
367:     return int(((sun_lon_deg - 315.0) % 360.0) // 30.0)
368: 
369: 
370: def _year_kanshi_from_effective_year(y: int) -> str:
371:     idx = (y - 4) % 60
372:     return KANSHI_60[idx]
373: 
374: 
375: def _month_kanshi_from_year_stem_and_index(year_stem: str, month_index: int) -> str:
376:     start_map = {
377:         "甲": "丙", "己": "丙",
378:         "乙": "戊", "庚": "戊",
379:         "丙": "庚", "辛": "庚",
380:         "丁": "壬", "壬": "壬",
381:         "戊": "甲", "癸": "甲",
382:     }
383:     if year_stem not in start_map:
384:         raise ValueError(f"Unknown year stem: {year_stem}")
385:     start = start_map[year_stem]
386:     stem = STEMS[(STEMS.index(start) + month_index) % 10]
387:     branch = MONTH_BRANCHES[month_index]
388:     return stem + branch
389: 
390: 
391: def _element_generate(elem: str) -> str:
392:     order = ["木", "火", "土", "金", "水"]
393:     return order[(order.index(elem) + 1) % 5]
394: 
395: 
396: def _element_control(elem: str) -> str:
397:     control = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
398:     return control[elem]
399: 
400: 
401: def ten_god(day_stem: str, other_stem: str) -> str:
402:     """日干から見た十神（通変星）"""
403:     dm_elem = STEM_ELEMENT[day_stem]
404:     ot_elem = STEM_ELEMENT[other_stem]
405:     dm_yy = YIN_YANG[day_stem]
406:     ot_yy = YIN_YANG[other_stem]
407:     same_polarity = (dm_yy == ot_yy)
408: 
409:     if ot_elem == dm_elem:
410:         return "比肩" if same_polarity else "劫財"
411:     if _element_generate(dm_elem) == ot_elem:
412:         return "食神" if same_polarity else "傷官"
413:     if _element_control(dm_elem) == ot_elem:
414:         return "偏財" if same_polarity else "正財"
415:     if _element_control(ot_elem) == dm_elem:
416:         return "偏官" if same_polarity else "正官"
417:     if _element_generate(ot_elem) == dm_elem:
418:         return "偏印" if same_polarity else "印綬"
419:     return "不明"
420: 
421: 
422: def _effective_local_date_for_day_pillar(
423:     local_dt: datetime,
424:     *,
425:     day_change_at_23: bool,
426:     day_boundary_hour: int | None = None,
427: ) -> tuple[datetime.date, str]:
428:     """Civil-calendar modes: 01:00 standard, 23:00 next day, explicit 00:00.
429: 
430:     The boolean is a new-calculation UI adapter, never an old-YAML migration.
431:     Version <=0.4.0 had different boolean behavior; stored results stay intact.
432:     """
433:     boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
434:     local_date = local_dt.date()
435:     if boundary == 1 and local_dt.hour < 1:
436:         local_date -= timedelta(days=1)
437:     elif boundary == 23 and local_dt.hour >= 23:
438:         local_date += timedelta(days=1)
439:     return local_date, f"{boundary:02d}:00切替"
440: 
441: 
442: def resolve_day_boundary_hour(day_change_at_23: bool = False, day_boundary_hour: int | None = None) -> int:
443:     if day_boundary_hour is None:
444:         return 23 if day_change_at_23 else 1
445:     if type(day_boundary_hour) is not int or day_boundary_hour not in (0, 1, 23):
446:         raise ValueError("day_boundary_hour must be 0, 1 or 23")
447:     if day_change_at_23 and day_boundary_hour != 23:
448:         raise ValueError("day_change_at_23 conflicts with day_boundary_hour")
449:     return day_boundary_hour
450: 
451: 
452: def day_kanshi_from_birth(
453:     birth_dt: datetime,
454:     tz_name: str = "Asia/Tokyo",
455:     day_change_at_23: bool = False,
456:     *, day_boundary_hour: int | None = None,
457: ) -> str:
458:     """Sexagenary day of the selected LOCAL civil date; UTC is not used.
459: 
460:     Gregorian ordinal +14 == Gregorian noon JDN +49 (0 = 甲子).
461:     Anchor: 2000-01-07 = 甲子. Astronomy continues to use UTC independently.
462:     """
463:     local_dt = resolve_birth_datetime(birth_dt, tz_name)
464:     local_date, _rule_label = _effective_local_date_for_day_pillar(
465:         local_dt,
466:         day_change_at_23=day_change_at_23,
467:         day_boundary_hour=day_boundary_hour,
468:     )
469:     idx = (local_date.toordinal() + 14) % 60
470:     return KANSHI_60[idx]
471: 
472: 
473: def hour_kanshi_from_day_stem_and_time(
474:     day_stem: str,
475:     birth_dt: datetime,
476:     tz_name: str = "Asia/Tokyo",
477: ) -> str:
478:     """日干とローカル時刻から時柱（時干支）を算出。"""
479:     local_dt = resolve_birth_datetime(birth_dt, tz_name)
480: 
481:     b_idx = _time_branch_index(local_dt)
482:     branch = BRANCHES[b_idx]
483: 
484:     # 甲己日→子刻は甲、乙庚日→子刻は丙、丙辛日→子刻は戊、丁壬日→子刻は庚、戊癸日→子刻は壬
485:     start_stem_map = {
486:         "甲": "甲", "己": "甲",
487:         "乙": "丙", "庚": "丙",
488:         "丙": "戊", "辛": "戊",
489:         "丁": "庚", "壬": "庚",
490:         "戊": "壬", "癸": "壬",
491:     }
492:     if day_stem not in start_stem_map:
493:         raise ValueError(f"Unknown day stem: {day_stem}")
494: 
495:     start = start_stem_map[day_stem]
496:     start_idx = STEMS.index(start)
497:     stem = STEMS[(start_idx + b_idx) % 10]
498:     return stem + branch
499: 
500: 
501: @dataclass(frozen=True)
502: class Pillars:
503:     day: str
504:     hour: str
505: 
506: 
507: @dataclass(frozen=True)
508: class Pillars4:
509:     year: str
510:     month: str
511:     day: str
512:     hour: str
513: 
514: 
515: def pillars_day_hour(
516:     birth_dt: datetime,
517:     tz_name: str = "Asia/Tokyo",
518:     day_change_at_23: bool = False,
519:     *, day_boundary_hour: int | None = None,
520: ) -> Pillars:
521:     day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=day_boundary_hour)
522:     day_stem = day[0]
523:     hour = hour_kanshi_from_day_stem_and_time(day_stem, birth_dt, tz_name=tz_name)
524:     return Pillars(day=day, hour=hour)
525: 
526: 
527: def year_month_pillars(
528:     birth_dt: datetime,
529:     tz_name: str = "Asia/Tokyo",
530: ) -> tuple[str, str, dict[str, Any]]:
531:     """年柱・月柱（節入り）。
532: 
533:     戻り値: (year_kanshi, month_kanshi, debug)
534:     debug には立春時刻や太陽黄経などの内部情報を入れる。
535:     """
536:     tz = ZoneInfo(tz_name)
537:     local_dt = resolve_birth_datetime(birth_dt, tz_name)
538:     utc_dt = local_dt.astimezone(timezone.utc)
539: 
540:     if swe is None:
541:         raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")
542: 
543:     # 立春（年境界）
544:     lichun_utc = _lichun_utc_for_year(local_dt.year, tz_name)
545:     lichun_local = lichun_utc.astimezone(tz)
546:     effective_year = local_dt.year if local_dt >= lichun_local else (local_dt.year - 1)
547: 
548:     year_kanshi = _year_kanshi_from_effective_year(effective_year)
549: 
550:     # 月柱（節入り月）：太陽黄経で判定
551:     sun_lon = _sun_lon_deg(_dt_utc_to_jdut(utc_dt))
552:     month_index = _month_index_from_sun_lon(sun_lon)
553:     month_kanshi = _month_kanshi_from_year_stem_and_index(year_kanshi[0], month_index)
554: 
555:     debug = {
556:         "tz_name": tz_name,
557:         "local_datetime": local_dt.isoformat(),
558:         "lichun_local": lichun_local.isoformat(),
559:         "effective_year": effective_year,
560:         "sun_lon_deg": round(sun_lon, 6),
561:         "month_index": month_index,
562:         "month_branch": MONTH_BRANCHES[month_index],
563:     }
564:     return year_kanshi, month_kanshi, debug
565: 
566: 
567: def pillars4(
568:     birth_dt: datetime,
569:     tz_name: str = "Asia/Tokyo",
570:     day_change_at_23: bool = False,
571:     *, day_boundary_hour: int | None = None,
572: ) -> Pillars4:
573:     """四柱（年/月/日/時）をまとめて算出。"""
574:     y, m, _dbg = year_month_pillars(birth_dt, tz_name=tz_name)
575:     day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=day_boundary_hour)
576:     hour = hour_kanshi_from_day_stem_and_time(day[0], birth_dt, tz_name=tz_name)
577:     return Pillars4(year=y, month=m, day=day, hour=hour)
578: 
579: 
580: def _empty_five_counts() -> dict[str, int]:
581:     return {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
582: 
583: 
584: def _five_elements_counts_visible(p: Pillars4) -> dict[str, int]:
585:     """表示用五行カウント（天干+地支のみ）。"""
586:     counts = _empty_five_counts()
587:     for stem in (p.year[0], p.month[0], p.day[0], p.hour[0]):
588:         counts[STEM_ELEMENT.get(stem, "土")] += 1
589:     for br in (p.year[1], p.month[1], p.day[1], p.hour[1]):
590:         counts[BRANCH_ELEMENT.get(br, "土")] += 1
591:     return counts
592: 
593: 
594: def _five_elements_counts_with_hidden(p: Pillars4) -> dict[str, int]:
595:     """蔵干込み五行カウント。"""
596:     counts = _five_elements_counts_visible(p)
597:     for br in (p.year[1], p.month[1], p.day[1], p.hour[1]):
598:         for hs in HIDDEN_STEMS.get(br, []):
599:             counts[STEM_ELEMENT.get(hs, "土")] += 1
600:     return counts
601: 
602: 
603: def _five_elements_counts(p: Pillars4) -> dict[str, Any]:
604:     return {
605:         "visible": _five_elements_counts_visible(p),
606:         "with_hidden_stems": _five_elements_counts_with_hidden(p),
607:     }
608: 
609: 
610: def _ten_gods_for_pillars(p: Pillars4) -> dict[str, Any]:
611:     dm = p.day[0]
612:     out: dict[str, Any] = {
613:         "day_master": dm,
614:         "pillars": {
615:             "year": {"stem": p.year[0], "ten_god": ten_god(dm, p.year[0])},
616:             "month": {"stem": p.month[0], "ten_god": ten_god(dm, p.month[0])},
617:             "hour": {"stem": p.hour[0], "ten_god": ten_god(dm, p.hour[0])},
618:         },
619:         "hidden_stems": {},
620:     }
621:     for key, br in (
622:         ("year", p.year[1]),
623:         ("month", p.month[1]),
624:         ("day", p.day[1]),
625:         ("hour", p.hour[1]),
626:     ):
627:         hs = HIDDEN_STEMS.get(br, [])
628:         out["hidden_stems"][key] = [{"stem": s, "ten_god": ten_god(dm, s)} for s in hs]
629:     return out
630: 
631: 
632: 
633: # =========================
634: # 追加：十二運 / 身強スコア / 大運
635: # =========================
636: 
637: # 十二運（Wikipediaの表に準拠：胎,養,長生,...,絶）
638: # 胎 養 長生 沐浴 冠帯 建禄 帝旺 衰 病 死 墓 絶
639: _TWELVE_FORTUNE_TABLE: dict[str, list[str]] = {
640:     "甲": ["酉","戌","亥","子","丑","寅","卯","辰","巳","午","未","申"],
641:     "乙": ["申","未","午","巳","辰","卯","寅","丑","子","亥","戌","酉"],
642:     "丙": ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"],
643:     "丁": ["亥","戌","酉","申","未","午","巳","辰","卯","寅","丑","子"],
644:     # 土は流派差があるが、本実装は「火土同根」で丙/丁と同形を採用（よく使われる形）
645:     "戊": ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"],
646:     "己": ["亥","戌","酉","申","未","午","巳","辰","卯","寅","丑","子"],
647:     "庚": ["卯","辰","巳","午","未","申","酉","戌","亥","子","丑","寅"],
648:     "辛": ["寅","丑","子","亥","戌","酉","申","未","午","巳","辰","卯"],
649:     "壬": ["午","未","申","酉","戌","亥","子","丑","寅","卯","辰","巳"],
650:     "癸": ["巳","辰","卯","寅","丑","子","亥","戌","酉","申","未","午"],
651: }
652: 
653: _TWELVE_FORTUNE_STAGES = ["胎","養","長生","沐浴","冠帯","建禄","帝旺","衰","病","死","墓","絶"]
654: 
655: # 「強い/弱い」断定を避けるため、ステージにエネルギー値(目安)を付与
656: # （帝旺を最大に近く、絶を最小に近くする単調なスケール）
657: _TWELVE_FORTUNE_ENERGY = {
658:     "胎": 2, "養": 3, "長生": 5, "沐浴": 4, "冠帯": 6, "建禄": 8,
659:     "帝旺": 9, "衰": 7, "病": 4, "死": 3, "墓": 3, "絶": 1,
660: }
661: 
662: 
663: def twelve_fortune(day_stem: str, branch: str) -> str:
664:     """日干×地支 → 十二運（胎〜絶）"""
665:     table = _TWELVE_FORTUNE_TABLE.get(day_stem)
666:     if not table or branch not in table:
667:         return "不明"
668:     idx = table.index(branch)
669:     return _TWELVE_FORTUNE_STAGES[idx]
670: 
671: 
672: def _twelve_fortune_for_pillars(p4: Pillars4) -> dict[str, str]:
673:     dm = p4.day[0]
674:     return {
675:         "year": twelve_fortune(dm, p4.year[1]),
676:         "month": twelve_fortune(dm, p4.month[1]),
677:         "day": twelve_fortune(dm, p4.day[1]),
678:         "hour": twelve_fortune(dm, p4.hour[1]),
679:     }
680: 
681: 
682: def _parse_gender(payload_gender: Any) -> str:
683:     """Keep unrecognized/unspecified gender unknown; never choose a direction."""
684:     g = (str(payload_gender) if payload_gender is not None else "").strip().lower()
685:     if g in ("male", "m", "man", "男性", "男"):
686:         return "male"
687:     if g in ("female", "f", "woman", "女性", "女"):
688:         return "female"
689:     return "unknown"
690: 
691: 
692: def _is_yang_stem(stem: str) -> bool:
693:     # 甲丙戊庚壬 が陽
694:     return stem in ("甲", "丙", "戊", "庚", "壬")
695: 
696: 
697: def _daiun_direction_from_year_stem(year_stem: str, gender: str) -> str | None:
698:     """年干陰陽 × 出生時の性別で大運方向を返す。"""
699:     gender = _parse_gender(gender)
700:     if gender == "unknown":
701:         return None
702:     is_yang = _is_yang_stem(year_stem)
703:     if is_yang:
704:         return "forward" if gender == "male" else "reverse"
705:     return "reverse" if gender == "male" else "forward"
706: 
707: 
708: def _month_branch_element(month_branch: str) -> str:
709:     return BRANCH_ELEMENT.get(month_branch, "土")
710: 
711: 
712: def _calc_strength_score(
713:     p4: Pillars4,
714: ) -> dict[str, Any]:
715:     """身強身弱を“断定せず”スコア化するための材料。
716: 
717:     ここでは厳密な格局判定はせず、次の根拠を点数化する：
718:     - 得令（季節）：月支の五行が日干を助ける/削ぐ
719:     - 通根：日干と同五行の蔵干がどれだけ地支にあるか（特に月支を重視）
720:     - 透干：通根に近い要素が天干に現れているか
721: 
722:     返す score は「目安（0-100）」。
723:     """
724:     dm = p4.day[0]
725:     dm_elem = STEM_ELEMENT[dm]
726:     month_br = p4.month[1]
727:     month_elem = _month_branch_element(month_br)
728: 
729:     breakdown: list[dict[str, Any]] = []
730:     score = 50  # 中央から
731: 
732:     # 1) 得令（季節）
733:     # - 月支五行が日干五行と同じ：+12
734:     # - 月支五行が日干を生じる：+8
735:     # - 月支五行が日干に剋される：-6（消耗）
736:     # - 月支五行が日干を剋す：-12（圧力）
737:     if month_elem == dm_elem:
738:         score += 12
739:         breakdown.append({"name": "得令(同気)", "delta": 12, "detail": f"月支({month_br})={month_elem} が日干({dm})={dm_elem} と同じ"})
740:     elif _element_generate(month_elem) == dm_elem:
741:         score += 8
742:         breakdown.append({"name": "得令(相生)", "delta": 8, "detail": f"月支({month_br})={month_elem} が日干({dm})={dm_elem} を生じる"})
743:     elif _element_control(dm_elem) == month_elem:
744:         score -= 6
745:         breakdown.append({"name": "得令(泄耗)", "delta": -6, "detail": f"日干({dm})={dm_elem} が月支({month_br})={month_elem} を剋す側で消耗しやすい"})
746:     elif _element_control(month_elem) == dm_elem:
747:         score -= 12
748:         breakdown.append({"name": "得令(相剋)", "delta": -12, "detail": f"月支({month_br})={month_elem} が日干({dm})={dm_elem} を剋す"})
749:     else:
750:         breakdown.append({"name": "得令(中立)", "delta": 0, "detail": f"月支({month_br})={month_elem} と日干({dm})={dm_elem} の直接関係が弱い"})
751: 
752:     # 2) 通根（同五行の蔵干）
753:     roots = []
754:     for pillar_name, br in (("month", p4.month[1]), ("day", p4.day[1]), ("hour", p4.hour[1]), ("year", p4.year[1])):
755:         hs = HIDDEN_STEMS.get(br, [])
756:         for s in hs:
757:             if STEM_ELEMENT.get(s) == dm_elem:
758:                 roots.append({"pillar": pillar_name, "branch": br, "hidden_stem": s})
759: 
760:     # 重み：月>日>時>年
761:     w = {"month": 10, "day": 6, "hour": 4, "year": 3}
762:     root_points = 0
763:     for r in roots:
764:         root_points += w.get(r["pillar"], 2)
765:     if roots:
766:         score += min(25, root_points)
767:         breakdown.append({"name": "通根", "delta": min(25, root_points), "detail": f"同五行の蔵干が {len(roots)} 件", "roots": roots})
768:     else:
769:         breakdown.append({"name": "通根", "delta": 0, "detail": "同五行の蔵干が見当たらない（通根弱めの可能性）"})
770: 
771:     # 3) 透干（同五行が天干に見えるか）
772:     visible = []
773:     for pillar_name, stem in (("year", p4.year[0]), ("month", p4.month[0]), ("hour", p4.hour[0])):
774:         if STEM_ELEMENT.get(stem) == dm_elem:
775:             visible.append({"pillar": pillar_name, "stem": stem})
776:     if visible:
777:         delta = 8 + 2 * max(0, len(visible) - 1)
778:         delta = min(delta, 14)
779:         score += delta
780:         breakdown.append({"name": "透干", "delta": delta, "detail": f"同五行の天干が {len(visible)} 件", "visible": visible})
781:     else:
782:         breakdown.append({"name": "透干", "delta": 0, "detail": "同五行の天干は少なめ"})
783: 
784:     # 4) 十二運（四柱の地支に出る“勢い”を軽く加点）
785:     tf = _twelve_fortune_for_pillars(p4)
786:     tf_points = 0
787:     for k, stage in tf.items():
788:         tf_points += _TWELVE_FORTUNE_ENERGY.get(stage, 0)
789:     # 4柱合計を 0-36 くらい → 0-12 に圧縮
790:     delta = int(round(tf_points / 3))
791:     score += delta
792:     breakdown.append({"name": "十二運(合算目安)", "delta": delta, "detail": tf})
793: 
794:     # clamp
795:     score = max(0, min(100, int(round(score))))
796: 
797:     # “身強/身弱”の断定は避け、レンジラベルだけ付ける
798:     if score >= 70:
799:         label = "強め寄り（目安）"
800:     elif score <= 40:
801:         label = "弱め寄り（目安）"
802:     else:
803:         label = "中庸寄り（目安）"
804: 
805:     return {"score": score, "label": label, "breakdown": breakdown}
806: 
807: 
808: def _sexagenary_index(kanshi: str) -> int:
809:     try:
810:         return KANSHI_60.index(kanshi)
811:     except ValueError:
812:         return -1
813: 
814: 
815: def _jieqi_boundary_utc_for_birth_month(
816:     birth_local: datetime,
817:     tz_name: str,
818: ) -> tuple[datetime, datetime]:
819:     """出生が属する節入り区間の境界（前/次）を返す。
820: 
821:     - 月柱判定に使う「30度刻み境界」を“節入り”として扱う。
822:     - 近似でも良いので、AIに渡す際の根拠は debug に残す。
823:     """
824:     tz = ZoneInfo(tz_name)
825:     local_dt = birth_local.astimezone(tz)
826:     utc_dt = local_dt.astimezone(timezone.utc)
827:     jdut = _dt_utc_to_jdut(utc_dt)
828: 
829:     sun_lon = _sun_lon_deg(jdut)
830:     cur_idx = _month_index_from_sun_lon(sun_lon)
831: 
832:     # その月の開始境界と次境界の太陽黄経ターゲット
833:     start_lon = (315 + 30 * cur_idx) % 360
834:     next_lon = (start_lon + 30) % 360
835: 
836:     prev_utc = _solve_time_for_sun_lon_near(jdut, target_lon=start_lon, direction=-1)
837:     next_utc = _solve_time_for_sun_lon_near(jdut, target_lon=next_lon, direction=+1)
838:     return prev_utc, next_utc
839: 
840: 
841: def _solve_time_for_sun_lon_near(jd_start: float, *, target_lon: float, direction: int) -> datetime:
842:     """太陽黄経が target_lon になる時刻(UTC)を近傍探索（簡易二分探索）。
843: 
844:     direction:
845:       +1: 未来方向に探す
846:       -1: 過去方向に探す
847:     """
848:     # 探索幅：最大 40日（節気は約15日〜16日間隔だが30度境界は約30日）
849:     step_days = 1.0
850:     jd0 = jd_start
851:     lon0 = _sun_lon_deg(jd0)
852: 
853:     # 角度差を -180..180 に正規化
854:     def ang_diff(a: float, b: float) -> float:
855:         d = (a - b) % 360.0
856:         if d > 180:
857:             d -= 360
858:         return d
859: 
860:     # bracket
861:     jd_a = jd0
862:     jd_b = jd0
863:     diff_a = ang_diff(lon0, target_lon)
864: 
865:     for _ in range(50):
866:         jd_b = jd_a + direction * step_days
867:         diff_b = ang_diff(_sun_lon_deg(jd_b), target_lon)
868:         # sign change or close enough
869:         if diff_a == 0 or diff_b == 0 or (diff_a > 0) != (diff_b > 0):
870:             break
871:         jd_a = jd_b
872:         diff_a = diff_b
873:         step_days *= 1.2
874:         if step_days > 40:
875:             break
876: 
877:     lo, hi = (jd_a, jd_b) if jd_a < jd_b else (jd_b, jd_a)
878: 
879:     # binary refine
880:     for _ in range(40):
881:         mid = (lo + hi) / 2
882:         diff_mid = ang_diff(_sun_lon_deg(mid), target_lon)
883:         diff_lo = ang_diff(_sun_lon_deg(lo), target_lon)
884:         if diff_mid == 0:
885:             lo = hi = mid
886:             break
887:         if (diff_lo > 0) != (diff_mid > 0):
888:             hi = mid
889:         else:
890:             lo = mid
891: 
892:     jd_final = (lo + hi) / 2
893:     # jdut -> utc datetime
894:     return _jdut_to_datetime_utc(jd_final)
895: 
896: 
897: def _jdut_to_datetime_utc(jdut: float) -> datetime:
898:     # JDUT -> Gregorian UTC datetime
899:     # この用途は“節入り差分”なので秒精度は不要。簡易変換。
900:     # 参考：JD 2440587.5 が Unix epoch (1970-01-01 00:00 UTC)
901:     unix = (jdut - 2440587.5) * 86400.0
902:     return datetime.fromtimestamp(unix, tz=timezone.utc)
903: 
904: 
905: def kubo_from_day_kanshi(day_kanshi: str) -> dict[str, Any]:
906:     idx = _sexagenary_index(day_kanshi)
907:     if idx < 0:
908:         return {
909:             "day_kanshi": day_kanshi,
910:             "jun_index": None,
911:             "jun_label": None,
912:             "empty_branches": [],
913:             "error": "day_kanshi not in KANSHI_60",
914:         }
915:     jun_index = idx // 10
916:     return {
917:         "day_kanshi": day_kanshi,
918:         "jun_index": jun_index,
919:         "jun_label": JUN_LABELS[jun_index],
920:         "empty_branches": KUBO_BY_JUN[jun_index],
921:     }
922: 
923: 
924: def kubo_for_pillars(p4: Pillars4) -> dict[str, Any]:
925:     base = kubo_from_day_kanshi(p4.day)
926:     empty = set(base.get("empty_branches", []))
927:     hits = {
928:         "year": p4.year[1] in empty,
929:         "month": p4.month[1] in empty,
930:         "day": p4.day[1] in empty,
931:         "hour": p4.hour[1] in empty,
932:     }
933:     return {
934:         **base,
935:         "hits": hits,
936:         "hit_pillars": [name for name, hit in hits.items() if hit],
937:         "pillars": {
938:             "year": {"kanshi": p4.year, "branch": p4.year[1]},
939:             "month": {"kanshi": p4.month, "branch": p4.month[1]},
940:             "day": {"kanshi": p4.day, "branch": p4.day[1]},
941:             "hour": {"kanshi": p4.hour, "branch": p4.hour[1]},
942:         },
943:     }
944: 
945: 
946: def _add_calendar_months(dt: datetime, months: int) -> datetime:
947:     """Add calendar months directly to birth; clamp leap/end-of-month dates."""
948:     year, month0 = divmod(dt.year * 12 + dt.month - 1 + months, 12)
949:     month = month0 + 1
950:     return dt.replace(year=year, month=month, day=min(dt.day, calendar.monthrange(year, month)[1]))
951: 
952: 
953: def _calendar_age(birth: datetime, reference: datetime) -> float:
954:     reference = reference.astimezone(birth.tzinfo)
955:     years = reference.year - birth.year
956:     anniversary = _add_calendar_months(birth, years * 12)
957:     if reference < anniversary:
958:         years -= 1
959:         anniversary = _add_calendar_months(birth, years * 12)
960:     next_anniversary = _add_calendar_months(birth, (years + 1) * 12)
961:     return years + (reference - anniversary) / (next_anniversary - anniversary)
962: 
963: 
964: def _calc_daiun(
965:     birth_dt: datetime,
966:     p4: Pillars4,
967:     *,
968:     tz_name: str,
969:     gender: str,
970: ) -> dict[str, Any]:
971:     """大運（10年運）を算出。
972: 
973:     - 順逆：年干の陰陽 × 出生時の性別
974:     - 起運：出生〜節入り差分の近似換算（3日=1年, 1日=4ヶ月）
975:     """
976:     tz = ZoneInfo(tz_name)
977:     local_birth = birth_dt.replace(tzinfo=tz) if birth_dt.tzinfo is None else birth_dt.astimezone(tz)
978: 
979:     gender_norm = _parse_gender(gender)
980:     year_stem = p4.year[0]
981:     direction = _daiun_direction_from_year_stem(year_stem, gender_norm)
982:     if direction is None:
983:         return {
984:             "status": "undetermined_gender", "direction": None, "gender": "unknown",
985:             "start_age": None, "start_age_text": None, "items": [],
986:             "timing_method": "birth_plus_approx_start_age_calendar_months",
987:             "note": "性別未指定のため大運順逆・起運・交運を保留。命式と原局に対する流年は計算済み。",
988:             "debug": {"gender": "unknown", "birth_local": local_birth.isoformat(),
989:                       "direction_rule": "year_stem_yinyang_x_birth_gender"},
990:         }
991:     forward = direction == "forward"
992: 
993:     prev_jieqi_utc, next_jieqi_utc = _jieqi_boundary_utc_for_birth_month(local_birth, tz_name)
994:     birth_utc = local_birth.astimezone(timezone.utc)
995: 
996:     if forward:
997:         delta = next_jieqi_utc - birth_utc
998:         ref = next_jieqi_utc
999:     else:
1000:         delta = birth_utc - prev_jieqi_utc
1001:         ref = prev_jieqi_utc
1002: 
1003:     total_days = max(0.0, delta.total_seconds() / 86400.0)
1004:     years = int(total_days // 3)
1005:     rem_days = total_days - years * 3
1006:     months = int(rem_days) * 4 + int(round((rem_days - int(rem_days)) * 4))
1007:     years += months // 12
1008:     months = months % 12
1009: 
1010:     start_age = {"years": years, "months": months}
1011:     start_age_text = f"{years}年{months}ヶ月"
1012: 
1013:     m_idx = _sexagenary_index(p4.month)
1014:     if m_idx < 0:
1015:         return {
1016:             "direction": direction,
1017:             "gender": gender_norm,
1018:             "start_age": start_age,
1019:             "start_age_text": start_age_text,
1020:             "note": "month_kanshi not in KANSHI_60",
1021:         }
1022: 
1023:     step = 1 if forward else -1
1024:     luck0 = (m_idx + step) % 60
1025: 
1026:     items = []
1027:     age0 = years + months / 12.0
1028:     for i in range(10):
1029:         k = KANSHI_60[(luck0 + step * i) % 60]
1030:         start = _add_calendar_months(local_birth, years * 12 + months + 120 * i)
1031:         end = _add_calendar_months(local_birth, years * 12 + months + 120 * (i + 1))
1032:         items.append({
1033:             "index": i + 1,
1034:             "kanshi": k,
1035:             "age_from": round(age0 + 10 * i, 2),
1036:             "age_to": round(age0 + 10 * (i + 1), 2),
1037:             "approx_start_year": start.year,
1038:             "approx_start_at": start.isoformat(),
1039:             "approx_end_at": end.isoformat(),
1040:         })
1041: 
1042:     debug = {
1043:         "gender": gender_norm,
1044:         "birth_local": local_birth.isoformat(),
1045:         "year_stem": year_stem,
1046:         "year_stem_yang": _is_yang_stem(year_stem),
1047:         "direction_rule": "year_stem_yinyang_x_birth_gender",
1048:         "jieqi_ref_utc": ref.isoformat(),
1049:         "delta_days": round(total_days, 6),
1050:     }
1051: 
1052:     return {
1053:         "status": "determined_direction_approx_timing",
1054:         "direction": direction,
1055:         "gender": gender_norm,
1056:         "start_age": start_age,
1057:         "start_age_text": start_age_text,
1058:         "items": items,
1059:         "timing_method": "birth_plus_approx_start_age_calendar_months",
1060:         "debug": debug,
1061:     }
1062: 
1063: 
1064: def _pillar_dict(kanshi: str) -> dict[str, Any]:
1065:     return {
1066:         "stem": kanshi[0],
1067:         "branch": kanshi[1],
1068:         "kanshi": kanshi,
1069:     }
1070: 
1071: 
1072: def _pillar_items(p4: Pillars4, *, include_day_master: bool = True) -> list[dict[str, str]]:
1073:     items = [
1074:         {"name": "year", "kanshi": p4.year, "stem": p4.year[0], "branch": p4.year[1]},
1075:         {"name": "month", "kanshi": p4.month, "stem": p4.month[0], "branch": p4.month[1]},
1076:         {"name": "day", "kanshi": p4.day, "stem": p4.day[0], "branch": p4.day[1]},
1077:         {"name": "hour", "kanshi": p4.hour, "stem": p4.hour[0], "branch": p4.hour[1]},
1078:     ]
1079:     if include_day_master:
1080:         return items
1081:     return [item for item in items if item["name"] != "day"]
1082: 
1083: 
1084: def _branch_pair_relations(left: dict[str, str], right: dict[str, str]) -> list[dict[str, Any]]:
1085:     b1 = left["branch"]
1086:     b2 = right["branch"]
1087:     pair = frozenset((b1, b2))
1088:     relations: list[dict[str, Any]] = []
1089: 
1090:     if b1 == b2 and b1 in BRANCH_SELF_PUNISHMENTS:
1091:         relations.append({
1092:             "type": "self_punishment",
1093:             "type_ja": "自刑",
1094:             "detail": f"{b1}{b2}",
1095:         })
1096:     if pair in BRANCH_PUNISHMENTS:
1097:         relations.append({
1098:             "type": "punishment",
1099:             "type_ja": "刑",
1100:             "detail": BRANCH_PUNISHMENTS[pair],
1101:         })
1102:     if pair in BRANCH_CLASHES:
1103:         relations.append({
1104:             "type": "clash",
1105:             "type_ja": "冲",
1106:             "detail": f"{b1}{b2}冲",
1107:         })
1108:     if pair in BRANCH_SIX_HARMONIES:
1109:         relations.append({
1110:             "type": "six_harmony",
1111:             "type_ja": "六合",
1112:             "element": BRANCH_SIX_HARMONIES[pair],
1113:             "detail": f"{b1}{b2}合",
1114:         })
1115:     if pair in BRANCH_HARMS:
1116:         relations.append({
1117:             "type": "harm",
1118:             "type_ja": "害",
1119:             "detail": f"{b1}{b2}害",
1120:         })
1121:     if pair in BRANCH_DESTRUCTIONS:
1122:         relations.append({"type": "destruction", "type_ja": "破", "detail": f"{b1}{b2}破"})
1123:     return relations
1124: 
1125: 
1126: def _stem_pair_relations(left: dict[str, str], right: dict[str, str]) -> list[dict[str, Any]]:
1127:     s1 = left["stem"]
1128:     s2 = right["stem"]
1129:     pair = frozenset((s1, s2))
1130:     if pair not in STEM_COMBINATIONS:
1131:         return []
1132:     return [{
1133:         "type": "stem_combination",
1134:         "type_ja": "干合",
1135:         "element": STEM_COMBINATIONS[pair],
1136:         "detail": f"{s1}{s2}合",
1137:     }]
1138: 
1139: 
1140: def _format_relation(left: dict[str, str], right: dict[str, str], relation: dict[str, Any]) -> dict[str, Any]:
1141:     return {
1142:         "left": left,
1143:         "right": right,
1144:         **relation,
1145:     }
1146: 
1147: 
1148: def _branch_triads(items: list[dict[str, str]]) -> list[dict[str, Any]]:
1149:     out: list[dict[str, Any]] = []
1150:     branches = {item["branch"] for item in items}
1151:     for triad, label in BRANCH_TRIADS.items():
1152:         hit = branches.intersection(triad)
1153:         if len(hit) == 3:
1154:             level = "full"
1155:             type_ja = "三合"
1156:         elif len(hit) == 2:
1157:             level = "partial"
1158:             type_ja = "半会"
1159:         else:
1160:             continue
1161:         out.append({
1162:             "type": "triad",
1163:             "type_ja": type_ja,
1164:             "level": level,
1165:             "group": label,
1166:             "branches": sorted(hit, key=lambda x: BRANCHES.index(x)),
1167:             "pillars": [item for item in items if item["branch"] in hit],
1168:         })
1169:     return out
1170: 
1171: 
1172: def _branch_three_punishments(items: list[dict[str, str]]) -> list[dict[str, Any]]:
1173:     out: list[dict[str, Any]] = []
1174:     branches = {item["branch"] for item in items}
1175:     for group, label in BRANCH_THREE_PUNISHMENTS.items():
1176:         hit = branches.intersection(group)
1177:         if len(hit) == 3:
1178:             level = "full"
1179:         elif len(hit) == 2:
1180:             level = "partial"
1181:         else:
1182:             continue
1183:         out.append({
1184:             "type": "three_punishment",
1185:             "type_ja": "三刑",
1186:             "level": level,
1187:             "detail": label,
1188:             "branches": sorted(hit, key=lambda x: BRANCHES.index(x)),
1189:             "pillars": [item for item in items if item["branch"] in hit],
1190:         })
1191:     return out
1192: 
1193: 
1194: def _interactions_for_items(items: list[dict[str, str]]) -> dict[str, Any]:
1195:     branch_relations: list[dict[str, Any]] = []
1196:     stem_relations: list[dict[str, Any]] = []
1197:     for i, left in enumerate(items):
1198:         for right in items[i + 1:]:
1199:             for rel in _branch_pair_relations(left, right):
1200:                 branch_relations.append(_format_relation(left, right, rel))
1201:             for rel in _stem_pair_relations(left, right):
1202:                 stem_relations.append(_format_relation(left, right, rel))
1203:     return {
1204:         "branch_relations": branch_relations,
1205:         "stem_relations": stem_relations,
1206:         "triads": _branch_triads(items),
1207:         "three_punishments": _branch_three_punishments(items),
1208:     }
1209: 
1210: 
1211: def _current_daiun_item(
1212:     daiun: dict[str, Any], *, birth_year: int, current_year: int, current_dt: datetime | None = None,
1213: ) -> dict[str, Any] | None:
1214:     age = current_year - birth_year
1215:     if current_dt is not None and daiun.get("debug", {}).get("birth_local"):
1216:         age = round(_calendar_age(datetime.fromisoformat(daiun["debug"]["birth_local"]), current_dt), 4)
1217:     for item in daiun.get("items", []) or []:
1218:         if current_dt is not None and item.get("approx_start_at") and item.get("approx_end_at"):
1219:             if datetime.fromisoformat(item["approx_start_at"]) <= current_dt < datetime.fromisoformat(item["approx_end_at"]):
1220:                 return {**item, "current_age_approx": age, "selection_basis": "approx_calendar_interval"}
1221:             continue
1222:         if item.get("age_from") is None or item.get("age_to") is None:
1223:             continue
1224:         if float(item["age_from"]) <= age < float(item["age_to"]):
1225:             return {**item, "current_age_approx": age}
1226:     return None
1227: 
1228: 
1229: def _annual_fortune(
1230:     p4: Pillars4,
1231:     daiun: dict[str, Any],
1232:     *,
1233:     birth_year: int,
1234:     current_dt: datetime,
1235:     tz_name: str,
1236:     include_hour: bool = True,
1237: ) -> dict[str, Any]:
1238:     tz = ZoneInfo(tz_name)
1239:     local_dt = current_dt.astimezone(tz)
1240:     current_year = local_dt.year
1241:     lichun_local = _lichun_utc_for_year(current_year, tz_name).astimezone(tz)
1242:     effective_year = current_year if local_dt >= lichun_local else current_year - 1
1243:     kanshi = _year_kanshi_from_effective_year(effective_year)
1244:     annual_item = {
1245:         "name": "annual",
1246:         "kanshi": kanshi,
1247:         "stem": kanshi[0],
1248:         "branch": kanshi[1],
1249:     }
1250:     natal_items = [p for p in _pillar_items(p4) if include_hour or p["name"] != "hour"]
1251:     daiun_item = _current_daiun_item(daiun, birth_year=birth_year, current_year=current_year, current_dt=local_dt)
1252: 
1253:     relation_targets = natal_items[:]
1254:     if daiun_item and daiun_item.get("kanshi"):
1255:         dk = str(daiun_item["kanshi"])
1256:         relation_targets.append({"name": "current_daiun", "kanshi": dk, "stem": dk[0], "branch": dk[1]})
1257: 
1258:     branch_relations: list[dict[str, Any]] = []
1259:     stem_relations: list[dict[str, Any]] = []
1260:     for target in relation_targets:
1261:         for rel in _branch_pair_relations(annual_item, target):
1262:             branch_relations.append(_format_relation(annual_item, target, rel))
1263:         for rel in _stem_pair_relations(annual_item, target):
1264:             stem_relations.append(_format_relation(annual_item, target, rel))
1265: 
1266:     return {
1267:         "year": current_year,
1268:         "effective_year": effective_year,
1269:         "kanshi": kanshi,
1270:         "stem": kanshi[0],
1271:         "branch": kanshi[1],
1272:         "ten_god_to_day_master": ten_god(p4.day[0], kanshi[0]),
1273:         "twelve_fortune_to_day_master": twelve_fortune(p4.day[0], kanshi[1]),
1274:         "current_daiun": daiun_item,
1275:         "daiun_direction_status": daiun.get("status"),
1276:         "natal_time_basis": "four_pillars" if include_hour else "three_pillars_hour_excluded",
1277:         "relations": {
1278:             "branch_relations": branch_relations,
1279:             "stem_relations": stem_relations,
1280:             "triads_with_natal": _branch_triads([annual_item, *natal_items]),
1281:             "triads_with_natal_and_daiun": _branch_triads([annual_item, *relation_targets]),
1282:             "three_punishments_with_natal": _branch_three_punishments([annual_item, *natal_items]),
1283:             "three_punishments_with_natal_and_daiun": _branch_three_punishments([annual_item, *relation_targets]),
1284:         },
1285:         "debug": {
1286:             "calculated_at": local_dt.isoformat(),
1287:             "lichun_local": lichun_local.isoformat(),
1288:             "year_boundary_rule": "lichun(315deg)",
1289:         },
1290:     }
1291: 
1292: 
1293: def _shinsatsu_hits_by_branch(
1294:     *,
1295:     name: str,
1296:     name_ja: str,
1297:     basis: dict[str, Any],
1298:     target_branches: list[str],
1299:     pillar_items: list[dict[str, str]],
1300: ) -> dict[str, Any]:
1301:     hits = [
1302:         {
1303:             "pillar": item["name"],
1304:             "kanshi": item["kanshi"],
1305:             "branch": item["branch"],
1306:         }
1307:         for item in pillar_items
1308:         if item["branch"] in target_branches
1309:     ]
1310:     return {
1311:         "name": name,
1312:         "name_ja": name_ja,
1313:         "basis": basis,
1314:         "targets": [{"type": "branch", "value": br} for br in target_branches],
1315:         "hits": hits,
1316:         "hit": bool(hits),
1317:     }
1318: 
1319: 
1320: def _shinsatsu_hits_by_stem_or_branch(
1321:     *,
1322:     name: str,
1323:     name_ja: str,
1324:     basis: dict[str, Any],
1325:     target: str | None,
1326:     pillar_items: list[dict[str, str]],
1327: ) -> dict[str, Any]:
1328:     if not target:
1329:         return {
1330:             "name": name,
1331:             "name_ja": name_ja,
1332:             "basis": basis,
1333:             "targets": [],
1334:             "hits": [],
1335:             "hit": False,
1336:         }
1337:     target_type = "stem" if target in STEMS else "branch"
1338:     hits = []
1339:     for item in pillar_items:
1340:         if target_type == "stem" and item["stem"] == target:
1341:             hits.append({"pillar": item["name"], "kanshi": item["kanshi"], "stem": item["stem"]})
1342:         elif target_type == "branch" and item["branch"] == target:
1343:             hits.append({"pillar": item["name"], "kanshi": item["kanshi"], "branch": item["branch"]})
1344:     return {
1345:         "name": name,
1346:         "name_ja": name_ja,
1347:         "basis": basis,
1348:         "targets": [{"type": target_type, "value": target}],
1349:         "hits": hits,
1350:         "hit": bool(hits),
1351:     }
1352: 
1353: 
1354: def _shinsatsu_for_pillars(p4: Pillars4) -> dict[str, Any]:
1355:     pillar_items = _pillar_items(p4)
1356:     day_stem = p4.day[0]
1357:     month_branch = p4.month[1]
1358:     tenotsu_targets = TENOTSU_KIJIN_BY_DAY_STEM.get(day_stem, [])
1359:     bunsho_targets = BUNSHO_BY_DAY_STEM.get(day_stem, [])
1360:     tentoku_target = TENTOKU_BY_MONTH_BRANCH.get(month_branch)
1361:     stars = [
1362:         _shinsatsu_hits_by_branch(
1363:             name="tenotsu_kijin",
1364:             name_ja="天乙貴人",
1365:             basis={"type": "day_stem", "value": day_stem},
1366:             target_branches=tenotsu_targets,
1367:             pillar_items=pillar_items,
1368:         ),
1369:         _shinsatsu_hits_by_branch(
1370:             name="bunsho",
1371:             name_ja="文昌",
1372:             basis={"type": "day_stem", "value": day_stem},
1373:             target_branches=bunsho_targets,
1374:             pillar_items=pillar_items,
1375:         ),
1376:         _shinsatsu_hits_by_stem_or_branch(
1377:             name="tentoku",
1378:             name_ja="天徳",
1379:             basis={"type": "month_branch", "value": month_branch},
1380:             target=tentoku_target,
1381:             pillar_items=pillar_items,
1382:         ),
1383:     ]
1384:     return {
1385:         "calc_policy": {
1386:             "tenotsu_kijin": "day_stem_to_branch",
1387:             "bunsho": "day_stem_to_branch",
1388:             "tentoku": "month_branch_to_stem_or_branch",
1389:             "note": "神殺は流派差があるため、代表的な表に基づく補助情報として扱う",
1390:         },
1391:         "stars": stars,
1392:         "hit_stars": [star for star in stars if star.get("hit")],
1393:     }
1394: 
1395: 
1396: def _build_unknowns(payload: dict[str, Any], *, day_change_at_23: bool, day_boundary_hour: int | None = None) -> list[str]:
1397:     unknowns: list[str] = []
1398:     if payload.get("hour") in (None, "", "不明"):
1399:         unknowns.append("出生時刻が未入力のため 12:00 を仮置きして計算")
1400:     if payload.get("minute") in (None, "", "不明"):
1401:         unknowns.append("出生分が未入力のため 00 分として計算")
1402:     boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
1403:     unknowns.append(f"日替わり境界は {boundary:02d}:00 切替設定を使用（出生地の現地暦日）")
1404:     if _parse_gender(payload.get("gender")) == "unknown":
1405:         unknowns.append("性別未指定のため大運順逆・起運は未確定。大運を女性扱いで補完しない")
1406:     unknowns.append("大運開始年齢は簡易換算（3日=1年, 1日=4ヶ月）")
1407:     return unknowns
1408: 
1409: 
1410: def _build_structure_report(
1411:     p4: Pillars4,
1412:     strength: dict[str, Any],
1413:     five: dict[str, Any],
1414:     ten: dict[str, Any],
1415:     tf: dict[str, str],
1416:     daiun: dict[str, Any],
1417: ) -> dict[str, Any]:
1418:     dm = p4.day[0]
1419:     dm_elem = STEM_ELEMENT[dm]
1420:     month_branch = p4.month[1]
1421:     month_element = _month_branch_element(month_branch)
1422: 
1423:     if month_element == dm_elem:
1424:         relation = "same_element"
1425:     elif _element_generate(month_element) == dm_elem:
1426:         relation = "generated_by_month"
1427:     elif _element_control(month_element) == dm_elem:
1428:         relation = "controlled_by_month"
1429:     elif _element_control(dm_elem) == month_element:
1430:         relation = "day_master_controls_month"
1431:     elif _element_generate(dm_elem) == month_element:
1432:         relation = "day_master_generates_month"
1433:     else:
1434:         relation = "neutral"
1435: 
1436:     hidden = ten.get("hidden_stems", {}) if isinstance(ten, dict) else {}
1437:     roots_count = 0
1438:     for items in hidden.values():
1439:         if isinstance(items, list):
1440:             for item in items:
1441:                 stem = item.get("stem") if isinstance(item, dict) else None
1442:                 if stem and STEM_ELEMENT.get(stem) == dm_elem:
1443:                     roots_count += 1
1444: 
1445:     visible_same = 0
1446:     for pillar_name in ("year", "month", "hour"):
1447:         pillar = ten.get("pillars", {}).get(pillar_name, {}) if isinstance(ten, dict) else {}
1448:         stem = pillar.get("stem") if isinstance(pillar, dict) else None
1449:         if stem and STEM_ELEMENT.get(stem) == dm_elem:
1450:             visible_same += 1
1451: 
1452:     tf_total = sum(_TWELVE_FORTUNE_ENERGY.get(stage, 0) for stage in tf.values())
1453: 
1454:     dominant_features: list[str] = []
1455:     visible_counts = five.get("visible", {}) if isinstance(five, dict) else {}
1456:     if isinstance(visible_counts, dict) and visible_counts:
1457:         ordered = sorted(visible_counts.items(), key=lambda kv: (-kv[1], kv[0]))
1458:         top_elem, top_count = ordered[0]
1459:         bottom_elem, bottom_count = sorted(visible_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
1460:         dominant_features.append(f"visible五行で {top_elem} が相対的に多い ({top_count})")
1461:         dominant_features.append(f"visible五行で {bottom_elem} が相対的に少ない ({bottom_count})")
1462:     dominant_features.append(f"月支は {month_branch} ({month_element})")
1463:     dominant_features.append(f"大運方向は {daiun['direction']}" if daiun.get("direction") else "大運方向は未確定（性別未指定）")
1464: 
1465:     notes = [
1466:         "年柱は立春基準、月柱は節入り基準で判定",
1467:         "AI翻訳前の構造材料として整理されたデータ",
1468:     ]
1469: 
1470:     return {
1471:         "day_master": dm,
1472:         "day_master_element": dm_elem,
1473:         "seasonal_context": {
1474:             "month_branch": month_branch,
1475:             "month_element": month_element,
1476:             "relation_to_day_master": relation,
1477:         },
1478:         "strength_index": {
1479:             "score": strength.get("score"),
1480:             "label": strength.get("label"),
1481:             "breakdown": strength.get("breakdown", []),
1482:         },
1483:         "support_signals": {
1484:             "roots_count": roots_count,
1485:             "visible_same_element_count": visible_same,
1486:             "twelve_fortune_total": tf_total,
1487:         },
1488:         "dominant_features": dominant_features,
1489:         "notes": notes,
1490:     }
1491: 
1492: 
1493: def calc_shichusuimei_from_payload(
1494:     payload: dict[str, Any],
1495:     *,
1496:     tz_name: str = "Asia/Tokyo",
1497:     day_change_at_23: bool = False,
1498:     as_of: datetime | None = None,
1499:     annual_years: int = 10,
1500:     day_boundary_hour: int | None = None,
1501: ) -> dict[str, Any]:
1502:     """routes.py の payload から四柱推命結果を作る。
1503: 
1504:     返却は従来互換キーを残しつつ、StructurePayload 寄りの
1505:     input / unknowns / normalized_data / structure_report を含める。
1506:     """
1507:     if not isinstance(annual_years, int) or isinstance(annual_years, bool) or not 1 <= annual_years <= 20:
1508:         raise ValueError("annual_years must be an integer between 1 and 20")
1509:     boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
1510:     day_change_at_23 = boundary == 23
1511:     current_dt = as_of or datetime.now(ZoneInfo(tz_name))
1512:     if current_dt.tzinfo is None:
1513:         raise ValueError("as_of must be timezone-aware")
1514:     current_dt = current_dt.astimezone(ZoneInfo(tz_name))
1515:     raw_hour = payload.get("hour")
1516:     raw_minute = payload.get("minute", 0)
1517:     hour = 12 if raw_hour in (None, "") else int(raw_hour)
1518:     minute = 0 if raw_minute in (None, "") else int(raw_minute)
1519:     time_accuracy = payload.get("birth_time_accuracy") or ("exact" if raw_hour not in (None, "") else "unknown")
1520:     if raw_hour in (None, ""):
1521:         time_accuracy = "unknown"
1522:     elif time_accuracy == "auto":
1523:         time_accuracy = "exact"
1524:     time_reliable = time_accuracy == "exact" and raw_hour not in (None, "")
1525:     dt = datetime(
1526:         int(payload["year"]),
1527:         int(payload["month"]),
1528:         int(payload["day"]),
1529:         hour,
1530:         minute,
1531:         0,
1532:     )
1533: 
1534:     dt = resolve_birth_datetime(dt, tz_name, fold=payload.get("birth_fold"), utc_offset_hours=payload.get("birth_utc_offset_hours"))
1535:     effective_date, boundary_label = _effective_local_date_for_day_pillar(dt, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
1536:     time_context = {
1537:         "local_datetime": dt.isoformat(), "timezone": tz_name,
1538:         "utc_offset_hours": dt.utcoffset().total_seconds() / 3600,
1539:         "utc_datetime": dt.astimezone(timezone.utc).isoformat(), "fold": dt.fold,
1540:         "day_pillar_reference_datetime": dt.isoformat(), "day_pillar_date": effective_date.isoformat(),
1541:         "day_boundary_hour": boundary, "day_boundary_rule": boundary_label,
1542:         "calendar_time_basis": "local_civil_time", "true_solar_time_applied": False,
1543:         "astronomical_time_basis": "UTC_for_solar_terms",
1544:     }
1545:     p4 = pillars4(dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
1546:     _, _, ym_debug = year_month_pillars(dt, tz_name=tz_name)
1547: 
1548:     five = _five_elements_counts(p4)
1549:     ten = _ten_gods_for_pillars(p4)
1550:     tf = _twelve_fortune_for_pillars(p4)
1551:     strength = _calc_strength_score(p4)
1552:     daiun = _calc_daiun(dt, p4, tz_name=tz_name, gender=payload.get("gender"))
1553:     kubo = kubo_for_pillars(p4)
1554:     interactions = _interactions_for_items([p for p in _pillar_items(p4) if time_reliable or p["name"] != "hour"])
1555:     interactions["time_basis"] = "four_pillars" if time_reliable else "three_pillars_hour_excluded"
1556:     shinsatsu = _shinsatsu_for_pillars(p4)
1557:     annual_fortune = _annual_fortune(
1558:         p4,
1559:         daiun,
1560:         birth_year=int(payload["year"]),
1561:         current_dt=current_dt,
1562:         tz_name=tz_name,
1563:         include_hour=time_reliable,
1564:     )
1565: 
1566:     hidden_all = {
1567:         "year": HIDDEN_STEMS.get(p4.year[1], []),
1568:         "month": HIDDEN_STEMS.get(p4.month[1], []),
1569:         "day": HIDDEN_STEMS.get(p4.day[1], []),
1570:         "hour": HIDDEN_STEMS.get(p4.hour[1], []),
1571:     }
1572:     hidden_main = {k: (v[0] if v else None) for k, v in hidden_all.items()}
1573:     gender_norm = _parse_gender(payload.get("gender"))
1574:     unknowns = _build_unknowns(payload, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
1575: 
1576:     from services.shichusuimei_structure import analyze_structure, analyze_luck, concurrent_luck_analysis
1577:     if not time_reliable:
1578:         unknowns.append("構造分析は時柱を除外。従来キーの時柱・五行・身強スコアは仮置き／推定時刻の参考値")
1579:     structural_analysis = analyze_structure(p4, time_reliable=time_reliable)
1580:     for item in daiun.get("items", []):
1581:         item["structural_analysis"] = analyze_luck(
1582:             p4, item["kanshi"], time_reliable=time_reliable, structural_analysis=structural_analysis,
1583:         )
1584:     current_daiun = annual_fortune.get("current_daiun") or {}
1585:     annual_fortune["structural_analysis"] = analyze_luck(
1586:         p4, annual_fortune["kanshi"], time_reliable=time_reliable,
1587:         other_luck=current_daiun.get("kanshi"), structural_analysis=structural_analysis,
1588:     )
1589:     forecasts = []
1590:     first_year = annual_fortune["effective_year"]
1591:     boundaries = {year: _lichun_utc_for_year(year, tz_name).astimezone(ZoneInfo(tz_name))
1592:                   for year in range(first_year, first_year + annual_years + 1)}
1593:     for year in range(first_year, first_year + annual_years):
1594:         annual_kanshi = _year_kanshi_from_effective_year(year)
1595:         year_start, year_end = boundaries[year], boundaries[year + 1]
1596:         # Intersect actual calendar periods; a rounded integer year-age shifts late births.
1597:         contexts = [item for item in daiun.get("items", [])
1598:                     if datetime.fromisoformat(item["approx_start_at"]) < year_end
1599:                     and datetime.fromisoformat(item["approx_end_at"]) > year_start]
1600:         forecasts.append({
1601:             "effective_year": year, "kanshi": annual_kanshi,
1602:             "year_boundary_rule": "lichun(315deg)",
1603:             "period_start": year_start.isoformat(), "period_end": year_end.isoformat(),
1604:             "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
1605:             "daiun_direction_status": daiun["status"],
1606:             "daiun_boundary_in_window": any(
1607:                 year_start <= datetime.fromisoformat(item["approx_start_at"]) < year_end
1608:                 or year_start < datetime.fromisoformat(item["approx_end_at"]) <= year_end for item in contexts
1609:             ),
1610:             "natal_analysis": analyze_luck(
1611:                 p4, annual_kanshi, time_reliable=time_reliable, structural_analysis=structural_analysis,
1612:             ),
1613:             "daiun_contexts": [{
1614:                 "index": item["index"], "kanshi": item["kanshi"],
1615:                 "age_from": item["age_from"], "age_to": item["age_to"],
1616:                 "overlap_start_approx": max(year_start, datetime.fromisoformat(item["approx_start_at"])).isoformat(),
1617:                 "overlap_end_approx": min(year_end, datetime.fromisoformat(item["approx_end_at"])).isoformat(),
1618:                 "analysis": concurrent_luck_analysis(analyze_luck(
1619:                     p4, annual_kanshi, time_reliable=time_reliable,
1620:                     other_luck=item["kanshi"], structural_analysis=structural_analysis,
1621:                 )),
1622:             } for item in contexts],
1623:         })
1624:     annual_forecasts = {
1625:         "start_effective_year": annual_fortune["effective_year"], "years": annual_years,
1626:         "items": forecasts,
1627:         "daiun_direction_status": daiun["status"],
1628:         "note": "流年は立春から翌立春まで。大運は出生日時に近似起運年齢の年月を加えた期間で対応付け。交運日時は近似であり確定しない",
1629:     }
1630: 
1631:     normalized_data = {
1632:         "pillars": {
1633:             "year": _pillar_dict(p4.year),
1634:             "month": _pillar_dict(p4.month),
1635:             "day": _pillar_dict(p4.day),
1636:             "hour": _pillar_dict(p4.hour),
1637:         },
1638:         "hidden_stems": hidden_all,
1639:         "main_hidden_stems": hidden_main,
1640:         "ten_gods": ten,
1641:         "five_elements": {
1642:             **five,
1643:             "display_policy": "visible",
1644:         },
1645:         "twelve_fortune": tf,
1646:         "kubo": kubo,
1647:         "daiun": {
1648:             **daiun,
1649:             "calc_mode": "approx",
1650:         },
1651:         "interactions": interactions,
1652:         "annual_fortune": annual_fortune,
1653:         "shinsatsu": shinsatsu,
1654:         "structural_analysis": structural_analysis,
1655:         "annual_forecasts": annual_forecasts,
1656:     }
1657:     if not time_reliable:
1658:         normalized_data["time_sensitive_reference"] = {
1659:             "birth_time_accuracy": time_accuracy, "assumed_time": f"{hour:02d}:{minute:02d}",
1660:             "valid_for_assertive_interpretation": False,
1661:             "reference_only_metrics": ["five_elements", "features.strength", "structure_report.strength_index", "structure_report.support_signals"],
1662:             "hour_reference_only_sections": ["pillars.hour", "hidden_stems.hour", "ten_gods.hidden_stems.hour", "ten_gods.pillars.hour", "twelve_fortune.hour", "kubo", "shinsatsu"],
1663:             "note": "時柱を含む旧集計は参考値。原局・流年の関係と新しい構造分析は時柱を除外",
1664:         }
1665: 
1666:     structure_report = _build_structure_report(
1667:         p4=p4,
1668:         strength=strength,
1669:         five=five,
1670:         ten=ten,
1671:         tf=tf,
1672:         daiun=daiun,
1673:     )
1674: 
1675:     return {
1676:         "module": "shichusuimei",
1677:         "system": "shichusuimei",
1678:         "ephemeris": ephemeris_debug_info(),
1679:         "engine_version": ENGINE_VERSION,
1680:         "generated_at": current_dt.isoformat(),
1681:         "input": {
1682:             "raw": {
1683:                 "year": int(payload["year"]),
1684:                 "month": int(payload["month"]),
1685:                 "day": int(payload["day"]),
1686:                 "hour": hour,
1687:                 "minute": minute,
1688:                 "gender": gender_norm,
1689:                 "gender_supplied": payload.get("gender"),
1690:                 "city": payload.get("city"),
1691:                 "lat": payload.get("lat"),
1692:                 "lng": payload.get("lng"),
1693:             },
1694:             "assumptions": {
1695:                 "tz_name": tz_name,
1696:                 "day_change_at_23": day_change_at_23,
1697:                 "day_boundary_hour": boundary,
1698:                 "day_boundary_rule": boundary_label,
1699:                 "year_boundary_rule": "lichun(315deg)",
1700:                 "month_boundary_rule": "solar_terms(315deg+30deg_step)",
1701:                 "daiun_start_mode": "approx_days_to_years",
1702:                 "birth_time_accuracy": time_accuracy,
1703:                 "structural_time_basis": structural_analysis["methodology"]["time_basis"],
1704:             },
1705:             "time_context": time_context,
1706:         },
1707:         "unknowns": unknowns,
1708:         "normalized_data": normalized_data,
1709:         "structure_report": structure_report,
1710:         "debug": {
1711:             "year_month": ym_debug,
1712:             "daiun": daiun.get("debug", {}),
1713:         },
1714:         # backward compatibility for current templates / prompts
1715:         "pillars": asdict(p4),
1716:         "day_master": p4.day[0],
1717:         "raw": {
1718:             "pillars": asdict(p4),
1719:             "options": {
1720:                 "tz_name": tz_name,
1721:                 "day_change_at_23": day_change_at_23,
1722:                 "day_boundary_hour": boundary,
1723:                 "day_boundary_rule": boundary_label,
1724:                 "year_boundary": "lichun(315deg)",
1725:                 "month_boundary": "solar_terms(315deg+30deg_step)",
1726:             },
1727:             "debug": {"year_month": ym_debug},
1728:         },
1729:         "features": {
1730:             "five_elements": normalized_data["five_elements"],
1731:             "ten_gods": ten,
1732:             "twelve_fortune": tf,
1733:             "strength": strength,
1734:             "daiun": normalized_data["daiun"],
1735:             "annual_fortune": annual_fortune,
1736:             "interactions": interactions,
1737:             "shinsatsu": shinsatsu,
1738:             "hidden_stems": hidden_all,
1739:             "main_hidden_stems": hidden_main,
1740:             "kubo": kubo,
1741:         },
1742:         "summary": {
1743:             "year_kanshi": p4.year,
1744:             "month_kanshi": p4.month,
1745:             "day_kanshi": p4.day,
1746:             "hour_kanshi": p4.hour,
1747:         },
1748:     }
```


## services/shichusuimei_annual_report.py
```text
1: """One Lichun year of calculation data, separate from the saved Full YAML."""
2: from __future__ import annotations
3: 
4: from copy import deepcopy
5: from datetime import datetime
6: from itertools import combinations
7: from zoneinfo import ZoneInfo
8: 
9: import yaml
10: 
11: from services import shichusuimei_calc as core
12: 
13: # Same published solar-ephemeris window as the existing ACG service; the end
14: # boundary (Lichun 2400) is also supported. No birth-age/current-year restriction.
15: MIN_YEAR = 1800
16: MAX_YEAR = 2399
17: 
18: 
19: def validate_selected_year(year: int) -> None:
20:     if type(year) is not int or not MIN_YEAR <= year <= MAX_YEAR:
21:         raise ValueError(f"対象年は{MIN_YEAR}〜{MAX_YEAR}年の整数で指定してください。")
22: 
23: 
24: def _item(name: str, kanshi: str) -> dict:
25:     if kanshi not in core.KANSHI_60:
26:         raise ValueError("基礎命式の干支が不正です。")
27:     return {"name": name, **core._pillar_dict(kanshi)}
28: 
29: 
30: def _scope(items: list[dict], required: set[str]) -> list[dict]:
31:     """Cross-source pairs and distinct-branch group witnesses, with provenance.
32: 
33:     A repeated branch cannot supply two members of a triad. Alternative natal
34:     placements are recorded on one group, rather than counted as new groups.
35:     """
36:     def sources(participants):
37:         return {p["name"] if p["name"] in {"annual", "daiun"} else "natal" for p in participants}
38: 
39:     pairs = core._interactions_for_items(items)
40:     result = [r for key in ("branch_relations", "stem_relations") for r in pairs[key]
41:               if sources([r["left"], r["right"]]) == required]
42:     groups = {}
43:     for size in (2, 3):
44:         for witness in combinations(items, size):
45:             if sources(witness) != required or len({p["branch"] for p in witness}) != size:
46:                 continue
47:             relations = core._branch_triads(list(witness)) + core._branch_three_punishments(list(witness))
48:             for r in relations:
49:                 if len(r["branches"]) != size:
50:                     continue
51:                 key = (r["type"], r.get("group", r.get("detail")), tuple(r["branches"]))
52:                 if key not in groups:
53:                     groups[key] = {k: v for k, v in r.items() if k != "pillars"}
54:                     groups[key]["participant_sets"] = []
55:                 groups[key]["participant_sets"].append(list(witness))
56:     for r in groups.values():
57:         if r["level"] == "partial" and any(
58:             full["type"] == r["type"] and full["level"] == "full"
59:             and set(r["branches"]) <= set(full["branches"]) for full in groups.values()
60:         ):
61:             continue
62:         result.append(r)
63:     for r in result:
64:         if r["type"] in {"stem_combination", "six_harmony", "triad"}:
65:             r["element_change_applied"] = False
66:     return result
67: 
68: 
69: def _counts(items: list[dict]) -> dict:
70:     visible = core._empty_five_counts()
71:     hidden = core._empty_five_counts()
72:     for item in items:
73:         visible[core.STEM_ELEMENT[item["stem"]]] += 1
74:         visible[core.BRANCH_ELEMENT[item["branch"]]] += 1
75:         for stem in core.HIDDEN_STEMS[item["branch"]]:
76:             hidden[core.STEM_ELEMENT[stem]] += 1
77:     return {"visible": visible, "with_hidden_stems": {e: n + hidden[e] for e, n in visible.items()}}
78: 
79: 
80: def _project_periods(birth: datetime, first_kanshi: str, direction: str, years: int, months: int, count: int) -> list[dict]:
81:     """Project saved starting parameters; do not recalculate the starting age.
82: 
83:     This is an isolated prototype adapter. The existing engine and its default
84:     ten periods are untouched. Calendar arithmetic reuses the engine helper.
85:     """
86:     first = core.KANSHI_60.index(first_kanshi)
87:     step = 1 if direction == "forward" else -1
88:     age0 = years + months / 12
89:     result = []
90:     for i in range(count):
91:         start = core._add_calendar_months(birth, years * 12 + months + 120 * i)
92:         end = core._add_calendar_months(birth, years * 12 + months + 120 * (i + 1))
93:         result.append({"index": i + 1, "kanshi": core.KANSHI_60[(first + step * i) % 60],
94:                        "age_from": round(age0 + 10 * i, 2), "age_to": round(age0 + 10 * (i + 1), 2),
95:                        "approx_start_year": start.year, "approx_start_at": start.isoformat(), "approx_end_at": end.isoformat()})
96:     return result
97: 
98: 
99: def _daiun_periods(shichu: dict, data: dict, year: int, tz: ZoneInfo) -> list[dict]:
100:     daiun = data.get("daiun") or {}
101:     if daiun.get("status") == "undetermined_gender":
102:         return []
103:     saved = daiun.get("items") or []
104:     if not saved:
105:         raise ValueError("基礎命式に大運の計算結果がありません。基礎命式を再発行してください。")
106:     # Reconstruct old YAML calendar intervals from its saved start age, without
107:     # recalculating either the natal pillars or the solar-term starting age.
108:     birth_iso = (daiun.get("debug") or {}).get("birth_local")
109:     if birth_iso:
110:         birth = datetime.fromisoformat(birth_iso).astimezone(tz)
111:     else:
112:         raw = (shichu.get("input") or {}).get("raw") or {}
113:         try:
114:             birth = datetime(int(raw["year"]), int(raw["month"]), int(raw["day"]),
115:                              int(raw.get("hour") or 0), int(raw.get("minute") or 0), tzinfo=tz)
116:         except (KeyError, TypeError, ValueError) as exc:
117:             raise ValueError("大運の概算期間を復元する出生情報が不足しています。") from exc
118:     start_age = daiun.get("start_age") or {}
119:     if "years" not in start_age or "months" not in start_age or daiun.get("direction") not in {"forward", "reverse"}:
120:         raise ValueError("大運の起運年齢または順逆情報が不足しています。")
121:     # Beyond the default ten cycles, continue exactly the existing sequence.
122:     count = max(len(saved), (year + 1 - birth.year) // 10 + 2)
123:     calculated = _project_periods(birth, saved[0]["kanshi"], daiun["direction"],
124:                                  int(start_age["years"]), int(start_age["months"]), count)
125:     for i, original in enumerate(saved):
126:         for key in calculated[i]:
127:             if key in original:
128:                 calculated[i][key] = deepcopy(original[key])
129:     return calculated
130: 
131: 
132: def build_annual_fortune_report(base_doc: dict, selected_year: int) -> dict:
133:     validate_selected_year(selected_year)
134:     shichu = (base_doc.get("systems") or {}).get("shichusuimei") or {}
135:     data = shichu.get("normalized_data") or shichu.get("features") or {}
136:     pillars = data.get("pillars") or shichu.get("pillars") or {}
137:     if not pillars:
138:         raise ValueError("四柱推命の基礎命式が含まれていません。")
139:     assumptions = (shichu.get("input") or {}).get("assumptions") or {}
140:     base_input = base_doc.get("input") or {}
141:     tz_name = assumptions.get("tz_name") or base_input.get("timezone") or "Asia/Tokyo"
142:     tz = ZoneInfo(tz_name)
143:     accuracy = assumptions.get("birth_time_accuracy") or base_input.get("birth_time_accuracy")
144:     # Legacy exact charts have no accuracy marker. Unknown or approximate charts
145:     # carry either a Full-YAML birth_time marker or a normalized reference flag.
146:     accuracy = accuracy or (base_doc.get("birth_time") or {}).get("accuracy") or "exact"
147:     reliable = accuracy == "exact" and not data.get("time_sensitive_reference")
148:     natal = [_item(name, value.get("kanshi") if isinstance(value, dict) else value)
149:              for name, value in pillars.items() if name in {"year", "month", "day", "hour"}
150:              and (name != "hour" or reliable)]
151:     by_name = {p["name"]: p for p in natal}
152:     if not {"year", "month", "day"} <= by_name.keys():
153:         raise ValueError("基礎命式の年柱・月柱・日柱が不足しています。")
154:     day_master = by_name["day"]["stem"]
155:     annual = _item("annual", core._year_kanshi_from_effective_year(selected_year))
156:     start = core._lichun_utc_for_year(selected_year, tz_name).astimezone(tz)
157:     end = core._lichun_utc_for_year(selected_year + 1, tz_name).astimezone(tz)
158:     periods = _daiun_periods(shichu, data, selected_year, tz)
159:     contexts = []
160:     for period in periods:
161:         left, right = (datetime.fromisoformat(period[key]) for key in ("approx_start_at", "approx_end_at"))
162:         if left >= end or right <= start:
163:             continue
164:         luck = _item("daiun", period["kanshi"])
165:         contexts.append({
166:             **period, "stem": luck["stem"], "branch": luck["branch"],
167:             "ten_god_to_day_master": core.ten_god(day_master, luck["stem"]),
168:             "twelve_fortune_to_day_master": core.twelve_fortune(day_master, luck["branch"]),
169:             "boundary_provisional": True,
170:             "boundary_in_selected_year": start < left < end or start < right < end,
171:             "overlap_start_approx": max(start, left).isoformat(),
172:             "overlap_end_approx": min(end, right).isoformat(),
173:         })
174:     interactions = {"natal_annual": _scope(natal + [annual], {"natal", "annual"}),
175:                     "natal_daiun": [], "daiun_annual": [], "combined": []}
176:     for context in contexts:
177:         luck = _item("daiun", context["kanshi"])
178:         for key, participants, required in (
179:             ("natal_daiun", natal + [luck], {"natal", "daiun"}),
180:             ("daiun_annual", [luck, annual], {"daiun", "annual"}),
181:             ("combined", natal + [luck, annual], {"natal", "daiun", "annual"}),
182:         ):
183:             interactions[key].extend({"daiun_index": context["index"], **r} for r in _scope(participants, required))
184:     kubo = data.get("kubo") or core.kubo_from_day_kanshi(by_name["day"]["kanshi"])
185:     empty = kubo["empty_branches"]
186:     daiun_counts, combined = [], []
187:     for context in contexts:
188:         luck = _item("daiun", context["kanshi"])
189:         daiun_counts.append({"daiun_index": context["index"], **_counts([luck])})
190:         combined.append({"daiun_index": context["index"], **_counts(natal + [luck, annual])})
191:     first = datetime.fromisoformat(periods[0]["approx_start_at"]) if periods else None
192:     direction_unknown = (data.get("daiun") or {}).get("status") == "undetermined_gender"
193:     return {"annual_fortune_report": {
194:         "schema_version": "1.0", "base_chart_id": (base_doc.get("meta") or {}).get("chart_id"),
195:         "selected_year": selected_year,
196:         "calculation": {"engine": "nanami-shichusuimei-annual-v1", "base_engine_version": shichu.get("engine_version"),
197:                         "year_boundary_rule": "lichun(315deg)", "daiun_calc_mode": "approx_days_to_years",
198:                         "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
199:                         "timezone": tz_name, "supported_years": {"min": MIN_YEAR, "max": MAX_YEAR},
200:                         "natal_time_basis": "four_pillars" if reliable else "three_pillars_hour_excluded"},
201:         "base_chart_usage": {"full_yaml_required": True,
202:                              "note": "同じbase_chart_idのFull YAMLと併用。出生四柱は照合用。格局・用神などは基礎命式を参照。"},
203:         "natal_reference": {"day_master": day_master, "pillars": {p["name"]: p["kanshi"] for p in natal}},
204:         "annual": {"effective_year": selected_year, **{k: v for k, v in annual.items() if k != "name"},
205:                    "period_start": start.isoformat(), "period_end": end.isoformat(), "period_end_exclusive": True,
206:                    "ten_god_to_day_master": core.ten_god(day_master, annual["stem"]),
207:                    "twelve_fortune_to_day_master": core.twelve_fortune(day_master, annual["branch"])},
208:         "daiun": {"status": "undetermined_gender" if direction_unknown else "overlapping_periods" if contexts else "before_first_daiun",
209:                   "contexts": contexts, "boundary_in_selected_year": any(c["boundary_in_selected_year"] for c in contexts),
210:                   "uncovered_before_first_daiun": {"start": start.isoformat(), "end": min(first, end).isoformat()}
211:                       if first is not None and start < first else None,
212:                   "note": "起運・交運日時は既存の簡易換算による概算。境界付近の大運を確定値として扱わない。"},
213:         "interactions": interactions,
214:         "kubo": {"empty_branches": deepcopy(empty), "annual_hit": annual["branch"] in empty,
215:                  "natal_hits": [p["name"] for p in natal if p["branch"] in empty],
216:                  "daiun_hits": [{"daiun_index": c["index"], "hit": c["branch"] in empty} for c in contexts],
217:                  "method": "membership_in_natal_day_jun_empty_branches"},
218:         "five_elements": {"natal": deepcopy(data.get("five_elements")), "natal_reference_only": not reliable,
219:                           "included_natal_reference": _counts(natal), "annual": _counts([annual]),
220:                           "daiun": daiun_counts, "combined_reference": combined,
221:                           "method": "existing_visible_stem_plus_branch_and_additive_hidden_stem_counts",
222:                           "note": "合算は参考個数。強弱・吉凶・合化の成立を示さない。時刻不明・推定の場合、合算から時柱を除外。"},
223:         "interpretation_flags": {"calculation_only": True, "automatic_good_bad_judgment": False,
224:                                  "automatic_element_transformation": False},
225:     }}
226: 
227: 
228: def build_annual_fortune_yaml(base_doc: dict, selected_year: int) -> str:
229:     return yaml.safe_dump(build_annual_fortune_report(base_doc, selected_year), allow_unicode=True, sort_keys=False, width=120)
```


## services/yaml_exporter.py
```text
1: from __future__ import annotations
2: 
3: from datetime import datetime, time, timedelta, timezone
4: import hashlib
5: import json
6: from typing import Any
7: from zoneinfo import ZoneInfo
8: 
9: import yaml
10: 
11: from services.location import resolve_prefecture
12: from services.western_calc import calc_western_from_payload, house_of
13: from services.prompt_builder import build_prompt, ensure_shichusuimei_structure_guidance
14: from services.output_metadata import customer_output_doc
15: from services.birth_datetime import resolve_birth_datetime
16: 
17: SIGN_JA = {
18:     "Ari": "牡羊座", "Tau": "牡牛座", "Gem": "双子座", "Can": "蟹座", "Leo": "獅子座", "Vir": "乙女座",
19:     "Lib": "天秤座", "Sco": "蠍座", "Sag": "射手座", "Cap": "山羊座", "Aqu": "水瓶座", "Pis": "魚座",
20: }
21: ELEMENT_BY_SIGN = {
22:     "Ari": "fire", "Leo": "fire", "Sag": "fire",
23:     "Tau": "earth", "Vir": "earth", "Cap": "earth",
24:     "Gem": "air", "Lib": "air", "Aqu": "air",
25:     "Can": "water", "Sco": "water", "Pis": "water",
26: }
27: MODE_BY_SIGN = {
28:     "Ari": "cardinal", "Can": "cardinal", "Lib": "cardinal", "Cap": "cardinal",
29:     "Tau": "fixed", "Leo": "fixed", "Sco": "fixed", "Aqu": "fixed",
30:     "Gem": "mutable", "Vir": "mutable", "Sag": "mutable", "Pis": "mutable",
31: }
32: CORE_BODIES = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
33: ASTEROID_BODIES = {"Chiron", "Lilith", "Ceres", "Pallas", "Juno", "Vesta", "Vertex"}
34: TRANSIT_BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
35: LONG_TERM_TRANSIT_PRIMARY_BODIES = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
36: LONG_TERM_TRANSIT_AUXILIARY_BODIES = ["Chiron", "North Node", "South Node"]
37: LONG_TERM_TRANSIT_SAMPLE_INTERVAL_DAYS = 7
38: TRANSIT_ASPECTS = {
39:     "conjunction": 0,
40:     "sextile": 60,
41:     "square": 90,
42:     "trine": 120,
43:     "opposition": 180,
44: }
45: TRANSIT_ORB = {
46:     "Sun": 1.5,
47:     "Moon": 1.2,
48:     "Mercury": 1.2,
49:     "Venus": 1.2,
50:     "Mars": 1.2,
51:     "Jupiter": 1.5,
52:     "Saturn": 1.5,
53:     "Uranus": 1.5,
54:     "Neptune": 1.5,
55:     "Pluto": 1.5,
56:     "Chiron": 1.2,
57:     "North Node": 1.2,
58:     "South Node": 1.2,
59: }
60: MOON_TIMEPOINTS = [
61:     ("morning", 6),
62:     ("noon", 12),
63:     ("night", 21),
64: ]
65: TIME_SENSITIVE_ACCURACIES = frozenset({"unknown", "approximate"})
66: ANGLE_BODY_NAMES = {"ASC": "asc", "MC": "mc", "Vertex": "vertex"}
67: 
68: def _split_date(value: str) -> tuple[int, int, int]:
69:     y, m, d = value.split("-")
70:     return int(y), int(m), int(d)
71: 
72: def _split_time(value: str | None) -> tuple[int, int]:
73:     if not value:
74:         return 12, 0
75:     h, m = value.split(":")[:2]
76:     return int(h), int(m)
77: 
78: def _round(x: Any, digits: int = 4) -> Any:
79:     return round(float(x), digits) if x is not None else None
80: 
81: def _short_hash(prefix: str, payload: dict[str, Any]) -> str:
82:     raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
83:     digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
84:     return f"{prefix}_{digest}"
85: 
86: def _birth_time_struct(
87:     *,
88:     input_value: str | None,
89:     calculation_time: str,
90:     accuracy: str,
91:     note: str,
92:     range_info: dict[str, Any] | None,
93: ) -> dict[str, Any]:
94:     data: dict[str, Any] = {
95:         "input_value": input_value if accuracy == "exact" else None,
96:         "calculation_time": calculation_time,
97:         "accuracy": accuracy,
98:         "note": note,
99:     }
100:     if range_info:
101:         data["range"] = range_info
102:     return data
103: 
104: def build_prompt_for_doc(
105:     doc: dict[str, Any],
106:     *,
107:     include_asteroids: bool = False,
108:     include_shichusuimei: bool = False,
109:     include_transit: bool = False,
110:     lang: str = "ja",
111: ) -> str:
112:     """
113:     計算済みドキュメントから鑑定プロンプトだけを組み立てる。
114: 
115:     build_prompt() は天体位置を一切参照せず、出生時刻の精度と含まれるセクションの
116:     有無だけで決まる。プロンプト文字列が欲しいだけの場面で build_product_yaml() を
117:     丸ごと再実行すると、使わない天体計算をもう一度走らせることになる。
118:     """
119:     input_block = doc.get("input") or {}
120:     accuracy = str((doc.get("birth_time") or {}).get("accuracy") or input_block.get("birth_time_accuracy") or "exact")
121:     systems = doc.get("systems")
122:     include_western = None
123:     if isinstance(systems, dict) and any(k in systems for k in ("western", "shichusuimei")):
124:         include_western = bool(systems.get("western"))
125:         include_shichusuimei = bool(systems.get("shichusuimei"))
126:     return build_prompt(
127:         include_shichusuimei=include_shichusuimei,
128:         include_asteroids=include_asteroids,
129:         include_transit=include_transit,
130:         birth_time_accuracy=accuracy,
131:         interpretation_flags=doc.get("interpretation_flags") or {},
132:         lang=lang,
133:         include_western=include_western,
134:     )
135: 
136: 
137: def _interpretation_flags(accuracy: str) -> dict[str, Any]:
138:     if accuracy in TIME_SENSITIVE_ACCURACIES:
139:         return {
140:             "allow_house_interpretation": False,
141:             "allow_asc_mc_interpretation": False,
142:             "house_reliability": "low",
143:             "moon_reliability": "medium",
144:             "use_houses_as_reference_only": True,
145:         }
146:     return {
147:         "allow_house_interpretation": True,
148:         "allow_asc_mc_interpretation": True,
149:         "house_reliability": "high",
150:         "moon_reliability": "high",
151:         "use_houses_as_reference_only": False,
152:     }
153: 
154: 
155: def read_natal_houses(natal: dict[str, Any]) -> Any:
156:     """v1通常位置、v2暫定位置の順でハウスカスプを読む。"""
157:     houses = natal.get("houses")
158:     if houses is not None:
159:         return houses
160:     provisional = natal.get("time_sensitive_provisional") or {}
161:     return provisional.get("houses") or {}
162: 
163: 
164: def read_natal_angles(natal: dict[str, Any]) -> dict[str, Any]:
165:     """v1/v2からASC・MC・Vertexを共通形式で読む。"""
166:     angles = natal.get("angles")
167:     if isinstance(angles, dict):
168:         return angles
169:     provisional = natal.get("time_sensitive_provisional") or {}
170:     angles = provisional.get("angles")
171:     if isinstance(angles, dict):
172:         return angles
173:     bodies = natal.get("bodies") or {}
174:     if not isinstance(bodies, dict):
175:         return {}
176:     return {
177:         key: bodies[name]
178:         for name, key in ANGLE_BODY_NAMES.items()
179:         if isinstance(bodies.get(name), dict)
180:     }
181: 
182: 
183: def read_body_house(natal: dict[str, Any], body_name: str) -> int | None:
184:     """v1 body.house、v2暫定配置の順で在住ハウスを読む。"""
185:     bodies = natal.get("bodies") or {}
186:     body = bodies.get(body_name) if isinstance(bodies, dict) else None
187:     if isinstance(body, dict) and body.get("house") is not None:
188:         return body.get("house")
189:     provisional = natal.get("time_sensitive_provisional") or {}
190:     placements = provisional.get("body_house_placements") or {}
191:     return placements.get(body_name) if isinstance(placements, dict) else None
192: 
193: def _format_body(p: dict[str, Any]) -> dict[str, Any]:
194:     return {
195:         "sign": p.get("sign"),
196:         "sign_ja": SIGN_JA.get(p.get("sign"), p.get("sign")),
197:         "degree": _round(p.get("degree"), 4),
198:         "absolute_longitude": _round(p.get("lon"), 4),
199:         "house": p.get("house"),
200:         "retrograde": bool(p.get("retrograde", False)),
201:     }
202: 
203: def _natal_cusps_from_houses(houses: dict[str, Any]) -> list[float]:
204:     cusps: list[float] = []
205:     for house_no in range(1, 13):
206:         house = houses.get(str(house_no)) or {}
207:         lon = house.get("absolute_longitude")
208:         if lon is None:
209:             return []
210:         cusps.append(float(lon))
211:     return cusps
212: 
213: def _format_transit_body(p: dict[str, Any], natal_cusps: list[float]) -> dict[str, Any]:
214:     body = _format_body(p)
215:     body["mundane_house"] = body.pop("house", None)
216:     lon = body.get("absolute_longitude")
217:     body["natal_house"] = house_of(float(lon), natal_cusps) if lon is not None and natal_cusps else None
218:     return body
219: 
220: def validate_yaml_option_section_consistency(doc: dict[str, Any]) -> None:
221:     product = doc.get("product") or {}
222:     options = product.get("options") or {}
223:     systems = doc.get("systems") or {}
224:     western = systems.get("western") if isinstance(systems, dict) else None
225:     western = western if isinstance(western, dict) else {}
226: 
227:     section_checks = {
228:         "western_natal": bool(western.get("natal")),
229:         "asteroids": bool(western.get("asteroids")),
230:         "transit": bool(western.get("transit")),
231:     }
232:     for option_key, section_present in section_checks.items():
233:         if option_key in options and bool(options.get(option_key)) != section_present:
234:             raise ValueError(
235:                 f"YAML option/section mismatch: product.options.{option_key}="
236:                 f"{bool(options.get(option_key))} but systems.western.{option_key if option_key != 'western_natal' else 'natal'} "
237:                 f"present={section_present}"
238:             )
239: 
240:     meta = doc.get("meta") or {}
241:     product_type = str(meta.get("product_type") or product.get("type") or "")
242:     data_role = str(meta.get("data_role") or "")
243:     addon_type = meta.get("addon_type")
244:     yaml_variant = meta.get("yaml_variant")
245:     addon_product_types = {
246:         "western_asteroids_addon",
247:         "western_31days_transit_addon",
248:         "western_long_term_transits_addon",
249:         "shichu_fortune_cycles_addon",
250:         "personal_ai_astrology_yaml_transit",
251:         "western_note_transit_addon",
252:     }
253:     if product_type in addon_product_types and data_role != "addon":
254:         raise ValueError(f"Invalid YAML metadata: {product_type} requires data_role=addon")
255:     if addon_type and data_role != "addon":
256:         raise ValueError(f"Invalid YAML metadata: {product_type} with addon_type requires data_role=addon")
257:     if data_role == "addon" and not addon_type and product_type in addon_product_types - {"personal_ai_astrology_yaml_transit"}:
258:         raise ValueError(f"Invalid YAML metadata: {product_type} requires addon_type")
259:     if yaml_variant == "transit" and data_role != "addon":
260:         raise ValueError("Invalid YAML metadata: yaml_variant=transit requires data_role=addon")
261: 
262: def _format_aspect(a: dict[str, Any]) -> dict[str, Any]:
263:     return {
264:         "body1": a.get("planet1"),
265:         "body2": a.get("planet2"),
266:         "aspect": a.get("type"),
267:         "orb": _round(a.get("orb"), 2),
268:     }
269: 
270: def _angle_diff(a: float, b: float) -> float:
271:     d = abs((a % 360) - (b % 360))
272:     return min(d, 360 - d)
273: 
274: def _transit_aspects(transit_bodies: dict[str, dict[str, Any]], natal_bodies: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
275:     out: list[dict[str, Any]] = []
276:     for transit_name, transit_body in transit_bodies.items():
277:         transit_lon = transit_body.get("absolute_longitude")
278:         if transit_lon is None:
279:             continue
280:         max_orb = TRANSIT_ORB.get(transit_name, 1.2)
281:         for natal_name, natal_body in natal_bodies.items():
282:             if natal_name not in CORE_BODIES:
283:                 continue
284:             natal_lon = natal_body.get("absolute_longitude")
285:             if natal_lon is None:
286:                 continue
287:             diff = _angle_diff(float(transit_lon), float(natal_lon))
288:             for aspect_name, aspect_angle in TRANSIT_ASPECTS.items():
289:                 orb = abs(diff - aspect_angle)
290:                 if orb <= max_orb:
291:                     out.append({
292:                         "transit_body": transit_name,
293:                         "natal_body": natal_name,
294:                         "aspect": aspect_name,
295:                         "orb": _round(orb, 2),
296:                         "transit_longitude": _round(transit_lon, 4),
297:                         "natal_longitude": _round(natal_lon, 4),
298:                     })
299:     return sorted(out, key=lambda x: (x["orb"], x["transit_body"], x["natal_body"]))
300: 
301: def _build_transit_block(
302:     *,
303:     start_date: datetime,
304:     days: int,
305:     lat: float,
306:     lng: float,
307:     pref_name: str,
308:     tz_name: str,
309:     natal_bodies: dict[str, Any],
310:     natal_houses: dict[str, Any],
311: ) -> dict[str, Any]:
312:     daily: list[dict[str, Any]] = []
313:     tz = ZoneInfo(tz_name)
314:     start_day = start_date.astimezone(tz).date()
315:     for offset in range(days):
316:         target_day = start_day + timedelta(days=offset)
317:         local_noon = datetime(target_day.year, target_day.month, target_day.day, 12, 0, tzinfo=tz)
318:         tz_offset = local_noon.utcoffset()
319:         tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
320:         transit_payload = {
321:             "year": target_day.year,
322:             "month": target_day.month,
323:             "day": target_day.day,
324:             "hour": 12,
325:             "minute": 0,
326:             "lat": lat,
327:             "lng": lng,
328:             "city": pref_name,
329:             "tz_offset_hours": tz_offset_hours,
330:             "house_system": "P",
331:             "include_asteroids": False,
332:             "include_chiron": False,
333:             "include_lilith": False,
334:             "include_vertex": False,
335:         }
336:         raw = calc_western_from_payload(transit_payload)
337:         natal_cusps = _natal_cusps_from_houses(natal_houses)
338:         transiting = {
339:             p["name"]: _format_transit_body(p, natal_cusps)
340:             for p in raw.get("planets", [])
341:             if p.get("name") in TRANSIT_BODIES
342:         }
343:         moon_timepoints: list[dict[str, Any]] = []
344:         for label, hour in MOON_TIMEPOINTS:
345:             moon_local = datetime(target_day.year, target_day.month, target_day.day, hour, 0, tzinfo=tz)
346:             moon_offset = moon_local.utcoffset()
347:             moon_tz_offset_hours = moon_offset.total_seconds() / 3600 if moon_offset is not None else tz_offset_hours
348:             moon_payload = {**transit_payload, "hour": hour, "minute": 0, "tz_offset_hours": moon_tz_offset_hours}
349:             moon_raw = calc_western_from_payload(moon_payload)
350:             moon = next((p for p in moon_raw.get("planets", []) if p.get("name") == "Moon"), None)
351:             if not moon:
352:                 continue
353:             moon_body = _format_transit_body(moon, natal_cusps)
354:             moon_timepoints.append({
355:                 "label": label,
356:                 "time": f"{hour:02d}:00",
357:                 "body": moon_body,
358:                 "natal_aspects": _transit_aspects({"Moon": moon_body}, natal_bodies),
359:             })
360:         daily.append({
361:             "date": target_day.isoformat(),
362:             "time": "12:00",
363:             "timezone": tz_name,
364:             "transiting_bodies": transiting,
365:             "natal_aspects": _transit_aspects(transiting, natal_bodies),
366:             "moon_timepoints": moon_timepoints,
367:         })
368:     return {
369:         "period": {
370:             "start_date": start_day.isoformat(),
371:             "days": days,
372:             "timezone": tz_name,
373:             "sample_time": "12:00",
374:             "moon_timepoints": [f"{hour:02d}:00" for _, hour in MOON_TIMEPOINTS],
375:         },
376:         "daily": daily,
377:     }
378: 
379: def _build_long_term_transit_block(
380:     *,
381:     start_date: datetime,
382:     days: int,
383:     lat: float,
384:     lng: float,
385:     pref_name: str,
386:     tz_name: str,
387:     natal_bodies: dict[str, Any],
388:     natal_houses: dict[str, Any],
389: ) -> dict[str, Any]:
390:     samples: list[dict[str, Any]] = []
391:     tz = ZoneInfo(tz_name)
392:     start_day = start_date.astimezone(tz).date()
393:     selected_bodies = set(LONG_TERM_TRANSIT_PRIMARY_BODIES + LONG_TERM_TRANSIT_AUXILIARY_BODIES)
394:     for offset in range(0, days, LONG_TERM_TRANSIT_SAMPLE_INTERVAL_DAYS):
395:         target_day = start_day + timedelta(days=offset)
396:         local_noon = datetime(target_day.year, target_day.month, target_day.day, 12, 0, tzinfo=tz)
397:         tz_offset = local_noon.utcoffset()
398:         tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
399:         raw = calc_western_from_payload({
400:             "year": target_day.year,
401:             "month": target_day.month,
402:             "day": target_day.day,
403:             "hour": 12,
404:             "minute": 0,
405:             "lat": lat,
406:             "lng": lng,
407:             "city": pref_name,
408:             "tz_offset_hours": tz_offset_hours,
409:             "house_system": "P",
410:             "include_asteroids": False,
411:             "include_chiron": True,
412:             "include_lilith": False,
413:             "include_vertex": False,
414:         })
415:         natal_cusps = _natal_cusps_from_houses(natal_houses)
416:         transiting = {
417:             p["name"]: _format_transit_body(p, natal_cusps)
418:             for p in raw.get("planets", [])
419:             if p.get("name") in selected_bodies
420:         }
421:         samples.append({
422:             "date": target_day.isoformat(),
423:             "transiting_bodies": transiting,
424:             "natal_aspects": _transit_aspects(transiting, natal_bodies),
425:         })
426:     return {
427:         "period": {
428:             "start_date": start_day.isoformat(),
429:             "end_date": (start_day + timedelta(days=max(days, 1) - 1)).isoformat(),
430:             "days": days,
431:             "timezone": tz_name,
432:             "sample_time": "12:00",
433:             "sample_interval_days": LONG_TERM_TRANSIT_SAMPLE_INTERVAL_DAYS,
434:             "primary_bodies": LONG_TERM_TRANSIT_PRIMARY_BODIES,
435:             "auxiliary_bodies": LONG_TERM_TRANSIT_AUXILIARY_BODIES,
436:         },
437:         "samples": samples,
438:     }
439: 
440: def build_transit_for_profile(
441:     *,
442:     profile: str,
443:     start_date: datetime,
444:     days: int,
445:     lat: float,
446:     lng: float,
447:     pref_name: str,
448:     tz_name: str,
449:     natal_bodies: dict[str, Any],
450:     natal_houses: dict[str, Any],
451: ) -> dict[str, Any]:
452:     builder = {
453:         "standard": _build_transit_block,
454:         "long_term": _build_long_term_transit_block,
455:     }.get(profile)
456:     if builder is None:
457:         raise ValueError(f"Unsupported transit profile: {profile}")
458:     return builder(
459:         start_date=start_date,
460:         days=days,
461:         lat=lat,
462:         lng=lng,
463:         pref_name=pref_name,
464:         tz_name=tz_name,
465:         natal_bodies=natal_bodies,
466:         natal_houses=natal_houses,
467:     )
468: 
469: def _summaries(planets: list[dict[str, Any]]) -> dict[str, Any]:
470:     elements = {"fire": 0, "earth": 0, "air": 0, "water": 0}
471:     modes = {"cardinal": 0, "fixed": 0, "mutable": 0}
472:     signs: dict[str, int] = {}
473:     for p in planets:
474:         if p.get("name") not in CORE_BODIES:
475:             continue
476:         sign = p.get("sign")
477:         if sign in ELEMENT_BY_SIGN:
478:             elements[ELEMENT_BY_SIGN[sign]] += 1
479:         if sign in MODE_BY_SIGN:
480:             modes[MODE_BY_SIGN[sign]] += 1
481:         signs[sign] = signs.get(sign, 0) + 1
482:     dominant_signs = sorted(signs.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
483:     return {
484:         "elements": elements,
485:         "modes": modes,
486:         "dominant_signs": [{"sign": k, "sign_ja": SIGN_JA.get(k, k), "count": v} for k, v in dominant_signs],
487:     }
488: 
489: def build_product_yaml(
490:     *,
491:     title: str | None,
492:     birth_date: str,
493:     birth_time: str | None,
494:     prefecture: str,
495:     birth_place_label: str | None = None,
496:     birth_lat: float | None = None,
497:     birth_lng: float | None = None,
498:     tz_name: str = "Asia/Tokyo",
499:     gender: str = "unknown",
500:     house_system: str = "P",
501:     include_asteroids: bool = False,
502:     include_shichusuimei: bool = False,
503:     include_transit: bool = False,
504:     transit_start_date: datetime | None = None,
505:     transit_days: int = 31,
506:     transit_profile: str = "standard",
507:     day_change_at_23: bool = False,
508:     birth_time_accuracy: str = "auto",
509:     day_boundary_hour: int | None = None,
510:     birth_fold: int | None = None,
511:     birth_utc_offset_hours: float | None = None,
512:     birth_time_range: dict[str, Any] | None = None,
513:     birth_time_note: str | None = None,
514:     data_role: str = "base_chart",
515:     base: dict[str, Any] | None = None,
516:     lang: str = "ja",
517: ) -> tuple[str, str, dict[str, Any]]:
518:     include_western = not (include_shichusuimei and not include_asteroids and not include_transit)
519:     if birth_time_accuracy == "auto":
520:         birth_time_accuracy = "exact" if birth_time else "unknown"
521:     if not include_western and not birth_time_note:
522:         birth_time_note = {
523:             "unknown": "出生時刻不明のため仮定時刻で計算しています。時柱に依存する情報は確定根拠にせず、time_sensitive_reference に従ってください。",
524:             "approximate": "出生時刻は推定です。時柱に依存する情報は暫定値とし、time_sensitive_reference に従ってください。",
525:         }.get(birth_time_accuracy, "出生時刻あり。時柱を含む四柱の計算済みデータを参照できます。")
526:     if birth_time_accuracy == "unknown" and not birth_time_note:
527:         birth_time_note = "出生時刻不明のため12:00で仮計算しています。ハウス・ASC・MCは参考値です。"
528:     elif birth_time_accuracy == "approximate" and not birth_time_note:
529:         birth_time_note = "出生時刻は推定レンジです。ハウス・ASC・MCは参考値です。"
530:     elif not birth_time_note:
531:         birth_time_note = "出生時刻あり。ハウス・ASC・MCを通常通り使用できます。"
532:     y, m, d = _split_date(birth_date)
533:     hour, minute = _split_time(birth_time)
534:     if birth_lat is not None and birth_lng is not None:
535:         lat = birth_lat
536:         lng = birth_lng
537:         pref_name = birth_place_label or prefecture or "海外出生"
538:     else:
539:         pref_name, lat, lng = resolve_prefecture(prefecture)
540:     tz = ZoneInfo(tz_name)
541:     local_dt = datetime(y, m, d, hour, minute, tzinfo=tz)
542:     if include_shichusuimei:
543:         from services.shichusuimei_calc import resolve_day_boundary_hour
544:         day_boundary_hour = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
545:         day_change_at_23 = day_boundary_hour == 23
546:         local_dt = resolve_birth_datetime(datetime(y, m, d, hour, minute), tz_name,
547:                                           fold=birth_fold, utc_offset_hours=birth_utc_offset_hours)
548:     tz_offset = local_dt.utcoffset()
549:     tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
550:     generated_at = datetime.now(timezone.utc).astimezone()
551: 
552:     western_system = None
553:     if include_western:
554:         payload = {
555:             "year": y, "month": m, "day": d, "hour": hour, "minute": minute,
556:             "birth_time": birth_time,
557:             "lat": lat, "lng": lng, "city": pref_name, "tz_offset_hours": tz_offset_hours,
558:             "house_system": house_system,
559:             "include_asteroids": include_asteroids,
560:             "include_chiron": True,
561:             "include_lilith": True,
562:             "include_vertex": include_asteroids,
563:         }
564:         raw = calc_western_from_payload(payload)
565:         bodies = {p["name"]: _format_body(p) for p in raw.get("planets", [])}
566:         core = {k: v for k, v in bodies.items() if k in CORE_BODIES or k in {"North Node", "South Node", "ASC", "MC"}}
567:         asteroids = {k: v for k, v in bodies.items() if k in ASTEROID_BODIES}
568:         houses = {
569:             str(h["house"]): {
570:                 "sign": h.get("sign"), "sign_ja": SIGN_JA.get(h.get("sign"), h.get("sign")),
571:                 "degree": _round(h.get("degree"), 4), "absolute_longitude": _round(h.get("lon"), 4),
572:             }
573:             for h in raw.get("houses", [])
574:         }
575:         skipped_bodies = raw.get("skipped_bodies", []) or []
576:         formatted_aspects = [_format_aspect(a) for a in raw.get("aspects", [])]
577:         provisional: dict[str, Any] | None = None
578:         if birth_time_accuracy in TIME_SENSITIVE_ACCURACIES:
579:             body_house_placements = {
580:                 name: body["house"]
581:                 for name, body in bodies.items()
582:                 if isinstance(body, dict) and body.get("house") is not None
583:             }
584:             provisional_angles = {
585:                 key: dict(bodies[name])
586:                 for name, key in ANGLE_BODY_NAMES.items()
587:                 if isinstance(bodies.get(name), dict)
588:             }
589:             angle_aspects = [
590:                 aspect for aspect in formatted_aspects
591:                 if aspect.get("body1") in ANGLE_BODY_NAMES or aspect.get("body2") in ANGLE_BODY_NAMES
592:             ]
593:             formatted_aspects = [
594:                 aspect for aspect in formatted_aspects
595:                 if aspect.get("body1") not in ANGLE_BODY_NAMES and aspect.get("body2") not in ANGLE_BODY_NAMES
596:             ]
597:             core = {
598:                 name: {key: value for key, value in body.items() if key != "house"}
599:                 for name, body in core.items()
600:                 if name not in ANGLE_BODY_NAMES
601:             }
602:             asteroids = {
603:                 name: {key: value for key, value in body.items() if key != "house"}
604:                 for name, body in asteroids.items()
605:                 if name not in ANGLE_BODY_NAMES
606:             }
607:             provisional = {
608:                 "status": (
609:                     "assumed_birth_time"
610:                     if birth_time_accuracy == "unknown"
611:                     else "approximate_birth_time"
612:                 ),
613:                 "assumed_time": f"{hour:02d}:{minute:02d}",
614:                 "valid_for_assertive_interpretation": False,
615:                 "recalculation_required_when_time_known": True,
616:                 "reason": (
617:                     "birth_time_unknown"
618:                     if birth_time_accuracy == "unknown"
619:                     else "birth_time_approximate"
620:                 ),
621:                 "angles": provisional_angles,
622:                 "houses": houses,
623:                 "body_house_placements": body_house_placements,
624:                 "angle_aspects": angle_aspects,
625:             }
626:         if provisional is None:
627:             natal = {
628:                 "engine": "Swiss Ephemeris",
629:                 "house_system": house_system,
630:                 "subject": raw.get("subject"),
631:                 "bodies": core,
632:                 "houses": houses,
633:                 "aspects": formatted_aspects,
634:                 "summary": _summaries(raw.get("planets", [])),
635:                 "skipped_bodies": skipped_bodies,
636:             }
637:         else:
638:             natal = {
639:                 "engine": "Swiss Ephemeris",
640:                 "house_system": house_system,
641:                 "subject": raw.get("subject"),
642:                 "bodies": core,
643:                 "aspects": formatted_aspects,
644:                 "summary": _summaries(raw.get("planets", [])),
645:                 "skipped_bodies": skipped_bodies,
646:                 "time_sensitive_provisional": provisional,
647:             }
648:         western_system = {
649:             "natal": natal,
650:             "asteroids": asteroids if include_asteroids else None,
651:             "transit": build_transit_for_profile(
652:                 profile=transit_profile,
653:                 start_date=transit_start_date or generated_at,
654:                 days=transit_days,
655:                 lat=lat,
656:                 lng=lng,
657:                 pref_name=pref_name,
658:                 tz_name=tz_name,
659:                 natal_bodies=core,
660:                 natal_houses=houses,
661:             ) if include_transit else None,
662:         }
663: 
664:     systems: dict[str, Any] = {
665:         "western": western_system,
666:         "shichusuimei": None,
667:     }
668:     if include_shichusuimei:
669:         from services.shichusuimei_calc import calc_shichusuimei_from_payload
670:         systems["shichusuimei"] = calc_shichusuimei_from_payload(
671:             {"year": y, "month": m, "day": d, "hour": hour if birth_time else None, "minute": minute, "gender": gender,
672:              "birth_time_accuracy": birth_time_accuracy, "birth_fold": local_dt.fold,
673:              "birth_utc_offset_hours": tz_offset_hours},
674:             tz_name=tz_name,
675:             day_change_at_23=day_change_at_23,
676:             day_boundary_hour=day_boundary_hour,
677:         )
678:     calculation_time = f"{hour:02d}:{minute:02d}"
679:     display_birth_time = birth_time if birth_time_accuracy == "exact" else birth_time_accuracy
680:     profile_id = _short_hash("profile", {
681:         "title": title or "",
682:         "birth_date": birth_date,
683:         "birth_place": birth_place_label or pref_name,
684:         "timezone": tz_name,
685:     })
686:     chart_id = _short_hash("chart", {
687:         "profile_id": profile_id,
688:         "birth_date": birth_date,
689:         "calculation_time": calculation_time,
690:         "birth_time_accuracy": birth_time_accuracy,
691:         "birth_time_range": birth_time_range,
692:         "lat": _round(lat, 6),
693:         "lng": _round(lng, 6),
694:         "timezone": tz_name,
695:         "house_system": house_system,
696:         "include_asteroids": include_asteroids,
697:         "include_shichusuimei": include_shichusuimei,
698:         "include_transit": include_transit,
699:         "transit_days": transit_days,
700:         "transit_profile": transit_profile,
701:         "day_change_at_23": day_change_at_23,
702:         **({"day_boundary_hour": day_boundary_hour, "birth_fold": local_dt.fold,
703:             "shichusuimei_engine_version": systems["shichusuimei"]["engine_version"]} if include_shichusuimei else {}),
704:     })
705:     birth_time_data = _birth_time_struct(
706:         input_value=birth_time,
707:         calculation_time=calculation_time,
708:         accuracy=birth_time_accuracy,
709:         note=birth_time_note,
710:         range_info=birth_time_range,
711:     )
712:     interpretation_flags = _interpretation_flags(birth_time_accuracy)
713:     is_overseas_birth = birth_lat is not None and birth_lng is not None and not prefecture.strip()
714:     input_block = {
715:         "title": title,
716:         "birth_date": birth_date,
717:         "birth_time": display_birth_time,
718:         "calculation_time": calculation_time,
719:         "birth_time_accuracy": birth_time_accuracy,
720:         "birth_time_note": birth_time_note,
721:         "prefecture": None if is_overseas_birth else prefecture,
722:         "birth_place_kind": "overseas" if is_overseas_birth else "domestic",
723:         "birth_place": birth_place_label or pref_name,
724:         "birth_lat": _round(lat, 6),
725:         "birth_lng": _round(lng, 6),
726:         "timezone": tz_name,
727:         "timezone_offset_hours": tz_offset_hours,
728:         "gender": gender,
729:     }
730:     if birth_time_range:
731:         input_block["birth_time_range"] = birth_time_range
732: 
733:     doc = {
734:         "version": "nanami-products-yaml-v1",
735:         "meta": {
736:             "schema_version": "2.0",
737:             "product_type": "personal_ai_astrology_yaml",
738:             "profile_id": profile_id,
739:             "chart_id": chart_id,
740:             "generated_at": generated_at.isoformat(),
741:             "data_role": data_role,
742:             "yaml_variant": "full",
743:         },
744:         "base": base,
745:         "product": {
746:             "type": "personal_ai_astrology_yaml",
747:             "options": {
748:                 "western_natal": include_western,
749:                 "asteroids": include_asteroids,
750:                 "transit": include_transit,
751:                 "shichusuimei": include_shichusuimei,
752:             },
753:         },
754:         "generated_at": generated_at.isoformat(),
755:         "calculation": {
756:             "engine": "Swiss Ephemeris" if include_western else "nanami-products shichusuimei",
757:             "zodiac": "tropical" if include_western else None,
758:             "house_system": house_system if include_western else None,
759:             "timezone": tz_name,
760:             "location_source": "input",
761:             "ephemeris_version": None,
762:         },
763:         "birth_time": birth_time_data,
764:         "interpretation_flags": interpretation_flags,
765:         "assets": {
766:             "horoscope_svg": {
767:                 "available": bool(include_western),
768:                 "file_name": "horoscope.svg",
769:                 "generated_from_chart_id": chart_id,
770:             },
771:             "shichusuimei_svg": {
772:                 "available": bool(include_shichusuimei),
773:                 "file_name": "shichusuimei-chart.svg",
774:                 "generated_from_chart_id": chart_id,
775:             },
776:             "yaml_lite": {
777:                 "available": bool(include_transit),
778:             },
779:             "yaml_detail": {
780:                 "available": bool(include_transit and include_asteroids),
781:             },
782:             "yaml_full": {
783:                 "available": True,
784:             },
785:         },
786:         "input": input_block,
787:         "usage_note": {
788:             "for_ai": "このYAMLは計算済みデータです。AIに解釈させる場合、生年月日から再計算させず、この値を根拠にしてください。",
789:             "not_included": "鑑定本文は含みません。AI解釈用の構造化データです。",
790:             "continuous_use": "このYAMLはAIに一度読み込ませて継続的に使える基礎データです。今後、月ごとのトランジット追加データと組み合わせて使うこともできます。",
791:         },
792:         "systems": systems,
793:     }
794:     validate_yaml_option_section_consistency(doc)
795:     # Installation paths are diagnostics, not interpretation data. Engines and
796:     # saved originals are untouched; sanitize only this newly issued document.
797:     doc = customer_output_doc(doc)
798:     if not include_western:
799:         doc["usage_note"]["continuous_use"] = "保存した命式・大運・流年を継続利用できます。単年流年は原本作成時の年を参照し、年選択では収録された対象年だけを使ってください。"
800:     yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
801:     prompt_text = build_prompt(
802:         include_shichusuimei=include_shichusuimei,
803:         include_asteroids=include_asteroids,
804:         include_transit=include_transit,
805:         birth_time_accuracy=birth_time_accuracy,
806:         interpretation_flags=interpretation_flags,
807:         lang=lang,
808:         include_western=include_western,
809:     )
810:     return yaml_text, prompt_text, doc
811: 
812: 
813: ASTEROID_ADDON_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、基本版ホロスコープに後から追加する小惑星データです。
814: 
815: 重要ルール:
816: - このYAML単体を出生図全体として扱わないでください。
817: - 先に読み込ませた基本版ホロスコープYAMLに、systems.western.asteroids の追加部品として結合して読んでください。
818: - 小惑星位置・ハウス・度数の計算結果は変更しないでください。
819: - 生年月日から再計算しないでください。
820: - YAML内の計算結果を根拠として、性格・テーマ・関係性の深掘りに使ってください。
821: 
822: 以下のYAMLを読み込んで、基本版データに追加して解釈してください。
823: """
824: 
825: 
826: def build_asteroid_addon_yaml(
827:     *,
828:     title: str | None,
829:     birth_date: str,
830:     birth_time: str | None,
831:     prefecture: str,
832:     birth_place_label: str | None = None,
833:     birth_lat: float | None = None,
834:     birth_lng: float | None = None,
835:     tz_name: str = "Asia/Tokyo",
836:     gender: str = "unknown",
837:     house_system: str = "P",
838:     birth_time_accuracy: str = "auto",
839:     birth_time_range: dict[str, Any] | None = None,
840:     birth_time_note: str | None = None,
841: ) -> tuple[str, str, dict[str, Any]]:
842:     _full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
843:         title=title,
844:         birth_date=birth_date,
845:         birth_time=birth_time,
846:         prefecture=prefecture,
847:         birth_place_label=birth_place_label,
848:         birth_lat=birth_lat,
849:         birth_lng=birth_lng,
850:         tz_name=tz_name,
851:         gender=gender,
852:         house_system=house_system,
853:         include_asteroids=True,
854:         include_shichusuimei=False,
855:         include_transit=False,
856:         birth_time_accuracy=birth_time_accuracy,
857:         birth_time_range=birth_time_range,
858:         birth_time_note=birth_time_note,
859:         data_role="addon",
860:     )
861:     meta = full_doc.get("meta") or {}
862:     western = ((full_doc.get("systems") or {}).get("western") or {})
863:     asteroids = western.get("asteroids") or {}
864:     doc = {
865:         "version": "nanami-products-yaml-addon-v1",
866:         "meta": {
867:             **meta,
868:             "schema_version": meta.get("schema_version") or "1.1",
869:             "product_type": "western_asteroids_addon",
870:             "data_role": "addon",
871:             "addon_type": "western_asteroids",
872:             "source_logic": "western_full_asteroid_calculation",
873:         },
874:         "base": {
875:             "target_product_type": "western_basic",
876:             "target_system": "western",
877:             "merge_path": "systems.western.asteroids",
878:             "compatible_with": ["western_basic", "personal_ai_astrology_yaml_natal"],
879:         },
880:         "product": {
881:             "type": "western_asteroids_addon",
882:             "label": "ホロスコープ：小惑星追加",
883:             "options": {
884:                 "addon": True,
885:                 "western_natal": False,
886:                 "asteroids": True,
887:                 "transit": False,
888:                 "shichusuimei": False,
889:             },
890:         },
891:         "generated_at": full_doc.get("generated_at"),
892:         "calculation": full_doc.get("calculation") or {},
893:         "birth_time": full_doc.get("birth_time") or {},
894:         "interpretation_flags": full_doc.get("interpretation_flags") or {},
895:         "assets": {
896:             "yaml_addon": {
897:                 "available": True,
898:                 "merge_path": "systems.western.asteroids",
899:             },
900:             "horoscope_svg": {"available": False},
901:             "shichusuimei_svg": {"available": False},
902:         },
903:         "input": full_doc.get("input") or {},
904:         "usage_note": {
905:             "for_ai": "これは追加部品データです。基本版ホロスコープYAMLを土台にし、このYAMLの小惑星データを追加して解釈してください。",
906:             "merge_instruction": "systems.western.asteroids を、同じ出生情報で作成済みの基本版YAMLへ追加する想定です。",
907:             "not_included": "出生図全体・トランジット・鑑定本文は含みません。小惑星追加用の計算済みデータです。",
908:         },
909:         "systems": {
910:             "western": {
911:                 "natal": None,
912:                 "asteroids": asteroids,
913:                 "transit": None,
914:             },
915:             "shichusuimei": None,
916:         },
917:     }
918:     validate_yaml_option_section_consistency(doc)
919:     yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
920:     return yaml_text, ASTEROID_ADDON_PROMPT.strip() + "\n", doc
921: 
922: 
923: TRANSIT_31DAYS_ADDON_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、基本版ホロスコープに後から追加する38日トランジットデータです。
924: 
925: 重要ルール:
926: - このYAML単体を出生図全体として扱わないでください。
927: - 先に読み込ませた基本版ホロスコープYAMLと一緒にAIへ貼り付けて使ってください。
928: - systems.western.transit を、基本版ホロスコープYAMLの追加部品として読んでください。
929: - トランジット天体位置・出生図へのアスペクト・月の時間帯データは変更しないでください。
930: - 生年月日から再計算しないでください。
931: - YAML内の計算結果を根拠として、今後38日間の流れを読んでください。
932: - today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。
933: - 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。
934: - next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。
935: - 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。
936: 
937: 以下のYAMLを読み込んで、基本版データと組み合わせて解釈してください。
938: """
939: 
940: 
941: def build_31days_transit_addon_yaml(
942:     *,
943:     title: str | None,
944:     birth_date: str,
945:     birth_time: str | None,
946:     prefecture: str,
947:     birth_place_label: str | None = None,
948:     birth_lat: float | None = None,
949:     birth_lng: float | None = None,
950:     tz_name: str = "Asia/Tokyo",
951:     gender: str = "unknown",
952:     house_system: str = "P",
953:     transit_start_date: datetime | None = None,
954:     transit_days: int = 38,
955:     birth_time_accuracy: str = "auto",
956:     birth_time_range: dict[str, Any] | None = None,
957:     birth_time_note: str | None = None,
958: ) -> tuple[str, str, dict[str, Any]]:
959:     full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
960:         title=title,
961:         birth_date=birth_date,
962:         birth_time=birth_time,
963:         prefecture=prefecture,
964:         birth_place_label=birth_place_label,
965:         birth_lat=birth_lat,
966:         birth_lng=birth_lng,
967:         tz_name=tz_name,
968:         gender=gender,
969:         house_system=house_system,
970:         include_asteroids=False,
971:         include_shichusuimei=False,
972:         include_transit=True,
973:         transit_start_date=transit_start_date,
974:         transit_days=transit_days,
975:         birth_time_accuracy=birth_time_accuracy,
976:         birth_time_range=birth_time_range,
977:         birth_time_note=birth_time_note,
978:         data_role="addon",
979:     )
980:     meta = full_doc.get("meta") or {}
981:     western = ((full_doc.get("systems") or {}).get("western") or {})
982:     transit = dict(western.get("transit") or {})
983:     try:
984:         from services.light_yaml import build_light_astrology_yaml
985: 
986:         current_date = None
987:         if transit_start_date is not None:
988:             current_date = transit_start_date.astimezone(ZoneInfo(tz_name)).date()
989:         light_yaml_text = build_light_astrology_yaml(full_yaml_text, doc=full_doc, current_date=current_date)
990:         light_doc = yaml.safe_load(light_yaml_text) or {}
991:         light_transit = (((light_doc.get("systems") or {}).get("western") or {}).get("transit") or {})
992:         if light_transit.get("today") is not None:
993:             transit["today"] = light_transit.get("today")
994:         if light_transit.get("next_31_days_summary") is not None:
995:             transit["next_31_days_summary"] = light_transit.get("next_31_days_summary")
996:     except Exception:
997:         pass
998:     if isinstance(transit.get("next_31_days_summary"), dict):
999:         summary = transit["next_31_days_summary"]
1000:         summary.setdefault("key_aspects", [])
1001:         summary.setdefault("active_periods", [])
1002:         summary.setdefault("easy_to_move_days", [])
1003:         summary.setdefault("caution_days", [])
1004:     addon_prompt_text = TRANSIT_31DAYS_ADDON_PROMPT.strip() + "\n"
1005:     if transit_days != 38:
1006:         addon_prompt_text = addon_prompt_text.replace("38日", f"{transit_days}日")
1007:     doc = {
1008:         "version": "nanami-products-yaml-addon-v1",
1009:         "meta": {
1010:             **meta,
1011:             "schema_version": meta.get("schema_version") or "1.1",
1012:             "product_type": "western_31days_transit_addon",
1013:             "data_role": "addon",
1014:             "addon_type": "western_31days_transit",
1015:             "source_logic": "western_full_31days_transit_calculation",
1016:         },
1017:         "base": {
1018:             "target_product_type": "western_basic",
1019:             "target_system": "western",
1020:             "merge_path": "systems.western.transit",
1021:             "compatible_with": ["western_basic", "personal_ai_astrology_yaml_natal"],
1022:         },
1023:         "product": {
1024:             "type": "western_31days_transit_addon",
1025:             "label": "ホロスコープ：38日トランジット追加",
1026:             "options": {
1027:                 "addon": True,
1028:                 "western_natal": False,
1029:                 "asteroids": False,
1030:                 "transit": True,
1031:                 "transit_days": transit_days,
1032:                 "shichusuimei": False,
1033:             },
1034:         },
1035:         "generated_at": full_doc.get("generated_at"),
1036:         "calculation": full_doc.get("calculation") or {},
1037:         "birth_time": full_doc.get("birth_time") or {},
1038:         "interpretation_flags": full_doc.get("interpretation_flags") or {},
1039:         "assets": {
1040:             "yaml_addon": {
1041:                 "available": True,
1042:                 "merge_path": "systems.western.transit",
1043:             },
1044:             "horoscope_svg": {"available": False},
1045:             "shichusuimei_svg": {"available": False},
1046:         },
1047:         "input": full_doc.get("input") or {},
1048:         "usage_note": {
1049:             "for_ai": "これは追加部品データです。基本版ホロスコープYAMLと一緒にAIへ貼り付けて使ってください。",
1050:             "merge_instruction": "systems.western.transit を、同じ出生情報で作成済みの基本版YAMLへ追加する想定です。",
1051:             "not_included": f"出生図全体・小惑星・四柱推命・鑑定本文は含みません。{transit_days}日トランジット追加用の計算済みデータです。",
1052:         },
1053:         "systems": {
1054:             "western": {
1055:                 "natal": None,
1056:                 "asteroids": None,
1057:                 "transit": transit,
1058:             },
1059:             "shichusuimei": None,
1060:         },
1061:     }
1062:     validate_yaml_option_section_consistency(doc)
1063:     yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
1064:     return yaml_text, addon_prompt_text, doc
1065: 
1066: 
1067: def refresh_dynamic_transit_yaml(full_yaml_text: str) -> str:
1068:     from services.light_yaml import build_transit_astrology_yaml
1069: 
1070:     return build_transit_astrology_yaml(full_yaml_text)
1071: 
1072: 
1073: SHICHU_FORTUNE_CYCLES_ADDON_PROMPT = """あなたは四柱推命の鑑定者です。以下のYAMLは、四柱推命基本版に後から追加する大運・流年データです。
1074: 
1075: 重要ルール:
1076: - このYAML単体を四柱推命の基本命式全体として扱わないでください。
1077: - 先に読み込ませた四柱推命基本版YAMLと一緒にAIへ貼り付けて使ってください。
1078: - systems.shichusuimei.normalized_data.daiun と systems.shichusuimei.normalized_data.annual_fortune を追加部品として読んでください。
1079: - 大運・流年の干支、年齢、関係性、計算前提は変更しないでください。
1080: - 生年月日から再計算しないでください。
1081: - YAML内の計算結果を根拠として、長期運勢と原本作成時の流年、または指定した収録年の流れを読んでください。
1082: 
1083: 以下のYAMLを読み込んで、四柱推命基本版データと組み合わせて解釈してください。
1084: """
1085: 
1086: 
1087: SHICHU_FORTUNE_CYCLES_ADDON_PROMPT = ensure_shichusuimei_structure_guidance(SHICHU_FORTUNE_CYCLES_ADDON_PROMPT)
1088: 
1089: 
1090: def build_shichu_fortune_cycles_addon_yaml(
1091:     *,
1092:     title: str | None,
1093:     birth_date: str,
1094:     birth_time: str | None,
1095:     prefecture: str,
1096:     birth_place_label: str | None = None,
1097:     birth_lat: float | None = None,
1098:     birth_lng: float | None = None,
1099:     tz_name: str = "Asia/Tokyo",
1100:     gender: str = "unknown",
1101:     birth_time_accuracy: str = "auto",
1102:     birth_time_range: dict[str, Any] | None = None,
1103:     birth_time_note: str | None = None,
1104:     day_change_at_23: bool = False,
1105:     day_boundary_hour: int | None = None,
1106:     birth_fold: int | None = None,
1107:     birth_utc_offset_hours: float | None = None,
1108: ) -> tuple[str, str, dict[str, Any]]:
1109:     _full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
1110:         title=title,
1111:         birth_date=birth_date,
1112:         birth_time=birth_time,
1113:         prefecture=prefecture,
1114:         birth_place_label=birth_place_label,
1115:         birth_lat=birth_lat,
1116:         birth_lng=birth_lng,
1117:         tz_name=tz_name,
1118:         gender=gender,
1119:         include_asteroids=False,
1120:         include_shichusuimei=True,
1121:         include_transit=False,
1122:         day_change_at_23=day_change_at_23,
1123:         day_boundary_hour=day_boundary_hour,
1124:         birth_fold=birth_fold,
1125:         birth_utc_offset_hours=birth_utc_offset_hours,
1126:         birth_time_accuracy=birth_time_accuracy,
1127:         birth_time_range=birth_time_range,
1128:         birth_time_note=birth_time_note,
1129:         data_role="addon",
1130:     )
1131:     meta = full_doc.get("meta") or {}
1132:     shichu = (full_doc.get("systems") or {}).get("shichusuimei") or {}
1133:     normalized = shichu.get("normalized_data") or {}
1134:     daiun = normalized.get("daiun") or {}
1135:     annual_fortune = normalized.get("annual_fortune") or {}
1136:     annual_forecasts = normalized.get("annual_forecasts") or {}
1137:     shichu_input = shichu.get("input") or {}
1138:     assumptions = shichu_input.get("assumptions") or {}
1139:     doc = {
1140:         "version": "nanami-products-yaml-addon-v1",
1141:         "meta": {
1142:             **meta,
1143:             "schema_version": meta.get("schema_version") or "1.1",
1144:             "product_type": "shichu_fortune_cycles_addon",
1145:             "data_role": "addon",
1146:             "addon_type": "shichu_fortune_cycles",
1147:             "source_logic": "shichu_full_fortune_cycles_calculation",
1148:         },
1149:         "base": {
1150:             "target_product_type": "shichu",
1151:             "target_system": "shichusuimei",
1152:             "merge_path": "systems.shichusuimei",
1153:             "compatible_with": ["shichu", "personal_ai_astrology_yaml"],
1154:         },
1155:         "product": {
1156:             "type": "shichu_fortune_cycles_addon",
1157:             "label": "四柱推命：大運・流年追加",
1158:             "options": {
1159:                 "addon": True,
1160:                 "western_natal": False,
1161:                 "asteroids": False,
1162:                 "transit": False,
1163:                 "shichusuimei": True,
1164:                 "fortune_cycles": True,
1165:             },
1166:         },
1167:         "generated_at": full_doc.get("generated_at"),
1168:         "calculation": {
1169:             "engine": "nanami-products shichusuimei",
1170:             "engine_version": shichu.get("engine_version"),
1171:             "timezone": tz_name,
1172:             "day_change_at_23": assumptions.get("day_change_at_23"),
1173:             "day_boundary_hour": assumptions.get("day_boundary_hour"),
1174:             "day_boundary_rule": assumptions.get("day_boundary_rule"),
1175:             "time_context": shichu_input.get("time_context"),
1176:             "year_boundary_rule": assumptions.get("year_boundary_rule"),
1177:             "daiun_start_mode": assumptions.get("daiun_start_mode"),
1178:         },
1179:         "birth_time": full_doc.get("birth_time") or {},
1180:         "interpretation_flags": full_doc.get("interpretation_flags") or {},
1181:         "assets": {
1182:             "yaml_addon": {
1183:                 "available": True,
1184:                 "merge_path": "systems.shichusuimei",
1185:             },
1186:             "horoscope_svg": {"available": False},
1187:             "shichusuimei_svg": {"available": False},
1188:         },
1189:         "input": full_doc.get("input") or {},
1190:         "usage_note": {
1191:             "for_ai": "これは追加部品データです。四柱推命基本版YAMLと一緒にAIへ貼り付けて使ってください。",
1192:             "merge_instruction": "systems.shichusuimei.normalized_data.daiun、annual_fortune、annual_forecasts を、同じ出生情報で作成済みの四柱推命基本版YAMLへ追加する想定です。",
1193:             "not_included": "基本命式全体・通変星一覧・十二運一覧・神殺・五行バランス・鑑定本文は含みません。大運・流年追加用の計算済みデータです。",
1194:             "reference_scope": "流年の十神・十二運を読むため、日主と計算前提だけを最小参照情報として含めています。",
1195:         },
1196:         "systems": {
1197:             "western": None,
1198:             "shichusuimei": {
1199:                 "normalized_data": {
1200:                     "daiun": daiun,
1201:                     "annual_fortune": annual_fortune,
1202:                     "annual_forecasts": annual_forecasts,
1203:                 },
1204:                 "reference": {
1205:                     "day_master": shichu.get("day_master"),
1206:                     "day_kanshi": (normalized.get("pillars") or {}).get("day", {}).get("kanshi"),
1207:                     "assumptions": {
1208:                         "tz_name": assumptions.get("tz_name"),
1209:                         "day_change_at_23": assumptions.get("day_change_at_23"),
1210:                         "day_boundary_hour": assumptions.get("day_boundary_hour"),
1211:                         "day_boundary_rule": assumptions.get("day_boundary_rule"),
1212:                         "year_boundary_rule": assumptions.get("year_boundary_rule"),
1213:                         "daiun_start_mode": assumptions.get("daiun_start_mode"),
1214:                     },
1215:                     "note": "大運・流年の解釈に必要な最小参照です。基本命式の代替としては使わないでください。",
1216:                 },
1217:             },
1218:         },
1219:     }
1220:     validate_yaml_option_section_consistency(doc)
1221:     yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
1222:     return yaml_text, SHICHU_FORTUNE_CYCLES_ADDON_PROMPT.strip() + "\n", doc
```


## services/api_calc.py
```text
1: from __future__ import annotations
2: 
3: from datetime import date, datetime, time
4: from typing import Any
5: from zoneinfo import ZoneInfo
6: 
7: from services.api_tags import integration_tags, shichu_tags, transit_tags, western_tags
8: from services.api_yaml import build_handoff_yaml, build_ai_prompt_context
9: from services.yaml_exporter import build_product_yaml
10: from services.birth_datetime import BirthDatetimeError
11: 
12: API_VERSION = "1.0"
13: ENGINE_NAME = "nanami-products"
14: 
15: 
16: class ApiCalcError(Exception):
17:     def __init__(self, code: str, message: str, status_code: int = 400):
18:         super().__init__(message)
19:         self.code = code
20:         self.message = message
21:         self.status_code = status_code
22: 
23: 
24: def _error(code: str, message: str, *, status_code: int = 400) -> tuple[dict[str, Any], int]:
25:     return {
26:         "ok": False,
27:         "error": {
28:             "code": code,
29:             "message": message,
30:         },
31:     }, status_code
32: 
33: 
34: def _success(endpoint: str, input_data: dict[str, Any], doc: dict[str, Any], *, yaml_text: str | None = None) -> tuple[dict[str, Any], int]:
35:     raw_western = doc.get("systems", {}).get("western")
36:     raw_shichu = doc.get("systems", {}).get("shichusuimei")
37:     raw_transit = None
38:     if isinstance(raw_western, dict):
39:         raw_transit = raw_western.get("transit")
40: 
41:     western = raw_western if raw_western is not None else None
42:     shichu = raw_shichu if raw_shichu is not None else None
43: 
44:     tags_western = western_tags(western)
45:     tags_shichu = shichu_tags(shichu)
46:     tags_transit = transit_tags(raw_transit)
47:     tags_integration = integration_tags(western, shichu, raw_transit)
48: 
49:     writing = input_data.get("writing", {})
50:     tone = writing.get("tone", {}) if isinstance(writing, dict) else {}
51:     focus_areas_raw = writing.get("focus_areas", []) if isinstance(writing, dict) else []
52:     if isinstance(focus_areas_raw, list):
53:         focus_areas = [str(item) for item in focus_areas_raw if str(item).strip()]
54:     elif str(focus_areas_raw).strip():
55:         focus_areas = [str(focus_areas_raw).strip()]
56:     else:
57:         focus_areas = []
58:     writing_hints = {
59:         "tone": {
60:             "sharpness": int(tone.get("sharpness", 50)),
61:             "warmth": int(tone.get("warmth", 50)),
62:             "mystical": int(tone.get("mystical", 50)),
63:         },
64:         "focus_areas": focus_areas,
65:         "key_concepts": [
66:             tag["label"]
67:             for tag in sorted(
68:                 [*tags_western, *tags_shichu, *tags_transit, *tags_integration],
69:                 key=lambda item: (-int(item.get("strength", 0)), item.get("id", "")),
70:             )
71:             if int(tag.get("strength", 0)) > 0
72:         ][:5],
73:     }
74: 
75:     response_doc = {
76:         "meta": {
77:             "api_version": API_VERSION,
78:             "engine": ENGINE_NAME,
79:             "endpoint": endpoint,
80:         },
81:         "input": input_data,
82:         "raw_data": {
83:             "western": western,
84:             "shichu": shichu,
85:             "transit": raw_transit,
86:         },
87:         "interpreted_tags": {
88:             "western": tags_western,
89:             "shichu": tags_shichu,
90:             "transit": tags_transit,
91:             "integration": tags_integration,
92:         },
93:         "writing_hints": writing_hints,
94:         "ai_prompt_context": {
95:             "role": "構造分析型の占星術鑑定",
96:             "instruction": "raw_dataを直接断定せず、interpreted_tagsを主軸に鑑定文を作成してください。",
97:             "caution": [
98:                 "運命断定を避ける",
99:                 "不安を煽らない",
100:                 "basisがあるタグを優先する",
101:                 "strengthが高いタグを優先する",
102:             ],
103:         },
104:     }
105:     if isinstance(western, dict) and isinstance((western.get("natal") if western else None), dict):
106:         response_doc["chart"] = {
107:             "svg_available": False,
108:             "chart_id": None,
109:             "svg_url": None,
110:         }
111:     if isinstance(shichu, dict):
112:         response_doc["shichusuimei_chart"] = {
113:             "svg_available": False,
114:             "png_available": False,
115:             "chart_id": None,
116:             "svg_url": None,
117:             "png_url": None,
118:         }
119:     response_doc["ai_prompt_context"] = build_ai_prompt_context(doc, response_doc["ai_prompt_context"])
120:     response_doc["handoff_yaml"] = build_handoff_yaml(response_doc)
121:     if yaml_text and ("chart" in response_doc or "shichusuimei_chart" in response_doc):
122:         response_doc["_internal_chart_yaml_text"] = yaml_text
123:     return {
124:         "ok": True,
125:         **response_doc,
126:     }, 200
127: 
128: 
129: def _normalize_birth_place(payload: dict[str, Any]) -> str:
130:     birth_place = str(payload.get("birth_place") or payload.get("prefecture") or "").strip()
131:     if not birth_place:
132:         raise ApiCalcError("INVALID_INPUT", "birth_place is required", 400)
133:     return birth_place
134: 
135: 
136: def _normalize_timezone(payload: dict[str, Any]) -> str:
137:     tz = str(payload.get("timezone") or payload.get("tz_name") or "Asia/Tokyo").strip()
138:     tz = tz or "Asia/Tokyo"
139:     try:
140:         ZoneInfo(tz)
141:     except Exception as exc:
142:         raise ApiCalcError("INVALID_TIMEZONE", f"invalid timezone: {tz}", 400) from exc
143:     return tz
144: 
145: 
146: def _normalize_day_boundary(payload: dict[str, Any]) -> bool:
147:     return _normalize_day_boundary_hour(payload) == 23
148: 
149: 
150: def _normalize_shichu_timezone(payload: dict[str, Any]) -> str:
151:     raw = payload.get("timezone", payload.get("tz_name"))
152:     if raw is not None:
153:         if not str(raw).strip():
154:             raise ApiCalcError("INVALID_TIMEZONE", "an IANA birth timezone is required", 400)
155:         return _normalize_timezone(payload)
156:     # Preserve the domestic prefecture API default; an overseas place cannot
157:     # silently inherit that default or UTC.
158:     from services.location import resolve_prefecture
159:     try:
160:         resolve_prefecture(_normalize_birth_place(payload))
161:     except ValueError as exc:
162:         raise ApiCalcError("INVALID_TIMEZONE", "specify the overseas IANA birth timezone", 400) from exc
163:     return "Asia/Tokyo"
164: 
165: 
166: def _normalize_day_boundary_hour(payload: dict[str, Any]) -> int:
167:     raw = payload.get("day_boundary")
168:     value = str(raw if raw is not None else "").strip().lower()
169:     choices = {"": 1, "01:00": 1, "1": 1, "01": 1, "false": 1, "off": 1, "no": 1,
170:                "00:00": 0, "0": 0, "midnight": 0,
171:                "23:00": 23, "23": 23, "true": 23, "on": 23, "yes": 23}
172:     if value not in choices:
173:         raise ApiCalcError("INVALID_DAY_BOUNDARY", "day_boundary must be 00:00, 01:00 or 23:00", 400)
174:     return choices[value]
175: 
176: 
177: def _normalize_period(payload: dict[str, Any]) -> str:
178:     period = str(payload.get("period") or "month").strip().lower()
179:     if period not in {"day", "month"}:
180:         raise ApiCalcError("UNSUPPORTED_PERIOD", "period must be 'day' or 'month'", 400)
181:     return period
182: 
183: 
184: def _normalize_writing(payload: dict[str, Any]) -> dict[str, Any]:
185:     writing = payload.get("writing")
186:     return writing if isinstance(writing, dict) else {}
187: 
188: 
189: def _optional_float(payload: dict[str, Any], field_name: str) -> float | None:
190:     value = payload.get(field_name)
191:     if value in (None, ""):
192:         return None
193:     try:
194:         return float(value)
195:     except (TypeError, ValueError) as exc:
196:         raise ApiCalcError("INVALID_INPUT", f"{field_name} must be a number", 400) from exc
197: 
198: 
199: def _parse_date(value: Any, field_name: str) -> date:
200:     if not value:
201:         raise ApiCalcError("INVALID_INPUT", f"{field_name} is required", 400)
202:     try:
203:         return date.fromisoformat(str(value))
204:     except ValueError as exc:
205:         raise ApiCalcError("INVALID_INPUT", f"{field_name} must be YYYY-MM-DD", 400) from exc
206: 
207: 
208: def _parse_optional_datetime(value: Any, field_name: str, *, tz_name: str, default_hour: int = 12) -> datetime:
209:     target_date = _parse_date(value, field_name)
210:     return datetime.combine(target_date, time(default_hour, 0), tzinfo=ZoneInfo(tz_name))
211: 
212: 
213: def _build_doc(
214:     *,
215:     title: str | None,
216:     birth_date: str,
217:     birth_time: str | None,
218:     birth_place: str,
219:     birth_lat: float | None,
220:     birth_lng: float | None,
221:     tz_name: str,
222:     gender: str,
223:     include_asteroids: bool,
224:     include_shichusuimei: bool,
225:     include_transit: bool,
226:     transit_start_date: datetime | None = None,
227:     transit_days: int = 31,
228:     day_change_at_23: bool = False,
229:     day_boundary_hour: int | None = None,
230:     birth_fold: int | None = None,
231:     birth_utc_offset_hours: float | None = None,
232: ) -> dict[str, Any]:
233:     yaml_text, _prompt_text, doc = build_product_yaml(
234:         title=title,
235:         birth_date=birth_date,
236:         birth_time=birth_time,
237:         prefecture=birth_place,
238:         birth_place_label=birth_place,
239:         birth_lat=birth_lat,
240:         birth_lng=birth_lng,
241:         tz_name=tz_name,
242:         gender=gender,
243:         include_asteroids=include_asteroids,
244:         include_shichusuimei=include_shichusuimei,
245:         include_transit=include_transit,
246:         transit_start_date=transit_start_date,
247:         transit_days=transit_days,
248:         day_change_at_23=day_change_at_23,
249:         **({"day_boundary_hour": day_boundary_hour, "birth_fold": birth_fold,
250:             "birth_utc_offset_hours": birth_utc_offset_hours} if include_shichusuimei else {}),
251:     )
252:     return {
253:         "doc": doc,
254:         "yaml_text": yaml_text,
255:     }
256: 
257: 
258: def calc_western_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
259:     try:
260:         birth_date = str(payload.get("birth_date", "")).strip()
261:         tz_name = _normalize_timezone(payload)
262:         writing = _normalize_writing(payload)
263:         input_data = {
264:             "name": payload.get("name"),
265:             "birth_date": birth_date,
266:             "birth_time": payload.get("birth_time"),
267:             "birth_place": _normalize_birth_place(payload),
268:             "timezone": tz_name,
269:             "lat": payload.get("lat"),
270:             "lon": payload.get("lon"),
271:             "writing": writing,
272:         }
273:         if not birth_date:
274:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
275:         result = _build_doc(
276:             title=payload.get("name"),
277:             birth_date=birth_date,
278:             birth_time=str(payload.get("birth_time") or "").strip() or None,
279:             birth_place=input_data["birth_place"],
280:             birth_lat=_optional_float(payload, "lat"),
281:             birth_lng=_optional_float(payload, "lon"),
282:             tz_name=tz_name,
283:             gender=str(payload.get("gender") or "unknown"),
284:             include_asteroids=True,
285:             include_shichusuimei=False,
286:             include_transit=False,
287:         )
288:         return _success("western", input_data, result["doc"], yaml_text=result.get("yaml_text"))
289:     except ApiCalcError as exc:
290:         return _error(exc.code, exc.message, status_code=exc.status_code)
291:     except Exception as exc:
292:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
293: 
294: 
295: def calc_shichu_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
296:     try:
297:         birth_date = str(payload.get("birth_date", "")).strip()
298:         writing = _normalize_writing(payload)
299:         input_data = {
300:             "name": payload.get("name"),
301:             "birth_date": birth_date,
302:             "birth_time": payload.get("birth_time"),
303:             "birth_place": _normalize_birth_place(payload),
304:             "gender": payload.get("gender") or "unknown",
305:             "day_boundary": payload.get("day_boundary"),
306:             "writing": writing,
307:         }
308:         if not birth_date:
309:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
310:         result = _build_doc(
311:             title=payload.get("name"),
312:             birth_date=birth_date,
313:             birth_time=str(payload.get("birth_time") or "").strip() or None,
314:             birth_place=input_data["birth_place"],
315:             birth_lat=_optional_float(payload, "lat"),
316:             birth_lng=_optional_float(payload, "lon"),
317:             tz_name=_normalize_shichu_timezone(payload),
318:             gender=str(payload.get("gender") or "unknown"),
319:             include_asteroids=False,
320:             include_shichusuimei=True,
321:             include_transit=False,
322:             day_change_at_23=_normalize_day_boundary(payload),
323:             day_boundary_hour=_normalize_day_boundary_hour(payload),
324:             birth_fold=payload.get("birth_fold"),
325:             birth_utc_offset_hours=payload.get("birth_utc_offset_hours"),
326:         )
327:         return _success("shichu", input_data, result["doc"], yaml_text=result.get("yaml_text"))
328:     except BirthDatetimeError as exc:
329:         return _error("INVALID_BIRTH_DATETIME", str(exc), status_code=400)
330:     except ApiCalcError as exc:
331:         return _error(exc.code, exc.message, status_code=exc.status_code)
332:     except Exception as exc:
333:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
334: 
335: 
336: def calc_transit_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
337:     try:
338:         birth_date = str(payload.get("birth_date", "")).strip()
339:         if not birth_date:
340:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
341:         period = _normalize_period(payload)
342:         tz_name = _normalize_timezone(payload)
343:         writing = _normalize_writing(payload)
344:         target_date_value = payload.get("target_date") or birth_date
345:         target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
346:         transit_days = 1 if period == "day" else 31
347:         input_data = {
348:             "name": payload.get("name"),
349:             "birth_date": birth_date,
350:             "birth_time": payload.get("birth_time"),
351:             "birth_place": _normalize_birth_place(payload),
352:             "timezone": tz_name,
353:             "lat": payload.get("lat"),
354:             "lon": payload.get("lon"),
355:             "target_date": payload.get("target_date"),
356:             "period": period,
357:             "writing": writing,
358:         }
359:         result = _build_doc(
360:             title=payload.get("name"),
361:             birth_date=birth_date,
362:             birth_time=str(payload.get("birth_time") or "").strip() or None,
363:             birth_place=input_data["birth_place"],
364:             birth_lat=_optional_float(payload, "lat"),
365:             birth_lng=_optional_float(payload, "lon"),
366:             tz_name=tz_name,
367:             gender=str(payload.get("gender") or "unknown"),
368:             include_asteroids=False,
369:             include_shichusuimei=False,
370:             include_transit=True,
371:             transit_start_date=target_start,
372:             transit_days=transit_days,
373:         )
374:         return _success("transit", input_data, result["doc"], yaml_text=result.get("yaml_text"))
375:     except ApiCalcError as exc:
376:         return _error(exc.code, exc.message, status_code=exc.status_code)
377:     except Exception as exc:
378:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
379: 
380: 
381: def calc_combined_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
382:     try:
383:         birth_date = str(payload.get("birth_date", "")).strip()
384:         if not birth_date:
385:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
386:         period = _normalize_period(payload)
387:         tz_name = _normalize_shichu_timezone(payload)
388:         writing = _normalize_writing(payload)
389:         target_date_value = payload.get("target_date") or birth_date
390:         target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
391:         transit_days = 1 if period == "day" else 31
392:         input_data = {
393:             "name": payload.get("name"),
394:             "birth_date": birth_date,
395:             "birth_time": payload.get("birth_time"),
396:             "birth_place": _normalize_birth_place(payload),
397:             "timezone": tz_name,
398:             "lat": payload.get("lat"),
399:             "lon": payload.get("lon"),
400:             "gender": payload.get("gender") or "unknown",
401:             "target_date": payload.get("target_date"),
402:             "day_boundary": payload.get("day_boundary"),
403:             "period": period,
404:             "writing": writing,
405:         }
406:         result = _build_doc(
407:             title=payload.get("name"),
408:             birth_date=birth_date,
409:             birth_time=str(payload.get("birth_time") or "").strip() or None,
410:             birth_place=input_data["birth_place"],
411:             birth_lat=_optional_float(payload, "lat"),
412:             birth_lng=_optional_float(payload, "lon"),
413:             tz_name=tz_name,
414:             gender=str(payload.get("gender") or "unknown"),
415:             include_asteroids=True,
416:             include_shichusuimei=True,
417:             include_transit=True,
418:             transit_start_date=target_start,
419:             transit_days=transit_days,
420:             day_change_at_23=_normalize_day_boundary(payload),
421:             day_boundary_hour=_normalize_day_boundary_hour(payload),
422:             birth_fold=payload.get("birth_fold"),
423:             birth_utc_offset_hours=payload.get("birth_utc_offset_hours"),
424:         )
425:         return _success("combined", input_data, result["doc"], yaml_text=result.get("yaml_text"))
426:     except BirthDatetimeError as exc:
427:         return _error("INVALID_BIRTH_DATETIME", str(exc), status_code=400)
428:     except ApiCalcError as exc:
429:         return _error(exc.code, exc.message, status_code=exc.status_code)
430:     except Exception as exc:
431:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
```


## services/prompt_builder.py
```text
1: from __future__ import annotations
2: 
3: from services.birth_time import BIRTH_TIME_ACCURACY_NOTE
4: from services.companion_locales import build_localized_companion_prompt
5: from services.prompt_locales import SUPPORTED_PROMPT_LANGS, build_localized_prompt
6: 
7: SHICHUSUIMEI_STRUCTURE_GUIDANCE = """【四柱推命構造分析の優先規則】
8: - 新規計算の input.assumptions.day_boundary_rule と input.time_context を参照し、出生地の現地暦日と節入り用UTCを区別してください。日替わりは1時・23時・明示0時の方式差です。保存済み旧原本のbooleanを新方式へ読み替えず、計算済みの日柱・時柱を使ってください。
9: - 大運の status が undetermined_gender、direction が null の場合、性別未指定による保留です。女性へ補完せず、大運・起運・交運や大運との相互作用を推測しないでください。計算済み命式と流年の natal_analysis は利用できます。
10: - systems.shichusuimei.normalized_data.structural_analysis があれば、通根・透干・十神の配置と重みを単純個数より優先してください。日干自身は十神強度に含まれません。
11: - pattern_analysis と useful_god_analysis は試験的な方式別候補です。confidence、reasons、conflicting_rules、methodology.limitations を参照し、格局・用神・喜忌を確定しないでください。五行の不足だけで用神を決めないでください。
12: - ten_god_flow と element_flow の both_present は配置の併存です。食神・財星の個数や接続だけで、生財・制殺・金運の成立を断定しないでください。日主が財を扱う材料は day_master_support と財星の通根・透干を合わせて読んでください。
13: - 合・三合の存在だけで合化したと扱わず、combination_screening の条件材料を参照してください。
14: - annual_fortune の単年流年は「原本作成時の流年」です。会話時点の「今年」に置き換えないでください。年選択では year_selection.included_years と選択された年のデータだけを解釈し、選択外・未収録の年を推測・再計算しないでください。
15: - annual_forecasts があれば対象年の natal_analysis と daiun_contexts を参照してください。流年は立春から翌立春まで、大運の期間は近似起運年齢を出生日時へ加えた近似です。daiun_boundary_in_window の年は各候補の overlap_start_approx / overlap_end_approx を参照し、正確な交運日時を断定しないでください。
16: - 出生時刻不明・推定時は time_basis に従い三柱の構造分析を優先してください。仮置き時柱から構造を補完しないでください。旧五行集計・身強スコア・structure_report の全柱集計は参考値です。時柱に基づく蔵干・十二運・空亡・神殺の作用を確定根拠にしないでください。
17: - 旧YAMLの normalized_data.interactions や annual_fortune.relations に仮置き時柱が関わる合・冲・三合等が残っていても、時刻不明・推定時は確定根拠にしないでください。
18: - evidence_id が基本版に存在しない、または解決できない場合、その根拠を推測で補完しないでください。未収録の分析項目は自然に省略してください。"""
19: 
20: 
21: def ensure_shichusuimei_structure_guidance(prompt: str) -> str:
22:     if SHICHUSUIMEI_STRUCTURE_GUIDANCE in prompt:
23:         return prompt
24:     for marker in ("\n重要ルール:", "\n## 最重要ルール"):
25:         if marker in prompt:
26:             return prompt.replace(marker, f"\n\n{SHICHUSUIMEI_STRUCTURE_GUIDANCE}\n{marker}", 1)
27:     return SHICHUSUIMEI_STRUCTURE_GUIDANCE + "\n\n" + prompt
28: 
29: TRANSIT_DATE_GUIDANCE = (
30:     '- today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。',
31:     '- 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。',
32:     '- next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。',
33:     '- 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。',
34: )
35: 
36: DATA_USAGE_PRIORITY = """【データ利用の優先規則】
37: - 計算済みの値を再計算・訂正しない
38: - interpretation_flags と time_sensitive_provisional の指示を最優先する
39: - time_sensitive_provisional 内の値（ハウス・ASC/MC・アングルとのアスペクト）は仮定時刻による参考計算である。本人の確定的特徴として断定に使わない。可能性として触れる場合は「出生時刻が不確かなため暫定」と明示する。出生時刻が判明した場合は再計算が必要である
40: - データに存在しないセクションを推測で補完しない
41: - 配置と出来事の因果関係を断定しない"""
42: 
43: SHICHUSUIMEI_DATA_USAGE_PRIORITY = """【データ利用の優先規則】
44: - 計算済みの値を再計算・訂正しない
45: - birth_time.accuracy、time_sensitive_reference、time_basis と計算上の暫定フラグを最優先する
46: - データに存在しないセクションを推測で補完しない
47: - 計算結果、占術的な解釈、本人が話した客観的事実を区別する
48: - 配置と出来事の因果関係を断定しない"""
49: 
50: ACG_CONSULTATION_GUIDANCE = """【相談モード（ACG連携）】
51: ユーザーから旅行、移住、海外展開、活動場所、土地との相性について相談された場合は、出生図だけで判断せず、アストロカートグラフィも補助情報として利用してください。
52: 
53: アプリ:
54: https://chart.nanami-astro.com/acg?lang=ja&utm_source=chatgpt.com
55: 
56: AIがURLを参照できる場合は利用してください。
57: 
58: URLを参照できない場合は内容を推測しないでください。まず「ACGアプリへ貼り付ける占術YAMLをこの会話に表示しますか？」とユーザーに確認してください。
59: 
60: ユーザーが「はい」と答え、会話開始時に渡された元の占術YAMLを参照できる場合は、そのYAMLを要約・再計算・書き換えせず、YAMLコードブロックでそのまま再掲してください。元のYAMLを正確に参照できない場合は再構成や推測をせず、再掲できないことを伝えてください。
61: 
62: その後、ユーザーにYAMLをACGアプリへ貼り付けて対象地点を検索してもらい、ACGアプリから出力されたYAMLを会話へ貼り付けてもらうよう案内してください。
63: 
64: アストロカートグラフィ単独では判断せず、出生図・現在のトランジット・相談内容を合わせて解釈してください。"""
65: 
66: CHART_COMPANION_PROMPT = """あなたは「Chart Companion」です。
67: 
68: あなたは、西洋占星術の計算済みデータをもとに相談を受けるAI占い師です。
69: 
70: 以下のYAMLには、相談者の出生図と現在のトランジットが含まれています。
71: 
72: ## 最重要ルール
73: 
74: - interpretation_flags と time_sensitive_provisional の指示を最優先してください。
75: - time_sensitive_provisional 内の値は仮定時刻による参考計算です。本人の確定的特徴として断定せず、可能性として触れる場合は「出生時刻が不確かなため暫定」と明示してください。出生時刻が判明した場合は再計算が必要です。
76: - データに存在しないセクションを推測で補完しないでください。
77: - YAML内の天体位置、ハウス、アスペクト、トランジットは計算済みです。
78: - 生年月日から再計算しないでください。
79: - YAML内の計算結果を変更しないでください。
80: - YAML内の値を占術的な唯一の根拠として扱ってください。
81: - mundane_houseは出生図への解釈根拠として使用しないでください。
82: - transiting_bodies[].natal_houseがある場合は、出生図に対する在住ハウスとして参照してください。
83: - today.selected_dateを基準日として扱ってください。
84: - 基準日より前の日付を、今後の予定として扱わないでください。
85: 
86: ## あなたの役割
87: 
88: あなたは、一度鑑定して終わるAIではありません。
89: 
90: 相談者の出生図と現在の星の流れを理解した占い師として、仕事、創作、人間関係、活動、収益化、今後の方針などの相談に乗ってください。
91: 
92: 占星術だけで答えを決めず、以下を区別して考えてください。
93: 
94: 1. YAMLから確認できる占術的な傾向
95: 2. 相談者が会話内で伝えた現実の状況
96: 3. あなたが提案する選択肢や行動案
97: 
98: 占術的な傾向を、現実の事実のように断定しないでください。
99: 
100: ## 話し方
101: 
102: - 西洋占星術の鑑定者として自然に話してください。
103: - 丁寧ですが、過剰に堅くしないでください。
104: - 一般論だけで終わらせないでください。
105: - 必要な場面では、どの天体・ハウス・アスペクト・トランジットを根拠にしたか示してください。
106: - 毎回すべての配置を説明する必要はありません。
107: - 相談内容に関係する配置だけを選んでください。
108: - 「ラッキー」「絶対に成功する」などの軽い断定表現は避けてください。
109: - 病気、死、妊娠、事故、法律、投資などの重大事項を占星術だけで断定しないでください。
110: - 不安を煽らないでください。
111: - 励ますだけではなく、問題点や現実的な条件も整理してください。
112: - 相談者の意思を尊重してください。
113: - 「やったほうがいいこと」だけでなく、「やらなくていいこと・向いていないこと」も同じ重みで示してください。相談者の負担や行動を増やす方向だけに寄せないでください。
114: - 一般的な励まし（「一歩踏み出そう」「まずは小さく始めよう」「打席に立つ回数を増やそう」など）で回答を締めないでください。締めは、相談者固有の配置・状況に紐づいた、その人にしか当てはまらない一言にしてください。
115: 
116: ## 相談開始時の動作
117: 
118: 最初の回答では、長い総合鑑定を出さないでください。
119: 
120: 1. 相談者へ挨拶する
121: 2. 出生図と現在の流れから、相談時に参考になりそうな特徴を短く2〜4点だけ示す
122: 3. 「今日は何について相談したいですか」と尋ねる
123: 4. 必要なら相談テーマの例を少数示す
124: 
125: 相談テーマがまだ分からない段階で、一方的に仕事、恋愛、健康などを長く鑑定しないでください。
126: 
127: ## 相談中の動作
128: 
129: 相談者がテーマを話したら、以下の順番で考えてください。
130: 
131: 1. 相談内容を短く整理する
132: 2. 足りない現実情報があれば質問する
133: 3. 関係する出生図の配置を選ぶ
134: 4. 現在のトランジットを必要な範囲で参照する
135: 5. 現実的な選択肢を提示する
136: 6. それぞれの利点・懸念点を整理する。両立しにくい選択肢がある場合は、どちらを選び、どちらを捨てるかの判断まで踏み込んでください。すべてを頑張る前提で締めないでください。
137: 7. 必要な場合は、今日または今週できる具体的な一歩を提案する。まだ動かない方がよい場合は、「今は決めない」「確認だけする」「保留する」も具体的な提案として扱ってください。
138: 
139: 星の説明が相談の中心になりすぎないようにしてください。相談者が占術的な詳しい説明を求めた場合は、根拠を詳しく説明してください。
140: 
141: ## 結論の出し方
142: 
143: - 提案や結論は、可能な範囲で特定の天体・ハウス・アスペクト・トランジットに紐づけてください。占星術に一切触れずに成立する一般的なアドバイス（継続する、PDCAを回す、発信量を増やす、など）「だけ」で結論を出さないでください。
144: - 相談者を励ますことよりも、現実的な制約・トレードオフを正確に整理することを優先してください。
145: - 相談者の性質や現在の条件と噛み合いにくい選択肢は、無理に前向きに扱わず、「負担が大きい」「継続しにくい」「優先度が低い」と明確に伝えてください。
146: - 「向いていない」と判断する場合は、出生図だけで断定せず、相談者が話した経験・負担感・現実条件と、関連する配置の両方を根拠にしてください。
147: - 配置の根拠が薄い場合に、結論を正当化するために無理な占星術的こじつけをしないでください。根拠が弱いときは、現実情報を軸に整理してください。
148: - 現実情報が不足していても、分かる範囲の暫定結論は先に示してください。回答に不可欠な情報だけを、最大1〜2問に絞って確認してください。確認質問を並べて結論を先延ばしにしないでください。
149: - 締めの一言は、相談者固有の配置または現在の状況に結びつけ、直前に提示した結論を短く固定する内容にしてください。抽象的な詩や励ましだけで締めないでください。
150: - 相談者が明言していない感情・動機・過去の経験を、出生図だけから事実のように補完しないでください。推測する場合は、推測であることを明示してください。
151: 
152: ## 継続相談
153: 
154: 同じ会話内で鑑定後に質問された場合は、最初の鑑定内容と相談者の発言を引き継いでください。「先ほどの鑑定では」「今のお話を踏まえると」など、会話の連続性が感じられる応答にしてください。同じ出生図の説明を毎回最初から繰り返さないでください。
155: 
156: ## 回答の基本構成
157: 
158: 相談内容に応じて柔軟に変えて構いませんが、基本は以下です。
159: 
160: - 今の状況の整理
161: - 出生図から見た関連傾向
162: - 現在の流れ
163: - 現実的な選択肢
164: - 今日または今週の一歩、または今は動かない判断
165: - 必要な確認質問
166: 
167: 以下のYAMLを読み込み、Chart Companionとして相談を開始してください。
168: 以下がYAMLデータです。
169: """
170: 
171: CHART_COMPANION_PROMPT = CHART_COMPANION_PROMPT.replace(
172:     "\n以下のYAMLを読み込み、Chart Companionとして相談を開始してください。",
173:     f"\n{ACG_CONSULTATION_GUIDANCE}\n\n以下のYAMLを読み込み、Chart Companionとして相談を開始してください。",
174:     1,
175: )
176: 
177: SHICHUSUIMEI_CHART_COMPANION_PROMPT = """あなたは「Chart Companion」です。
178: あなたは、四柱推命の計算済みデータをもとに相談を受けるAI占い師です。
179: 以下のYAMLには、命式・五行・通変星・十二運・大運・流年など、商品に含まれる範囲の計算済みデータが入っています。
180: 
181: ## 最重要ルール
182: 
183: - YAML内の四柱推命の計算結果を唯一の占術的根拠として扱ってください。
184: - 生年月日や出生時刻から命式を再計算しないでください。
185: - 干支、蔵干、通変星、十二運、五行バランス、大運、流年などの値を変更しないでください。
186: - YAMLに存在しない項目を推測で補完しないでください。
187: - 吉凶や未来を断定せず、傾向・選択肢・活かし方として表現してください。
188: - 病気、死、妊娠、事故、法律、投資などの重大事項を四柱推命だけで断定しないでください。
189: 
190: ## あなたの役割
191: 
192: 一度鑑定して終わるAIではありません。命式と運気の流れを理解した相談相手として、仕事、創作、人間関係、生活、意思決定などの相談に応じてください。
193: 占術的な傾向、相談者が伝えた現実の状況、実行可能な選択肢を分けて整理してください。
194: 
195: ## 相談開始時
196: 
197: 最初の回答では長い総合鑑定を始めないでください。
198: 1. 挨拶する
199: 2. YAMLから確認できる、相談時に参考になりそうな特徴を1〜2点だけ示す
200: 3. 「今日は何について相談したいですか」と尋ねる
201: 4. 必要なら相談テーマの例を少数示す
202: 
203: ## 相談中
204: 
205: - 相談内容を短く整理する
206: - 関係する命式・五行・通変星・十二運・大運・流年のデータだけを選ぶ
207: - 占術上の傾向と現実的な条件を分ける
208: - 選択肢ごとの利点と注意点を整理する
209: - 今日または今週できる具体的な一歩を提案する。まだ動かない方がよい場合は「決めない」「確認する」「保留する」も具体的な選択肢として扱う
210: - 不足情報がある場合は、回答に不可欠な質問を最大1つだけ確認する
211: 
212: 以下のYAMLを読み込み、Chart Companionとして相談を開始してください。
213: 以下がYAMLデータです。"""
214: 
215: SHICHUSUIMEI_CHART_COMPANION_PROMPT = ensure_shichusuimei_structure_guidance(SHICHUSUIMEI_CHART_COMPANION_PROMPT)
216: 
217: def build_chart_companion_prompt(
218:     *, lang: str = "ja", include_shichusuimei: bool = False,
219:     include_western: bool | None = None,
220: ) -> str:
221:     """Return the consultation-mode prompt in the buyer's selected language."""
222:     if include_western is None:
223:         include_western = not include_shichusuimei
224:     if include_western and include_shichusuimei:
225:         return (
226:             build_chart_companion_prompt(lang=lang, include_western=True)
227:             + "\n"
228:             + build_chart_companion_prompt(lang=lang, include_shichusuimei=True, include_western=False)
229:         )
230:     if lang in SUPPORTED_PROMPT_LANGS:
231:         return build_localized_companion_prompt(
232:             lang=lang,
233:             include_shichusuimei=include_shichusuimei,
234:         )
235:     prompt = (
236:         SHICHUSUIMEI_CHART_COMPANION_PROMPT
237:         if include_shichusuimei
238:         else CHART_COMPANION_PROMPT
239:     )
240:     return prompt.strip() + "\n"
241: 
242: WESTERN_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、天体計算済みの出生図データです。
243: 
244: 重要ルール:
245: - 天体位置・ハウス・アスペクトの計算結果は変更しないでください。
246: - 生年月日から再計算しないでください。
247: - YAML内の計算結果を唯一の根拠として解釈してください。
248: - 断定しすぎず、傾向・使い方・活かし方として表現してください。
249: - 一般論だけではなく、配置同士のつながりから具体的に読んでください。
250: - このYAMLは出生図の基礎データです。後からトランジット追加YAMLが渡された場合は、再計算せず、この出生図を土台に現在や今後の流れを重ねて読んでください。
251: 
252: 出力してほしい内容:
253: - 全体像
254: - 才能・強み
255: - つまずきやすいパターン
256: - 仕事・活動の向き
257: - 人間関係の傾向
258: - 今後の活かし方
259: 
260: 以下のYAMLを読み込んで鑑定してください。
261: """
262: 
263: WESTERN_TRANSIT_PROMPT_TEMPLATE = """あなたは西洋占星術の鑑定者です。以下のYAMLは、{data_description}を含む計算済みデータです。
264: 
265: 重要ルール:
266: - 天体位置・ハウス・アスペクト・トランジットの計算結果は変更しないでください。
267: - 生年月日から再計算しないでください。
268: - YAML内の計算結果を唯一の根拠として解釈してください。
269: - 断定しすぎず、傾向・使い方・活かし方として表現してください。
270: - 出生図を土台に、{transit_instruction}をつなげて読んでください。
271: - 月は朝・昼・夜の動きが入っています。日内の変化を読む時に参照してください。
272: - transitデータは「現在の流れ」の根拠として使ってください。
273: - moon_timepoints は「朝・昼・夜」の日内の使い方の根拠として使ってください。
274: - 今後数日の動きは、トランジットのタイトなアスペクトを優先して判断してください。
275: - transiting_bodies[].natal_house は出生図カスプに対する在住ハウスです。mundane_house はその時刻のマンデンハウスなので、出生図への解釈根拠にしないでください。
276: - today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。
277: - 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。
278: - next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。
279: - 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。
280: - 「良い・悪い」ではなく、「どう使うとズレにくいか」を優先して書いてください。
281: - 「ラッキー」などの軽い表現は避け、具体的な行動ヒントに置き換えてください。
282: 
283: 出力してほしい内容:
284: - 全体像
285: - 才能・強み
286: - つまずきやすいパターン
287: - 仕事・活動の向き
288: - 人間関係の傾向
289: - 今後31日間の流れ
290: - 動きやすい日・注意したい日
291: - 現在の流れ（トランジット）
292: - 今日の使い方（朝・昼・夜）
293: - 今後数日の動き
294: - 今後の活かし方
295: 
296: 以下のYAMLを読み込んで鑑定してください。
297: """
298: 
299: WESTERN_FULL_PROMPT = WESTERN_TRANSIT_PROMPT_TEMPLATE.format(
300:     data_description="出生図・小惑星・31日分のトランジット",
301:     transit_instruction="小惑星と今後31日分のトランジット",
302: )
303: 
304: SHICHUSUIMEI_PROMPT = """あなたは四柱推命の鑑定者です。以下のYAMLは、四柱・蔵干・十神・十二運・五行バランス・大運・流年・刑冲合害・神殺を含む計算済みデータです。
305: 
306: 重要ルール:
307: - 四柱推命の計算結果は変更しないでください。
308: - 生年月日から再計算しないでください。
309: - YAML内の計算結果を唯一の根拠として解釈してください。
310: - 断定しすぎず、傾向・使い方・活かし方として表現してください。
311: - 出生時刻と time_sensitive_reference の前提を守り、日干、月令、信頼できる五行・十神・十二運・身強材料、空亡（旬空）、大運、流年、刑冲合害、神殺のつながりから具体的に読んでください。
312: - 神殺は補助情報として扱い、命式全体・大運・流年より優先しすぎないでください。
313: - 神殺データがYAMLにない場合は、神殺の項目は無理に作らずスキップしてください。
314: - 流年は収録された対象年のデータとして扱い、命式・大運との関係を優先して読んでください。
315: 
316: 出力してほしい内容:
317: - 命式の全体像
318: - 日干と五行バランス
319: - 才能・強み
320: - つまずきやすいパターン
321: - 仕事・活動の向き
322: - 人間関係の傾向
323: - 大運の流れ
324: - 原本作成時の流年、または指定した収録年と刑冲合害から見たテーマ
325: - 天乙貴人・文昌・天徳が示す補助的な強み
326: - 今後の活かし方
327: 
328: 以下のYAMLを読み込んで鑑定してください。
329: """
330: 
331: 
332: SHICHUSUIMEI_PROMPT = ensure_shichusuimei_structure_guidance(SHICHUSUIMEI_PROMPT)
333: 
334: 
335: def ensure_transit_date_guidance(prompt: str) -> str:
336:     if all(line in prompt for line in TRANSIT_DATE_GUIDANCE):
337:         return prompt
338:     guidance = "\n".join(line for line in TRANSIT_DATE_GUIDANCE if line not in prompt)
339:     for marker in ("\n出力してほしい内容:", "\n以下のYAMLを読み込んで"):
340:         if marker in prompt:
341:             return prompt.replace(marker, f"\n{guidance}\n{marker}", 1)
342:     return prompt.rstrip() + "\n" + guidance + "\n"
343: 
344: 
345: def ensure_data_usage_priority(prompt: str, *, shichusuimei_only: bool = False) -> str:
346:     guidance = SHICHUSUIMEI_DATA_USAGE_PRIORITY if shichusuimei_only else DATA_USAGE_PRIORITY
347:     if guidance in prompt:
348:         return prompt
349:     marker = "\n重要ルール:"
350:     if marker in prompt:
351:         return prompt.replace(marker, f"\n\n{guidance}\n{marker}", 1)
352:     return guidance + "\n\n" + prompt
353: 
354: 
355: def ensure_acg_consultation_guidance(prompt: str) -> str:
356:     if ACG_CONSULTATION_GUIDANCE in prompt:
357:         return prompt
358:     for marker in ("\n出力してほしい内容:", "\n以下のYAMLを読み込んで"):
359:         if marker in prompt:
360:             return prompt.replace(marker, f"\n\n{ACG_CONSULTATION_GUIDANCE}\n{marker}", 1)
361:     return prompt.rstrip() + "\n\n" + ACG_CONSULTATION_GUIDANCE + "\n"
362: 
363: 
364: def build_prompt(
365:     *,
366:     include_shichusuimei: bool = False,
367:     include_asteroids: bool = False,
368:     include_transit: bool = False,
369:     birth_time_accuracy: str = "exact",
370:     interpretation_flags: dict | None = None,
371:     lang: str = "ja",
372:     include_western: bool | None = None,
373: ) -> str:
374:     if include_western is None:
375:         # Compatibility for callers without a document; document-based callers
376:         # pass the actual systems explicitly, independently of product labels.
377:         include_western = not include_shichusuimei or include_asteroids or include_transit
378:     if not include_western:
379:         include_asteroids = include_transit = False
380:     flags = interpretation_flags or {}
381:     time_sensitive = (
382:         birth_time_accuracy in {"unknown", "approximate"}
383:         or (include_western and bool(flags.get("use_houses_as_reference_only")))
384:     )
385:     if lang in SUPPORTED_PROMPT_LANGS:
386:         return build_localized_prompt(
387:             lang=lang,
388:             include_shichusuimei=include_shichusuimei,
389:             include_asteroids=include_asteroids,
390:             include_transit=include_transit,
391:             time_sensitive=time_sensitive,
392:             include_western=include_western,
393:         )
394:     if include_shichusuimei and not include_western:
395:         prompt = SHICHUSUIMEI_PROMPT
396:     elif include_transit:
397:         if include_asteroids:
398:             data_description = "出生図・小惑星・31日分のトランジット"
399:             transit_instruction = "小惑星と今後31日分のトランジット"
400:         else:
401:             data_description = "出生図・31日分のトランジット"
402:             transit_instruction = "今後31日分のトランジット"
403:         prompt = WESTERN_TRANSIT_PROMPT_TEMPLATE.format(
404:             data_description=data_description,
405:             transit_instruction=transit_instruction,
406:         )
407:     else:
408:         prompt = WESTERN_PROMPT
409:     if include_shichusuimei and include_western:
410:         prompt += "\n\n" + SHICHUSUIMEI_PROMPT
411:     if include_shichusuimei:
412:         prompt = ensure_shichusuimei_structure_guidance(prompt)
413:     prompt = ensure_data_usage_priority(prompt, shichusuimei_only=include_shichusuimei and not include_western)
414:     if include_western:
415:         prompt = ensure_acg_consultation_guidance(prompt)
416:     if time_sensitive and include_western:
417:         prompt = prompt.replace("以下のYAMLを読み込んで鑑定してください。", BIRTH_TIME_ACCURACY_NOTE + "\n\n以下のYAMLを読み込んで鑑定してください。")
418:     return prompt.strip() + "\n"
```


## services/shichu_chart.py
```text
1: from __future__ import annotations
2: 
3: import html
4: from typing import Any
5: 
6: import yaml
7: 
8: PILLARS = [
9:     ("year", "年柱"),
10:     ("month", "月柱"),
11:     ("day", "日柱"),
12:     ("hour", "時柱"),
13: ]
14: 
15: ELEMENT_COLORS = {
16:     "木": "#6f8f4f",
17:     "火": "#b65b44",
18:     "土": "#a98349",
19:     "金": "#9a8b73",
20:     "水": "#517c9b",
21: }
22: 
23: 
24: def _attrs(**attrs: Any) -> str:
25:     normalized = []
26:     for key, value in attrs.items():
27:         attr_name = key.rstrip("_").replace("_", "-")
28:         normalized.append(f'{attr_name}="{html.escape(str(value))}"')
29:     return " ".join(normalized)
30: 
31: 
32: def _text(x: float, y: float, value: Any, **attrs: Any) -> str:
33:     return f'<text x="{x:.2f}" y="{y:.2f}" {_attrs(**attrs)}>{html.escape(_label(value))}</text>'
34: 
35: 
36: def _rect(x: float, y: float, width: float, height: float, **attrs: Any) -> str:
37:     return f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" {_attrs(**attrs)}/>'
38: 
39: 
40: def _label(value: Any, fallback: str = "不明") -> str:
41:     if value is None:
42:         return fallback
43:     text = str(value).strip()
44:     return text if text else fallback
45: 
46: 
47: def _display_title(value: Any, fallback: str) -> str:
48:     title = str(value or "").strip()
49:     if not title:
50:         return fallback
51:     if title.endswith("さん"):
52:         return title
53:     return f"{title}さん"
54: 
55: 
56: def _nested(data: dict[str, Any], *keys: str) -> Any:
57:     current: Any = data
58:     for key in keys:
59:         if not isinstance(current, dict):
60:             return None
61:         current = current.get(key)
62:     return current
63: 
64: 
65: def _hidden_stems_label(items: Any) -> str:
66:     if isinstance(items, list):
67:         values = [_label(item, "") for item in items if _label(item, "")]
68:         return "・".join(values) if values else "不明"
69:     return _label(items)
70: 
71: 
72: def _hidden_ten_gods_label(items: Any) -> str:
73:     if not isinstance(items, list):
74:         return "不明"
75:     labels = []
76:     for item in items:
77:         if isinstance(item, dict):
78:             labels.append(f"{_label(item.get('stem'), '')}{_label(item.get('ten_god'), '')}")
79:     return " / ".join(label for label in labels if label) or "不明"
80: 
81: 
82: def _pillar_ten_god(ten_gods: dict[str, Any], pillar_key: str) -> str:
83:     if pillar_key == "day":
84:         return "日主"
85:     value = _nested(ten_gods, "pillars", pillar_key, "ten_god")
86:     return _label(value)
87: 
88: 
89: def _has_shichu_data(doc: dict[str, Any]) -> bool:
90:     normalized = _nested(doc, "systems", "shichusuimei", "normalized_data")
91:     return isinstance(normalized, dict) and isinstance(normalized.get("pillars"), dict)
92: 
93: 
94: def has_shichusuimei_chart_data(yaml_text: str) -> bool:
95:     try:
96:         doc = yaml.safe_load(yaml_text) or {}
97:     except Exception:
98:         return False
99:     return _has_shichu_data(doc)
100: 
101: 
102: def build_shichusuimei_svg_from_yaml(yaml_text: str, *, compact: bool = False, doc: dict[str, Any] | None = None) -> str | None:
103:     doc = doc if isinstance(doc, dict) else (yaml.safe_load(yaml_text) or {})
104:     if not _has_shichu_data(doc):
105:         return None
106: 
107:     shichu = _nested(doc, "systems", "shichusuimei") or {}
108:     normalized = shichu.get("normalized_data") or {}
109:     input_block = doc.get("input") or {}
110:     title = _display_title(input_block.get("title"), "Four pillars")
111:     birth_date = input_block.get("birth_date") or ""
112:     calculation_time = input_block.get("calculation_time") or input_block.get("birth_time") or ""
113:     place = input_block.get("birth_place") or ""
114: 
115:     pillars = normalized.get("pillars") or {}
116:     hidden_stems = normalized.get("hidden_stems") or {}
117:     ten_gods = normalized.get("ten_gods") or {}
118:     hidden_ten_gods = (ten_gods.get("hidden_stems") if isinstance(ten_gods, dict) else {}) or {}
119:     twelve_fortune = normalized.get("twelve_fortune") or {}
120:     kubo = normalized.get("kubo") or {}
121:     five_elements = (normalized.get("five_elements") or {}).get("with_hidden_stems") or (normalized.get("five_elements") or {}).get("visible") or {}
122:     daiun_items = _nested(normalized, "daiun", "items") or []
123:     day_master = _label(_nested(ten_gods, "day_master"), "")
124: 
125:     if compact:
126:         width = 940
127:         height = 780
128:         pad = 42
129:         title_y = 58
130:         table_y = 118
131:         table_h = 382
132:         bar_y = 548
133:     else:
134:         width = 1080
135:         height = 1280
136:         pad = 74
137:         title_y = 112
138:         table_y = 216
139:         table_h = 470
140:         bar_y = 770
141: 
142:     table_x = pad
143:     table_w = width - pad * 2
144:     label_w = 142 if compact else 160
145:     col_w = (table_w - label_w) / 4
146:     row_labels = [
147:         ("干支", "kanshi"),
148:         ("天干", "stem"),
149:         ("地支", "branch"),
150:         ("蔵干", "hidden_stems"),
151:         ("通変星", "ten_god"),
152:         ("蔵干通変", "hidden_ten_god"),
153:         ("十二運", "twelve_fortune"),
154:         ("空亡", "kubo"),
155:     ]
156:     header_h = 54 if compact else 62
157:     row_h = (table_h - header_h) / len(row_labels)
158: 
159:     parts: list[str] = [
160:         f'<svg class="shichu-chart-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="四柱推命 命式図">',
161:         "<defs>",
162:         '<style>.shichu-chart-svg text{font-family:"Noto Sans JP","Hiragino Sans","Yu Gothic","Meiryo",sans-serif}.title{font-size:42px;font-weight:700}.meta{font-size:21px;letter-spacing:.03em}.small{font-size:19px}.cell-label{font-size:20px;font-weight:700}.pillar-head{font-size:24px;font-weight:700}.kanshi,.cell-main,.cell-sub{font-size:23px;font-weight:600}.footer{font-size:18px;letter-spacing:.04em}</style>',
163:         '<radialGradient id="shichuBg" cx="50%" cy="42%" r="72%"><stop offset="0%" stop-color="#fffaf2"/><stop offset="66%" stop-color="#f3eadc"/><stop offset="100%" stop-color="#e7d5bd"/></radialGradient>',
164:         "</defs>",
165:     ]
166: 
167:     if compact:
168:         parts.append(_rect(0, 0, width, height, fill="#fffaf2"))
169:     else:
170:         parts.extend([
171:             _rect(0, 0, width, height, fill="url(#shichuBg)"),
172:             _rect(52, 52, width - 104, height - 104, rx="36", fill="none", stroke="#b79b74", stroke_width="2"),
173:         ])
174: 
175:     parts.append(_text(width / 2, title_y, str(title), fill="#3b2b1d", text_anchor="middle", class_="title"))
176:     parts.append(_text(width / 2, title_y + 40, f"四柱推命 命式図 / {birth_date} {calculation_time} / {place}", fill="#80684a", text_anchor="middle", class_="meta"))
177:     if day_master:
178:         parts.append(_text(width / 2, title_y + 76, f"日主: {day_master}", fill="#8a5c24", text_anchor="middle", font_size="24", font_weight="700"))
179: 
180:     parts.append(_rect(table_x, table_y, table_w, table_h, rx="18", fill="rgba(255,255,255,.5)", stroke="#9d7c54", stroke_width="2"))
181:     parts.append(_rect(table_x, table_y, label_w, header_h, fill="#ead8bd", stroke="#c1a077", stroke_width="1"))
182:     for idx, (_key, label) in enumerate(PILLARS):
183:         x = table_x + label_w + idx * col_w
184:         parts.append(_rect(x, table_y, col_w, header_h, fill="#ead8bd", stroke="#c1a077", stroke_width="1"))
185:         parts.append(_text(x + col_w / 2, table_y + 38, label, fill="#4a321f", text_anchor="middle", class_="pillar-head"))
186: 
187:     for row_idx, (row_label, field) in enumerate(row_labels):
188:         y = table_y + header_h + row_idx * row_h
189:         parts.append(_rect(table_x, y, label_w, row_h, fill="#f5ead8", stroke="#d3b991", stroke_width="1"))
190:         parts.append(_text(table_x + label_w / 2, y + row_h / 2 + 7, row_label, fill="#74563a", text_anchor="middle", class_="cell-label"))
191:         for col_idx, (pillar_key, _pillar_label) in enumerate(PILLARS):
192:             x = table_x + label_w + col_idx * col_w
193:             fill = "#fffaf2"
194:             if pillar_key == "day" and field in {"kanshi", "stem"}:
195:                 fill = "#f3dfb7"
196:             parts.append(_rect(x, y, col_w, row_h, fill=fill, stroke="#d3b991", stroke_width="1"))
197:             pillar = pillars.get(pillar_key) if isinstance(pillars, dict) else {}
198:             if not isinstance(pillar, dict):
199:                 pillar = {}
200:             if field == "hidden_stems":
201:                 value = _hidden_stems_label(hidden_stems.get(pillar_key))
202:                 class_name = "cell-sub"
203:             elif field == "hidden_ten_god":
204:                 value = _hidden_ten_gods_label(hidden_ten_gods.get(pillar_key))
205:                 class_name = "cell-sub"
206:             elif field == "ten_god":
207:                 value = _pillar_ten_god(ten_gods, pillar_key)
208:                 class_name = "cell-main"
209:             elif field == "twelve_fortune":
210:                 value = _label(twelve_fortune.get(pillar_key))
211:                 class_name = "cell-main"
212:             elif field == "kubo":
213:                 hits = kubo.get("hits") if isinstance(kubo, dict) else {}
214:                 value = "該当" if isinstance(hits, dict) and hits.get(pillar_key) else "なし"
215:                 class_name = "cell-main"
216:             else:
217:                 value = _label(pillar.get(field))
218:                 class_name = "kanshi" if field == "kanshi" else "cell-main"
219:             parts.append(_text(x + col_w / 2, y + row_h / 2 + 7, value, fill="#3c2a1a", text_anchor="middle", class_=class_name))
220: 
221:     empty_branches = kubo.get("empty_branches") if isinstance(kubo, dict) else []
222:     empty_text = "・".join(empty_branches) if isinstance(empty_branches, list) and empty_branches else "不明"
223:     parts.append(_text(table_x, table_y + table_h + 36, f"空亡: {empty_text}", fill="#705235", class_="small"))
224: 
225:     bar_x = table_x
226:     bar_w = table_w
227:     max_value = max([float(v) for v in five_elements.values()] or [1.0])
228:     parts.append(_text(bar_x, bar_y, "五行バランス", fill="#3b2b1d", font_size="28", font_weight="700"))
229:     element_y = bar_y + 34
230:     for idx, element in enumerate(["木", "火", "土", "金", "水"]):
231:         value = float(five_elements.get(element) or 0)
232:         y = element_y + idx * 45
233:         parts.append(_text(bar_x, y + 24, element, fill="#4a321f", font_size="24", font_weight="700"))
234:         parts.append(_rect(bar_x + 44, y + 4, bar_w - 120, 24, rx="12", fill="#eadbc6", stroke="#d2b991", stroke_width="1"))
235:         parts.append(_rect(bar_x + 44, y + 4, (bar_w - 120) * (value / max_value if max_value else 0), 24, rx="12", fill=ELEMENT_COLORS[element]))
236:         parts.append(_text(bar_x + bar_w - 54, y + 24, str(int(value) if value.is_integer() else value), fill="#4a321f", text_anchor="middle", font_size="20"))
237: 
238:     if isinstance(daiun_items, list) and daiun_items:
239:         daiun_y = element_y + 5 * 45 + 40
240:         parts.append(_text(bar_x, daiun_y, "大運（先頭のみ）", fill="#3b2b1d", font_size="24", font_weight="700"))
241:         chips = []
242:         for item in daiun_items[:5]:
243:             if isinstance(item, dict):
244:                 age = _label(item.get("start_age"), "")
245:                 kanshi = _label(item.get("kanshi"), "")
246:                 chips.append(f"{age}歳 {kanshi}".strip())
247:         parts.append(_text(bar_x, daiun_y + 34, " / ".join(chips) or "不明", fill="#705235", class_="small"))
248:     elif _nested(normalized, "daiun", "status") == "undetermined_gender":
249:         parts.append(_text(bar_x, element_y + 5 * 45 + 40, "大運：未確定（性別未指定）", fill="#705235", class_="small"))
250: 
251:     if not compact:
252:         parts.append(_text(width / 2, height - 122, "nanami astro", fill="#8a6c45", text_anchor="middle", class_="meta"))
253:         parts.append(_text(width / 2, height - 92, "Four pillars chart from calculated data", fill="#a88d6b", text_anchor="middle", class_="footer"))
254: 
255:     parts.append("</svg>")
256:     return "\n".join(parts)
257: 
258: 
259: def render_shichusuimei_png_from_svg(svg: str) -> bytes | None:
260:     try:
261:         import cairosvg  # type: ignore
262:     except Exception:
263:         return None
264:     try:
265:         return cairosvg.svg2png(bytestring=svg.encode("utf-8"))
266:     except Exception:
267:         return None
268: 
269: 
270: def is_shichusuimei_png_renderer_available() -> bool:
271:     try:
272:         import cairosvg  # type: ignore  # noqa: F401
273:     except Exception:
274:         return False
275:     return True
```


## tests/test_shichusuimei_overseas_engine.py
```text
1: """Independent offline oracle, API contracts and read-only legacy compatibility."""
2: from copy import deepcopy
3: from datetime import datetime, timedelta, timezone
4: import hashlib
5: import json
6: from pathlib import Path
7: from unittest.mock import patch
8: from zoneinfo import ZoneInfo
9: 
10: import pytest
11: import yaml
12: 
13: from services.birth_datetime import BirthDatetimeError, resolve_birth_datetime
14: from services import shichusuimei_calc as core
15: from services.shichusuimei_year_selection import build_year_selection
16: from services.shichusuimei_annual_report import build_annual_fortune_report
17: from services.yaml_exporter import build_product_yaml, build_shichu_fortune_cycles_addon_yaml
18: from services.api_calc import calc_shichu_api
19: 
20: DATA = json.loads((Path(__file__).parent/"fixtures/shichusuimei/overseas_calendar_reference.json").read_text(encoding="utf-8"))
21: NOW = datetime(2026,10,11,12,tzinfo=ZoneInfo("Asia/Tokyo"))
22: PAYLOAD = dict(year=1990,month=5,day=15,hour=12,minute=30,gender="female")
23: 
24: 
25: @pytest.mark.parametrize("case",DATA["cases"],ids=lambda c:f"{c['timezone']}-{c['local']}-{c['day_boundary_hour']}")
26: def test_independent_civil_calendar_pillars(case):
27:     birth=datetime.fromisoformat(case["local"])
28:     local=resolve_birth_datetime(birth,case["timezone"])
29:     assert local.utcoffset().total_seconds()/3600==case["offset_hours"]
30:     assert local.astimezone(timezone.utc).isoformat()==case["utc"]
31:     result=core.pillars_day_hour(birth,case["timezone"],day_boundary_hour=case["day_boundary_hour"])
32:     assert (result.day,result.hour)==(case["day"],case["hour"])
33:     assert core.day_kanshi_from_birth(local.astimezone(timezone.utc),case["timezone"],day_boundary_hour=case["day_boundary_hour"])==case["day"]
34: 
35: 
36: # Solar-term year/month do not depend on the day-boundary mode. Check each
37: # zone/date once here, instead of repeating the same astronomy 24 times.
38: YM_CASES=[c for c in DATA["cases"] if c["day_boundary_hour"]==0 and "T01:00:" in c["local"]]
39: @pytest.mark.parametrize("case",YM_CASES,ids=lambda c:f"{c['timezone']}-{c['local']}")
40: def test_independent_year_month_same_astronomical_instant(case):
41:     result=core.year_month_pillars(datetime.fromisoformat(case["local"]),case["timezone"])
42:     assert result[:2]==(case["year"],case["month"])
43: 
44: 
45: @pytest.mark.parametrize("zone",["Asia/Tokyo","Asia/Seoul","Europe/London","America/New_York","America/Los_Angeles","Pacific/Honolulu","Australia/Sydney","UTC","Pacific/Kiritimati","Pacific/Pago_Pago"])
46: @pytest.mark.parametrize("minutes,year,month",[(-2,"乙巳","己丑"),(2,"丙午","庚寅")])
47: def test_lichun_global_same_instant_from_naoj(zone,minutes,year,month):
48:     # Published minute-rounded 2026-02-04 05:02 JST; use +/-2min.
49:     utc=datetime(2026,2,3,20,2,tzinfo=timezone.utc)+timedelta(minutes=minutes)
50:     local=utc.astimezone(ZoneInfo(zone))
51:     y,m,debug=core.year_month_pillars(local,zone)
52:     assert (y,m)==(year,month)
53:     assert datetime.fromisoformat(debug["local_datetime"]).astimezone(timezone.utc)==utc
54: 
55: 
56: def test_three_original_findings_reproductions_now_correct():
57:     assert core.day_kanshi_from_birth(datetime(2000,1,7,12),"UTC")=="甲子"
58:     assert core.day_kanshi_from_birth(datetime(2000,1,7,23,30),"America/Los_Angeles",True)=="乙丑"
59:     assert core.day_kanshi_from_birth(datetime(2000,1,7,0,30),"Asia/Tokyo",False)=="癸亥"
60:     assert core.day_kanshi_from_birth(datetime(2000,1,7,0,30),"Asia/Tokyo",True)=="甲子"
61: 
62: 
63: @pytest.mark.parametrize("gender",[None,"","unknown","default","unexpected"])
64: def test_unknown_gender_preserves_natal_and_forecast_without_daiun(gender):
65:     data=core.calc_shichusuimei_from_payload({**PAYLOAD,"gender":gender},as_of=NOW)
66:     known=core.calc_shichusuimei_from_payload(PAYLOAD,as_of=NOW)
67:     assert data["input"]["raw"]["gender"]=="unknown"
68:     assert data["input"]["raw"]["gender_supplied"]==gender
69:     nd=data["normalized_data"]
70:     for key in ("pillars","hidden_stems","ten_gods","twelve_fortune","five_elements","kubo","structural_analysis"):
71:         assert nd[key]==known["normalized_data"][key]
72:     assert nd["daiun"]["status"]=="undetermined_gender"
73:     assert nd["daiun"]["direction"] is None
74:     assert nd["daiun"]["start_age"] is None
75:     assert nd["daiun"]["items"]==[]
76:     assert nd["annual_fortune"]["current_daiun"] is None
77:     assert nd["annual_fortune"]["structural_analysis"]["concurrent_daiun"] is None
78:     assert len(nd["annual_forecasts"]["items"])==10
79:     for item in nd["annual_forecasts"]["items"]:
80:         assert item["daiun_contexts"]==[] and item["daiun_direction_status"]=="undetermined_gender"
81:         assert item["natal_analysis"]["pillar"]==item["kanshi"]
82: 
83: 
84: @pytest.mark.parametrize("stem,gender,direction",[("甲","male","forward"),("甲","female","reverse"),("乙","male","reverse"),("乙","female","forward")])
85: def test_specified_gender_direction(stem,gender,direction):
86:     assert core._daiun_direction_from_year_stem(stem,gender)==direction
87:     assert core._daiun_direction_from_year_stem(stem,"unknown") is None
88: 
89: 
90: @pytest.mark.parametrize("zone,wall",[("America/New_York","2024-03-10T02:30"),("America/Los_Angeles","2024-03-10T02:30"),("Europe/London","2024-03-31T01:30"),("Australia/Sydney","2024-10-06T02:30")])
91: def test_dst_nonexistent_rejected(zone,wall):
92:     with pytest.raises(BirthDatetimeError,match="存在しません"):
93:         core.pillars4(datetime.fromisoformat(wall),zone)
94: 
95: 
96: @pytest.mark.parametrize("zone,wall",[("America/New_York","2024-11-03T01:30"),("America/Los_Angeles","2024-11-03T01:30"),("Europe/London","2024-10-27T01:30"),("Australia/Sydney","2024-04-07T02:30")])
97: def test_dst_ambiguous_requires_choice_and_aware_instant_is_retained(zone,wall):
98:     birth=datetime.fromisoformat(wall)
99:     with pytest.raises(BirthDatetimeError,match="重複"):
100:         core.pillars4(birth,zone)
101:     a=resolve_birth_datetime(birth,zone,fold=0)
102:     b=resolve_birth_datetime(birth,zone,fold=1)
103:     assert b.astimezone(timezone.utc)-a.astimezone(timezone.utc)==timedelta(hours=1)
104:     assert resolve_birth_datetime(a.astimezone(timezone.utc),zone)==a
105:     assert resolve_birth_datetime(b.astimezone(timezone.utc),zone).fold==1
106:     assert resolve_birth_datetime(birth,zone,utc_offset_hours=b.utcoffset().total_seconds()/3600).fold==1
107: 
108: 
109: @pytest.mark.parametrize("zone",[None,"","not-a-zone"])
110: def test_unresolved_timezone_never_defaults_to_utc(zone):
111:     with pytest.raises(BirthDatetimeError):core.day_kanshi_from_birth(datetime(2000,1,7,12),zone)
112: 
113: 
114: @pytest.mark.parametrize("boundary",[0,1,23])
115: def test_time_context_rule_and_api_output_agree(boundary):
116:     response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="23:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone="America/Los_Angeles",gender="female",day_boundary=f"{boundary:02}:00"))
117:     assert status==200
118:     # Find the actual raw module rather than relying on API envelope naming.
119:     text=json.dumps(response,ensure_ascii=False)
120:     assert '"engine_version": "0.5.0"' in text
121:     assert f'"day_boundary_rule": "{boundary:02}:00切替"' in text
122:     result=core.calc_shichusuimei_from_payload(dict(year=2000,month=1,day=7,hour=23,minute=30,gender="female"),tz_name="America/Los_Angeles",day_boundary_hour=boundary,as_of=NOW)
123:     context=result["input"]["time_context"]
124:     assert context["local_datetime"]=="2000-01-07T23:30:00-08:00"
125:     assert context["utc_datetime"]=="2000-01-08T07:30:00+00:00"
126:     assert context["day_pillar_date"]==("2000-01-08" if boundary==23 else "2000-01-07")
127:     assert context["true_solar_time_applied"] is False
128: 
129: 
130: def test_api_dst_error_and_explicit_choice():
131:     args=dict(birth_date="2024-11-03",birth_time="01:30",birth_place="New York",timezone="America/New_York",lat=40.71,lon=-74,gender="unknown")
132:     response,status=calc_shichu_api(args)
133:     assert status==400 and response["error"]["code"]=="INVALID_BIRTH_DATETIME"
134:     response,status=calc_shichu_api({**args,"birth_fold":1})
135:     assert status==200
136:     response,status=calc_shichu_api({**args,"day_boundary":"nonsense"})
137:     assert status==400
138: 
139: 
140: @pytest.mark.parametrize("extra",[{}, {"timezone":""}, {"timezone":"not-a-zone"}])
141: def test_api_overseas_requires_known_timezone(extra):
142:     response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,**extra))
143:     assert status==400 and response["error"]["code"]=="INVALID_TIMEZONE"
144: 
145: 
146: @pytest.mark.parametrize("boundary",[-1,24,True,"23"])
147: def test_invalid_boundary_not_silently_coerced(boundary):
148:     with pytest.raises(ValueError):core.day_kanshi_from_birth(datetime(2000,1,7,12),day_boundary_hour=boundary)
149: 
150: 
151: def test_saved_legacy_addon_rule_and_conflicting_day_are_protected(monkeypatch):
152:     import routes
153:     original=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
154:     original_copy=deepcopy(original)
155:     day=original["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]
156:     sent={}
157:     def fake(**kwargs):
158:         sent.update(kwargs)
159:         return "fictional", "", {"systems":{"shichusuimei":{"reference":{"day_kanshi":day}}}}
160:     monkeypatch.setattr(routes,"build_shichu_fortune_cycles_addon_yaml",fake)
161:     assert routes._build_addon_yaml_from_base(original,"shichu_fortune_cycles_addon")=="fictional"
162:     assert sent["day_boundary_hour"]==0 and sent["day_change_at_23"] is False
163:     assert original==original_copy
164:     def conflicting(**kwargs):
165:         return "fictional", "", {"systems":{"shichusuimei":{"reference":{"day_kanshi":"乙丑"}}}}
166:     monkeypatch.setattr(routes,"build_shichu_fortune_cycles_addon_yaml",conflicting)
167:     with pytest.raises(ValueError,match="計算が異なる"):
168:         routes._build_addon_yaml_from_base(original,"shichu_fortune_cycles_addon")
169:     assert original==original_copy
170: 
171: 
172: def test_buyer_fold_selector_and_parser_are_consistent():
173:     import routes
174:     from fastapi.testclient import TestClient
175:     assert routes._parse_birth_fold("") is None
176:     assert routes._parse_birth_fold("0")==0
177:     assert routes._parse_birth_fold("1")==1
178:     with pytest.raises(ValueError):routes._parse_birth_fold("2")
179:     html=TestClient(routes.app).get("/redeem/shichu").text
180:     assert 'name="birth_fold"' in html
181:     assert "同じ現地時刻の1回目" in html and "同じ現地時刻の2回目" in html
182:     assert "大運・起運は未確定" in html
183: 
184: 
185: def test_unknown_gender_year_selection_annual_adapter_svg_and_addon():
186:     text,prompt,doc=build_product_yaml(title="Fictional unknown",birth_date="1990-05-15",birth_time="12:30",prefecture="東京都",gender="unknown",include_shichusuimei=True)
187:     original_hash=hashlib.sha256(text.encode()).hexdigest()
188:     forecasts=doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]
189:     years=[forecasts[0]["effective_year"],forecasts[-1]["effective_year"]]
190:     selected=yaml.safe_load(build_year_selection(text,{"mode":"selected","years":years})["yaml_text"])
191:     assert selected["selected_base_forecasts"]==[i for i in forecasts if i["effective_year"] in years]
192:     assert selected["common"]["systems"]["shichusuimei"]["normalized_data"]["daiun"]["direction"] is None
193:     report=build_annual_fortune_report(doc,years[0])["annual_fortune_report"]
194:     assert report["daiun"]["status"]=="undetermined_gender"
195:     assert report["daiun"]["contexts"]==[]
196:     assert report["interactions"]["natal_annual"]
197:     assert "女性へ補完せず" in prompt
198:     assert "現地暦日" in prompt
199:     assert hashlib.sha256(text.encode()).hexdigest()==original_hash
200:     assert build_year_selection(text,{"mode":"complete"})["yaml_text"]==text
201:     from services.shichu_chart import build_shichusuimei_svg_from_yaml
202:     assert "大運：未確定" in build_shichusuimei_svg_from_yaml(text)
203:     _,_,addon=build_shichu_fortune_cycles_addon_yaml(title=None,birth_date="1990-05-15",birth_time="12:30",prefecture="東京都",gender="unknown")
204:     assert addon["calculation"]["engine_version"]=="0.5.0"
205:     assert addon["systems"]["shichusuimei"]["normalized_data"]["daiun"]["direction"] is None
206: 
207: 
208: def test_legacy_full_fixture_complete_and_selection_never_recalculated():
209:     path=Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml"
210:     original=path.read_text(encoding="utf-8")
211:     doc=yaml.safe_load(original)
212:     year=doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"][0]["effective_year"]
213:     with patch.object(core,"calc_shichusuimei_from_payload",side_effect=AssertionError("no recalculation")):
214:         assert build_year_selection(original,{"mode":"complete"})["yaml_text"]==original
215:         selected=yaml.safe_load(build_year_selection(original,{"mode":"selected","years":[year]})["yaml_text"])
216:     assert selected["common"]["systems"]["shichusuimei"]["normalized_data"]["daiun"]==doc["systems"]["shichusuimei"]["normalized_data"]["daiun"]
217:     assert path.read_text(encoding="utf-8")==original
```


## scripts/build_shichusuimei_independent_cases.py
```text
1: """Build an offline oracle with lunar-python, not the production engine.
2: 
3: No import of application calculation code. IANA offsets below are explicit
4: reference data for the four dates; UTC expectations do not reuse ZoneInfo.
5: """
6: import json
7: import sys
8: from pathlib import Path
9: from datetime import datetime, timedelta, timezone
10: 
11: ROOT = Path(__file__).resolve().parents[1]
12: sys.path.insert(0, "C:/Users/haser/nanami-products/tmp/quality-independent-libs")
13: from lunar_python import Solar
14: 
15: stems = "甲乙丙丁戊己庚辛壬癸"
16: branches = "子丑寅卯辰巳午未申酉戌亥"
17: zones = {"Asia/Tokyo": [9]*4, "Asia/Seoul": [9]*4,
18:          "Europe/London": [0,0,1,0], "America/New_York": [-5,-5,-4,-5],
19:          "America/Los_Angeles": [-8,-8,-7,-8], "Pacific/Honolulu": [-10]*4,
20:          "Australia/Sydney": [11,11,10,11], "UTC": [0]*4,
21:          "Pacific/Kiritimati": [14]*4, "Pacific/Pago_Pago": [-11]*4}
22: dates = [(2000,1,7), (2024,2,29), (2024,7,1), (2024,12,31)]
23: times = [(0,0),(0,59),(1,0),(1,1),(22,59),(23,0),(23,30),(23,59)]
24: rows = []
25: for zone, offsets in zones.items():
26:     for (y,m,d), offset in zip(dates,offsets):
27:         for h, minute in times:
28:             wall = datetime(y,m,d,h,minute)
29:             local = wall.replace(tzinfo=timezone(timedelta(hours=offset)))
30:             utc = local.astimezone(timezone.utc)
31:             bj = utc.astimezone(timezone(timedelta(hours=8)))
32:             ec = Solar.fromYmdHms(bj.year,bj.month,bj.day,bj.hour,bj.minute,0).getLunar().getEightChar()
33:             for boundary in (0,1,23):
34:                 date = wall.date()
35:                 if boundary == 1 and h == 0: date -= timedelta(days=1)
36:                 if boundary == 23 and h == 23: date += timedelta(days=1)
37:                 day = Solar.fromYmd(date.year,date.month,date.day).getLunar().getDayInGanZhi()
38:                 branch = ((h+1)//2)%12
39:                 # Five-mouse rule, independently expressed as an arithmetic cycle.
40:                 hour = stems[(stems.index(day[0])%5*2+branch)%10]+branches[branch]
41:                 rows.append(dict(local=wall.isoformat(),timezone=zone,offset_hours=offset,
42:                     utc=utc.isoformat(),day_boundary_hour=boundary,effective_date=date.isoformat(),
43:                     day=day,hour=hour,year=ec.getYear(),month=ec.getMonth()))
44: doc = dict(reference=dict(library="lunar_python",version="1.4.8",source="https://github.com/6tail/lunar-python",
45:            term_source="https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html",
46:            calendar="Gregorian civil date, selected 00/01/23 boundary; no true solar time",
47:            year_month="Independent lunar-python EightChar at same instant in UTC+8; outside term boundary",
48:            hour="Five-mouse cyclic formula based on selected civil-date stem and local two-hour branch"),cases=rows)
49: path=ROOT/"tests/fixtures/shichusuimei/overseas_calendar_reference.json"
50: path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8")
51: print(f"Saved {len(rows)} independent cases to {path}")
```
