"""Calculate the tropical transit data used by the planner.

This script deliberately keeps astronomical calculation separate from PDF
layout. It requires PySwissEph (`swisseph`) and writes a stable JSON snapshot
that can be reviewed, versioned, and replaced by nanami-astro output later.

The period is a run of full calendar months (default: calendar year 2027) and
all event dates are assigned in the requested time zone. With --personal-yaml
a nanami-products YAML (natal + transit_long_term addon) supplies the personal
layer instead of the fictional sample profile.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "data" / "2027_transits.json"
PERSONAL_INPUT = ROOT / "data" / "personal_sample.json"

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

BODIES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
}

PLANET_ORDER = list(BODIES)
OUTER = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
STATION_BODIES = ["Mercury", "Venus", "Mars", *OUTER]
INGRESS_BODIES = ["Sun", "Mercury", "Venus", "Mars", *OUTER]
ASPECTS = {0: "Conjunction", 60: "Sextile", 90: "Square", 120: "Trine", 180: "Opposition"}
ASPECT_ANGLES = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED

# Peak refinement is limited to bodies Moshier can compute directly.
REFINABLE_TRANSITS = set(OUTER)


class Period:
    """Run of full calendar months with a display time zone."""

    def __init__(self, start_year: int, start_month: int, months: int, tz_name: str) -> None:
        self.tz_name = tz_name
        self.tz = timezone.utc if tz_name == "UTC" else ZoneInfo(tz_name)
        self.months: list[tuple[int, int]] = []
        year, month = start_year, start_month
        for _ in range(months):
            self.months.append((year, month))
            month += 1
            if month == 13:
                year, month = year + 1, 1
        self.start_date = date(start_year, start_month, 1)
        last_year, last_month = self.months[-1]
        self.end_date = date(last_year, last_month, calendar.monthrange(last_year, last_month)[1])

    def contains(self, value: date) -> bool:
        return self.start_date <= value <= self.end_date

    def local_date(self, dt_utc: datetime) -> date:
        return dt_utc.astimezone(self.tz).date()

    def local_time(self, dt_utc: datetime) -> str:
        return dt_utc.astimezone(self.tz).strftime("%H:%M")

    def local_noon_utc(self, day: date) -> datetime:
        return datetime(day.year, day.month, day.day, 12, tzinfo=self.tz).astimezone(timezone.utc)

    @property
    def label(self) -> str:
        if self.start_date.year == self.end_date.year:
            return str(self.start_date.year)
        return f"{self.start_date.year}-{self.end_date.year}"


PERIOD = Period(2027, 1, 12, "UTC")


def dt_to_jd(value: datetime) -> float:
    value = value.astimezone(timezone.utc)
    hour = value.hour + value.minute / 60 + value.second / 3600
    return swe.julday(value.year, value.month, value.day, hour)


def jd_to_datetime(jd: float) -> datetime:
    year, month, day, hour = swe.revjul(jd, swe.GREG_CAL)
    total_seconds = int(round(hour * 3600))
    base = datetime(year, month, day, tzinfo=timezone.utc)
    return base + timedelta(seconds=total_seconds)


def iso_minute(jd: float) -> str:
    return jd_to_datetime(jd).strftime("%Y-%m-%dT%H:%MZ")


@lru_cache(maxsize=400_000)
def body_state(name: str, jd_rounded: float) -> tuple[float, float]:
    values, _ = swe.calc_ut(jd_rounded, BODIES[name], FLAGS)
    return values[0] % 360.0, values[3]


def state(name: str, jd: float) -> tuple[float, float]:
    return body_state(name, round(jd, 9))


def zodiac_position(longitude: float) -> dict[str, object]:
    longitude %= 360
    sign_index = int(longitude // 30)
    within = longitude % 30
    degrees = int(within)
    minutes = int(round((within - degrees) * 60))
    if minutes == 60:
        degrees += 1
        minutes = 0
    return {
        "longitude": round(longitude, 6),
        "sign": SIGNS[sign_index],
        "degree": degrees,
        "minute": minutes,
        "display": f"{degrees:02d} {SIGNS[sign_index]} {minutes:02d}",
    }


def separation(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def aspect_orb(name_a: str, name_b: str, jd: float, angle: int) -> float:
    lon_a, _ = state(name_a, jd)
    lon_b, _ = state(name_b, jd)
    return abs(separation(lon_a, lon_b) - angle)


def transit_natal_orb(transit: str, natal_longitude: float, jd: float, angle: int) -> float:
    longitude, _ = state(transit, jd)
    return abs(separation(longitude, natal_longitude) - angle)


def golden_minimum(function, left: float, right: float, iterations: int = 34) -> tuple[float, float]:
    ratio = (math.sqrt(5) - 1) / 2
    c = right - ratio * (right - left)
    d = left + ratio * (right - left)
    fc, fd = function(c), function(d)
    for _ in range(iterations):
        if fc < fd:
            right, d, fd = d, c, fc
            c = right - ratio * (right - left)
            fc = function(c)
        else:
            left, c, fc = c, d, fd
            d = left + ratio * (right - left)
            fd = function(d)
    point = (left + right) / 2
    return point, function(point)


def scan_bounds(margin_days: float) -> tuple[float, float]:
    start = datetime(PERIOD.start_date.year, PERIOD.start_date.month, PERIOD.start_date.day, tzinfo=PERIOD.tz)
    end_day = PERIOD.end_date + timedelta(days=1)
    end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=PERIOD.tz)
    return dt_to_jd(start) - margin_days, dt_to_jd(end) + margin_days


def event_stamp(exact_jd: float) -> dict[str, object] | None:
    """utc/date/time fields for an exact event, or None when outside the period."""
    exact_dt = jd_to_datetime(exact_jd)
    local = PERIOD.local_date(exact_dt)
    if not PERIOD.contains(local):
        return None
    return {
        "utc": iso_minute(exact_jd),
        "date": local.isoformat(),
        "time": PERIOD.local_time(exact_dt),
    }


def moon_phase_events() -> list[dict[str, object]]:
    start, end = scan_bounds(7)
    step = 0.125
    labels = {0: "New Moon", 1: "First Quarter", 2: "Full Moon", 3: "Last Quarter"}

    def raw_phase(jd: float) -> float:
        moon, _ = state("Moon", jd)
        sun, _ = state("Sun", jd)
        return (moon - sun) % 360

    events: list[dict[str, object]] = []
    previous_jd = start
    previous_raw = raw_phase(start)
    previous_unwrapped = previous_raw
    jd = start + step
    while jd <= end:
        current_raw = raw_phase(jd)
        delta = (current_raw - previous_raw + 180) % 360 - 180
        current_unwrapped = previous_unwrapped + delta
        first_quarter = math.floor(previous_unwrapped / 90) + 1
        last_quarter = math.floor(current_unwrapped / 90)
        for quarter in range(first_quarter, last_quarter + 1):
            target = quarter * 90.0
            left, right = previous_jd, jd
            left_u = previous_unwrapped
            left_raw = previous_raw
            for _ in range(32):
                middle = (left + right) / 2
                middle_raw = raw_phase(middle)
                middle_u = left_u + ((middle_raw - left_raw + 180) % 360 - 180)
                if middle_u < target:
                    left, left_u, left_raw = middle, middle_u, middle_raw
                else:
                    right = middle
            exact_jd = (left + right) / 2
            stamp = event_stamp(exact_jd)
            if stamp:
                moon_longitude, _ = state("Moon", exact_jd)
                phase_index = quarter % 4
                events.append({
                    "type": "moon_phase",
                    "name": labels[phase_index],
                    **stamp,
                    "sign": zodiac_position(moon_longitude)["sign"],
                })
        previous_jd = jd
        previous_raw = current_raw
        previous_unwrapped = current_unwrapped
        jd += step
    return events


def station_events() -> list[dict[str, object]]:
    start, end = scan_bounds(7)
    step = 0.25
    events: list[dict[str, object]] = []
    for body in STATION_BODIES:
        previous_jd = start
        _, previous_speed = state(body, previous_jd)
        jd = start + step
        while jd <= end:
            _, current_speed = state(body, jd)
            if previous_speed == 0 or previous_speed * current_speed < 0:
                left, right = previous_jd, jd
                left_speed = previous_speed
                for _ in range(34):
                    middle = (left + right) / 2
                    _, middle_speed = state(body, middle)
                    if left_speed == 0 or left_speed * middle_speed <= 0:
                        right = middle
                    else:
                        left, left_speed = middle, middle_speed
                exact_jd = (left + right) / 2
                stamp = event_stamp(exact_jd)
                if stamp:
                    longitude, _ = state(body, exact_jd)
                    direction = "Direct" if current_speed > 0 else "Retrograde"
                    events.append({
                        "type": "station",
                        "name": f"{body} stations {direction}",
                        "body": body,
                        "direction": direction,
                        **stamp,
                        "position": zodiac_position(longitude),
                    })
            previous_jd, previous_speed = jd, current_speed
            jd += step
    return sorted(events, key=lambda item: item["utc"])


def ingress_events() -> list[dict[str, object]]:
    start, end = scan_bounds(2)
    step = 0.125
    events: list[dict[str, object]] = []
    for body in INGRESS_BODIES:
        previous_jd = start
        previous_longitude, _ = state(body, previous_jd)
        previous_sign = int(previous_longitude // 30)
        jd = start + step
        while jd <= end:
            current_longitude, current_speed = state(body, jd)
            current_sign = int(current_longitude // 30)
            if current_sign != previous_sign:
                left, right = previous_jd, jd
                left_sign = previous_sign
                for _ in range(32):
                    middle = (left + right) / 2
                    middle_longitude, _ = state(body, middle)
                    middle_sign = int(middle_longitude // 30)
                    if middle_sign == left_sign:
                        left = middle
                    else:
                        right = middle
                exact_jd = (left + right) / 2
                stamp = event_stamp(exact_jd)
                if stamp:
                    longitude, speed = state(body, exact_jd + (1 / 86400))
                    destination = SIGNS[int(longitude // 30)]
                    events.append({
                        "type": "ingress",
                        "name": f"{body} enters {destination}",
                        "body": body,
                        "direction": "Direct" if speed >= 0 else "Retrograde",
                        **stamp,
                        "sign": destination,
                    })
            previous_jd = jd
            previous_sign = current_sign
            previous_longitude = current_longitude
            jd += step
    return sorted(events, key=lambda item: item["utc"])


def exact_outer_aspects() -> list[dict[str, object]]:
    start, end = scan_bounds(0)
    step = 0.5
    events: list[dict[str, object]] = []
    for index, body_a in enumerate(OUTER):
        for body_b in OUTER[index + 1:]:
            for angle, aspect_name in ASPECTS.items():
                values: list[tuple[float, float]] = []
                jd = start - step
                while jd <= end + step:
                    values.append((jd, aspect_orb(body_a, body_b, jd, angle)))
                    jd += step
                for sample_index in range(1, len(values) - 1):
                    before = values[sample_index - 1]
                    current = values[sample_index]
                    after = values[sample_index + 1]
                    if current[1] <= before[1] and current[1] <= after[1] and current[1] < 0.45:
                        exact_jd, orb = golden_minimum(
                            lambda point: aspect_orb(body_a, body_b, point, angle),
                            before[0],
                            after[0],
                        )
                        stamp = event_stamp(exact_jd)
                        if stamp and orb < 0.03:
                            event = {
                                "type": "outer_aspect",
                                "name": f"{body_a} {aspect_name} {body_b}",
                                "bodies": [body_a, body_b],
                                "aspect": aspect_name,
                                "angle": angle,
                                **stamp,
                                "orb": round(orb, 4),
                            }
                            if not events or not (
                                events[-1]["name"] == event["name"]
                                and abs((jd_to_datetime(exact_jd) - datetime.fromisoformat(events[-1]["utc"].replace("Z", "+00:00"))).total_seconds()) < 43200
                            ):
                                events.append(event)
    return sorted(events, key=lambda item: item["utc"])


def phase_label(jd: float) -> str:
    moon, _ = state("Moon", jd)
    sun, _ = state("Sun", jd)
    angle = (moon - sun) % 360
    names = [
        "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
        "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent",
    ]
    return names[int(((angle + 22.5) % 360) // 45)]


def daily_aspects(jd: float, names: list[str], maximum: int, limit: float) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for index, body_a in enumerate(names):
        for body_b in names[index + 1:]:
            lon_a, _ = state(body_a, jd)
            lon_b, _ = state(body_b, jd)
            current_separation = separation(lon_a, lon_b)
            angle = min(ASPECTS, key=lambda value: abs(current_separation - value))
            orb = abs(current_separation - angle)
            if orb <= limit:
                candidates.append({
                    "name": f"{body_a} {ASPECTS[angle]} {body_b}",
                    "body_a": body_a,
                    "aspect": ASPECTS[angle],
                    "body_b": body_b,
                    "orb": round(orb, 2),
                })
    return sorted(candidates, key=lambda item: item["orb"])[:maximum]


def daily_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current = PERIOD.start_date
    while current <= PERIOD.end_date:
        jd = dt_to_jd(PERIOD.local_noon_utc(current))
        positions: dict[str, object] = {}
        for name in PLANET_ORDER:
            longitude, speed = state(name, jd)
            item = zodiac_position(longitude)
            item["retrograde"] = speed < 0
            positions[name] = item
        records.append({
            "date": current.isoformat(),
            "weekday": calendar.day_name[current.weekday()],
            "snapshot_utc": "12:00",
            "moon_phase": phase_label(jd),
            "positions": positions,
            "major_aspects": daily_aspects(jd, PLANET_ORDER, 4, 1.6),
            "long_term_aspects": daily_aspects(jd, OUTER, 2, 2.5),
        })
        current += timedelta(days=1)
    return records


def personal_sample_data() -> dict[str, object]:
    source = json.loads(PERSONAL_INPUT.read_text(encoding="utf-8"))
    birth_dt = datetime.fromisoformat(source["birth_utc"].replace("Z", "+00:00"))
    birth_jd = dt_to_jd(birth_dt)
    natal: dict[str, object] = {}
    natal_longitudes: dict[str, float] = {}
    for name in PLANET_ORDER:
        longitude, speed = state(name, birth_jd)
        item = zodiac_position(longitude)
        item["retrograde"] = speed < 0
        natal[name] = item
        natal_longitudes[name] = longitude

    cusps, angles = swe.houses_ex(
        birth_jd,
        float(source["latitude"]),
        float(source["longitude"]),
        b"P",
    )
    natal["Ascendant"] = zodiac_position(angles[0])
    natal["Midheaven"] = zodiac_position(angles[1])
    natal_longitudes["Ascendant"] = angles[0]
    natal_longitudes["Midheaven"] = angles[1]

    targets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Ascendant", "Midheaven"]
    start, end = scan_bounds(0)
    events: list[dict[str, object]] = []
    step = 1.0
    for transit in OUTER:
        for target in targets:
            natal_longitude = natal_longitudes[target]
            for angle, aspect_name in ASPECTS.items():
                values: list[tuple[float, float]] = []
                jd = start - step
                while jd <= end + step:
                    values.append((jd, transit_natal_orb(transit, natal_longitude, jd, angle)))
                    jd += step
                for index in range(1, len(values) - 1):
                    if values[index][1] <= values[index - 1][1] and values[index][1] <= values[index + 1][1] and values[index][1] < 0.55:
                        exact_jd, orb = golden_minimum(
                            lambda point: transit_natal_orb(transit, natal_longitude, point, angle),
                            values[index - 1][0],
                            values[index + 1][0],
                        )
                        stamp = event_stamp(exact_jd)
                        if stamp and orb < 0.04:
                            event = {
                                "name": f"Transit {transit} {aspect_name} natal {target}",
                                "transit": transit,
                                "target": target,
                                "aspect": aspect_name,
                                **stamp,
                                "orb": round(orb, 4),
                            }
                            exact_dt = jd_to_datetime(exact_jd)
                            duplicate = any(
                                prior["name"] == event["name"]
                                and abs((datetime.fromisoformat(prior["utc"].replace("Z", "+00:00")) - exact_dt).total_seconds()) < 64800
                                for prior in events
                            )
                            if not duplicate:
                                events.append(event)

    return {
        "profile": source,
        "natal_positions": natal,
        "house_cusps": [zodiac_position(value) for value in cusps],
        "selected_2027_transits": sorted(events, key=lambda item: item["utc"]),
    }


def refine_window_peak(item: dict[str, object], natal_longitude: float) -> None:
    """Sharpen a weekly-sampled peak_date to the exact orb minimum."""
    body = item["transiting_body"]
    if body not in REFINABLE_TRANSITS:
        item["peak_refined"] = False
        return
    angle = ASPECT_ANGLES[str(item["aspect"]).lower()]
    start = date.fromisoformat(item["start_date"]) - timedelta(days=5)
    end = date.fromisoformat(item["end_date"]) + timedelta(days=5)
    left = dt_to_jd(datetime(start.year, start.month, start.day, tzinfo=timezone.utc))
    right = dt_to_jd(datetime(end.year, end.month, end.day, tzinfo=timezone.utc))
    # Retrograde loops can cross the exact aspect several times inside one
    # window: scan daily, refine every local minimum, and keep each pass.
    samples: list[tuple[float, float]] = []
    jd = left
    while jd <= right:
        samples.append((jd, transit_natal_orb(body, natal_longitude, jd, angle)))
        jd += 1.0
    hits: list[dict[str, object]] = []
    for index in range(len(samples)):
        prev_orb = samples[index - 1][1] if index > 0 else samples[index][1] + 1
        next_orb = samples[index + 1][1] if index < len(samples) - 1 else samples[index][1] + 1
        sample_jd, sample_orb = samples[index]
        if sample_orb <= prev_orb and sample_orb <= next_orb and sample_orb < 0.5:
            exact_jd, orb = golden_minimum(
                lambda point: transit_natal_orb(body, natal_longitude, point, angle),
                max(left, sample_jd - 2.0),
                min(right, sample_jd + 2.0),
            )
            exact_dt = jd_to_datetime(exact_jd)
            hit = {
                "date": PERIOD.local_date(exact_dt).isoformat(),
                "time": PERIOD.local_time(exact_dt),
                "orb": round(orb, 4),
                "jd": exact_jd,
            }
            if not any(abs(hit["jd"] - prior["jd"]) < 5.0 for prior in hits):
                hits.append(hit)
    if not hits:
        item["peak_refined"] = False
        return
    hits.sort(key=lambda entry: entry["jd"])
    best = min(hits, key=lambda entry: (entry["orb"], entry["jd"]))
    for hit in hits:
        hit.pop("jd")
    item["peak_date"] = best["date"]
    item["peak_time"] = best["time"]
    item["peak_orb"] = best["orb"]
    item["exact_hits"] = hits
    item["peak_refined"] = True


def personal_from_yaml(path: Path) -> dict[str, object]:
    import yaml as yaml_lib

    source = yaml_lib.safe_load(path.read_text(encoding="utf-8"))
    western = source["systems"]["western"]
    natal_bodies = western["natal"]["bodies"]

    rename = {"ASC": "Ascendant", "MC": "Midheaven"}
    natal: dict[str, object] = {}
    natal_longitudes: dict[str, float] = {}
    for raw_name, values in natal_bodies.items():
        name = rename.get(raw_name, raw_name)
        item = zodiac_position(float(values["absolute_longitude"]))
        item["retrograde"] = bool(values.get("retrograde", False))
        if "house" in values:
            item["house"] = values["house"]
        natal[name] = item
        natal_longitudes[name] = float(values["absolute_longitude"])

    windows: list[dict[str, object]] = []
    long_term = western.get("transit_long_term") or {}
    for item in long_term.get("items", []):
        window = {
            "transiting_body": item["transiting_body"],
            "natal_body": rename.get(item["natal_body"], item["natal_body"]),
            "aspect": str(item["aspect"]).lower(),
            "start_date": item["start_date"],
            "end_date": item["end_date"],
            "peak_date": item["peak_date"],
            "importance": item.get("importance", "medium"),
            "retrograde_any": bool(item.get("retrograde", {}).get("any", False)),
            "hint_ja": item.get("interpretation_hint", ""),
        }
        natal_name = window["natal_body"]
        if natal_name in natal_longitudes:
            refine_window_peak(window, natal_longitudes[natal_name])
        else:
            window["peak_refined"] = False
        windows.append(window)
    windows.sort(key=lambda entry: entry["start_date"])

    profile_input = source.get("input", {})
    birth_display = f"{profile_input.get('birth_date', '')} {profile_input.get('birth_time', '')}".strip()
    tz_name = profile_input.get("timezone", PERIOD.tz_name)
    return {
        "source": "yaml",
        "profile": {
            "display_name": profile_input.get("title", ""),
            "birth_display": birth_display,
            "birth_timezone": tz_name,
            "birthplace_label": profile_input.get("birth_place", ""),
            "zodiac": "Tropical",
            "house_system": "Placidus",
        },
        "natal_positions": natal,
        "windows": windows,
    }


def build_snapshot(personal_yaml: Path | None) -> dict[str, object]:
    phases = moon_phase_events()
    stations = station_events()
    ingresses = ingress_events()
    outer_aspects = exact_outer_aspects()
    snapshot: dict[str, object] = {
        "metadata": {
            "start_date": PERIOD.start_date.isoformat(),
            "end_date": PERIOD.end_date.isoformat(),
            "months": [list(pair) for pair in PERIOD.months],
            "tz": PERIOD.tz_name,
            "period_label": PERIOD.label,
            "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "zodiac": "Tropical",
            "ephemeris": f"Swiss Ephemeris {swe.version}; Moshier planetary ephemeris",
            "time_standard": PERIOD.tz_name,
            "daily_snapshot_time": f"12:00 {PERIOD.tz_name}",
            "accuracy_note": "Calendar dates follow the configured time zone. Validate against the production nanami-astro engine before sale.",
        },
        "moon_phases": phases,
        "stations": stations,
        "ingresses": ingresses,
        "outer_aspects": outer_aspects,
        "daily": daily_records(),
    }
    if personal_yaml is not None:
        snapshot["personal"] = personal_from_yaml(personal_yaml)
    else:
        snapshot["personal_sample"] = personal_sample_data()
    return snapshot


def main() -> None:
    global PERIOD
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--start-month", help="YYYY-MM of the first month (default 2027-01, or the personal YAML long-term start)")
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--tz", help="IANA time zone for date assignment (default UTC, or the personal YAML timezone)")
    parser.add_argument("--personal-yaml", type=Path, help="nanami-products YAML with natal + transit_long_term")
    args = parser.parse_args()

    start_month = args.start_month
    tz_name = args.tz
    if args.personal_yaml is not None:
        import yaml as yaml_lib

        source = yaml_lib.safe_load(args.personal_yaml.read_text(encoding="utf-8"))
        if start_month is None:
            long_start = source["systems"]["western"]["transit_long_term"]["period"]["start_date"]
            start_month = long_start[:7]
        if tz_name is None:
            tz_name = source.get("input", {}).get("timezone", "UTC")
    start_month = start_month or "2027-01"
    tz_name = tz_name or "UTC"
    year, month = int(start_month[:4]), int(start_month[5:7])
    PERIOD = Period(year, month, args.months, tz_name)

    output = args.output or DEFAULT_OUTPUT
    snapshot = build_snapshot(args.personal_yaml)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}")
    counts = [
        f"{len(snapshot['moon_phases'])} phases",
        f"{len(snapshot['stations'])} stations",
        f"{len(snapshot['ingresses'])} ingresses",
        f"{len(snapshot['outer_aspects'])} outer aspects",
        f"{len(snapshot['daily'])} daily records",
    ]
    if "personal" in snapshot:
        counts.append(f"{len(snapshot['personal']['windows'])} personal windows")
    print(", ".join(counts))


if __name__ == "__main__":
    main()
