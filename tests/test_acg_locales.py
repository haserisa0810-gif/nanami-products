from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from routes import app
from services.acg_locales import ACG_UI
from services.prompt_builder import build_chart_companion_prompt, build_prompt


client = TestClient(app)


@pytest.mark.parametrize(
    ("lang", "heading", "search_label"),
    [
        ("ja", "ACG 天空線マップ", "地点検索"),
        ("en", "ACG Sky-Line Map", "Place search"),
        ("es", "Mapa de astrocartografía ACG", "Buscar lugar"),
        ("de", "ACG-Astrokartografie-Karte", "Ortssuche"),
    ],
)
def test_public_acg_page_is_localized(lang: str, heading: str, search_label: str) -> None:
    response = client.get(
        f"/acg?lang={lang}&utm_source=chatgpt.com&load=%2Fchart%2Fsample.yaml"
    )
    assert response.status_code == 200
    assert f'<html lang="{lang}">' in response.text
    assert heading in response.text
    assert search_label in response.text
    assert "Español" not in response.text  # compact switch uses language codes
    assert "?utm_source=chatgpt.com&amp;load=" in response.text
    assert "%2Fchart%2Fsample.yaml" in response.text


@pytest.mark.parametrize(
    ("lang", "language_name"),
    [("en", "English"), ("es", "Spanish"), ("de", "German")],
)
def test_acg_export_requests_the_selected_output_language(
    lang: str, language_name: str,
) -> None:
    response = client.get(f"/acg?lang={lang}")
    assert response.status_code == 200
    assert f'"output_language": "{language_name}"' in response.text
    assert '"  requested_output_language: " + yamlString(UI.output_language)' in response.text


@pytest.mark.parametrize("lang", ["es", "de"])
def test_acg_interpretation_catalogues_match_english_keys(lang: str) -> None:
    root = Path("static")
    english = json.loads((root / "acg_interpretations_en.json").read_text(encoding="utf-8"))
    localized = json.loads((root / f"acg_interpretations_{lang}.json").read_text(encoding="utf-8"))
    assert set(localized) == set(english)
    assert all(localized[key]["meaning"] for key in localized)


@pytest.mark.parametrize("lang", ["en", "es", "de"])
def test_consultation_and_reading_prompts_open_acg_in_selected_language(lang: str) -> None:
    expected_url = (
        f"https://chart.nanami-astro.com/acg?lang={lang}&utm_source=chatgpt.com"
    )
    companion = build_chart_companion_prompt(lang=lang)
    reading = build_prompt(include_transit=True, lang=lang)
    assert expected_url in companion
    assert expected_url in reading
    assert "以下のYAML" not in companion


def test_all_acg_locale_catalogues_have_the_same_keys() -> None:
    expected = set(ACG_UI["ja"])
    assert set(ACG_UI) == {"ja", "en", "es", "de"}
    for lang in ("en", "es", "de"):
        assert set(ACG_UI[lang]) == expected
