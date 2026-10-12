"""D-1: 出生時刻不明・推定 × 節入り日/立春日の保留仕様（エンジン0.6.1）のテスト。

仕様: docs/claude_daiun_ryunen_review_20261012.md 9.3節（リポジトリ本体側資料）。
2026-03-05 は啓蟄（22:59 JST）、2026-02-04 は立春（05:02 JST）。
節気時刻は国立天文台暦要項と照合済み（claude_shichu_calc_verification_20261012.md B節）。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from services import shichusuimei_calc as core

AS_OF = datetime(2026, 10, 12, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def _calc(payload, **kw):
    return core.calc_shichusuimei_from_payload(payload, as_of=AS_OF, **kw)


def test_unknown_time_on_jie_day_withholds_daiun():
    result = _calc({"year": 2026, "month": 3, "day": 5, "hour": None, "minute": None, "gender": "male"})
    nd = result["normalized_data"]
    daiun = nd["daiun"]
    assert daiun["status"] == "undetermined_month_pillar"
    assert daiun["direction"] is None
    assert daiun["items"] == []
    assert daiun["undetermined_pillars"] == ["month"]
    months = {c["month_pillar"] for c in daiun["candidates"]}
    assert months == {"庚寅", "辛卯"}
    firsts = {c["first_daiun_kanshi"] for c in daiun["candidates"]}
    assert firsts == {"辛卯", "壬辰"}
    # 2026=丙午（陽年）×男性なので両候補とも順行
    assert {c["direction"] for c in daiun["candidates"]} == {"forward"}
    # 年別予測は保留
    assert nd["annual_forecasts"]["items"] == []
    assert nd["annual_forecasts"]["daiun_direction_status"] == "undetermined_month_pillar"
    # 月柱は関係検出から除外（確定柱のみ提供）
    assert nd["annual_fortune"]["undetermined_excluded_pillars"] == ["month"]
    for rel in nd["annual_fortune"]["relations"]["branch_relations"] + nd["annual_fortune"]["relations"]["stem_relations"]:
        assert rel["right"]["name"] != "month"
    for rel in nd["annual_fortune"]["special_relations_natal"]:
        assert "month" not in rel["pillars"]
    for rel in nd["interactions"]["branch_relations"] + nd["interactions"]["stem_relations"]:
        assert "month" not in (rel["left"]["name"], rel["right"]["name"])
    # 開示
    evaluation = result["input"]["time_context"]["time_window_evaluation"]
    assert evaluation["month_pillar_stable"] is False
    assert evaluation["year_pillar_stable"] is True
    assert any("節入り" in u for u in result["unknowns"])
    assert "time_window_policy" in result["input"]["assumptions"]
    assert nd["time_sensitive_reference"]["undetermined_pillars"] == ["month"]


def test_exact_time_on_jie_day_stays_normal():
    result = _calc({"year": 2026, "month": 3, "day": 5, "hour": 8, "minute": 0, "gender": "male"})
    nd = result["normalized_data"]
    assert nd["daiun"].get("status") == "determined_direction_approx_timing"
    assert len(nd["daiun"]["items"]) == 10
    assert nd["daiun"]["items"][0]["kanshi"] == "辛卯"
    assert len(nd["annual_forecasts"]["items"]) == 10
    assert "time_window_evaluation" not in result["input"]["time_context"]
    assert "start_age_window" not in nd["daiun"]


def test_unknown_time_on_lichun_day_withholds_year_pillar():
    result = _calc({"year": 2026, "month": 2, "day": 4, "hour": None, "minute": None, "gender": "male"})
    daiun = result["normalized_data"]["daiun"]
    assert daiun["status"] == "undetermined_year_pillar"
    assert daiun["undetermined_pillars"] == ["year", "month"]
    years = {c["year_pillar"] for c in daiun["candidates"]}
    assert years == {"乙巳", "丙午"}
    # 乙巳（陰年）×男性=逆行、丙午（陽年）×男性=順行
    directions = {c["year_pillar"]: c["direction"] for c in daiun["candidates"]}
    assert directions == {"乙巳": "reverse", "丙午": "forward"}
    evaluation = result["input"]["time_context"]["time_window_evaluation"]
    assert evaluation["year_pillar_stable"] is False


def test_unknown_time_on_ordinary_day_keeps_daiun_with_age_window():
    result = _calc({"year": 1990, "month": 5, "day": 15, "hour": None, "minute": None, "gender": "female"})
    nd = result["normalized_data"]
    assert len(nd["daiun"]["items"]) == 10
    assert len(nd["annual_forecasts"]["items"]) == 10
    window = nd["daiun"]["start_age_window"]
    assert len(window["endpoints"]) == 2
    assert all(e["start_age_text"] for e in window["endpoints"])
    evaluation = result["input"]["time_context"]["time_window_evaluation"]
    assert evaluation["month_pillar_stable"] is True and evaluation["year_pillar_stable"] is True


def test_approximate_range_decides_by_crossing_the_jie():
    # 啓蟄 2026-03-05 22:59 JST。午前(06:00-11:59)は跨がず一意、夜(18:00-23:59)は跨ぐ。
    base = {"year": 2026, "month": 3, "day": 5, "gender": "male", "birth_time_accuracy": "approximate"}
    morning = _calc({**base, "hour": 9, "minute": 0,
                     "birth_time_range": {"estimated_range": "06:00-11:59"}})
    nd_m = morning["normalized_data"]
    assert len(nd_m["daiun"]["items"]) == 10
    assert nd_m["daiun"]["items"][0]["kanshi"] == "辛卯"
    assert "start_age_window" in nd_m["daiun"]
    night = _calc({**base, "hour": 21, "minute": 0,
                   "birth_time_range": {"estimated_range": "18:00-23:59"}})
    assert night["normalized_data"]["daiun"]["status"] == "undetermined_month_pillar"


def test_undetermined_gender_and_time_window_together():
    result = _calc({"year": 2026, "month": 3, "day": 5, "hour": None, "minute": None, "gender": "unknown"})
    daiun = result["normalized_data"]["daiun"]
    # 柱の未確定が優先。候補の方向は性別未指定のため null
    assert daiun["status"] == "undetermined_month_pillar"
    assert {c["direction"] for c in daiun["candidates"]} == {None}


def test_engine_version_is_0_6_1():
    result = _calc({"year": 1990, "month": 5, "day": 15, "hour": 12, "minute": 30, "gender": "female"})
    # 0.6.1 で導入した保留方式。以降の版でも維持する。
    assert result["engine_version"] == core.ENGINE_VERSION
    assert tuple(int(n) for n in core.ENGINE_VERSION.split(".")) >= (0, 6, 1)


def test_product_yaml_svg_and_year_selection_for_undetermined():
    from services.yaml_exporter import build_product_yaml
    from services.shichu_chart import build_shichusuimei_svg_from_yaml
    from services.shichusuimei_year_selection import selection_info
    yaml_text, _prompt, doc = build_product_yaml(
        title=None, birth_date="2026-03-05", birth_time=None, prefecture="東京都",
        gender="male", include_shichusuimei=True,
    )
    shichu = doc["systems"]["shichusuimei"]
    assert shichu["normalized_data"]["daiun"]["status"] == "undetermined_month_pillar"
    svg = build_shichusuimei_svg_from_yaml(yaml_text)
    assert "大運：未確定（出生時刻により変動）" in svg
    info = selection_info(yaml_text)
    assert info["available_years"] == []
    assert info["year_selection_available"] is False


def test_addon_and_annual_report_pass_through_undetermined_status():
    from services.yaml_exporter import build_product_yaml, build_shichu_fortune_cycles_addon_yaml
    from services.shichusuimei_annual_report import build_annual_fortune_report
    _, _, addon = build_shichu_fortune_cycles_addon_yaml(
        title=None, birth_date="2026-03-05", birth_time=None, prefecture="東京都", gender="male",
    )
    addon_daiun = addon["systems"]["shichusuimei"]["normalized_data"]["daiun"]
    assert addon_daiun["status"] == "undetermined_month_pillar"
    assert addon_daiun["candidates"]
    _, _, doc = build_product_yaml(
        title=None, birth_date="2026-03-05", birth_time=None, prefecture="東京都",
        gender="male", include_shichusuimei=True,
    )
    report = build_annual_fortune_report(doc, 2028)["annual_fortune_report"]
    assert report["daiun"]["status"] == "undetermined_month_pillar"
    assert report["daiun"]["contexts"] == []
