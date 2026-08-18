from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

import pytest

from services.planner_ai import build_daily_ai_prompt


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "demo" / "chief_editor_neko.yaml"


@pytest.mark.parametrize(
    ("lang", "timezone", "instruction"),
    [
        ("ja", "Asia/Tokyo", "再計算せずに読み解いてください"),
        ("en", "UTC", "without recalculating it"),
    ],
)
def test_daily_ai_prompt_matches_planner_language_and_timezone(
    lang: str, timezone: str, instruction: str,
) -> None:
    prompt = build_daily_ai_prompt(
        chart_yaml=FIXTURE.read_text(encoding="utf-8"),
        target_date=date(2026, 7, 1),
        lang=lang,
    )

    assert instruction in prompt
    assert "target_date: '2026-07-01'" in prompt
    assert f"timezone: {timezone}" in prompt
    assert "natal_bodies:" in prompt
    assert "transiting_bodies:" in prompt


def test_daily_ai_uses_stored_natal_positions_without_recalculation() -> None:
    chart_yaml = FIXTURE.read_text(encoding="utf-8")
    source = yaml.safe_load(chart_yaml)
    stored_bodies = source["systems"]["western"]["natal"]["bodies"]
    fake_transit = {
        "daily": [{
            "date": "2026-07-01", "time": "00:00", "transiting_bodies": {},
            "natal_aspects": [], "moon_timepoints": [],
        }]
    }
    with patch("services.planner_ai.build_transit_for_profile", return_value=fake_transit) as build:
        prompt = build_daily_ai_prompt(
            chart_yaml=chart_yaml, target_date=date(2026, 7, 1), lang="en")

    assert build.call_args.kwargs["natal_bodies"] == stored_bodies
    assert str(stored_bodies["Sun"]["absolute_longitude"]) in prompt
