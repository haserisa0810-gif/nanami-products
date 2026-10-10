"""Nationwide public holidays for the planner's initial country selector.

Only country-wide holidays are included.  Subdivision and municipal holidays
are deliberately out of scope so a country selection never implies that a
buyer's local calendar is complete.
"""

from __future__ import annotations

from datetime import date, timedelta


SUPPORTED_COUNTRIES = ("ES", "MX", "CO", "AR", "CL")
COUNTRY_NAMES = {
    "ES": {"en": "Spain", "es": "España"},
    "MX": {"en": "Mexico", "es": "México"},
    "CO": {"en": "Colombia", "es": "Colombia"},
    "AR": {"en": "Argentina", "es": "Argentina"},
    "CL": {"en": "Chile", "es": "Chile"},
}


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _next_monday(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _argentina_transfer(day: date) -> date:
    if day.weekday() in (1, 2):  # Tue/Wed -> previous Monday
        return day - timedelta(days=day.weekday())
    if day.weekday() in (3, 4):  # Thu/Fri -> following Monday
        return day + timedelta(days=7 - day.weekday())
    return day


def _chile_reformation_day(year: int) -> date:
    """Chile's 31 October holiday, including its statutory Friday move."""
    day = date(year, 10, 31)
    if day.weekday() == 1:  # Tuesday -> preceding Friday
        return day - timedelta(days=4)
    if day.weekday() == 2:  # Wednesday -> following Friday
        return day + timedelta(days=2)
    return day


def _chile_extra_september_holiday(year: int) -> date | None:
    """Return the additional nationwide September holiday when required."""
    independence = date(year, 9, 18)
    army_day = date(year, 9, 19)
    if independence.weekday() == 5 and army_day.weekday() == 6:
        return date(year, 9, 17)
    if independence.weekday() == 1 and army_day.weekday() == 2:
        return date(year, 9, 17)
    if independence.weekday() == 2 and army_day.weekday() == 3:
        return date(year, 9, 20)
    return None


def _labels(lang: str, en: str, es: str) -> str:
    return es if lang == "es" else en


def holidays_for_year(country: str | None, year: int, lang: str = "en") -> dict[date, str]:
    code = (country or "").strip().upper()
    if not code:
        return {}
    if code not in SUPPORTED_COUNTRIES:
        raise ValueError(f"unsupported holiday country: {country!r}")
    easter = _easter(year)
    rows: list[tuple[date, str, str]] = []

    if code == "ES":
        rows = [
            (date(year, 1, 1), "New Year's Day", "Año Nuevo"),
            (date(year, 1, 6), "Epiphany", "Epifanía del Señor"),
            (easter - timedelta(days=2), "Good Friday", "Viernes Santo"),
            (date(year, 5, 1), "Labour Day", "Fiesta del Trabajo"),
            (date(year, 8, 15), "Assumption", "Asunción de la Virgen"),
            (date(year, 10, 12), "National Day of Spain", "Fiesta Nacional de España"),
            (date(year, 11, 1), "All Saints' Day", "Todos los Santos"),
            (date(year, 12, 6), "Constitution Day", "Día de la Constitución"),
            (date(year, 12, 8), "Immaculate Conception", "Inmaculada Concepción"),
            (date(year, 12, 25), "Christmas Day", "Navidad"),
        ]
    elif code == "MX":
        rows = [
            (date(year, 1, 1), "New Year's Day", "Año Nuevo"),
            (_nth_weekday(year, 2, 0, 1), "Constitution Day", "Día de la Constitución"),
            (_nth_weekday(year, 3, 0, 3), "Benito Juárez's Birthday", "Natalicio de Benito Juárez"),
            (date(year, 5, 1), "Labour Day", "Día del Trabajo"),
            (date(year, 9, 16), "Independence Day", "Día de la Independencia"),
            (_nth_weekday(year, 11, 0, 3), "Revolution Day", "Día de la Revolución"),
            (date(year, 12, 25), "Christmas Day", "Navidad"),
        ]
        if (year - 2024) % 6 == 0:
            rows.append((date(year, 10, 1), "Presidential Transition Day", "Transmisión del Poder Ejecutivo Federal"))
        if (year - 2024) % 3 == 0:
            rows.append(
                (
                    _nth_weekday(year, 6, 6, 1),
                    "Federal Election Day",
                    "Jornada Electoral Federal",
                )
            )
    elif code == "CO":
        mondayized = [
            (date(year, 1, 6), "Epiphany", "Día de los Reyes Magos"),
            (date(year, 3, 19), "Saint Joseph's Day", "Día de San José"),
            (date(year, 6, 29), "Saints Peter and Paul", "San Pedro y San Pablo"),
            (date(year, 8, 15), "Assumption", "Asunción de la Virgen"),
            (date(year, 10, 12), "Columbus Day", "Día de la Raza"),
            (date(year, 11, 1), "All Saints' Day", "Todos los Santos"),
            (date(year, 11, 11), "Independence of Cartagena", "Independencia de Cartagena"),
        ]
        rows = [
            (date(year, 1, 1), "New Year's Day", "Año Nuevo"),
            (easter - timedelta(days=3), "Maundy Thursday", "Jueves Santo"),
            (easter - timedelta(days=2), "Good Friday", "Viernes Santo"),
            (date(year, 5, 1), "Labour Day", "Día del Trabajo"),
            (easter + timedelta(days=43), "Ascension Day", "Ascensión del Señor"),
            (easter + timedelta(days=64), "Corpus Christi", "Corpus Christi"),
            (easter + timedelta(days=71), "Sacred Heart", "Sagrado Corazón"),
            (date(year, 7, 20), "Independence Day", "Día de la Independencia"),
            (date(year, 8, 7), "Battle of Boyacá", "Batalla de Boyacá"),
            (date(year, 12, 8), "Immaculate Conception", "Inmaculada Concepción"),
            (date(year, 12, 25), "Christmas Day", "Navidad"),
        ] + [(_next_monday(d), en, es) for d, en, es in mondayized]
    elif code == "AR":
        rows = [
            (date(year, 1, 1), "New Year's Day", "Año Nuevo"),
            (easter - timedelta(days=48), "Carnival Monday", "Lunes de Carnaval"),
            (easter - timedelta(days=47), "Carnival Tuesday", "Martes de Carnaval"),
            (date(year, 3, 24), "Day of Remembrance for Truth and Justice", "Día Nacional de la Memoria por la Verdad y la Justicia"),
            (date(year, 4, 2), "Malvinas Day", "Día del Veterano y de los Caídos en la Guerra de Malvinas"),
            (easter - timedelta(days=2), "Good Friday", "Viernes Santo"),
            (date(year, 5, 1), "Labour Day", "Día del Trabajador"),
            (date(year, 5, 25), "May Revolution Day", "Día de la Revolución de Mayo"),
            (_argentina_transfer(date(year, 6, 17)), "Martín Miguel de Güemes Day", "Paso a la Inmortalidad del General Güemes"),
            (date(year, 6, 20), "Manuel Belgrano Day", "Paso a la Inmortalidad del General Belgrano"),
            (date(year, 7, 9), "Independence Day", "Día de la Independencia"),
            (_argentina_transfer(date(year, 8, 17)), "José de San Martín Day", "Paso a la Inmortalidad del General San Martín"),
            (_argentina_transfer(date(year, 10, 12)), "Cultural Diversity Day", "Día del Respeto a la Diversidad Cultural"),
            (_argentina_transfer(date(year, 11, 20)), "National Sovereignty Day", "Día de la Soberanía Nacional"),
            (date(year, 12, 8), "Immaculate Conception", "Inmaculada Concepción"),
            (date(year, 12, 25), "Christmas Day", "Navidad"),
        ]
    else:  # CL
        solstice = {
            2026: date(2026, 6, 21),
            2027: date(2027, 6, 21),
            2028: date(2028, 6, 20),
        }.get(year)
        if solstice is None:
            raise ValueError(
                "Chile holiday dates are currently verified only for 2026-2028"
            )
        rows = [
            (date(year, 1, 1), "New Year's Day", "Año Nuevo"),
            (easter - timedelta(days=2), "Good Friday", "Viernes Santo"),
            (easter - timedelta(days=1), "Holy Saturday", "Sábado Santo"),
            (date(year, 5, 1), "Labour Day", "Día Nacional del Trabajo"),
            (date(year, 5, 21), "Navy Day", "Día de las Glorias Navales"),
            (date(year, 7, 16), "Our Lady of Mount Carmel", "Día de la Virgen del Carmen"),
            (date(year, 8, 15), "Assumption", "Asunción de la Virgen"),
            (date(year, 9, 18), "Independence Day", "Independencia Nacional"),
            (date(year, 9, 19), "Army Day", "Día de las Glorias del Ejército"),
            (
                _chile_reformation_day(year),
                "Reformation Day",
                "Día de las Iglesias Evangélicas",
            ),
            (date(year, 11, 1), "All Saints' Day", "Día de Todos los Santos"),
            (date(year, 12, 8), "Immaculate Conception", "Inmaculada Concepción"),
            (date(year, 12, 25), "Christmas Day", "Navidad"),
        ]
        rows.append((solstice, "National Day of Indigenous Peoples", "Día Nacional de los Pueblos Indígenas"))
        extra_september = _chile_extra_september_holiday(year)
        if extra_september:
            rows.append((extra_september, "Additional National Holiday", "Feriado adicional de Fiestas Patrias"))
        if date(year, 1, 1).weekday() == 6:
            rows.append((date(year, 1, 2), "Additional New Year Holiday", "Feriado adicional de Año Nuevo"))
        peter_paul = date(year, 6, 29)
        rows.append((_argentina_transfer(peter_paul), "Saints Peter and Paul", "San Pedro y San Pablo"))
        encounter = date(year, 10, 12)
        rows.append((_argentina_transfer(encounter), "Encounter of Two Worlds", "Encuentro de Dos Mundos"))

    return {day: _labels(lang, en, es) for day, en, es in rows}


def country_name(country: str | None, lang: str = "en") -> str:
    code = (country or "").strip().upper()
    names = COUNTRY_NAMES.get(code)
    return names.get(lang, names["en"]) if names else ""


def scope_note(country: str | None, lang: str = "en") -> str:
    name = country_name(country, lang)
    if not name:
        return ""
    if lang == "es":
        return (
            f"Festivos nacionales de {name} según la normativa vigente; no incluye "
            "festivos autonómicos, estatales, provinciales o municipales, ni cambios "
            "oficiales o días extraordinarios anunciados posteriormente"
        )
    return (
        f"Nationwide public holidays for {name} under current law; regional, state, "
        "provincial, and local holidays, later official changes, and exceptional "
        "one-off days are not included"
    )
