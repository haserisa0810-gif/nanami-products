from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import hashlib
import json
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
LONG_TERM_TRANSIT_PRIMARY_BODIES = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
LONG_TERM_TRANSIT_AUXILIARY_BODIES = ["Chiron", "North Node", "South Node"]
LONG_TERM_TRANSIT_SAMPLE_INTERVAL_DAYS = 7
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
    "Chiron": 1.2,
    "North Node": 1.2,
    "South Node": 1.2,
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

def _short_hash(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"

def _birth_time_struct(
    *,
    input_value: str | None,
    calculation_time: str,
    accuracy: str,
    note: str,
    range_info: dict[str, Any] | None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "input_value": input_value if accuracy == "exact" else None,
        "calculation_time": calculation_time,
        "accuracy": accuracy,
        "note": note,
    }
    if range_info:
        data["range"] = range_info
    return data

def _interpretation_flags(accuracy: str) -> dict[str, Any]:
    if accuracy in {"unknown", "approximate"}:
        return {
            "allow_house_interpretation": False,
            "allow_asc_mc_interpretation": False,
            "house_reliability": "low",
            "moon_reliability": "medium",
            "use_houses_as_reference_only": True,
        }
    return {
        "allow_house_interpretation": True,
        "allow_asc_mc_interpretation": True,
        "house_reliability": "high",
        "moon_reliability": "high",
        "use_houses_as_reference_only": False,
    }

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

def _build_long_term_transit_block(
    *,
    start_date: datetime,
    days: int,
    lat: float,
    lng: float,
    pref_name: str,
    tz_name: str,
    natal_bodies: dict[str, Any],
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    tz = ZoneInfo(tz_name)
    start_day = start_date.astimezone(tz).date()
    selected_bodies = set(LONG_TERM_TRANSIT_PRIMARY_BODIES + LONG_TERM_TRANSIT_AUXILIARY_BODIES)
    for offset in range(0, days, LONG_TERM_TRANSIT_SAMPLE_INTERVAL_DAYS):
        target_day = start_day + timedelta(days=offset)
        local_noon = datetime(target_day.year, target_day.month, target_day.day, 12, 0, tzinfo=tz)
        tz_offset = local_noon.utcoffset()
        tz_offset_hours = tz_offset.total_seconds() / 3600 if tz_offset is not None else 9
        raw = calc_western_from_payload({
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
            "include_chiron": True,
            "include_lilith": False,
            "include_vertex": False,
        })
        transiting = {
            p["name"]: _format_body(p)
            for p in raw.get("planets", [])
            if p.get("name") in selected_bodies
        }
        samples.append({
            "date": target_day.isoformat(),
            "transiting_bodies": transiting,
            "natal_aspects": _transit_aspects(transiting, natal_bodies),
        })
    return {
        "period": {
            "start_date": start_day.isoformat(),
            "end_date": (start_day + timedelta(days=max(days, 1) - 1)).isoformat(),
            "days": days,
            "timezone": tz_name,
            "sample_time": "12:00",
            "sample_interval_days": LONG_TERM_TRANSIT_SAMPLE_INTERVAL_DAYS,
            "primary_bodies": LONG_TERM_TRANSIT_PRIMARY_BODIES,
            "auxiliary_bodies": LONG_TERM_TRANSIT_AUXILIARY_BODIES,
        },
        "samples": samples,
    }

def _build_transit_for_profile(
    *,
    profile: str,
    start_date: datetime,
    days: int,
    lat: float,
    lng: float,
    pref_name: str,
    tz_name: str,
    natal_bodies: dict[str, Any],
) -> dict[str, Any]:
    builder = {
        "standard": _build_transit_block,
        "long_term": _build_long_term_transit_block,
    }.get(profile)
    if builder is None:
        raise ValueError(f"Unsupported transit profile: {profile}")
    return builder(
        start_date=start_date,
        days=days,
        lat=lat,
        lng=lng,
        pref_name=pref_name,
        tz_name=tz_name,
        natal_bodies=natal_bodies,
    )

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
    transit_profile: str = "standard",
    day_change_at_23: bool = False,
    birth_time_accuracy: str = "auto",
    birth_time_range: dict[str, Any] | None = None,
    birth_time_note: str | None = None,
    data_role: str = "base_chart",
    base: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    include_western = not (include_shichusuimei and not include_asteroids and not include_transit)
    if birth_time_accuracy == "auto":
        birth_time_accuracy = "exact" if birth_time else "unknown"
    if birth_time_accuracy == "unknown" and not birth_time_note:
        birth_time_note = "出生時刻不明のため12:00で仮計算しています。ハウス・ASC・MCは参考値です。"
    elif birth_time_accuracy == "approximate" and not birth_time_note:
        birth_time_note = "出生時刻は推定レンジです。ハウス・ASC・MCは参考値です。"
    elif not birth_time_note:
        birth_time_note = "出生時刻あり。ハウス・ASC・MCを通常通り使用できます。"
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
            "transit": _build_transit_for_profile(
                profile=transit_profile,
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
    calculation_time = f"{hour:02d}:{minute:02d}"
    display_birth_time = birth_time if birth_time_accuracy == "exact" else birth_time_accuracy
    profile_id = _short_hash("profile", {
        "title": title or "",
        "birth_date": birth_date,
        "birth_place": birth_place_label or pref_name,
        "timezone": tz_name,
    })
    chart_id = _short_hash("chart", {
        "profile_id": profile_id,
        "birth_date": birth_date,
        "calculation_time": calculation_time,
        "birth_time_accuracy": birth_time_accuracy,
        "birth_time_range": birth_time_range,
        "lat": _round(lat, 6),
        "lng": _round(lng, 6),
        "timezone": tz_name,
        "house_system": house_system,
        "include_asteroids": include_asteroids,
        "include_shichusuimei": include_shichusuimei,
        "include_transit": include_transit,
        "transit_days": transit_days,
        "transit_profile": transit_profile,
        "day_change_at_23": day_change_at_23,
    })
    birth_time_data = _birth_time_struct(
        input_value=birth_time,
        calculation_time=calculation_time,
        accuracy=birth_time_accuracy,
        note=birth_time_note,
        range_info=birth_time_range,
    )
    interpretation_flags = _interpretation_flags(birth_time_accuracy)
    is_overseas_birth = birth_lat is not None and birth_lng is not None and not prefecture.strip()
    input_block = {
        "title": title,
        "birth_date": birth_date,
        "birth_time": display_birth_time,
        "calculation_time": calculation_time,
        "birth_time_accuracy": birth_time_accuracy,
        "birth_time_note": birth_time_note,
        "prefecture": None if is_overseas_birth else prefecture,
        "birth_place_kind": "overseas" if is_overseas_birth else "domestic",
        "birth_place": birth_place_label or pref_name,
        "birth_lat": _round(lat, 6),
        "birth_lng": _round(lng, 6),
        "timezone": tz_name,
        "timezone_offset_hours": tz_offset_hours,
        "gender": gender,
    }
    if birth_time_range:
        input_block["birth_time_range"] = birth_time_range

    doc = {
        "version": "nanami-products-yaml-v1",
        "meta": {
            "schema_version": "1.1",
            "product_type": "personal_ai_astrology_yaml",
            "profile_id": profile_id,
            "chart_id": chart_id,
            "generated_at": generated_at.isoformat(),
            "data_role": data_role,
        },
        "base": base,
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
        "calculation": {
            "engine": "Swiss Ephemeris" if include_western else "nanami-products shichusuimei",
            "zodiac": "tropical" if include_western else None,
            "house_system": house_system if include_western else None,
            "timezone": tz_name,
            "location_source": "input",
            "ephemeris_version": None,
        },
        "birth_time": birth_time_data,
        "interpretation_flags": interpretation_flags,
        "assets": {
            "horoscope_svg": {
                "available": bool(include_western),
                "file_name": "horoscope.svg",
                "generated_from_chart_id": chart_id,
            },
            "shichusuimei_svg": {
                "available": bool(include_shichusuimei),
                "file_name": "shichusuimei-chart.svg",
                "generated_from_chart_id": chart_id,
            },
            "yaml_lite": {
                "available": bool(include_transit),
            },
            "yaml_detail": {
                "available": bool(include_transit and include_asteroids),
            },
            "yaml_full": {
                "available": True,
            },
        },
        "input": input_block,
        "usage_note": {
            "for_ai": "このYAMLは計算済みデータです。AIに解釈させる場合、生年月日から再計算させず、この値を根拠にしてください。",
            "not_included": "鑑定本文は含みません。AI解釈用の構造化データです。",
            "continuous_use": "このYAMLはAIに一度読み込ませて継続的に使える基礎データです。今後、月ごとのトランジット追加データと組み合わせて使うこともできます。",
        },
        "systems": systems,
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    prompt_text = build_prompt(
        include_shichusuimei=include_shichusuimei,
        include_asteroids=include_asteroids,
        include_transit=include_transit,
        birth_time_accuracy=birth_time_accuracy,
        interpretation_flags=interpretation_flags,
    )
    return yaml_text, prompt_text, doc


ASTEROID_ADDON_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、基本版ホロスコープに後から追加する小惑星データです。

重要ルール:
- このYAML単体を出生図全体として扱わないでください。
- 先に読み込ませた基本版ホロスコープYAMLに、systems.western.asteroids の追加部品として結合して読んでください。
- 小惑星位置・ハウス・度数の計算結果は変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を根拠として、性格・テーマ・関係性の深掘りに使ってください。

以下のYAMLを読み込んで、基本版データに追加して解釈してください。
"""


def build_asteroid_addon_yaml(
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
    birth_time_accuracy: str = "auto",
    birth_time_range: dict[str, Any] | None = None,
    birth_time_note: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    _full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
        title=title,
        birth_date=birth_date,
        birth_time=birth_time,
        prefecture=prefecture,
        birth_place_label=birth_place_label,
        birth_lat=birth_lat,
        birth_lng=birth_lng,
        tz_name=tz_name,
        gender=gender,
        house_system=house_system,
        include_asteroids=True,
        include_shichusuimei=False,
        include_transit=False,
        birth_time_accuracy=birth_time_accuracy,
        birth_time_range=birth_time_range,
        birth_time_note=birth_time_note,
        data_role="addon",
    )
    meta = full_doc.get("meta") or {}
    western = ((full_doc.get("systems") or {}).get("western") or {})
    asteroids = western.get("asteroids") or {}
    doc = {
        "version": "nanami-products-yaml-addon-v1",
        "meta": {
            **meta,
            "schema_version": meta.get("schema_version") or "1.1",
            "product_type": "western_asteroids_addon",
            "data_role": "addon",
            "addon_type": "western_asteroids",
            "source_logic": "western_full_asteroid_calculation",
        },
        "base": {
            "target_product_type": "western_basic",
            "target_system": "western",
            "merge_path": "systems.western.asteroids",
            "compatible_with": ["western_basic", "personal_ai_astrology_yaml_natal"],
        },
        "product": {
            "type": "western_asteroids_addon",
            "label": "ホロスコープ：小惑星追加",
            "options": {
                "addon": True,
                "western_natal": False,
                "asteroids": True,
                "transit": False,
                "shichusuimei": False,
            },
        },
        "generated_at": full_doc.get("generated_at"),
        "calculation": full_doc.get("calculation") or {},
        "birth_time": full_doc.get("birth_time") or {},
        "interpretation_flags": full_doc.get("interpretation_flags") or {},
        "assets": {
            "yaml_addon": {
                "available": True,
                "merge_path": "systems.western.asteroids",
            },
            "horoscope_svg": {"available": False},
            "shichusuimei_svg": {"available": False},
        },
        "input": full_doc.get("input") or {},
        "usage_note": {
            "for_ai": "これは追加部品データです。基本版ホロスコープYAMLを土台にし、このYAMLの小惑星データを追加して解釈してください。",
            "merge_instruction": "systems.western.asteroids を、同じ出生情報で作成済みの基本版YAMLへ追加する想定です。",
            "not_included": "出生図全体・トランジット・鑑定本文は含みません。小惑星追加用の計算済みデータです。",
        },
        "systems": {
            "western": {
                "natal": None,
                "asteroids": asteroids,
                "transit": None,
            },
            "shichusuimei": None,
        },
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    return yaml_text, ASTEROID_ADDON_PROMPT.strip() + "\n", doc


TRANSIT_31DAYS_ADDON_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、基本版ホロスコープに後から追加する38日トランジットデータです。

重要ルール:
- このYAML単体を出生図全体として扱わないでください。
- 先に読み込ませた基本版ホロスコープYAMLと一緒にAIへ貼り付けて使ってください。
- systems.western.transit を、基本版ホロスコープYAMLの追加部品として読んでください。
- トランジット天体位置・出生図へのアスペクト・月の時間帯データは変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を根拠として、今後38日間の流れを読んでください。
- today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。
- 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。
- next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。
- 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。

以下のYAMLを読み込んで、基本版データと組み合わせて解釈してください。
"""


def build_31days_transit_addon_yaml(
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
    transit_start_date: datetime | None = None,
    transit_days: int = 38,
    birth_time_accuracy: str = "auto",
    birth_time_range: dict[str, Any] | None = None,
    birth_time_note: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
        title=title,
        birth_date=birth_date,
        birth_time=birth_time,
        prefecture=prefecture,
        birth_place_label=birth_place_label,
        birth_lat=birth_lat,
        birth_lng=birth_lng,
        tz_name=tz_name,
        gender=gender,
        house_system=house_system,
        include_asteroids=False,
        include_shichusuimei=False,
        include_transit=True,
        transit_start_date=transit_start_date,
        transit_days=transit_days,
        birth_time_accuracy=birth_time_accuracy,
        birth_time_range=birth_time_range,
        birth_time_note=birth_time_note,
        data_role="addon",
    )
    meta = full_doc.get("meta") or {}
    western = ((full_doc.get("systems") or {}).get("western") or {})
    transit = dict(western.get("transit") or {})
    try:
        from services.light_yaml import build_light_astrology_yaml

        current_date = None
        if transit_start_date is not None:
            current_date = transit_start_date.astimezone(ZoneInfo(tz_name)).date()
        light_yaml_text = build_light_astrology_yaml(full_yaml_text, doc=full_doc, current_date=current_date)
        light_doc = yaml.safe_load(light_yaml_text) or {}
        light_transit = (((light_doc.get("systems") or {}).get("western") or {}).get("transit") or {})
        if light_transit.get("today") is not None:
            transit["today"] = light_transit.get("today")
        if light_transit.get("next_31_days_summary") is not None:
            transit["next_31_days_summary"] = light_transit.get("next_31_days_summary")
    except Exception:
        pass
    if isinstance(transit.get("next_31_days_summary"), dict):
        summary = transit["next_31_days_summary"]
        summary.setdefault("key_aspects", [])
        summary.setdefault("active_periods", [])
        summary.setdefault("easy_to_move_days", [])
        summary.setdefault("caution_days", [])
    addon_prompt_text = TRANSIT_31DAYS_ADDON_PROMPT.strip() + "\n"
    if transit_days != 38:
        addon_prompt_text = addon_prompt_text.replace("38日", f"{transit_days}日")
    doc = {
        "version": "nanami-products-yaml-addon-v1",
        "meta": {
            **meta,
            "schema_version": meta.get("schema_version") or "1.1",
            "product_type": "western_31days_transit_addon",
            "data_role": "addon",
            "addon_type": "western_31days_transit",
            "source_logic": "western_full_31days_transit_calculation",
        },
        "base": {
            "target_product_type": "western_basic",
            "target_system": "western",
            "merge_path": "systems.western.transit",
            "compatible_with": ["western_basic", "personal_ai_astrology_yaml_natal"],
        },
        "product": {
            "type": "western_31days_transit_addon",
            "label": "ホロスコープ：38日トランジット追加",
            "options": {
                "addon": True,
                "western_natal": False,
                "asteroids": False,
                "transit": True,
                "transit_days": transit_days,
                "shichusuimei": False,
            },
        },
        "generated_at": full_doc.get("generated_at"),
        "calculation": full_doc.get("calculation") or {},
        "birth_time": full_doc.get("birth_time") or {},
        "interpretation_flags": full_doc.get("interpretation_flags") or {},
        "assets": {
            "yaml_addon": {
                "available": True,
                "merge_path": "systems.western.transit",
            },
            "horoscope_svg": {"available": False},
            "shichusuimei_svg": {"available": False},
        },
        "input": full_doc.get("input") or {},
        "usage_note": {
            "for_ai": "これは追加部品データです。基本版ホロスコープYAMLと一緒にAIへ貼り付けて使ってください。",
            "merge_instruction": "systems.western.transit を、同じ出生情報で作成済みの基本版YAMLへ追加する想定です。",
            "not_included": f"出生図全体・小惑星・四柱推命・鑑定本文は含みません。{transit_days}日トランジット追加用の計算済みデータです。",
        },
        "systems": {
            "western": {
                "natal": None,
                "asteroids": None,
                "transit": transit,
            },
            "shichusuimei": None,
        },
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    return yaml_text, addon_prompt_text, doc


def refresh_dynamic_transit_yaml(full_yaml_text: str) -> str:
    from services.light_yaml import build_transit_astrology_yaml

    return build_transit_astrology_yaml(full_yaml_text)


SHICHU_FORTUNE_CYCLES_ADDON_PROMPT = """あなたは四柱推命の鑑定者です。以下のYAMLは、四柱推命基本版に後から追加する大運・流年データです。

重要ルール:
- このYAML単体を四柱推命の基本命式全体として扱わないでください。
- 先に読み込ませた四柱推命基本版YAMLと一緒にAIへ貼り付けて使ってください。
- systems.shichusuimei.normalized_data.daiun と systems.shichusuimei.normalized_data.annual_fortune を追加部品として読んでください。
- 大運・流年の干支、年齢、関係性、計算前提は変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を根拠として、長期運勢と今年の流れを読んでください。

以下のYAMLを読み込んで、四柱推命基本版データと組み合わせて解釈してください。
"""


def build_shichu_fortune_cycles_addon_yaml(
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
    birth_time_accuracy: str = "auto",
    birth_time_range: dict[str, Any] | None = None,
    birth_time_note: str | None = None,
    day_change_at_23: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    _full_yaml_text, _full_prompt_text, full_doc = build_product_yaml(
        title=title,
        birth_date=birth_date,
        birth_time=birth_time,
        prefecture=prefecture,
        birth_place_label=birth_place_label,
        birth_lat=birth_lat,
        birth_lng=birth_lng,
        tz_name=tz_name,
        gender=gender,
        include_asteroids=False,
        include_shichusuimei=True,
        include_transit=False,
        day_change_at_23=day_change_at_23,
        birth_time_accuracy=birth_time_accuracy,
        birth_time_range=birth_time_range,
        birth_time_note=birth_time_note,
        data_role="addon",
    )
    meta = full_doc.get("meta") or {}
    shichu = (full_doc.get("systems") or {}).get("shichusuimei") or {}
    normalized = shichu.get("normalized_data") or {}
    daiun = normalized.get("daiun") or {}
    annual_fortune = normalized.get("annual_fortune") or {}
    shichu_input = shichu.get("input") or {}
    assumptions = shichu_input.get("assumptions") or {}
    doc = {
        "version": "nanami-products-yaml-addon-v1",
        "meta": {
            **meta,
            "schema_version": meta.get("schema_version") or "1.1",
            "product_type": "shichu_fortune_cycles_addon",
            "data_role": "addon",
            "addon_type": "shichu_fortune_cycles",
            "source_logic": "shichu_full_fortune_cycles_calculation",
        },
        "base": {
            "target_product_type": "shichu",
            "target_system": "shichusuimei",
            "merge_path": "systems.shichusuimei",
            "compatible_with": ["shichu", "personal_ai_astrology_yaml"],
        },
        "product": {
            "type": "shichu_fortune_cycles_addon",
            "label": "四柱推命：大運・流年追加",
            "options": {
                "addon": True,
                "western_natal": False,
                "asteroids": False,
                "transit": False,
                "shichusuimei": True,
                "fortune_cycles": True,
            },
        },
        "generated_at": full_doc.get("generated_at"),
        "calculation": {
            "engine": "nanami-products shichusuimei",
            "timezone": tz_name,
            "day_change_at_23": day_change_at_23,
            "year_boundary_rule": assumptions.get("year_boundary_rule"),
            "daiun_start_mode": assumptions.get("daiun_start_mode"),
        },
        "birth_time": full_doc.get("birth_time") or {},
        "interpretation_flags": full_doc.get("interpretation_flags") or {},
        "assets": {
            "yaml_addon": {
                "available": True,
                "merge_path": "systems.shichusuimei",
            },
            "horoscope_svg": {"available": False},
            "shichusuimei_svg": {"available": False},
        },
        "input": full_doc.get("input") or {},
        "usage_note": {
            "for_ai": "これは追加部品データです。四柱推命基本版YAMLと一緒にAIへ貼り付けて使ってください。",
            "merge_instruction": "systems.shichusuimei.normalized_data.daiun と annual_fortune を、同じ出生情報で作成済みの四柱推命基本版YAMLへ追加する想定です。",
            "not_included": "基本命式全体・通変星一覧・十二運一覧・神殺・五行バランス・鑑定本文は含みません。大運・流年追加用の計算済みデータです。",
            "reference_scope": "流年の十神・十二運を読むため、日主と計算前提だけを最小参照情報として含めています。",
        },
        "systems": {
            "western": None,
            "shichusuimei": {
                "normalized_data": {
                    "daiun": daiun,
                    "annual_fortune": annual_fortune,
                },
                "reference": {
                    "day_master": shichu.get("day_master"),
                    "assumptions": {
                        "tz_name": assumptions.get("tz_name"),
                        "day_change_at_23": assumptions.get("day_change_at_23"),
                        "day_boundary_rule": assumptions.get("day_boundary_rule"),
                        "year_boundary_rule": assumptions.get("year_boundary_rule"),
                        "daiun_start_mode": assumptions.get("daiun_start_mode"),
                    },
                    "note": "大運・流年の解釈に必要な最小参照です。基本命式の代替としては使わないでください。",
                },
            },
        },
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    return yaml_text, SHICHU_FORTUNE_CYCLES_ADDON_PROMPT.strip() + "\n", doc
