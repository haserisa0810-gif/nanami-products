from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Any

import swisseph as swe
import yaml

from services.western_calc import PLANETS, calc_aspects, configure_ephemeris, ephemeris_debug_info, sign_of

MUNDANE_YAML_FORMAT = "mundane-monthly-yaml-v1"
MUNDANE_TIMEZONE = "Asia/Tokyo"
MUNDANE_TZ_OFFSET_HOURS = 9

PLANET_KEYS = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
    "Uranus": "uranus",
    "Neptune": "neptune",
    "Pluto": "pluto",
}
SOCIAL_BODIES = {"Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
PERSONAL_BODIES = {"Sun", "Mercury", "Venus", "Mars"}
LUNAR_TARGETS = {
    "new_moon": 0,
    "first_quarter": 90,
    "full_moon": 180,
    "last_quarter": 270,
}


def _angle_distance(a: float, b: float) -> float:
    diff = abs((a % 360) - (b % 360))
    return min(diff, 360 - diff)


def _julian_day_jst(year: int, month: int, day: int, hour: int = 12) -> float:
    return swe.julday(year, month, day, hour - MUNDANE_TZ_OFFSET_HOURS)


def _planet_items_for_day(year: int, month: int, day: int, *, hour: int = 12) -> list[dict[str, Any]]:
    jd_ut = _julian_day_jst(year, month, day, hour)
    flags = configure_ephemeris() | swe.FLG_SPEED
    items: list[dict[str, Any]] = []
    for name, body_id in PLANETS:
        xx, _ = swe.calc_ut(jd_ut, body_id, flags)
        sign, degree = sign_of(xx[0])
        items.append(
            {
                "name": name,
                "lon": round(xx[0] % 360, 6),
                "sign": sign,
                "degree": round(degree, 6),
                "retrograde": bool(xx[3] < 0),
                "speed": round(xx[3], 6),
            }
        )
    return items


def _planet_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        key = PLANET_KEYS.get(str(item.get("name")))
        if not key:
            continue
        out[key] = {
            "sign": item["sign"],
            "degree": item["degree"],
            "longitude": item["lon"],
            "retrograde": item["retrograde"],
        }
    return out


def _lunar_elongation(items: list[dict[str, Any]]) -> float:
    sun = next(item for item in items if item["name"] == "Sun")
    moon = next(item for item in items if item["name"] == "Moon")
    return (float(moon["lon"]) - float(sun["lon"])) % 360


def _detect_lunar_events(year: int, month: int, days_in_month: int) -> list[dict[str, Any]]:
    candidates: dict[str, tuple[int, float, list[dict[str, Any]]]] = {}
    for day in range(1, days_in_month + 1):
        items = _planet_items_for_day(year, month, day)
        elongation = _lunar_elongation(items)
        for phase, target in LUNAR_TARGETS.items():
            distance = _angle_distance(elongation, target)
            current = candidates.get(phase)
            if current is None or distance < current[1]:
                candidates[phase] = (day, distance, items)

    events = []
    for phase, (day, distance, items) in sorted(candidates.items(), key=lambda pair: pair[1][0]):
        moon = next(item for item in items if item["name"] == "Moon")
        sun = next(item for item in items if item["name"] == "Sun")
        events.append(
            {
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "phase": phase,
                "approximation": "daily_noon_jst_nearest",
                "orb_degrees": round(distance, 2),
                "sun": {"sign": sun["sign"], "degree": sun["degree"]},
                "moon": {"sign": moon["sign"], "degree": moon["degree"]},
            }
        )
    return events


def _is_mundane_aspect(aspect: dict[str, Any]) -> bool:
    bodies = {str(aspect.get("planet1")), str(aspect.get("planet2"))}
    if not bodies & SOCIAL_BODIES:
        return False
    if not bodies & (SOCIAL_BODIES | PERSONAL_BODIES):
        return False
    try:
        return float(aspect.get("orb", 99)) <= 1.2
    except (TypeError, ValueError):
        return False


def _daily_major_aspects(year: int, month: int, days_in_month: int) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for day in range(1, days_in_month + 1):
        items = _planet_items_for_day(year, month, day)
        for aspect in calc_aspects(items):
            if not _is_mundane_aspect(aspect):
                continue
            signature = (str(aspect["planet1"]), str(aspect["planet2"]), str(aspect["type"]))
            if signature in seen:
                continue
            seen.add(signature)
            out.append(
                {
                    "date": f"{year:04d}-{month:02d}-{day:02d}",
                    "body1": aspect["planet1"],
                    "body2": aspect["planet2"],
                    "aspect": aspect["type"],
                    "orb": aspect["orb"],
                    "calculation": "daily_noon_jst_first_tight_hit",
                }
            )
    return sorted(out, key=lambda item: (item["date"], item["orb"], item["body1"], item["body2"]))[:24]


def _sign_ingresses(year: int, month: int, days_in_month: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous: dict[str, str] = {}
    for day in range(1, days_in_month + 1):
        for item in _planet_items_for_day(year, month, day):
            name = str(item["name"])
            if name == "Moon":
                continue
            sign = str(item["sign"])
            old_sign = previous.get(name)
            if old_sign is not None and old_sign != sign:
                events.append(
                    {
                        "date": f"{year:04d}-{month:02d}-{day:02d}",
                        "body": name,
                        "from": old_sign,
                        "to": sign,
                        "approximation": "daily_noon_jst",
                    }
                )
            previous[name] = sign
    return events


def generate_mundane_yaml(*, title: str, slug: str, target_year: int, target_month: int) -> str:
    year = int(target_year)
    month = int(target_month)
    if not (1900 <= year <= 2100):
        raise ValueError("target_yearは1900〜2100で指定してください。")
    if not (1 <= month <= 12):
        raise ValueError("target_monthは1〜12で指定してください。")

    days_in_month = calendar.monthrange(year, month)[1]
    first_day_items = _planet_items_for_day(year, month, 1)
    doc = {
        "meta": {
            "schema_version": "1.0",
            "format": MUNDANE_YAML_FORMAT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "nanami-products.services.mundane_yaml.generate_mundane_yaml",
            "calculation_note": "月相・サイン移動・主要アスペクトはJST正午の近似値です。厳密な時刻計算は後続実装で差し替え可能です。",
        },
        "mundane_context": {
            "title": title.strip(),
            "slug": slug.strip(),
            "target_year": year,
            "target_month": month,
            "period": {
                "start_date": f"{year:04d}-{month:02d}-01",
                "end_date": f"{year:04d}-{month:02d}-{days_in_month:02d}",
                "timezone": MUNDANE_TIMEZONE,
            },
            "data_role": "monthly_social_context_for_ai",
        },
        "monthly_snapshot": {
            "date": f"{year:04d}-{month:02d}-01",
            "time": "12:00",
            "timezone": MUNDANE_TIMEZONE,
            "planets": _planet_map(first_day_items),
        },
        "lunar_events": _detect_lunar_events(year, month, days_in_month),
        "sign_ingresses": _sign_ingresses(year, month, days_in_month),
        "major_aspects": _daily_major_aspects(year, month, days_in_month),
        "ai_usage": {
            "purpose": "AIに対象月の社会全体の流れを渡すためのマンデン占星術コンテキスト",
            "not_included": "個人の出生図、個人トランジット、個別鑑定文",
            "suggested_prompt": "このマンデンYAMLを社会全体の背景として使い、個人データと混同せずに読み解いてください。",
        },
        "engine": {
            "name": "swisseph",
            "ephemeris": ephemeris_debug_info(),
        },
    }
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
