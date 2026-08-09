from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from services.planner_ai import build_daily_ai_prompt


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "planner_personal_sample.yaml"


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
