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
    assert result["useful_god_analysis"]["definitive_useful_god"] is None
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


def test_extreme_or_unknown_chart_holds_fuyi_instead_of_fixing_useful_god():
    p = Pillars4(year="乙卯", month="乙卯", day="甲子", hour="乙卯")
    result = analyze_structure(p)
    assert result["day_master_support"]["special_pattern_review_required"]
    useful = result["useful_god_analysis"]
    assert useful["methods"][0]["status"] == "held_for_review"
    assert useful["favorable_elements"] == useful["unfavorable_elements"] == []
    assert useful["definitive_useful_god"] is None
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
