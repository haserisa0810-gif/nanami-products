from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from services.location import resolve_prefecture
from services.western_calc import calc_western_from_payload
from services.prompt_builder import build_prompt

SIGN_JA = {
    "Ari": "牡羊座", "Tau": "牡牛座", "Gem": "双子座", "Can": "蟹座", "Leo": "獅子座", "Vir": "乙女座",
    "Lib": "天秤座", "Sco": "蠍座", "Sag": "射手座", "Cap": "山羊座", "Aqu": "水瓶座", "Pis": "魚座",
}
ELEMENT_BY_SIGN = {
    "Ari": "fire", "Leo": "fire", "Sag": "fire",
    "Tau": "earth", "Vir": "earth", "Cap": "earth",
    "Gem": "air", "Lib": "air", "Aqu": "air",
    "Can": "water", "Sco": "water", "Pis": "water",
}
MODE_BY_SIGN = {
    "Ari": "cardinal", "Can": "cardinal", "Lib": "cardinal", "Cap": "cardinal",
    "Tau": "fixed", "Leo": "fixed", "Sco": "fixed", "Aqu": "fixed",
    "Gem": "mutable", "Vir": "mutable", "Sag": "mutable", "Pis": "mutable",
}
CORE_BODIES = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
ASTEROID_BODIES = {"Chiron", "Lilith", "Ceres", "Pallas", "Juno", "Vesta", "Vertex"}
TRANSIT_BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
TRANSIT_ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}
TRANSIT_ORB = {
    "Sun": 1.5,
    "Moon": 1.2,
    "Mercury": 1.2,
    "Venus": 1.2,
    "Mars": 1.2,
    "Jupiter": 1.5,
    "Saturn": 1.5,
    "Uranus": 1.5,
    "Neptune": 1.5,
    "Pluto": 1.5,
}
MOON_TIMEPOINTS = [
    ("morning", 6),
    ("noon", 12),
    ("night", 21),
]

def _split_date(value: str) -> tuple[int, int, int]:
    y, m, d = value.split("-")
    return int(y), int(m), int(d)

def _split_time(value: str | None) -> tuple[int, int]:
    if not value:
        return 12, 0
    h, m = value.split(":")[:2]
    return int(h), int(m)

def _round(x: Any, digits: int = 4) -> Any:
    return round(float(x), digits) if x is not None else None

def _format_body(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "sign": p.get("sign"),
        "sign_ja": SIGN_JA.get(p.get("sign"), p.get("sign")),
        "degree": _round(p.get("degree"), 4),
        "absolute_longitude": _round(p.get("lon"), 4),
        "house": p.get("house"),
        "retrograde": bool(p.get("retrograde", False)),
    }

def _format_aspect(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "body1": a.get("planet1"),
        "body2": a.get("planet2"),
        "aspect": a.get("type"),
        "orb": _round(a.get("orb"), 2),
    }

def _angle_diff(a: float, b: float) -> float:
    d = abs((a % 360) - (b % 360))
    return min(d, 360 - d)

def _transit_aspects(transit_bodies: dict[str, dict[str, Any]], natal_bodies: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for transit_name, transit_body in transit_bodies.items():
        transit_lon = transit_body.get("absolute_longitude")
        if transit_lon is None:
            continue
        max_orb = TRANSIT_ORB.get(transit_name, 1.2)
        for natal_name, natal_body in natal_bodies.items():
            if natal_name not in CORE_BODIES:
                continue
            natal_lon = natal_body.get("absolute_longitude")
            if natal_lon is None:
                continue
            diff = _angle_diff(float(transit_lon), float(natal_lon))
            for aspect_name, aspect_angle in TRANSIT_ASPECTS.items():
                orb = abs(diff - aspect_angle)
                if orb <= max_orb:
                    out.append({
                        "transit_body": transit_name,
                        "natal_body": natal_name,
                        "aspect": aspect_name,
                        "orb": _round(orb, 2),
                        "transit_longitude": _round(transit_lon, 4),
                        "natal_longitude": _round(natal_lon, 4),
                    })
    return sorted(out, key=lambda x: (x["orb"], x["transit_body"], x["natal_body"]))

def _build_transit_block(
    *,
    start_date: datetime,
    days: int,
    lat: float,
    lng: float,
    pref_name: str,
    tz_name: str,
    natal_bodies: dict[str, Any],
) -> dict[str, Any]:
    daily: list[dict[str, Any]] = []
    tz = ZoneInfo(tz_name)
    start_day = start_date.astimezone(tz).date()
    for offset in range(days):
        target_day = start_day + timedelta(days=offset)
        local_noon = datetime(target_day.year, target_day.month, target_day.day, 12, 0, tzinfo=tz)
        tz_offset = local_noon.utcoffset()
        tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
        transit_payload = {
            "year": target_day.year,
            "month": target_day.month,
            "day": target_day.day,
            "hour": 12,
            "minute": 0,
            "lat": lat,
            "lng": lng,
            "city": pref_name,
            "tz_offset_hours": tz_offset_hours,
            "house_system": "P",
            "include_asteroids": False,
            "include_chiron": False,
            "include_lilith": False,
            "include_vertex": False,
        }
        raw = calc_western_from_payload(transit_payload)
        transiting = {
            p["name"]: _format_body(p)
            for p in raw.get("planets", [])
            if p.get("name") in TRANSIT_BODIES
        }
        moon_timepoints: list[dict[str, Any]] = []
        for label, hour in MOON_TIMEPOINTS:
            moon_local = datetime(target_day.year, target_day.month, target_day.day, hour, 0, tzinfo=tz)
            moon_offset = moon_local.utcoffset()
            moon_tz_offset_hours = moon_offset.total_seconds() / 3600 if moon_offset is not None else tz_offset_hours
            moon_payload = {**transit_payload, "hour": hour, "minute": 0, "tz_offset_hours": moon_tz_offset_hours}
            moon_raw = calc_western_from_payload(moon_payload)
            moon = next((p for p in moon_raw.get("planets", []) if p.get("name") == "Moon"), None)
            if not moon:
                continue
            moon_body = _format_body(moon)
            moon_timepoints.append({
                "label": label,
                "time": f"{hour:02d}:00",
                "body": moon_body,
                "natal_aspects": _transit_aspects({"Moon": moon_body}, natal_bodies),
            })
        daily.append({
            "date": target_day.isoformat(),
            "time": "12:00",
            "timezone": tz_name,
            "transiting_bodies": transiting,
            "natal_aspects": _transit_aspects(transiting, natal_bodies),
            "moon_timepoints": moon_timepoints,
        })
    return {
        "period": {
            "start_date": start_day.isoformat(),
            "days": days,
            "timezone": tz_name,
            "sample_time": "12:00",
            "moon_timepoints": [f"{hour:02d}:00" for _, hour in MOON_TIMEPOINTS],
        },
        "daily": daily,
    }

def _summaries(planets: list[dict[str, Any]]) -> dict[str, Any]:
    elements = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    modes = {"cardinal": 0, "fixed": 0, "mutable": 0}
    signs: dict[str, int] = {}
    for p in planets:
        if p.get("name") not in CORE_BODIES:
            continue
        sign = p.get("sign")
        if sign in ELEMENT_BY_SIGN:
            elements[ELEMENT_BY_SIGN[sign]] += 1
        if sign in MODE_BY_SIGN:
            modes[MODE_BY_SIGN[sign]] += 1
        signs[sign] = signs.get(sign, 0) + 1
    dominant_signs = sorted(signs.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return {
        "elements": elements,
        "modes": modes,
        "dominant_signs": [{"sign": k, "sign_ja": SIGN_JA.get(k, k), "count": v} for k, v in dominant_signs],
    }

def build_product_yaml(
    *,
    title: str | None,
    birth_date: str,
    birth_time: str | None,
    prefecture: str,
    birth_place_label: str | None = None,
    birth_lat: float | None = None,
    birth_lng: float | None = None,
    tz_name: str = "Asia/Tokyo",
    gender: str = "unknown",
    house_system: str = "P",
    include_asteroids: bool = False,
    include_shichusuimei: bool = False,
    include_transit: bool = False,
    transit_start_date: datetime | None = None,
    transit_days: int = 31,
    day_change_at_23: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    include_western = not (include_shichusuimei and not include_asteroids and not include_transit)
    y, m, d = _split_date(birth_date)
    hour, minute = _split_time(birth_time)
    if birth_lat is not None and birth_lng is not None:
        lat = birth_lat
        lng = birth_lng
        pref_name = birth_place_label or prefecture or "海外出生"
    else:
        pref_name, lat, lng = resolve_prefecture(prefecture)
    tz = ZoneInfo(tz_name)
    local_dt = datetime(y, m, d, hour, minute, tzinfo=tz)
    tz_offset = local_dt.utcoffset()
    tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
    generated_at = datetime.now(timezone.utc).astimezone()

    western_system = None
    if include_western:
        payload = {
            "year": y, "month": m, "day": d, "hour": hour, "minute": minute,
            "lat": lat, "lng": lng, "city": pref_name, "tz_offset_hours": tz_offset_hours,
            "house_system": house_system,
            "include_asteroids": include_asteroids,
            "include_chiron": True,
            "include_lilith": True,
            "include_vertex": include_asteroids,
        }
        raw = calc_western_from_payload(payload)
        bodies = {p["name"]: _format_body(p) for p in raw.get("planets", [])}
        core = {k: v for k, v in bodies.items() if k in CORE_BODIES or k in {"North Node", "South Node", "ASC", "MC"}}
        asteroids = {k: v for k, v in bodies.items() if k in ASTEROID_BODIES}
        houses = {
            str(h["house"]): {
                "sign": h.get("sign"), "sign_ja": SIGN_JA.get(h.get("sign"), h.get("sign")),
                "degree": _round(h.get("degree"), 4), "absolute_longitude": _round(h.get("lon"), 4),
            }
            for h in raw.get("houses", [])
        }
        skipped_bodies = raw.get("skipped_bodies", []) or []
        western_system = {
            "natal": {
                "engine": "Swiss Ephemeris",
                "house_system": house_system,
                "subject": raw.get("subject"),
                "bodies": core,
                "houses": houses,
                "aspects": [_format_aspect(a) for a in raw.get("aspects", [])],
                "summary": _summaries(raw.get("planets", [])),
                "skipped_bodies": skipped_bodies,
            },
            "asteroids": asteroids if include_asteroids else None,
            "transit": _build_transit_block(
                start_date=transit_start_date or generated_at,
                days=transit_days,
                lat=lat,
                lng=lng,
                pref_name=pref_name,
                tz_name=tz_name,
                natal_bodies=core,
            ) if include_transit else None,
        }

    systems: dict[str, Any] = {
        "western": western_system,
        "shichusuimei": None,
    }
    if include_shichusuimei:
        from services.shichusuimei_calc import calc_shichusuimei_from_payload
        systems["shichusuimei"] = calc_shichusuimei_from_payload(
            {"year": y, "month": m, "day": d, "hour": hour, "minute": minute, "gender": gender},
            tz_name=tz_name,
            day_change_at_23=day_change_at_23,
        )
    doc = {
        "version": "nanami-products-yaml-v1",
        "product": {
            "type": "personal_ai_astrology_yaml",
            "options": {
                "western_natal": include_western,
                "asteroids": include_asteroids,
                "transit": include_transit,
                "shichusuimei": include_shichusuimei,
            },
        },
        "generated_at": generated_at.isoformat(),
        "input": {
            "title": title,
            "birth_date": birth_date,
            "birth_time": birth_time or "unknown_noon_used",
            "prefecture": prefecture if birth_lat is None or birth_lng is None else None,
            "birth_place_kind": "overseas" if birth_lat is not None and birth_lng is not None else "domestic",
            "birth_place": birth_place_label or pref_name,
            "timezone": tz_name,
            "timezone_offset_hours": tz_offset_hours,
            "gender": gender,
        },
        "usage_note": {
            "for_ai": "このYAMLは計算済みデータです。AIに解釈させる場合、生年月日から再計算させず、この値を根拠にしてください。",
            "not_included": "鑑定本文は含みません。AI解釈用の構造化データです。",
        },
        "systems": systems,
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    prompt_text = build_prompt(
        include_shichusuimei=include_shichusuimei,
        include_asteroids=include_asteroids,
        include_transit=include_transit,
    )
    return yaml_text, prompt_text, doc
