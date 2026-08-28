from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from unittest.mock import patch

import yaml

import pytest

from services.planner_ai import (
    _strip_japanese_display_fields,
    build_daily_ai_prompt,
    get_planner_ai_ui,
)


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "demo" / "chief_editor_neko.yaml"


@pytest.mark.parametrize(
    ("lang", "timezone", "instruction"),
    [
        ("ja", "Asia/Tokyo", "再計算せずに読み解いてください"),
        ("en", "UTC", "without recalculating it"),
        ("es", "UTC", "sin volver a calcularlos"),
        ("de", "UTC", "ohne sie neu zu berechnen"),
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


@pytest.mark.parametrize(
    ("lang", "title", "copy_button"),
    [
        ("ja", "この日の星をAIで読む", "AI用プロンプトをコピー"),
        ("en", "Read this day with AI", "Copy AI prompt"),
        ("es", "Interpreta este día con IA", "Copiar prompt para IA"),
        ("de", "Diesen Tag mit KI deuten", "KI-Prompt kopieren"),
    ],
)
def test_daily_ai_ui_is_localized(lang: str, title: str, copy_button: str) -> None:
    ui = get_planner_ai_ui(lang)
    assert ui["title"] == title
    assert ui["copy_button"] == copy_button


@pytest.mark.parametrize("lang", ["en", "es", "de"])
def test_non_japanese_daily_prompt_hides_japanese_display_fields(lang: str) -> None:
    prompt = build_daily_ai_prompt(
        chart_yaml=FIXTURE.read_text(encoding="utf-8"),
        target_date=date(2026, 8, 1),
        lang=lang,
    )

    assert "sign_ja:" not in prompt
    assert re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", prompt) is None


def test_japanese_daily_prompt_keeps_japanese_display_fields() -> None:
    prompt = build_daily_ai_prompt(
        chart_yaml=FIXTURE.read_text(encoding="utf-8"),
        target_date=date(2026, 8, 1),
        lang="ja",
    )

    assert "sign_ja:" in prompt
    assert "魚座" in prompt


def test_japanese_field_filter_does_not_mutate_source_data() -> None:
    source = {
        "body": {"name": "Sun", "sign_ja": "魚座", "nested": [{"label_ja": "太陽", "degree": 3.2}]},
    }
    snapshot = yaml.safe_load(yaml.safe_dump(source, allow_unicode=True))

    filtered = _strip_japanese_display_fields(source)

    assert source == snapshot
    assert filtered == {"body": {"name": "Sun", "nested": [{"degree": 3.2}]}}


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
