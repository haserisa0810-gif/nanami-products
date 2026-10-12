"""Regressions found while preparing the independent Claude review."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.shichusuimei_calc import _add_calendar_months, calc_shichusuimei_from_payload

TZ = ZoneInfo("Asia/Tokyo")


def _calc(month: int, *, as_of: datetime, years: int = 1):
    return calc_shichusuimei_from_payload(
        dict(year=1990, month=month, day=15, hour=8, minute=30, gender="female"),
        as_of=as_of, annual_years=years,
    )["normalized_data"]


def test_current_daiun_is_not_selected_before_approximate_calendar_start():
    data = _calc(11, as_of=datetime(1993, 1, 15, tzinfo=TZ))
    assert data["daiun"]["start_age"] == {"years": 2, "months": 5}
    # 1990-11-15 + 2 years 5 months = approximately 1993-04-15.
    assert data["annual_fortune"]["current_daiun"] is None
    assert data["annual_fortune"]["structural_analysis"]["concurrent_daiun"] is None


def test_current_daiun_is_selected_after_approximate_calendar_start():
    data = _calc(1, as_of=datetime(1996, 10, 1, tzinfo=TZ))
    assert data["daiun"]["start_age"] == {"years": 6, "months": 8}
    # 1990-01-15 + 6 years 8 months = approximately 1996-09-15.
    assert data["annual_fortune"]["current_daiun"] is not None
    assert data["annual_fortune"]["current_daiun"]["index"] == 1
    assert 6.7 < data["annual_fortune"]["current_daiun"]["current_age_approx"] < 6.8


def test_late_birth_does_not_activate_daiun_a_year_early_in_forecast():
    data = _calc(11, as_of=datetime(1992, 7, 1, tzinfo=TZ), years=2)
    forecasts = data["annual_forecasts"]["items"]
    assert forecasts[0]["effective_year"] == 1992
    assert forecasts[0]["daiun_contexts"] == []
    assert forecasts[1]["effective_year"] == 1993
    assert forecasts[1]["daiun_contexts"][0]["index"] == 1


def test_reported_start_year_matches_birth_plus_start_age():
    data = _calc(5, as_of=datetime(2026, 10, 7, tzinfo=TZ))
    assert data["daiun"]["start_age"] == {"years": 3, "months": 1}
    # 1990-05-15 + 3 years 1 month = approximately 1993-06-15.
    assert data["daiun"]["items"][0]["approx_start_year"] == 1993


def _participants(relation):
    for key in ("left", "right"):
        if key in relation:
            yield relation[key]["name"]
    for item in relation.get("pillars", []):
        yield item["name"]


@pytest.mark.parametrize("accuracy", ["unknown", "approximate"])
def test_uncertain_hour_is_excluded_from_legacy_natal_and_annual_relations(accuracy):
    data = calc_shichusuimei_from_payload(
        dict(year=1990, month=5, day=15, hour=12, minute=0, gender="female", birth_time_accuracy=accuracy),
        as_of=datetime(2026, 10, 7, tzinfo=TZ), annual_years=1,
    )["normalized_data"]
    natal = data["interactions"]
    annual = data["annual_fortune"]["relations"]
    assert natal["time_basis"] == "three_pillars_hour_excluded"
    assert data["annual_fortune"]["natal_time_basis"] == "three_pillars_hour_excluded"
    assert data["time_sensitive_reference"]["valid_for_assertive_interpretation"] is False
    for section in (natal, annual):
        for values in section.values():
            if isinstance(values, list):
                assert all("hour" not in set(_participants(r)) for r in values)


def test_exact_hour_remains_available_in_relations():
    data = calc_shichusuimei_from_payload(
        dict(year=1990, month=5, day=15, hour=12, minute=0, gender="female"),
        as_of=datetime(2026, 10, 7, tzinfo=TZ), annual_years=1,
    )["normalized_data"]
    assert "time_sensitive_reference" not in data
    assert any("hour" in set(_participants(r)) for r in data["interactions"]["branch_relations"])


def test_all_shichu_prompt_variants_share_structural_and_provisional_rules():
    from services.prompt_builder import (
        SHICHUSUIMEI_CHART_COMPANION_PROMPT, SHICHUSUIMEI_STRUCTURE_GUIDANCE, build_prompt,
        ensure_shichusuimei_structure_guidance,
    )
    from services.yaml_exporter import SHICHU_FORTUNE_CYCLES_ADDON_PROMPT
    prompts = [build_prompt(include_shichusuimei=True, include_asteroids=a, include_transit=t)
               for a in (False, True) for t in (False, True)]
    prompts.extend([SHICHUSUIMEI_CHART_COMPANION_PROMPT, SHICHU_FORTUNE_CYCLES_ADDON_PROMPT])
    for prompt in prompts:
        assert prompt.count(SHICHUSUIMEI_STRUCTURE_GUIDANCE) == 1
        assert "旧五行集計・身強スコア" in prompt
        assert "daiun_boundary_in_window" in prompt
        assert "evidence_id" in prompt
        assert ensure_shichusuimei_structure_guidance(prompt) == prompt
    assert SHICHUSUIMEI_STRUCTURE_GUIDANCE not in build_prompt()


def test_calendar_arithmetic_clamps_leap_day_without_compounding_rounding():
    birth = datetime(2000, 2, 29, 14, 30, tzinfo=TZ)
    assert _add_calendar_months(birth, 12) == datetime(2001, 2, 28, 14, 30, tzinfo=TZ)
    assert _add_calendar_months(birth, 13) == datetime(2001, 3, 29, 14, 30, tzinfo=TZ)


def test_daiun_boundary_uses_half_open_interval_and_forecast_has_both_cycles():
    data = _calc(5, as_of=datetime(2026, 10, 7, tzinfo=TZ))
    first, second = data["daiun"]["items"][:2]
    boundary = datetime.fromisoformat(second["approx_start_at"])
    assert first["approx_end_at"] == second["approx_start_at"]
    at_boundary = _calc(5, as_of=boundary)
    assert at_boundary["annual_fortune"]["current_daiun"]["index"] == 2
    forecast = at_boundary["annual_forecasts"]["items"][0]
    assert forecast["daiun_boundary_in_window"] is True
    contexts = forecast["daiun_contexts"]
    assert [c["index"] for c in contexts] == [1, 2]
    assert contexts[0]["overlap_end_approx"] == contexts[1]["overlap_start_approx"]
