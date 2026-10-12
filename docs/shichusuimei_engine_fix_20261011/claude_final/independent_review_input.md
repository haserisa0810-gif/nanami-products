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
13: SHICHU_API_VERSION = "1.1"
14: ENGINE_NAME = "nanami-products"
15: 
16: 
17: class ApiCalcError(Exception):
18:     def __init__(self, code: str, message: str, status_code: int = 400):
19:         super().__init__(message)
20:         self.code = code
21:         self.message = message
22:         self.status_code = status_code
23: 
24: 
25: def _error(code: str, message: str, *, status_code: int = 400) -> tuple[dict[str, Any], int]:
26:     return {
27:         "ok": False,
28:         "error": {
29:             "code": code,
30:             "message": message,
31:         },
32:     }, status_code
33: 
34: 
35: def _success(endpoint: str, input_data: dict[str, Any], doc: dict[str, Any], *, yaml_text: str | None = None) -> tuple[dict[str, Any], int]:
36:     raw_western = doc.get("systems", {}).get("western")
37:     raw_shichu = doc.get("systems", {}).get("shichusuimei")
38:     raw_transit = None
39:     if isinstance(raw_western, dict):
40:         raw_transit = raw_western.get("transit")
41: 
42:     western = raw_western if raw_western is not None else None
43:     shichu = raw_shichu if raw_shichu is not None else None
44: 
45:     tags_western = western_tags(western)
46:     tags_shichu = shichu_tags(shichu)
47:     tags_transit = transit_tags(raw_transit)
48:     tags_integration = integration_tags(western, shichu, raw_transit)
49: 
50:     writing = input_data.get("writing", {})
51:     tone = writing.get("tone", {}) if isinstance(writing, dict) else {}
52:     focus_areas_raw = writing.get("focus_areas", []) if isinstance(writing, dict) else []
53:     if isinstance(focus_areas_raw, list):
54:         focus_areas = [str(item) for item in focus_areas_raw if str(item).strip()]
55:     elif str(focus_areas_raw).strip():
56:         focus_areas = [str(focus_areas_raw).strip()]
57:     else:
58:         focus_areas = []
59:     writing_hints = {
60:         "tone": {
61:             "sharpness": int(tone.get("sharpness", 50)),
62:             "warmth": int(tone.get("warmth", 50)),
63:             "mystical": int(tone.get("mystical", 50)),
64:         },
65:         "focus_areas": focus_areas,
66:         "key_concepts": [
67:             tag["label"]
68:             for tag in sorted(
69:                 [*tags_western, *tags_shichu, *tags_transit, *tags_integration],
70:                 key=lambda item: (-int(item.get("strength", 0)), item.get("id", "")),
71:             )
72:             if int(tag.get("strength", 0)) > 0
73:         ][:5],
74:     }
75: 
76:     response_doc = {
77:         "meta": {
78:             "api_version": SHICHU_API_VERSION if raw_shichu is not None else API_VERSION,
79:             "engine": ENGINE_NAME,
80:             "endpoint": endpoint,
81:         },
82:         "input": input_data,
83:         "raw_data": {
84:             "western": western,
85:             "shichu": shichu,
86:             "transit": raw_transit,
87:         },
88:         "interpreted_tags": {
89:             "western": tags_western,
90:             "shichu": tags_shichu,
91:             "transit": tags_transit,
92:             "integration": tags_integration,
93:         },
94:         "writing_hints": writing_hints,
95:         "ai_prompt_context": {
96:             "role": "構造分析型の占星術鑑定",
97:             "instruction": "raw_dataを直接断定せず、interpreted_tagsを主軸に鑑定文を作成してください。",
98:             "caution": [
99:                 "運命断定を避ける",
100:                 "不安を煽らない",
101:                 "basisがあるタグを優先する",
102:                 "strengthが高いタグを優先する",
103:             ],
104:         },
105:     }
106:     if isinstance(western, dict) and isinstance((western.get("natal") if western else None), dict):
107:         response_doc["chart"] = {
108:             "svg_available": False,
109:             "chart_id": None,
110:             "svg_url": None,
111:         }
112:     if isinstance(shichu, dict):
113:         response_doc["shichusuimei_chart"] = {
114:             "svg_available": False,
115:             "png_available": False,
116:             "chart_id": None,
117:             "svg_url": None,
118:             "png_url": None,
119:         }
120:     response_doc["ai_prompt_context"] = build_ai_prompt_context(doc, response_doc["ai_prompt_context"])
121:     response_doc["handoff_yaml"] = build_handoff_yaml(response_doc)
122:     if yaml_text and ("chart" in response_doc or "shichusuimei_chart" in response_doc):
123:         response_doc["_internal_chart_yaml_text"] = yaml_text
124:     return {
125:         "ok": True,
126:         **response_doc,
127:     }, 200
128: 
129: 
130: def _normalize_birth_place(payload: dict[str, Any]) -> str:
131:     birth_place = str(payload.get("birth_place") or payload.get("prefecture") or "").strip()
132:     if not birth_place:
133:         raise ApiCalcError("INVALID_INPUT", "birth_place is required", 400)
134:     return birth_place
135: 
136: 
137: def _normalize_timezone(payload: dict[str, Any]) -> str:
138:     tz = str(payload.get("timezone") or payload.get("tz_name") or "Asia/Tokyo").strip()
139:     tz = tz or "Asia/Tokyo"
140:     try:
141:         ZoneInfo(tz)
142:     except Exception as exc:
143:         raise ApiCalcError("INVALID_TIMEZONE", f"invalid timezone: {tz}", 400) from exc
144:     return tz
145: 
146: 
147: def _normalize_day_boundary(payload: dict[str, Any]) -> bool:
148:     return _normalize_day_boundary_hour(payload) == 23
149: 
150: 
151: def _normalize_shichu_timezone(payload: dict[str, Any]) -> str:
152:     raw = payload.get("timezone")
153:     if raw is None:
154:         raw = payload.get("tz_name")
155:     if raw is not None:
156:         if not isinstance(raw, str) or not raw.strip():
157:             raise ApiCalcError("INVALID_TIMEZONE", "an IANA birth timezone is required", 400)
158:         tz = raw.strip()
159:         try:
160:             ZoneInfo(tz)
161:         except Exception as exc:
162:             raise ApiCalcError("INVALID_TIMEZONE", "invalid IANA birth timezone", 400) from exc
163:         return tz
164:     # Preserve the domestic prefecture API default; an overseas place cannot
165:     # silently inherit that default or UTC.
166:     from services.location import resolve_prefecture
167:     try:
168:         resolve_prefecture(_normalize_birth_place(payload))
169:     except ValueError as exc:
170:         raise ApiCalcError("INVALID_TIMEZONE", "specify the overseas IANA birth timezone", 400) from exc
171:     return "Asia/Tokyo"
172: 
173: 
174: def _normalize_day_boundary_hour(payload: dict[str, Any]) -> int:
175:     raw = payload.get("day_boundary")
176:     value = str(raw if raw is not None else "").strip().lower()
177:     choices = {"": 1, "01:00": 1, "1": 1, "01": 1, "false": 1, "off": 1, "no": 1,
178:                "00:00": 0, "0": 0, "midnight": 0,
179:                "23:00": 23, "23": 23, "true": 23, "on": 23, "yes": 23}
180:     if value not in choices:
181:         raise ApiCalcError("INVALID_DAY_BOUNDARY", "day_boundary must be 00:00, 01:00 or 23:00", 400)
182:     return choices[value]
183: 
184: 
185: def _normalize_period(payload: dict[str, Any]) -> str:
186:     period = str(payload.get("period") or "month").strip().lower()
187:     if period not in {"day", "month"}:
188:         raise ApiCalcError("UNSUPPORTED_PERIOD", "period must be 'day' or 'month'", 400)
189:     return period
190: 
191: 
192: def _normalize_writing(payload: dict[str, Any]) -> dict[str, Any]:
193:     writing = payload.get("writing")
194:     return writing if isinstance(writing, dict) else {}
195: 
196: 
197: def _optional_float(payload: dict[str, Any], field_name: str) -> float | None:
198:     value = payload.get(field_name)
199:     if value in (None, ""):
200:         return None
201:     try:
202:         return float(value)
203:     except (TypeError, ValueError) as exc:
204:         raise ApiCalcError("INVALID_INPUT", f"{field_name} must be a number", 400) from exc
205: 
206: 
207: def _parse_date(value: Any, field_name: str) -> date:
208:     if not value:
209:         raise ApiCalcError("INVALID_INPUT", f"{field_name} is required", 400)
210:     try:
211:         return date.fromisoformat(str(value))
212:     except ValueError as exc:
213:         raise ApiCalcError("INVALID_INPUT", f"{field_name} must be YYYY-MM-DD", 400) from exc
214: 
215: 
216: def _parse_optional_datetime(value: Any, field_name: str, *, tz_name: str, default_hour: int = 12) -> datetime:
217:     target_date = _parse_date(value, field_name)
218:     return datetime.combine(target_date, time(default_hour, 0), tzinfo=ZoneInfo(tz_name))
219: 
220: 
221: def _build_doc(
222:     *,
223:     title: str | None,
224:     birth_date: str,
225:     birth_time: str | None,
226:     birth_place: str,
227:     birth_lat: float | None,
228:     birth_lng: float | None,
229:     tz_name: str,
230:     gender: str,
231:     include_asteroids: bool,
232:     include_shichusuimei: bool,
233:     include_transit: bool,
234:     transit_start_date: datetime | None = None,
235:     transit_days: int = 31,
236:     day_change_at_23: bool = False,
237:     day_boundary_hour: int | None = None,
238:     birth_fold: int | None = None,
239:     birth_utc_offset_hours: float | None = None,
240: ) -> dict[str, Any]:
241:     yaml_text, _prompt_text, doc = build_product_yaml(
242:         title=title,
243:         birth_date=birth_date,
244:         birth_time=birth_time,
245:         prefecture=birth_place,
246:         birth_place_label=birth_place,
247:         birth_lat=birth_lat,
248:         birth_lng=birth_lng,
249:         tz_name=tz_name,
250:         gender=gender,
251:         include_asteroids=include_asteroids,
252:         include_shichusuimei=include_shichusuimei,
253:         include_transit=include_transit,
254:         transit_start_date=transit_start_date,
255:         transit_days=transit_days,
256:         day_change_at_23=day_change_at_23,
257:         **({"day_boundary_hour": day_boundary_hour, "birth_fold": birth_fold,
258:             "birth_utc_offset_hours": birth_utc_offset_hours} if include_shichusuimei else {}),
259:     )
260:     return {
261:         "doc": doc,
262:         "yaml_text": yaml_text,
263:     }
264: 
265: 
266: def calc_western_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
267:     try:
268:         birth_date = str(payload.get("birth_date", "")).strip()
269:         tz_name = _normalize_timezone(payload)
270:         writing = _normalize_writing(payload)
271:         input_data = {
272:             "name": payload.get("name"),
273:             "birth_date": birth_date,
274:             "birth_time": payload.get("birth_time"),
275:             "birth_place": _normalize_birth_place(payload),
276:             "timezone": tz_name,
277:             "lat": payload.get("lat"),
278:             "lon": payload.get("lon"),
279:             "writing": writing,
280:         }
281:         if not birth_date:
282:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
283:         result = _build_doc(
284:             title=payload.get("name"),
285:             birth_date=birth_date,
286:             birth_time=str(payload.get("birth_time") or "").strip() or None,
287:             birth_place=input_data["birth_place"],
288:             birth_lat=_optional_float(payload, "lat"),
289:             birth_lng=_optional_float(payload, "lon"),
290:             tz_name=tz_name,
291:             gender=str(payload.get("gender") or "unknown"),
292:             include_asteroids=True,
293:             include_shichusuimei=False,
294:             include_transit=False,
295:         )
296:         return _success("western", input_data, result["doc"], yaml_text=result.get("yaml_text"))
297:     except ApiCalcError as exc:
298:         return _error(exc.code, exc.message, status_code=exc.status_code)
299:     except Exception as exc:
300:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
301: 
302: 
303: def calc_shichu_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
304:     try:
305:         birth_date = str(payload.get("birth_date", "")).strip()
306:         writing = _normalize_writing(payload)
307:         input_data = {
308:             "name": payload.get("name"),
309:             "birth_date": birth_date,
310:             "birth_time": payload.get("birth_time"),
311:             "birth_place": _normalize_birth_place(payload),
312:             "gender": payload.get("gender") or "unknown",
313:             "day_boundary": payload.get("day_boundary"),
314:             "writing": writing,
315:         }
316:         if not birth_date:
317:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
318:         result = _build_doc(
319:             title=payload.get("name"),
320:             birth_date=birth_date,
321:             birth_time=str(payload.get("birth_time") or "").strip() or None,
322:             birth_place=input_data["birth_place"],
323:             birth_lat=_optional_float(payload, "lat"),
324:             birth_lng=_optional_float(payload, "lon"),
325:             tz_name=_normalize_shichu_timezone(payload),
326:             gender=str(payload.get("gender") or "unknown"),
327:             include_asteroids=False,
328:             include_shichusuimei=True,
329:             include_transit=False,
330:             day_change_at_23=_normalize_day_boundary(payload),
331:             day_boundary_hour=_normalize_day_boundary_hour(payload),
332:             birth_fold=payload.get("birth_fold"),
333:             birth_utc_offset_hours=payload.get("birth_utc_offset_hours"),
334:         )
335:         return _success("shichu", input_data, result["doc"], yaml_text=result.get("yaml_text"))
336:     except BirthDatetimeError as exc:
337:         return _error("INVALID_BIRTH_DATETIME", str(exc), status_code=400)
338:     except ApiCalcError as exc:
339:         return _error(exc.code, exc.message, status_code=exc.status_code)
340:     except Exception as exc:
341:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
342: 
343: 
344: def calc_transit_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
345:     try:
346:         birth_date = str(payload.get("birth_date", "")).strip()
347:         if not birth_date:
348:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
349:         period = _normalize_period(payload)
350:         tz_name = _normalize_timezone(payload)
351:         writing = _normalize_writing(payload)
352:         target_date_value = payload.get("target_date") or birth_date
353:         target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
354:         transit_days = 1 if period == "day" else 31
355:         input_data = {
356:             "name": payload.get("name"),
357:             "birth_date": birth_date,
358:             "birth_time": payload.get("birth_time"),
359:             "birth_place": _normalize_birth_place(payload),
360:             "timezone": tz_name,
361:             "lat": payload.get("lat"),
362:             "lon": payload.get("lon"),
363:             "target_date": payload.get("target_date"),
364:             "period": period,
365:             "writing": writing,
366:         }
367:         result = _build_doc(
368:             title=payload.get("name"),
369:             birth_date=birth_date,
370:             birth_time=str(payload.get("birth_time") or "").strip() or None,
371:             birth_place=input_data["birth_place"],
372:             birth_lat=_optional_float(payload, "lat"),
373:             birth_lng=_optional_float(payload, "lon"),
374:             tz_name=tz_name,
375:             gender=str(payload.get("gender") or "unknown"),
376:             include_asteroids=False,
377:             include_shichusuimei=False,
378:             include_transit=True,
379:             transit_start_date=target_start,
380:             transit_days=transit_days,
381:         )
382:         return _success("transit", input_data, result["doc"], yaml_text=result.get("yaml_text"))
383:     except ApiCalcError as exc:
384:         return _error(exc.code, exc.message, status_code=exc.status_code)
385:     except Exception as exc:
386:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
387: 
388: 
389: def calc_combined_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
390:     try:
391:         birth_date = str(payload.get("birth_date", "")).strip()
392:         if not birth_date:
393:             raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
394:         period = _normalize_period(payload)
395:         tz_name = _normalize_shichu_timezone(payload)
396:         writing = _normalize_writing(payload)
397:         target_date_value = payload.get("target_date") or birth_date
398:         target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
399:         transit_days = 1 if period == "day" else 31
400:         input_data = {
401:             "name": payload.get("name"),
402:             "birth_date": birth_date,
403:             "birth_time": payload.get("birth_time"),
404:             "birth_place": _normalize_birth_place(payload),
405:             "timezone": tz_name,
406:             "lat": payload.get("lat"),
407:             "lon": payload.get("lon"),
408:             "gender": payload.get("gender") or "unknown",
409:             "target_date": payload.get("target_date"),
410:             "day_boundary": payload.get("day_boundary"),
411:             "period": period,
412:             "writing": writing,
413:         }
414:         result = _build_doc(
415:             title=payload.get("name"),
416:             birth_date=birth_date,
417:             birth_time=str(payload.get("birth_time") or "").strip() or None,
418:             birth_place=input_data["birth_place"],
419:             birth_lat=_optional_float(payload, "lat"),
420:             birth_lng=_optional_float(payload, "lon"),
421:             tz_name=tz_name,
422:             gender=str(payload.get("gender") or "unknown"),
423:             include_asteroids=True,
424:             include_shichusuimei=True,
425:             include_transit=True,
426:             transit_start_date=target_start,
427:             transit_days=transit_days,
428:             day_change_at_23=_normalize_day_boundary(payload),
429:             day_boundary_hour=_normalize_day_boundary_hour(payload),
430:             birth_fold=payload.get("birth_fold"),
431:             birth_utc_offset_hours=payload.get("birth_utc_offset_hours"),
432:         )
433:         return _success("combined", input_data, result["doc"], yaml_text=result.get("yaml_text"))
434:     except BirthDatetimeError as exc:
435:         return _error("INVALID_BIRTH_DATETIME", str(exc), status_code=400)
436:     except ApiCalcError as exc:
437:         return _error(exc.code, exc.message, status_code=exc.status_code)
438:     except Exception as exc:
439:         return _error("INTERNAL_ERROR", str(exc), status_code=500)
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
141:     base_version = str(shichu.get("engine_version") or "")
142:     try:
143:         legacy = tuple(int(n) for n in base_version.split(".")) < (0, 5, 0)
144:     except ValueError:
145:         legacy = True
146:     offset = base_input.get("timezone_offset_hours")
147:     if offset is None:
148:         offset = ((shichu.get("input") or {}).get("time_context") or {}).get("utc_offset_hours")
149:     try:
150:         day_suspect = float(offset) <= 0 if offset is not None else None
151:     except (TypeError, ValueError):
152:         day_suspect = None
153:     day_suspect = day_suspect if legacy else False
154:     raw_gender = ((shichu.get("input") or {}).get("raw") or {}).get("gender")
155:     legacy_imputed = legacy and "gender" in base_input and core._parse_gender(base_input["gender"]) == "unknown" and raw_gender == "female"
156:     legacy_notes = []
157:     if legacy and day_suspect is not False:
158:         legacy_notes.append("旧計算の原本です。出生時UTCオフセットが0以下または未確認のため、日柱に旧不具合の疑義があります。原本の保存値を参照しており、再計算・修正済みの命式ではありません。")
159:     if legacy_imputed:
160:         legacy_notes.append("旧原本の性別未指定が女性に補完されています。保存済み大運は参照用で、順逆の確定結果として扱わないでください。")
161:     tz_name = assumptions.get("tz_name") or base_input.get("timezone") or "Asia/Tokyo"
162:     tz = ZoneInfo(tz_name)
163:     accuracy = assumptions.get("birth_time_accuracy") or base_input.get("birth_time_accuracy")
164:     # Legacy exact charts have no accuracy marker. Unknown or approximate charts
165:     # carry either a Full-YAML birth_time marker or a normalized reference flag.
166:     accuracy = accuracy or (base_doc.get("birth_time") or {}).get("accuracy") or "exact"
167:     reliable = accuracy == "exact" and not data.get("time_sensitive_reference")
168:     natal = [_item(name, value.get("kanshi") if isinstance(value, dict) else value)
169:              for name, value in pillars.items() if name in {"year", "month", "day", "hour"}
170:              and (name != "hour" or reliable)]
171:     by_name = {p["name"]: p for p in natal}
172:     if not {"year", "month", "day"} <= by_name.keys():
173:         raise ValueError("基礎命式の年柱・月柱・日柱が不足しています。")
174:     day_master = by_name["day"]["stem"]
175:     annual = _item("annual", core._year_kanshi_from_effective_year(selected_year))
176:     start = core._lichun_utc_for_year(selected_year, tz_name).astimezone(tz)
177:     end = core._lichun_utc_for_year(selected_year + 1, tz_name).astimezone(tz)
178:     periods = _daiun_periods(shichu, data, selected_year, tz)
179:     contexts = []
180:     for period in periods:
181:         left, right = (datetime.fromisoformat(period[key]) for key in ("approx_start_at", "approx_end_at"))
182:         if left >= end or right <= start:
183:             continue
184:         luck = _item("daiun", period["kanshi"])
185:         contexts.append({
186:             **period, "stem": luck["stem"], "branch": luck["branch"],
187:             "ten_god_to_day_master": core.ten_god(day_master, luck["stem"]),
188:             "twelve_fortune_to_day_master": core.twelve_fortune(day_master, luck["branch"]),
189:             "boundary_provisional": True,
190:             "boundary_in_selected_year": start < left < end or start < right < end,
191:             "overlap_start_approx": max(start, left).isoformat(),
192:             "overlap_end_approx": min(end, right).isoformat(),
193:         })
194:     interactions = {"natal_annual": _scope(natal + [annual], {"natal", "annual"}),
195:                     "natal_daiun": [], "daiun_annual": [], "combined": []}
196:     for context in contexts:
197:         luck = _item("daiun", context["kanshi"])
198:         for key, participants, required in (
199:             ("natal_daiun", natal + [luck], {"natal", "daiun"}),
200:             ("daiun_annual", [luck, annual], {"daiun", "annual"}),
201:             ("combined", natal + [luck, annual], {"natal", "daiun", "annual"}),
202:         ):
203:             interactions[key].extend({"daiun_index": context["index"], **r} for r in _scope(participants, required))
204:     kubo = data.get("kubo") or core.kubo_from_day_kanshi(by_name["day"]["kanshi"])
205:     empty = kubo["empty_branches"]
206:     daiun_counts, combined = [], []
207:     for context in contexts:
208:         luck = _item("daiun", context["kanshi"])
209:         daiun_counts.append({"daiun_index": context["index"], **_counts([luck])})
210:         combined.append({"daiun_index": context["index"], **_counts(natal + [luck, annual])})
211:     first = datetime.fromisoformat(periods[0]["approx_start_at"]) if periods else None
212:     direction_unknown = (data.get("daiun") or {}).get("status") == "undetermined_gender"
213:     return {"annual_fortune_report": {
214:         "schema_version": "1.0", "base_chart_id": (base_doc.get("meta") or {}).get("chart_id"),
215:         "selected_year": selected_year,
216:         "calculation": {"engine": "nanami-shichusuimei-annual-v1", "base_engine_version": shichu.get("engine_version"),
217:                         "year_boundary_rule": "lichun(315deg)", "daiun_calc_mode": "approx_days_to_years",
218:                         "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
219:                         "timezone": tz_name, "supported_years": {"min": MIN_YEAR, "max": MAX_YEAR},
220:                         "base_day_pillar_suspect": day_suspect,
221:                         "legacy_female_imputed": legacy_imputed,
222:                         "legacy_reference_notes": legacy_notes,
223:                         "natal_time_basis": "four_pillars" if reliable else "three_pillars_hour_excluded"},
224:         "base_chart_usage": {"full_yaml_required": True,
225:                              "note": "同じbase_chart_idのFull YAMLと併用。出生四柱は照合用。格局・用神などは基礎命式を参照。"},
226:         "natal_reference": {"day_master": day_master, "pillars": {p["name"]: p["kanshi"] for p in natal}},
227:         "annual": {"effective_year": selected_year, **{k: v for k, v in annual.items() if k != "name"},
228:                    "period_start": start.isoformat(), "period_end": end.isoformat(), "period_end_exclusive": True,
229:                    "ten_god_to_day_master": core.ten_god(day_master, annual["stem"]),
230:                    "twelve_fortune_to_day_master": core.twelve_fortune(day_master, annual["branch"])},
231:         "daiun": {"status": "undetermined_gender" if direction_unknown else "legacy_female_imputed" if legacy_imputed else "overlapping_periods" if contexts else "before_first_daiun",
232:                   "contexts": contexts, "boundary_in_selected_year": any(c["boundary_in_selected_year"] for c in contexts),
233:                   "uncovered_before_first_daiun": {"start": start.isoformat(), "end": min(first, end).isoformat()}
234:                       if first is not None and start < first else None,
235:                   "note": "起運・交運日時は既存の簡易換算による概算。境界付近の大運を確定値として扱わない。"},
236:         "interactions": interactions,
237:         "kubo": {"empty_branches": deepcopy(empty), "annual_hit": annual["branch"] in empty,
238:                  "natal_hits": [p["name"] for p in natal if p["branch"] in empty],
239:                  "daiun_hits": [{"daiun_index": c["index"], "hit": c["branch"] in empty} for c in contexts],
240:                  "method": "membership_in_natal_day_jun_empty_branches"},
241:         "five_elements": {"natal": deepcopy(data.get("five_elements")), "natal_reference_only": not reliable,
242:                           "included_natal_reference": _counts(natal), "annual": _counts([annual]),
243:                           "daiun": daiun_counts, "combined_reference": combined,
244:                           "method": "existing_visible_stem_plus_branch_and_additive_hidden_stem_counts",
245:                           "note": "合算は参考個数。強弱・吉凶・合化の成立を示さない。時刻不明・推定の場合、合算から時柱を除外。"},
246:         "interpretation_flags": {"calculation_only": True, "automatic_good_bad_judgment": False,
247:                                  "base_day_pillar_suspect": day_suspect,
248:                                  "legacy_reference_notes": legacy_notes,
249:                                  "daiun_direction_confirmed": not direction_unknown and not legacy_imputed,
250:                                  "natal_day_pillar_verified_by_this_report": False,
251:                                  "automatic_element_transformation": False},
252:     }}
253: 
254: 
255: def build_annual_fortune_yaml(base_doc: dict, selected_year: int) -> str:
256:     return yaml.safe_dump(build_annual_fortune_report(base_doc, selected_year), allow_unicode=True, sort_keys=False, width=120)
```
