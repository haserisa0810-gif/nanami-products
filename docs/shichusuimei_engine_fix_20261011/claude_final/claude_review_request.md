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

## 最終の対応事項
2回目のOpus指摘を反映: N1 timezoneの非文字列false/0/[]/{}は400拒否しraw自体をZoneInfoで検証。
旧女性補完flagは元inputにgenderキーが存在する場合だけ付け、欠落を補完済みと断定しない。
旧日柱疑義をinterpretation_flagsにも明記。API変更履歴は日柱/unknown/必須timezone/新エラーを含める。
実生成関数をモックしない旧JST addon統合テストと西洋/トランジットAPI版1.0の回帰テストを追加。
外部販売ページ・外国語告知・旧原本の救済/返金/再発行・Windows1970以前は未解決事項として明示し、今回の公開はしない。
新規3件と追加保護のコードを最終確認する。未提示箇所への条件付き推測と、実在する反例を区別する。


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
@@ -148,11 +149,18 @@
 
 
 def _normalize_shichu_timezone(payload: dict[str, Any]) -> str:
-    raw = payload.get("timezone", payload.get("tz_name"))
+    raw = payload.get("timezone")
+    if raw is None:
+        raw = payload.get("tz_name")
     if raw is not None:
-        if not str(raw).strip():
+        if not isinstance(raw, str) or not raw.strip():
             raise ApiCalcError("INVALID_TIMEZONE", "an IANA birth timezone is required", 400)
-        return _normalize_timezone(payload)
+        tz = raw.strip()
+        try:
+            ZoneInfo(tz)
+        except Exception as exc:
+            raise ApiCalcError("INVALID_TIMEZONE", "invalid IANA birth timezone", 400) from exc
+        return tz
     # Preserve the domestic prefecture API default; an overseas place cannot
     # silently inherit that default or UTC.
     from services.location import resolve_prefecture
@@ -428,4 +436,4 @@
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
+    legacy_imputed = legacy and "gender" in base_input and core._parse_gender(base_input["gender"]) == "unknown" and raw_gender == "female"
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
@@ -221,9 +244,13 @@
                           "method": "existing_visible_stem_plus_branch_and_additive_hidden_stem_counts",
                           "note": "合算は参考個数。強弱・吉凶・合化の成立を示さない。時刻不明・推定の場合、合算から時柱を除外。"},
         "interpretation_flags": {"calculation_only": True, "automatic_good_bad_judgment": False,
+                                 "base_day_pillar_suspect": day_suspect,
+                                 "legacy_reference_notes": legacy_notes,
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
@@ -214,4 +215,99 @@
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
+    doc["systems"]["shichusuimei"]["engine_version"]="0.4.0"
+    doc["input"]["timezone_offset_hours"]=offset
+    doc["systems"]["shichusuimei"]["input"]["raw"]["gender"]="female"
+    snapshot=deepcopy(doc)
+    result=build_annual_fortune_report(doc,2028)["annual_fortune_report"]
+    assert result["calculation"]["base_day_pillar_suspect"] is (True if offset is not None else None)
+    assert result["calculation"]["legacy_female_imputed"] is True
+    assert result["daiun"]["status"]=="legacy_female_imputed"
+    assert result["interpretation_flags"]["daiun_direction_confirmed"] is False
+    assert result["interpretation_flags"]["base_day_pillar_suspect"] is (True if offset is not None else None)
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
+
+
+@pytest.mark.parametrize("bad_timezone",[False,0,[],{}])
+def test_api_non_string_timezone_cannot_inherit_tokyo(bad_timezone):
+    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone=bad_timezone))
+    assert status==400 and response["error"]["code"]=="INVALID_TIMEZONE"
+
+
+def test_old_report_missing_gender_is_not_claimed_as_female_imputation():
+    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
+    doc["input"].pop("gender",None)
+    report=build_annual_fortune_report(doc,2028)["annual_fortune_report"]
+    assert report["calculation"]["legacy_female_imputed"] is False
+
+
+def test_old_addon_saved_timezone_offset_works_with_real_generator():
+    import routes
+    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
+    snapshot=deepcopy(doc)
+    addon=yaml.safe_load(routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon"))
+    assert addon["calculation"]["day_boundary_hour"]==0
+    assert addon["calculation"]["time_context"]["utc_offset_hours"]==9.0
+    day=doc["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]
+    assert addon["systems"]["shichusuimei"]["reference"]["day_kanshi"]==day
+    assert doc==snapshot
+
+
+@pytest.mark.parametrize("endpoint",["western","transit"])
+def test_western_api_version_unchanged(endpoint):
+    from services.api_calc import _success
+    # Envelope check only; the actual natal/transit numeric regression is in
+    # verify_shichusuimei_engine_fix.py and the existing suite.
+    result,status=_success(endpoint,{}, {"systems":{}})
+    assert status==200 and result["meta"]["api_version"]=="1.0"

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

- UTCオフセットが0以下の出生地では、境界時刻以外も旧日柱の1日進みを修正する（例：LA 2000-01-07 12:00、旧乙丑→新甲子）。時干・十神などの派生値も変わる。
- `gender`省略／unknownは女性に補完しない。大運の順逆・起運を未確定としitemsは空、命式と原局×流年は維持する。
- 海外出生でIANAタイムゾーンが省略・空・不正な型なら400 `INVALID_TIMEZONE`。国内都道府県のJST既定値は維持する。
- 不正な日替わりは400 `INVALID_DAY_BOUNDARY`、不存在／未解決の重複日時は400 `INVALID_BIRTH_DATETIME`。重複は`birth_fold: 0/1`または`birth_utc_offset_hours`で指定する。
- `day_boundary`のJSON falseは1時、数値0は0時として区別する。時刻を文字列`"01:00"`・`"00:00"`・`"23:00"`で指定すると意味が明確になる。

## 概要

`nanami-products` に追加された計算結果APIの運用仕様です。
この仕様書は現時点の実装に合わせた実務用ドキュメントです。


## 国内も利用可能な夏時間fold欄
              <label class="full-span">夏時間終了時の重複時刻（任意）
                <select name="birth_fold">
                  <option value="">通常・未選択</option>
                  <option value="0" {% if form and form.birth_fold == '0' %}selected{% endif %}>同じ現地時刻の1回目</option>
                  <option value="1" {% if form and form.birth_fold == '1' %}selected{% endif %}>同じ現地時刻の2回目</option>
                </select>
                <small>夏時間終了で同じ時刻が2回存在する場合だけ指定します。不明なまま片方を推測しません。</small>
              </label>
            </div>