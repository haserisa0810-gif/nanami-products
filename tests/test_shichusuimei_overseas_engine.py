"""Independent offline oracle, API contracts and read-only legacy compatibility."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import yaml

from services.birth_datetime import BirthDatetimeError, resolve_birth_datetime
from services import shichusuimei_calc as core
from services.shichusuimei_year_selection import build_year_selection
from services.shichusuimei_annual_report import build_annual_fortune_report
from services.yaml_exporter import build_product_yaml, build_shichu_fortune_cycles_addon_yaml
from services.api_calc import calc_shichu_api

DATA = json.loads((Path(__file__).parent/"fixtures/shichusuimei/overseas_calendar_reference.json").read_text(encoding="utf-8"))
NOW = datetime(2026,10,11,12,tzinfo=ZoneInfo("Asia/Tokyo"))
PAYLOAD = dict(year=1990,month=5,day=15,hour=12,minute=30,gender="female")


@pytest.mark.parametrize("case",DATA["cases"],ids=lambda c:f"{c['timezone']}-{c['local']}-{c['day_boundary_hour']}")
def test_independent_civil_calendar_pillars(case):
    birth=datetime.fromisoformat(case["local"])
    local=resolve_birth_datetime(birth,case["timezone"])
    assert local.utcoffset().total_seconds()/3600==case["offset_hours"]
    assert local.astimezone(timezone.utc).isoformat()==case["utc"]
    result=core.pillars_day_hour(birth,case["timezone"],day_boundary_hour=case["day_boundary_hour"])
    assert (result.day,result.hour)==(case["day"],case["hour"])
    assert core.day_kanshi_from_birth(local.astimezone(timezone.utc),case["timezone"],day_boundary_hour=case["day_boundary_hour"])==case["day"]


# Solar-term year/month do not depend on the day-boundary mode. Check each
# zone/date once here, instead of repeating the same astronomy 24 times.
YM_CASES=[c for c in DATA["cases"] if c["day_boundary_hour"]==0 and "T01:00:" in c["local"]]
@pytest.mark.parametrize("case",YM_CASES,ids=lambda c:f"{c['timezone']}-{c['local']}")
def test_independent_year_month_same_astronomical_instant(case):
    result=core.year_month_pillars(datetime.fromisoformat(case["local"]),case["timezone"])
    assert result[:2]==(case["year"],case["month"])


@pytest.mark.parametrize("zone",["Asia/Tokyo","Asia/Seoul","Europe/London","America/New_York","America/Los_Angeles","Pacific/Honolulu","Australia/Sydney","UTC","Pacific/Kiritimati","Pacific/Pago_Pago"])
@pytest.mark.parametrize("minutes,year,month",[(-2,"乙巳","己丑"),(2,"丙午","庚寅")])
def test_lichun_global_same_instant_from_naoj(zone,minutes,year,month):
    # Published minute-rounded 2026-02-04 05:02 JST; use +/-2min.
    utc=datetime(2026,2,3,20,2,tzinfo=timezone.utc)+timedelta(minutes=minutes)
    local=utc.astimezone(ZoneInfo(zone))
    y,m,debug=core.year_month_pillars(local,zone)
    assert (y,m)==(year,month)
    assert datetime.fromisoformat(debug["local_datetime"]).astimezone(timezone.utc)==utc


def test_three_original_findings_reproductions_now_correct():
    assert core.day_kanshi_from_birth(datetime(2000,1,7,12),"UTC")=="甲子"
    assert core.day_kanshi_from_birth(datetime(2000,1,7,23,30),"America/Los_Angeles",True)=="乙丑"
    assert core.day_kanshi_from_birth(datetime(2000,1,7,0,30),"Asia/Tokyo",False)=="癸亥"
    assert core.day_kanshi_from_birth(datetime(2000,1,7,0,30),"Asia/Tokyo",True)=="甲子"


@pytest.mark.parametrize("gender",[None,"","unknown","default","unexpected"])
def test_unknown_gender_preserves_natal_and_forecast_without_daiun(gender):
    data=core.calc_shichusuimei_from_payload({**PAYLOAD,"gender":gender},as_of=NOW)
    known=core.calc_shichusuimei_from_payload(PAYLOAD,as_of=NOW)
    assert data["input"]["raw"]["gender"]=="unknown"
    assert data["input"]["raw"]["gender_supplied"]==gender
    nd=data["normalized_data"]
    for key in ("pillars","hidden_stems","ten_gods","twelve_fortune","five_elements","kubo","structural_analysis"):
        assert nd[key]==known["normalized_data"][key]
    assert nd["daiun"]["status"]=="undetermined_gender"
    assert nd["daiun"]["direction"] is None
    assert nd["daiun"]["start_age"] is None
    assert nd["daiun"]["items"]==[]
    assert nd["annual_fortune"]["current_daiun"] is None
    assert nd["annual_fortune"]["structural_analysis"]["concurrent_daiun"] is None
    assert len(nd["annual_forecasts"]["items"])==10
    for item in nd["annual_forecasts"]["items"]:
        assert item["daiun_contexts"]==[] and item["daiun_direction_status"]=="undetermined_gender"
        assert item["natal_analysis"]["pillar"]==item["kanshi"]


@pytest.mark.parametrize("stem,gender,direction",[("甲","male","forward"),("甲","female","reverse"),("乙","male","reverse"),("乙","female","forward")])
def test_specified_gender_direction(stem,gender,direction):
    assert core._daiun_direction_from_year_stem(stem,gender)==direction
    assert core._daiun_direction_from_year_stem(stem,"unknown") is None


@pytest.mark.parametrize("zone,wall",[("America/New_York","2024-03-10T02:30"),("America/Los_Angeles","2024-03-10T02:30"),("Europe/London","2024-03-31T01:30"),("Australia/Sydney","2024-10-06T02:30")])
def test_dst_nonexistent_rejected(zone,wall):
    with pytest.raises(BirthDatetimeError,match="存在しません"):
        core.pillars4(datetime.fromisoformat(wall),zone)


@pytest.mark.parametrize("zone,wall",[("America/New_York","2024-11-03T01:30"),("America/Los_Angeles","2024-11-03T01:30"),("Europe/London","2024-10-27T01:30"),("Australia/Sydney","2024-04-07T02:30")])
def test_dst_ambiguous_requires_choice_and_aware_instant_is_retained(zone,wall):
    birth=datetime.fromisoformat(wall)
    with pytest.raises(BirthDatetimeError,match="重複"):
        core.pillars4(birth,zone)
    a=resolve_birth_datetime(birth,zone,fold=0)
    b=resolve_birth_datetime(birth,zone,fold=1)
    assert b.astimezone(timezone.utc)-a.astimezone(timezone.utc)==timedelta(hours=1)
    assert resolve_birth_datetime(a.astimezone(timezone.utc),zone)==a
    assert resolve_birth_datetime(b.astimezone(timezone.utc),zone).fold==1
    assert resolve_birth_datetime(birth,zone,utc_offset_hours=b.utcoffset().total_seconds()/3600).fold==1


@pytest.mark.parametrize("zone",[None,"","not-a-zone"])
def test_unresolved_timezone_never_defaults_to_utc(zone):
    with pytest.raises(BirthDatetimeError):core.day_kanshi_from_birth(datetime(2000,1,7,12),zone)


@pytest.mark.parametrize("boundary",[0,1,23])
def test_time_context_rule_and_api_output_agree(boundary):
    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="23:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone="America/Los_Angeles",gender="female",day_boundary=f"{boundary:02}:00"))
    assert status==200
    assert response["meta"]["api_version"]=="1.1"
    # Find the actual raw module rather than relying on API envelope naming.
    text=json.dumps(response,ensure_ascii=False)
    assert f'"engine_version": "{core.ENGINE_VERSION}"' in text
    assert f'"day_boundary_rule": "{boundary:02}:00切替"' in text
    result=core.calc_shichusuimei_from_payload(dict(year=2000,month=1,day=7,hour=23,minute=30,gender="female"),tz_name="America/Los_Angeles",day_boundary_hour=boundary,as_of=NOW)
    context=result["input"]["time_context"]
    assert context["local_datetime"]=="2000-01-07T23:30:00-08:00"
    assert context["utc_datetime"]=="2000-01-08T07:30:00+00:00"
    assert context["day_pillar_date"]==("2000-01-08" if boundary==23 else "2000-01-07")
    assert context["true_solar_time_applied"] is False


def test_api_dst_error_and_explicit_choice():
    args=dict(birth_date="2024-11-03",birth_time="01:30",birth_place="New York",timezone="America/New_York",lat=40.71,lon=-74,gender="unknown")
    response,status=calc_shichu_api(args)
    assert status==400 and response["error"]["code"]=="INVALID_BIRTH_DATETIME"
    response,status=calc_shichu_api({**args,"birth_fold":1})
    assert status==200
    response,status=calc_shichu_api({**args,"day_boundary":"nonsense"})
    assert status==400


@pytest.mark.parametrize("extra",[{}, {"timezone":""}, {"timezone":"not-a-zone"}])
def test_api_overseas_requires_known_timezone(extra):
    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,**extra))
    assert status==400 and response["error"]["code"]=="INVALID_TIMEZONE"


@pytest.mark.parametrize("boundary",[-1,24,True,"23"])
def test_invalid_boundary_not_silently_coerced(boundary):
    with pytest.raises(ValueError):core.day_kanshi_from_birth(datetime(2000,1,7,12),day_boundary_hour=boundary)


def test_saved_legacy_addon_rule_and_conflicting_day_are_protected(monkeypatch):
    import routes
    original=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
    original_copy=deepcopy(original)
    day=original["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]
    sent={}
    def fake(**kwargs):
        sent.update(kwargs)
        return "fictional", "", {"systems":{"shichusuimei":{"reference":{"day_kanshi":day}}}}
    monkeypatch.setattr(routes,"build_shichu_fortune_cycles_addon_yaml",fake)
    assert routes._build_addon_yaml_from_base(original,"shichu_fortune_cycles_addon")=="fictional"
    assert sent["day_boundary_hour"]==0 and sent["day_change_at_23"] is False
    assert original==original_copy
    def conflicting(**kwargs):
        return "fictional", "", {"systems":{"shichusuimei":{"reference":{"day_kanshi":"乙丑"}}}}
    monkeypatch.setattr(routes,"build_shichu_fortune_cycles_addon_yaml",conflicting)
    with pytest.raises(ValueError,match="計算が異なる"):
        routes._build_addon_yaml_from_base(original,"shichu_fortune_cycles_addon")
    assert original==original_copy


def test_buyer_fold_selector_and_parser_are_consistent():
    import routes
    from fastapi.testclient import TestClient
    assert routes._parse_birth_fold("") is None
    assert routes._parse_birth_fold("0")==0
    assert routes._parse_birth_fold("1")==1
    with pytest.raises(ValueError):routes._parse_birth_fold("2")
    html=TestClient(routes.app).get("/redeem/shichu").text
    assert 'name="birth_fold"' in html
    assert "同じ現地時刻の1回目" in html and "同じ現地時刻の2回目" in html
    assert "大運・起運は未確定" in html


def test_unknown_gender_year_selection_annual_adapter_svg_and_addon():
    text,prompt,doc=build_product_yaml(title="Fictional unknown",birth_date="1990-05-15",birth_time="12:30",prefecture="東京都",gender="unknown",include_shichusuimei=True)
    original_hash=hashlib.sha256(text.encode()).hexdigest()
    forecasts=doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]
    years=[forecasts[0]["effective_year"],forecasts[-1]["effective_year"]]
    selected=yaml.safe_load(build_year_selection(text,{"mode":"selected","years":years})["yaml_text"])
    assert selected["selected_base_forecasts"]==[i for i in forecasts if i["effective_year"] in years]
    assert selected["common"]["systems"]["shichusuimei"]["normalized_data"]["daiun"]["direction"] is None
    report=build_annual_fortune_report(doc,years[0])["annual_fortune_report"]
    assert report["daiun"]["status"]=="undetermined_gender"
    assert report["daiun"]["contexts"]==[]
    assert report["interactions"]["natal_annual"]
    assert "女性へ補完せず" in prompt
    assert "現地暦日" in prompt
    assert hashlib.sha256(text.encode()).hexdigest()==original_hash
    assert build_year_selection(text,{"mode":"complete"})["yaml_text"]==text
    from services.shichu_chart import build_shichusuimei_svg_from_yaml
    assert "大運：未確定" in build_shichusuimei_svg_from_yaml(text)
    _,_,addon=build_shichu_fortune_cycles_addon_yaml(title=None,birth_date="1990-05-15",birth_time="12:30",prefecture="東京都",gender="unknown")
    assert addon["calculation"]["engine_version"]==core.ENGINE_VERSION
    assert addon["systems"]["shichusuimei"]["normalized_data"]["daiun"]["direction"] is None


def test_legacy_full_fixture_complete_and_selection_never_recalculated():
    path=Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml"
    original=path.read_text(encoding="utf-8")
    doc=yaml.safe_load(original)
    year=doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"][0]["effective_year"]
    with patch.object(core,"calc_shichusuimei_from_payload",side_effect=AssertionError("no recalculation")):
        assert build_year_selection(original,{"mode":"complete"})["yaml_text"]==original
        selected=yaml.safe_load(build_year_selection(original,{"mode":"selected","years":[year]})["yaml_text"])
    assert selected["common"]["systems"]["shichusuimei"]["normalized_data"]["daiun"]==doc["systems"]["shichusuimei"]["normalized_data"]["daiun"]
    assert path.read_text(encoding="utf-8")==original


@pytest.mark.parametrize("flag",["false","true"])
def test_engine_boolean_is_not_an_hour_or_truthy_string(flag):
    with pytest.raises(ValueError):
        core.day_kanshi_from_birth(datetime(2000,1,7,12),day_change_at_23=flag)


def test_api_timezone_null_preserves_explicit_alias():
    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone=None,tz_name="America/Los_Angeles"))
    assert status==200 and response["raw_data"]["shichu"]["input"]["time_context"]["timezone"]=="America/Los_Angeles"


@pytest.mark.parametrize("offset",[-8,None])
def test_legacy_annual_report_flags_suspect_day_and_imputed_gender_without_changing_original(offset):
    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
    doc["input"]["gender"]="unknown"
    doc["systems"]["shichusuimei"]["engine_version"]="0.4.0"
    doc["input"]["timezone_offset_hours"]=offset
    doc["systems"]["shichusuimei"]["input"]["raw"]["gender"]="female"
    snapshot=deepcopy(doc)
    result=build_annual_fortune_report(doc,2028)["annual_fortune_report"]
    assert result["calculation"]["base_day_pillar_suspect"] is (True if offset is not None else None)
    assert result["calculation"]["legacy_female_imputed"] is True
    assert result["daiun"]["status"]=="legacy_female_imputed"
    assert result["interpretation_flags"]["daiun_direction_confirmed"] is False
    assert result["interpretation_flags"]["base_day_pillar_suspect"] is (True if offset is not None else None)
    assert result["natal_reference"]["pillars"]["day"]==doc["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]
    assert doc==snapshot


@pytest.mark.parametrize("kind",["top_level","summary","missing"])
def test_legacy_addon_alternative_day_locations_and_saved_offset(monkeypatch,kind):
    import routes
    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
    shichu=doc["systems"]["shichusuimei"]
    day=shichu["normalized_data"]["pillars"].pop("day")["kanshi"]
    shichu.pop("pillars",None)
    shichu.pop("summary",None)
    if kind=="top_level":shichu["pillars"]={"day":day}
    if kind=="summary":shichu["summary"]={"day_kanshi":day}
    snapshot=deepcopy(doc)
    def fake(**args):
        assert args["birth_utc_offset_hours"]==9.0
        return "fictional","",{"systems":{"shichusuimei":{"reference":{"day_kanshi":day}}}}
    monkeypatch.setattr(routes,"build_shichu_fortune_cycles_addon_yaml",fake)
    if kind=="missing":
        with pytest.raises(ValueError,match="照合できない"):routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon")
    else:assert routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon")=="fictional"
    assert doc==snapshot


def test_japan_historic_dst_and_hour_stem_rule_are_explicit():
    wall=datetime(1949,9,11,0,30)
    with pytest.raises(BirthDatetimeError,match="重複"):resolve_birth_datetime(wall,"Asia/Tokyo")
    a=resolve_birth_datetime(wall,"Asia/Tokyo",fold=0)
    b=resolve_birth_datetime(wall,"Asia/Tokyo",fold=1)
    assert a.utcoffset()==timedelta(hours=10) and b.utcoffset()==timedelta(hours=9)
    assert b.astimezone(timezone.utc)-a.astimezone(timezone.utc)==timedelta(hours=1)
    result=core.calc_shichusuimei_from_payload(PAYLOAD,as_of=NOW)
    assert result["input"]["time_context"]["hour_stem_rule"]=="five_rat_from_effective_day_stem"


@pytest.mark.parametrize("bad_timezone",[False,0,[],{}])
def test_api_non_string_timezone_cannot_inherit_tokyo(bad_timezone):
    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="Los Angeles",lat=34.05,lon=-118.24,timezone=bad_timezone))
    assert status==400 and response["error"]["code"]=="INVALID_TIMEZONE"


def test_old_report_missing_gender_is_not_claimed_as_female_imputation():
    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
    doc["input"].pop("gender",None)
    doc["systems"]["shichusuimei"]["engine_version"]="0.4.0"
    doc["systems"]["shichusuimei"]["input"]["raw"]["gender"]="female"
    report=build_annual_fortune_report(doc,2028)["annual_fortune_report"]
    assert report["calculation"]["legacy_female_imputed"] is False
    assert report["calculation"]["legacy_gender_input_missing"] is True
    assert report["daiun"]["status"]=="legacy_gender_unverified"
    assert report["interpretation_flags"]["daiun_direction_confirmed"] is None


def test_old_addon_saved_timezone_offset_works_with_real_generator():
    import routes
    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
    snapshot=deepcopy(doc)
    addon=yaml.safe_load(routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon"))
    assert addon["calculation"]["day_boundary_hour"]==0
    assert addon["calculation"]["time_context"]["utc_offset_hours"]==9.0
    day=doc["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]
    assert addon["systems"]["shichusuimei"]["reference"]["day_kanshi"]==day
    assert doc==snapshot


@pytest.mark.parametrize("endpoint",["western","transit"])
def test_western_api_version_unchanged(endpoint):
    from services.api_calc import _success
    # Envelope check only; the actual natal/transit numeric regression is in
    # verify_shichusuimei_engine_fix.py and the existing suite.
    result,status=_success(endpoint,{}, {"systems":{}})
    assert status==200 and result["meta"]["api_version"]=="1.0"


@pytest.mark.parametrize("offset",[False,True])
def test_birth_offset_boolean_cannot_choose_dst_candidate(offset):
    with pytest.raises(BirthDatetimeError,match="数値"):
        resolve_birth_datetime(datetime(2024,10,27,1,30),"Europe/London",utc_offset_hours=offset)


def test_domestic_api_blank_timezone_preserves_prefecture_default():
    response,status=calc_shichu_api(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="東京都",timezone=""))
    assert status==200
    assert response["raw_data"]["shichu"]["input"]["time_context"]["timezone"]=="Asia/Tokyo"


def test_corrected_negative_offset_annual_report_has_no_legacy_day_warning():
    _,_,doc=build_product_yaml(title="Fictional new LA",birth_date="2000-01-07",birth_time="12:30",prefecture="",birth_place_label="Los Angeles",birth_lat=34.05,birth_lng=-118.24,tz_name="America/Los_Angeles",gender="female",include_shichusuimei=True)
    report=build_annual_fortune_report(doc,2028)["annual_fortune_report"]
    assert report["calculation"]["base_engine_version"]==core.ENGINE_VERSION
    assert report["interpretation_flags"]["base_day_pillar_suspect"] is False


@pytest.mark.parametrize("endpoint",["western","transit"])
def test_actual_western_endpoints_keep_version_one(endpoint):
    from services.api_calc import calc_western_api,calc_transit_api
    fn=calc_western_api if endpoint=="western" else calc_transit_api
    response,status=fn(dict(birth_date="2000-01-07",birth_time="12:30",birth_place="東京都",include_asteroids=False,period="day"))
    assert status==200 and response["meta"]["api_version"]=="1.0"
    assert response["raw_data"]["shichu"] is None


def test_old_la_addon_is_rejected_by_real_day_comparison():
    import routes
    doc=yaml.safe_load((Path(__file__).parent/"fixtures/shichusuimei/spring_exact_base.yaml").read_text(encoding="utf-8"))
    doc["input"].update(birth_date="2000-01-07",birth_time="12:00",calculation_time="12:00",birth_place="Los Angeles",prefecture="",birth_place_kind="overseas",birth_lat=34.05,birth_lng=-118.24,timezone="America/Los_Angeles",timezone_offset_hours=-8,gender="female")
    doc["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"]="乙丑"
    snapshot=deepcopy(doc)
    with pytest.raises(ValueError,match="計算が異なる"):
        routes._build_addon_yaml_from_base(doc,"shichu_fortune_cycles_addon")
    assert doc==snapshot
