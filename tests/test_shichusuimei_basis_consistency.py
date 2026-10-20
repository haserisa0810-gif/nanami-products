"""Candidate labels must survive generated rationale; fictional inputs only."""
import pytest
from services.shichusuimei_calc import Pillars4
from services.shichusuimei_structure import analyze_structure, _select_useful_god


@pytest.mark.parametrize("ratio", [.3999, .4, .4749, .475, .55, .5501])
@pytest.mark.parametrize("route", ["agreement", "officer", "output", "wealth", "resource", "peer"])
def test_regular_rationale_keeps_candidate_or_middle_status(ratio, route):
    label = "weak_candidate" if ratio < .4 else "strong_candidate" if ratio > .55 else "balanced_candidate"
    weak = label == "weak_candidate" or (label == "balanced_candidate" and ratio < .475)
    support = dict(peer_element="木", support_ratio=ratio, label=label,
                   special_pattern_review_required=False, hour_excluded=False)
    totals = dict(木=2, 火=1, 土=1, 金=1, 水=1)
    groups = {g: {"score": 1} for g in ("比劫", "印", "財", "官殺", "食傷")}
    heavy = {"officer": "官殺", "output": "食傷", "wealth": "財", "resource": "印", "peer": "比劫"}
    if route in heavy:
        groups[heavy[route]]["score"] = 3
    climate = dict(needs=[], season="仲春", climate_note="温和")
    mediation = [dict(element="水" if weak else "火", source="金", target="木")] if route == "agreement" else []
    selection = _select_useful_god(support, totals, groups, climate, mediation)
    basis = " ".join(selection["basis"])
    if label == "balanced_candidate":
        assert "強弱は中間" in basis and "扶抑の選択上" in basis
        assert ("弱い側として扱う" if weak else "強い側として扱う") in basis
        assert "日主が弱い" not in basis and "日主が強い" not in basis
    else:
        assert "候補" in basis and "この方式では" in basis
    assert selection["status"] == "selected"
    assert selection["method"] == "general_fuyi_with_climate_priority_v1"
    assert selection["useful_god"] not in selection["unfavorable_elements"]
    assert set(selection["favorable_elements"]).isdisjoint(selection["unfavorable_elements"])


def test_reported_middle_chart_keeps_middle_in_reason_and_preserves_selection():
    result = analyze_structure(Pillars4(year="乙丑", month="甲申", day="丁未", hour="乙巳"))
    support = result["day_master_support"]
    selection = result["useful_god_analysis"]["useful_god_selection"]
    assert support["label"] == "balanced_candidate" and support["support_ratio"] == .4459
    assert "強弱は中間" in selection["basis"][0]
    assert "日主が弱いため" not in selection["basis"][0]
    assert selection["useful_god"] == "火"
    assert selection["favorable_elements"] == ["木"]
    assert selection["unfavorable_elements"] == ["土", "金", "水"]


def test_reported_weak_chart_reason_preserves_candidate():
    result = analyze_structure(Pillars4(year="乙丑", month="甲申", day="甲午", hour="己巳"))
    assert result["day_master_support"]["label"] == "weak_candidate"
    selection = result["useful_god_analysis"]["useful_god_selection"]
    assert "弱い側の候補" in selection["basis"][0]
    assert selection["useful_god"] == "水"
    assert selection["favorable_elements"] == ["木"]
    assert selection["unfavorable_elements"] == ["火", "土", "金"]


@pytest.mark.parametrize("pillars,view", [
    (("壬子", "壬子", "丙子", "壬辰"), "follow_pattern"),
    (("乙卯", "乙卯", "甲子", "乙卯"), "dominant_pattern"),
])
def test_special_pattern_review_remains_a_candidate_in_reason(pillars, view):
    result = analyze_structure(Pillars4(*pillars))
    assert result["day_master_support"]["special_pattern_review_required"]
    useful = result["useful_god_analysis"]
    selection = useful["useful_god_selection"]
    assert selection["pattern_view"] == view
    assert "候補" in selection["basis"][0]
    assert useful["methods"][0]["status"] == "held_for_review"
    assert selection["status"] == "selected" and selection["alternatives"]
