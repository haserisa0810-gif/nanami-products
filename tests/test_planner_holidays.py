from __future__ import annotations

from datetime import date

import pytest

from services.planner.planner_holidays import holidays_for_year, scope_note


def test_no_country_preserves_existing_planner_behavior() -> None:
    assert holidays_for_year(None, 2027, "es") == {}


@pytest.mark.parametrize(
    ("country", "day", "label"),
    [
        ("ES", date(2027, 10, 12), "Fiesta Nacional de España"),
        ("MX", date(2027, 3, 15), "Natalicio de Benito Juárez"),
        ("CO", date(2027, 5, 10), "Ascensión del Señor"),
        ("AR", date(2027, 2, 8), "Lunes de Carnaval"),
        ("CL", date(2027, 9, 18), "Independencia Nacional"),
    ],
)
def test_initial_spanish_market_nationwide_holidays(country: str, day: date, label: str) -> None:
    assert holidays_for_year(country, 2027, "es")[day] == label


def test_spain_excludes_regional_holidays_and_discloses_scope() -> None:
    days = holidays_for_year("ES", 2027, "es")
    assert date(2027, 9, 11) not in days  # Catalonia
    assert "no incluye" in scope_note("ES", "es")
    assert "cambios oficiales" in scope_note("ES", "es")


def test_chile_includes_nationwide_conditional_holidays() -> None:
    holidays_2027 = holidays_for_year("CL", 2027, "es")
    assert holidays_2027[date(2027, 9, 17)] == "Feriado adicional de Fiestas Patrias"
    assert holidays_2027[date(2027, 10, 31)] == "Día de las Iglesias Evangélicas"

    holidays_2028 = holidays_for_year("CL", 2028, "es")
    assert holidays_2028[date(2028, 10, 27)] == "Día de las Iglesias Evangélicas"


def test_chile_rejects_unverified_year_instead_of_silently_omitting_solstice() -> None:
    with pytest.raises(ValueError, match="verified only for 2026-2028"):
        holidays_for_year("CL", 2029, "es")


def test_mexico_includes_2027_federal_election_rest_day() -> None:
    assert holidays_for_year("MX", 2027, "es")[date(2027, 6, 6)] == (
        "Jornada Electoral Federal"
    )


def test_unsupported_country_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported holiday country"):
        holidays_for_year("US", 2027, "es")
