from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import yaml

from services.shichusuimei_calc import HIDDEN_STEMS, KANSHI_60, Pillars4, calc_shichusuimei_from_payload
from services.shichusuimei_structure import analyze_structure, analyze_luck, concurrent_luck_analysis


def test_day_master_is_not_visible_peer_and_hidden_weight_is_conserved():
    p = Pillars4(year="丙寅", month="丙寅", day="甲子", hour="戊辰")
    result = analyze_structure(p)
    gods = result["ten_god_strength"]
    assert gods["比肩"]["visible_count"] == 0
    assert gods["食神"]["visible_count"] == 2
    assert all(x["pillar"] != "day" or x["layer"] != "visible"
               for g in gods.values() for x in g["placements"])
    useful = result["useful_god_analysis"]
    assert useful["definitive_useful_god"] == useful["useful_god_selection"]["useful_god"]
    assert useful["definitive_basis"] == "general_fuyi_with_climate_priority_v1"
    assert result["pattern_analysis"]["definitive_pattern"] is None


def test_unknown_hour_does_not_change_structure():
    a = Pillars4(year="丙寅", month="丙寅", day="甲子", hour="戊辰")
    b = Pillars4(year="丙寅", month="丙寅", day="甲子", hour="辛酉")
    assert analyze_structure(a, time_reliable=False) == analyze_structure(b, time_reliable=False)


def test_luck_relations_only_include_luck_and_do_not_transform():
    p = Pillars4(year="甲子", month="己丑", day="丙午", hour="辛卯")
    result = analyze_luck(p, "壬子")
    relations = result["interactions_with_natal"]["branch_relations"]
    assert any(r["type"] == "clash" and r["right"]["name"] == "day" for r in relations)
    assert all(r["left"]["name"] == "luck" for r in relations)
    assert result["transformation_status"] == "not_assessed_no_element_conversion"


def test_element_total_exceeds_gods_by_exactly_day_master_weight():
    p = Pillars4(year="甲子", month="己丑", day="丙午", hour="辛卯")
    result = analyze_structure(p)
    total = sum(result["element_flow"]["element_scores"].values())
    gods = sum(g["score"] for g in result["ten_god_strength"].values())
    assert abs(total - gods - result["methodology"]["seasonal_multipliers"]["火"]) < .0001


def test_root_rank_polarity_and_exposure_are_distinguished():
    p = Pillars4(year="甲寅", month="丙寅", day="乙卯", hour="戊辰")
    result = analyze_structure(p)
    root = next(r for r in result["roots_and_exposure"]["rooting"] if r["pillar"] == "day")
    assert any(x["stem"] == "甲" and x["match"] == "same_element" for x in root["roots"])
    assert any(x["stem"] == "乙" and x["match"] == "same_stem" and x["role"] == "main" for x in root["roots"])
    exposures = result["roots_and_exposure"]["exposure"]
    assert all(not x["visible_pillars"] for x in exposures if x["stem"] == "乙")
    assert any(x["visible_pillars"] == ["month"] for x in exposures if x["stem"] == "丙")


def test_hidden_branch_base_weights_always_sum_to_one_and_scores_stay_finite():
    for i, kanshi in enumerate(KANSHI_60):
        p = Pillars4(year=kanshi, month=KANSHI_60[(i + 7) % 60], day=KANSHI_60[(i + 17) % 60], hour=KANSHI_60[(i + 31) % 60])
        result = analyze_structure(p)
        placements = [x for g in result["ten_god_strength"].values() for x in g["placements"]]
        for pillar, value in vars(p).items():
            hidden = [x for x in placements if x["pillar"] == pillar and x["layer"] == "hidden"]
            assert len(hidden) == len(HIDDEN_STEMS[value[1]])
            assert sum(x["base_weight"] for x in hidden) == pytest.approx(1)
        assert sum(g["share"] for g in result["ten_god_strength"].values()) == pytest.approx(1, abs=.001)
        assert 0 < result["day_master_support"]["support_ratio"] <= 1


def test_extreme_chart_holds_fuyi_but_selects_dominant_pattern_view():
    p = Pillars4(year="乙卯", month="乙卯", day="甲子", hour="乙卯")
    result = analyze_structure(p)
    assert result["day_master_support"]["special_pattern_review_required"]
    useful = result["useful_god_analysis"]
    assert useful["methods"][0]["status"] == "held_for_review"
    assert useful["methods"][0]["favorable_elements"] == useful["methods"][0]["unfavorable_elements"] == []
    selection = useful["useful_god_selection"]
    assert selection["pattern_view"] == "dominant_pattern" and selection["useful_god"] == "木"
    assert selection["alternatives"] and "専旺格" in selection["basis"][0]
    unknown = analyze_structure(p, time_reliable=False)
    assert unknown["useful_god_analysis"]["methods"][0]["status"] == "held_for_review"


def test_flow_keeps_day_master_output_wealth_chain_and_missing_endpoints():
    p = Pillars4(year="丙寅", month="丙寅", day="甲子", hour="戊辰")
    result = analyze_structure(p)
    assert result["element_flow"]["day_master_output_wealth_path"] == {"elements": ["木", "火", "土"], "status": "all_present"}
    food_wealth = next(x for x in result["ten_god_flow"] if x["label"] == "食神生財")
    assert food_wealth["status"] == "both_present"
    assert food_wealth["source_evidence_ids"] and food_wealth["target_evidence_ids"]
    assert any(x["source"] == "金" or x["target"] == "金" for x in result["element_flow"]["bottlenecks"])


def test_combination_competition_clash_and_half_triad_are_materials_only():
    p = Pillars4(year="丙寅", month="辛酉", day="丙申", hour="戊戌")
    result = analyze_structure(p)
    screens = result["interactions"]["combination_screening"]
    stem_screens = [s for s in screens if s["type"] == "stem_combination"]
    assert len(stem_screens) == 2
    assert all(s["checks"]["competing_partners"] for s in stem_screens)
    assert all(s["confirmed"] is False and s["element_change_applied"] is False for s in screens)
    triad = next(s for s in screens if s["type"] == "triad" and s["candidate_element"] == "火")
    assert triad["partial_form"] == "arching_without_center"
    assert triad["status"] == "conditions_incomplete"


def test_luck_can_complete_three_way_triad_and_expose_natal_hidden_stem():
    p = Pillars4(year="甲申", month="丙寅", day="戊戌", hour="乙卯")
    analysis = analyze_luck(p, "甲辰", other_luck="壬子")
    triad = next(r for r in analysis["interactions_with_natal"]["triads"] if r["group"] == "水局")
    assert triad["level"] == "full"
    assert {x["name"] for x in triad["pillars"]} == {"luck", "year", "current_daiun"}
    assert any(x["pillar"] == "month" and x["stem"] == "甲" for x in analysis["exposed_natal_hidden_stems"])
    context = concurrent_luck_analysis(analysis)
    assert context["interactions_with_daiun"]["triads"][0]["level"] == "full"
    assert all(r["right"]["name"] == "current_daiun" for r in context["interactions_with_daiun"]["branch_relations"])


def test_destruction_has_named_target_gods_in_luck_analysis():
    p = Pillars4(year="甲子", month="己丑", day="丙午", hour="辛卯")
    analysis = analyze_luck(p, "癸酉")
    destruction = next(r for r in analysis["interactions_with_natal"]["branch_relations"] if r["type"] == "destruction")
    assert destruction["right"]["name"] == "year"
    assert destruction["target_ten_gods"] == {"stem": "偏印", "hidden": ["正官"]}


PAYLOAD = dict(year=1990, month=5, day=15, hour=8, minute=30, gender="female")


def test_engine_forecasts_respect_lichun_and_retain_existing_fields():
    as_of = datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Tokyo"))
    doc = calc_shichusuimei_from_payload(PAYLOAD, as_of=as_of)
    normalized = doc["normalized_data"]
    assert doc["generated_at"] == as_of.isoformat()
    assert doc["pillars"]["day"] == normalized["pillars"]["day"]["kanshi"]
    forecasts = normalized["annual_forecasts"]["items"]
    assert [i["effective_year"] for i in forecasts] == list(range(2025, 2035))
    assert forecasts[0]["kanshi"] == "乙巳"
    assert forecasts[1]["kanshi"] == "丙午"
    assert normalized["annual_fortune"]["effective_year"] == 2025
    assert all("structural_analysis" in i for i in normalized["daiun"]["items"])
    assert any(i["daiun_boundary_in_window"] for i in forecasts)
    assert any(len(i["daiun_contexts"]) == 2 for i in forecasts)
    assert calc_shichusuimei_from_payload(PAYLOAD, as_of=as_of) == doc


@pytest.mark.parametrize("years", [0, 21, True, 1.5])
def test_invalid_forecast_horizon_is_rejected(years):
    with pytest.raises(ValueError):
        calc_shichusuimei_from_payload(PAYLOAD, annual_years=years)


@pytest.mark.parametrize("accuracy,birth_time", [("unknown", None), ("approximate", "08:30"), ("exact", "08:30")])
def test_yaml_exporter_propagates_accuracy_and_serializes_new_analysis(accuracy, birth_time):
    from services.yaml_exporter import build_product_yaml
    text, prompt, doc = build_product_yaml(title="Structure QA", birth_date="1990-05-15",
        birth_time=birth_time, prefecture="東京都", include_shichusuimei=True, birth_time_accuracy=accuracy)
    parsed = yaml.safe_load(text)
    shichu = parsed["systems"]["shichusuimei"]
    assert shichu == doc["systems"]["shichusuimei"]
    assert shichu["input"]["assumptions"]["birth_time_accuracy"] == accuracy
    analysis = shichu["normalized_data"]["structural_analysis"]
    assert analysis["methodology"]["time_basis"] == ("four_pillars" if accuracy == "exact" else "three_pillars_hour_excluded")
    if accuracy != "exact":
        assert all(x["pillar"] != "hour" for g in analysis["ten_god_strength"].values() for x in g["placements"])
    assert "conflicting_rules" in prompt and "annual_forecasts" in prompt


def test_addon_contains_forecasts_and_svg_still_reads_legacy_fields():
    from services.shichu_chart import build_shichusuimei_svg_from_yaml
    from services.yaml_exporter import build_product_yaml, build_shichu_fortune_cycles_addon_yaml
    args = dict(title="Structure QA", birth_date="1990-05-15", birth_time="08:30", prefecture="東京都")
    text, _prompt, full = build_product_yaml(**args, include_shichusuimei=True)
    assert "<svg" in build_shichusuimei_svg_from_yaml(text, doc=full)
    addon_text, prompt, addon = build_shichu_fortune_cycles_addon_yaml(**args)
    normalized = yaml.safe_load(addon_text)["systems"]["shichusuimei"]["normalized_data"]
    assert len(normalized["annual_forecasts"]["items"]) == 10
    assert "annual_forecasts" in prompt
    assert "structural_analysis" not in normalized


def test_missing_hour_cannot_be_marked_reliable_by_exact_accuracy():
    doc = calc_shichusuimei_from_payload({**PAYLOAD, "hour": None, "birth_time_accuracy": "exact"}, annual_years=1)
    assert doc["input"]["assumptions"]["birth_time_accuracy"] == "unknown"
    assert doc["normalized_data"]["structural_analysis"]["methodology"]["time_basis"] == "three_pillars_hour_excluded"


def test_naive_as_of_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        calc_shichusuimei_from_payload(PAYLOAD, as_of=datetime(2026, 1, 15))


def _climate(result):
    return next(m for m in result["useful_god_analysis"]["methods"] if m["method"] == "climate_adjustment")


@pytest.mark.parametrize("month, element, urgency", [
    ("丙子", "火", "high"), ("丁丑", "火", "high"), ("己亥", "火", "medium"), ("丙寅", "火", "medium"),
    ("甲午", "水", "high"), ("乙未", "水", "high"), ("己巳", "水", "medium"),
    ("丙申", "水", "low"), ("丁酉", "水", "low"), ("戊戌", "水", "low"),
])
def test_climate_candidates_follow_month_branch_season(month, element, urgency):
    climate = _climate(analyze_structure(Pillars4(year="甲子", month=month, day="甲午", hour="甲戌")))
    assert climate["status"] == "candidate_only" and climate["confidence"] == "low"
    assert [(n["element"], n["urgency"]) for n in climate["needs"]] == [(element, urgency)]
    assert any("日干別の調候表" in x for x in climate["limitations"])


@pytest.mark.parametrize("month", ["丁卯", "戊辰"])
def test_mild_spring_months_have_no_climate_candidate(month):
    assert _climate(analyze_structure(Pillars4(year="甲子", month=month, day="甲午", hour="甲戌")))["needs"] == []


def test_climate_reports_natal_presence_and_hot_month_purposes():
    # 午月は暑く乾燥：冷ます・潤すの両方を水1つにまとめ、強い緊急度を残す。
    climate = _climate(analyze_structure(Pillars4(year="壬子", month="甲午", day="丙午", hour="甲午")))
    need = climate["needs"][0]
    assert need["purposes"] == ["cooling", "moistening"] and need["purpose_labels"] == ["冷ます", "潤す"]
    assert need["natal_presence"]["status"] == "visible_and_rooted"
    assert need["natal_presence"]["visible_pillars"] == ["year"]
    absent = _climate(analyze_structure(Pillars4(year="甲午", month="甲午", day="丙午", hour="甲午")))["needs"][0]
    assert absent["natal_presence"]["status"] == "absent" and absent["natal_presence"]["element_share"] == 0


def test_method_comparison_separates_agreement_conflict_and_single_method():
    # 甲日・申月・身弱候補：水は扶抑と調候が一致、土は通関と扶抑の忌が食い違う。
    useful = analyze_structure(Pillars4(year="丙辰", month="丙申", day="甲午", hour="甲戌"))["useful_god_analysis"]
    rows = {r["element"]: r for r in useful["method_comparison"]["elements"]}
    assert rows["水"]["status"] == "agreement"
    assert rows["水"]["supported_by"] == ["fuyi_weighted_support", "climate_adjustment"]
    assert rows["木"]["status"] == "single_method"
    assert rows["土"]["status"] == "conflict" and rows["土"]["opposed_by"] == ["fuyi_weighted_support"]
    assert rows["土"]["note"] == "通関が支持、扶抑は忌方向"
    assert {"element": "水", "method": "climate_adjustment", "status": "candidate", "urgency": "low"} in useful["candidates"]


def test_climate_conflicting_with_fuyi_is_recorded():
    # 庚日・午月の身弱候補：扶抑は水を忌（洩気）とし、調候は水で冷ます。両論として残す。
    useful = analyze_structure(Pillars4(year="丙午", month="甲午", day="庚午", hour="丙戌"))["useful_god_analysis"]
    assert "水" in useful["methods"][0]["unfavorable_elements"]  # 扶抑単独の忌方向
    assert "調候候補の水と扶抑の忌方向が食い違う" in useful["conflicting_rules"]
    rows = {r["element"]: r for r in useful["method_comparison"]["elements"]}
    assert rows["水"]["status"] == "conflict" and rows["水"]["note"] == "調候が支持、扶抑は忌方向"
    # 丁日・子月の身弱候補：調候の火は扶抑の喜と一致する。
    winter = analyze_structure(Pillars4(year="庚申", month="庚子", day="丁酉", hour="庚戌"))["useful_god_analysis"]
    assert {r["element"]: r["status"] for r in winter["method_comparison"]["elements"]}["火"] == "agreement"


@pytest.mark.parametrize("pillars, useful, favorable, basis_word", [
    # 甲日・申月・身弱：扶抑の水が調候とも一致。土（通関）は別の見方として併記。
    (("丙辰", "丙申", "甲午", "甲戌"), "水", ["木"], "調候とも一致"),
    # 庚日・午月・身弱：酷暑のため調候の水を優先し、扶抑の土を別の見方にする。
    (("丙午", "甲午", "庚午", "丙戌"), "水", ["土", "金"], "調候を優先"),
    # 丁日・子月：厳寒のため調候の火。扶抑の喜とも一致する。
    (("庚申", "庚子", "丁酉", "庚戌"), "火", ["木"], "調候を優先"),
])
def test_useful_god_is_selected_with_stated_general_method(pillars, useful, favorable, basis_word):
    analysis = analyze_structure(Pillars4(*pillars))["useful_god_analysis"]
    selection = analysis["useful_god_selection"]
    assert list(analysis)[0] == "useful_god_selection"  # AIが最初に読む位置
    assert selection["status"] == "selected" and selection["useful_god"] == useful
    assert selection["favorable_elements"] == favorable
    assert useful not in selection["unfavorable_elements"]
    assert set(selection["favorable_elements"]).isdisjoint(selection["unfavorable_elements"])
    assert basis_word in selection["basis"][0]
    assert "流派" in selection["school_note"] and "調候" in selection["method_label"]
    assert analysis["favorable_elements"] == selection["favorable_elements"]


def test_selection_lists_other_school_views_as_alternatives():
    selection = analyze_structure(Pillars4(year="丙辰", month="丙申", day="甲午", hour="甲戌"))["useful_god_analysis"]["useful_god_selection"]
    assert [a["element"] for a in selection["alternatives"]] == ["土"]
    assert "通関" in selection["alternatives"][0]["view"]
    summer = analyze_structure(Pillars4(year="丙午", month="甲午", day="庚午", hour="丙戌"))["useful_god_analysis"]["useful_god_selection"]
    assert summer["alternatives"][0] == {"element": "土", "view": "扶抑（日主の強弱の調整）を優先する見方"}


def test_unknown_hour_still_selects_from_three_pillars_with_condition_note():
    selection = analyze_structure(Pillars4(year="丙辰", month="丙申", day="甲午", hour="甲戌"),
                                  time_reliable=False)["useful_god_analysis"]["useful_god_selection"]
    assert selection["useful_god"] == "水"
    assert any("時刻が分かると変わる場合がある" in n for n in selection["notes"])


def test_follow_pattern_uses_dominant_element_and_its_feeder():
    selection = analyze_structure(Pillars4(year="壬子", month="壬子", day="丙子", hour="壬辰"))["useful_god_analysis"]["useful_god_selection"]
    assert selection["pattern_view"] == "follow_pattern" and selection["useful_god"] == "水"
    assert selection["favorable_elements"] == ["金"]
    assert selection["alternatives"] == [{"element": "木", "view": "通常の格として日主を助ける印を用いる見方"}]


def test_every_month_and_day_master_gets_one_useful_god():
    from services.shichusuimei_calc import KANSHI_60
    months = [k for k in KANSHI_60 if k[0] in "甲丙戊庚壬"][:12]
    for day in ("甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉"):
        for month in months:
            selection = analyze_structure(Pillars4(year="甲子", month=month, day=day, hour="甲子"))["useful_god_analysis"]["useful_god_selection"]
            assert selection["useful_god"] in ("木", "火", "土", "金", "水")
            assert selection["basis"]
