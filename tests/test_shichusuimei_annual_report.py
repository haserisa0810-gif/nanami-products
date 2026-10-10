from copy import deepcopy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import yaml

from services import shichusuimei_calc as core
from services.shichusuimei_annual_report import (
    _counts, _item, _scope, _project_periods, build_annual_fortune_report, build_annual_fortune_yaml,
)

TZ = ZoneInfo("Asia/Tokyo")


@pytest.fixture(scope="module")
def real_doc():
    result = core.calc_shichusuimei_from_payload(
        dict(year=1990, month=5, day=15, hour=8, minute=30, gender="female"),
        as_of=datetime(2026, 10, 7, tzinfo=timezone.utc), annual_years=1,
    )
    return {"meta": {"chart_id": "synthetic-test-chart"}, "systems": {"shichusuimei": result}}


def synthetic_doc(pillars=None, *, luck="庚子", birth="2020-05-15T08:30:00+09:00"):
    p = core.Pillars4(**(pillars or dict(year="甲子", month="己丑", day="丙午", hour="辛卯")))
    periods = _project_periods(datetime.fromisoformat(birth), luck, "forward", 0, 0, 10)
    return {"meta": {"chart_id": "synthetic"}, "systems": {"shichusuimei": {
        "engine_version": "test", "input": {"assumptions": {"birth_time_accuracy": "exact"}},
        "normalized_data": {"pillars": {name: core._pillar_dict(k) for name, k in vars(p).items()},
                            "five_elements": core._five_elements_counts(p), "kubo": core.kubo_for_pillars(p),
                            "daiun": {"items": periods, "start_age": {"years": 0, "months": 0},
                                      "direction": "forward", "debug": {"birth_local": birth}}},
    }}}


def report(doc, year=2026):
    return build_annual_fortune_report(doc, year)["annual_fortune_report"]


@pytest.mark.parametrize("year,kanshi", [(1800, "庚申"), (1984, "甲子"), (2026, "丙午"), (2027, "丁未"), (2399, "己未")])
def test_arbitrary_year_and_boundary_window(real_doc, year, kanshi):
    r = report(real_doc, year)
    assert r["annual"]["kanshi"] == kanshi
    assert r["annual"]["effective_year"] == year
    assert r["annual"]["ten_god_to_day_master"] == core.ten_god(r["natal_reference"]["day_master"], kanshi[0])
    assert r["annual"]["twelve_fortune_to_day_master"] == core.twelve_fortune(r["natal_reference"]["day_master"], kanshi[1])
    start, end = [datetime.fromisoformat(r["annual"][key]) for key in ("period_start", "period_end")]
    assert start == core._lichun_utc_for_year(year, "Asia/Tokyo")
    assert end == core._lichun_utc_for_year(year + 1, "Asia/Tokyo")
    assert r["annual"]["period_end_exclusive"] is True


@pytest.mark.parametrize("year", [1799, 2400, 2026.5, "2026", True])
def test_year_range_and_type(real_doc, year):
    with pytest.raises(ValueError):
        report(real_doc, year)


def test_selected_annual_window_matches_current_annual_before_and_after_lichun(real_doc):
    shichu = real_doc["systems"]["shichusuimei"]
    nd = shichu["normalized_data"]
    p4 = core.Pillars4(**shichu["pillars"])
    boundary = core._lichun_utc_for_year(2026, "Asia/Tokyo")
    before = core._annual_fortune(p4, nd["daiun"], birth_year=1990, current_dt=boundary - timedelta(seconds=1), tz_name="Asia/Tokyo")
    after = core._annual_fortune(p4, nd["daiun"], birth_year=1990, current_dt=boundary + timedelta(seconds=1), tz_name="Asia/Tokyo")
    assert before["kanshi"] == report(real_doc, 2025)["annual"]["kanshi"]
    assert after["kanshi"] == report(real_doc, 2026)["annual"]["kanshi"]


def test_transition_year_keeps_both_cycles_and_approximation(real_doc):
    r = report(real_doc, 2023)
    assert r["daiun"]["boundary_in_selected_year"] is True
    contexts = r["daiun"]["contexts"]
    assert [c["index"] for c in contexts] == [3, 4]
    assert contexts[0]["overlap_end_approx"] == contexts[1]["overlap_start_approx"]
    for c in contexts:
        assert c["boundary_provisional"] is True
        original = real_doc["systems"]["shichusuimei"]["normalized_data"]["daiun"]["items"][c["index"] - 1]
        for key in ("kanshi", "age_from", "age_to", "approx_start_year", "approx_start_at", "approx_end_at"):
            assert c[key] == original[key]


def test_before_first_cycle_and_extension_past_ten_cycles(real_doc):
    assert report(real_doc, 1992)["daiun"]["contexts"] == []
    assert report(real_doc, 1992)["daiun"]["status"] == "before_first_daiun"
    assert report(real_doc, 2200)["daiun"]["contexts"][0]["index"] > 10
    assert len(real_doc["systems"]["shichusuimei"]["normalized_data"]["daiun"]["items"]) == 10


def test_cross_scope_clashes_and_stem_combinations():
    r = report(synthetic_doc())
    for scope in ("natal_annual", "natal_daiun", "daiun_annual"):
        assert any(rel["type"] == "clash" for rel in r["interactions"][scope])
    assert any(rel["type"] == "stem_combination" for rel in r["interactions"]["natal_annual"])
    for scope, relations in r["interactions"].items():
        for rel in relations:
            if "left" in rel:
                names = {rel["left"]["name"], rel["right"]["name"]}
                assert names & {"annual", "daiun"}
                if scope == "daiun_annual":
                    assert names == {"annual", "daiun"}
            if scope != "natal_annual":
                assert rel["daiun_index"] == 1


@pytest.mark.parametrize("left,right,kind", [("壬辰", "甲辰", "self_punishment"), ("甲子", "己丑", "six_harmony"),
                                            ("甲子", "辛未", "harm"), ("甲子", "乙卯", "punishment"),
                                            ("甲子", "己酉", "destruction")])
def test_supported_pair_relations(left, right, kind):
    assert any(r["type"] == kind for r in _scope([_item("day", left), _item("annual", right)], {"natal", "annual"}))


def test_triad_partial_full_and_repeated_branch_provenance():
    annual, luck = _item("annual", "甲子"), _item("daiun", "壬申")
    partial = _scope([_item("day", "壬申"), annual], {"natal", "annual"})
    assert any(r["type"] == "triad" and r["level"] == "partial" for r in partial)
    natal = [_item("day", "壬辰"), _item("hour", "甲辰")]
    combined = _scope(natal + [luck, annual], {"natal", "daiun", "annual"})
    assert len(combined) == 1
    assert combined[0]["type"] == "triad" and combined[0]["level"] == "full"
    assert len(combined[0]["participant_sets"]) == 2
    assert all(len({p["branch"] for p in witness}) == 3 for witness in combined[0]["participant_sets"])
    assert not _scope([_item("day", "壬申"), luck, annual], {"natal", "daiun", "annual"})
    assert combined[0]["element_change_applied"] is False


def test_three_punishments_are_in_combined_scope():
    relations = _scope([_item("day", "甲寅"), _item("daiun", "己巳"), _item("annual", "壬申")], {"natal", "daiun", "annual"})
    assert any(r["type"] == "three_punishment" and r["level"] == "full" for r in relations)


def test_kubo_hit_and_five_element_reference():
    doc = synthetic_doc(dict(year="甲子", month="己丑", day="甲子", hour="辛卯"))
    r = report(doc, 2030)  # 庚戌: 甲子旬 has 戌亥空亡.
    assert r["kubo"]["empty_branches"] == ["戌", "亥"]
    assert r["kubo"]["annual_hit"] is True
    assert r["interpretation_flags"]["automatic_good_bad_judgment"] is False
    assert r["five_elements"]["natal"] == doc["systems"]["shichusuimei"]["normalized_data"]["five_elements"]
    assert sum(r["five_elements"]["annual"]["visible"].values()) == 2
    assert sum(r["five_elements"]["combined_reference"][0]["visible"].values()) == 12
    p4 = core.Pillars4(year="甲子", month="己丑", day="甲子", hour="辛卯")
    assert _counts(core._pillar_items(p4)) == core._five_elements_counts(p4)


@pytest.mark.parametrize("accuracy", ["unknown", "approximate"])
def test_uncertain_hour_is_excluded_everywhere_and_counts_marked(accuracy):
    doc = synthetic_doc(dict(year="甲子", month="己丑", day="甲子", hour="壬戌"))
    doc["systems"]["shichusuimei"]["input"]["assumptions"]["birth_time_accuracy"] = accuracy
    r = report(doc)
    assert "hour" not in r["natal_reference"]["pillars"]
    assert "hour" not in r["kubo"]["natal_hits"]
    assert r["five_elements"]["natal_reference_only"] is True
    assert sum(r["five_elements"]["combined_reference"][0]["visible"].values()) == 10
    assert all("'name': 'hour'" not in str(v) for v in r["interactions"].values())


def test_old_yaml_without_calendar_dates_uses_saved_start_age(real_doc):
    doc = deepcopy(real_doc)
    shichu = doc["systems"]["shichusuimei"]
    del shichu["normalized_data"]["daiun"]["debug"]["birth_local"]
    for item in shichu["normalized_data"]["daiun"]["items"]:
        del item["approx_start_at"], item["approx_end_at"]
    assert report(doc, 2023)["daiun"]["contexts"] == report(real_doc, 2023)["daiun"]["contexts"]


def test_yaml_round_trip_no_personal_info_or_base_mutation(real_doc):
    original = deepcopy(real_doc)
    original["input"] = {"title": "PRIVATE-NAME", "birth_place": "PRIVATE-ADDRESS"}
    snapshot = deepcopy(original)
    text = build_annual_fortune_yaml(original, 2027)
    assert yaml.safe_load(text) == build_annual_fortune_report(original, 2027)
    assert "PRIVATE-" not in text and "birth_local:" not in text
    assert original == snapshot
    assert report(original)["base_chart_id"] == "synthetic-test-chart"
    assert report(original)["base_chart_usage"]["full_yaml_required"] is True


