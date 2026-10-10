from __future__ import annotations

from datetime import date

import pytest

from services.planner import planner_i18n as i18n
from services.planner.generate_planner import Planner
from services.planner_export import SUPPORTED_LANGS


@pytest.mark.parametrize(
    ("lang", "title", "month", "weekday", "date_label"),
    [
        ("en", "Astrology Transit Planner", "September", "Tuesday", "September 01, 2026"),
        ("es", "Planificador de Tránsitos Astrológicos", "septiembre", "martes", "1 de septiembre de 2026"),
        ("de", "Astrologischer Transitplaner", "September", "Dienstag", "1. September 2026"),
        ("ja", "星のトランジット手帳", "9月", "火曜日", "2026年9月1日"),
    ],
)
def test_planner_calendar_and_ui_are_localized(
    lang: str, title: str, month: str, weekday: str, date_label: str,
) -> None:
    target = date(2026, 9, 1)
    assert i18n.S(lang, "planner_title") == title
    assert i18n.month_name(lang, 9) == month
    assert i18n.fmt_weekday(lang, target) == weekday
    assert i18n.fmt_full_date(lang, target) == date_label


@pytest.mark.parametrize("lang", ["en", "es", "de", "ja"])
def test_all_planner_locales_have_complete_string_catalogue(lang: str) -> None:
    assert lang in SUPPORTED_LANGS
    assert set(i18n.STR[lang]) == set(i18n.STR["en"])


def test_spanish_and_german_astrology_terms_are_localized() -> None:
    assert i18n.body_name("es", "Jupiter") == "Júpiter"
    assert i18n.sign_name("es", "Gemini") == "Géminis"
    assert i18n.phase_label("es", "Full") == "Luna llena"
    assert i18n.body_name("de", "Moon") == "Mond"
    assert i18n.sign_name("de", "Sagittarius") == "Schütze"
    assert i18n.phase_label("de", "New") == "Neumond"


def test_spanish_and_german_timeline_aspect_abbreviations_are_localized() -> None:
    window = {
        "transiting_body": "Jupiter",
        "aspect": "square",
        "natal_body": "Moon",
    }
    planner = Planner.__new__(Planner)
    planner.lang = "es"
    assert planner._gantt_label(window) == "Júpiter cuad. Luna"
    planner.lang = "de"
    assert planner._gantt_label(window) == "Jupiter Quadr. Mond"
