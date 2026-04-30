from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
    gender: str = "unknown",
    house_system: str = "P",
    include_asteroids: bool = False,
    include_shichusuimei: bool = False,
    include_transit: bool = False,
    day_change_at_23: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    y, m, d = _split_date(birth_date)
    hour, minute = _split_time(birth_time)
    pref_name, lat, lng = resolve_prefecture(prefecture)
    payload = {
        "year": y, "month": m, "day": d, "hour": hour, "minute": minute,
        "lat": lat, "lng": lng, "city": pref_name, "tz_offset_hours": 9,
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
    systems: dict[str, Any] = {
        "western": {
            "natal": {
                "engine": "Swiss Ephemeris",
                "house_system": house_system,
                "subject": raw.get("subject"),
                "bodies": core,
                "houses": houses,
                "aspects": [_format_aspect(a) for a in raw.get("aspects", [])],
                "summary": _summaries(raw.get("planets", [])),
                "skipped_bodies": raw.get("skipped_bodies", []),
            },
            "asteroids": asteroids if include_asteroids else None,
            "transit": {
                "period": {"days": 30},
                "note": "トランジット1ヶ月付きの商品です。詳細な日別トランジット本文はAI鑑定側で生成してください。",
            } if include_transit else None,
        },
        "shichusuimei": None,
    }
    if include_shichusuimei:
        from services.shichusuimei_calc import calc_shichusuimei_from_payload
        systems["shichusuimei"] = calc_shichusuimei_from_payload(
            {"year": y, "month": m, "day": d, "hour": hour, "minute": minute, "gender": gender},
            tz_name="Asia/Tokyo",
            day_change_at_23=day_change_at_23,
        )
    doc = {
        "version": "nanami-products-yaml-v1",
        "product": {
            "type": "personal_ai_astrology_yaml",
            "options": {
                "western_natal": True,
                "asteroids": include_asteroids,
                "transit": include_transit,
                "shichusuimei": include_shichusuimei,
            },
        },
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "input": {
            "title": title,
            "birth_date": birth_date,
            "birth_time": birth_time or "unknown_noon_used",
            "prefecture": pref_name,
            "timezone": "Asia/Tokyo",
            "gender": gender,
        },
        "usage_note": {
            "for_ai": "このYAMLは計算済みデータです。AIに解釈させる場合、生年月日から再計算させず、この値を根拠にしてください。",
            "not_included": "鑑定本文は含みません。AI解釈用の構造化データです。",
        },
        "systems": systems,
    }
    yaml_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    return yaml_text, build_prompt(), doc
