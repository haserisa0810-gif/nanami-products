from __future__ import annotations

import html
import math
from datetime import datetime
from typing import Any

from services.location import resolve_prefecture
from services.western_calc import calc_western_from_payload

PLANET_SYMBOLS = {
    "Sun": "☉",
    "Moon": "☽",
    "Mercury": "☿",
    "Venus": "♀",
    "Mars": "♂",
    "Jupiter": "♃",
    "Saturn": "♄",
    "Uranus": "♅",
    "Neptune": "♆",
    "Pluto": "♇",
    "North Node": "☊",
    "South Node": "☋",
    "Lilith": "⚸",
    "Chiron": "⚷",
    "Ceres": "⚳",
    "Pallas": "⚴",
    "Juno": "⚵",
    "Vesta": "⚶",
    "ASC": "ASC",
    "MC": "MC",
}

SIGN_LABELS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
POST_BODIES = {
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "Lilith",
    "Chiron",
    "Ceres",
    "Pallas",
    "Juno",
    "Vesta",
    "ASC",
    "MC",
}
POST_ASPECT_BODIES = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
ASPECT_STYLES = {
    "conjunction": {"stroke": "#8a6d3b", "stroke-width": "2.2", "opacity": ".72"},
    "sextile": {"stroke": "#4f8f7b", "stroke-width": "2", "opacity": ".72"},
    "square": {"stroke": "#b45b50", "stroke-width": "2.6", "opacity": ".82"},
    "trine": {"stroke": "#4b7da8", "stroke-width": "2.4", "opacity": ".78"},
    "opposition": {"stroke": "#9b5f9f", "stroke-width": "2.6", "opacity": ".82"},
}


def _parse_time(value: str | None) -> tuple[int, int]:
    if not value:
        return 12, 0
    parts = value.strip().split(":")
    if len(parts) < 2:
        return int(parts[0]), 0
    return int(parts[0]), int(parts[1])


def _polar(cx: float, cy: float, radius: float, lon: float) -> tuple[float, float]:
    # Astrology charts place Aries at the left and move counter-clockwise.
    angle = math.radians(180 - lon)
    return cx + radius * math.cos(angle), cy - radius * math.sin(angle)


def _line(cx: float, cy: float, r1: float, r2: float, lon: float, **attrs: str) -> str:
    x1, y1 = _polar(cx, cy, r1, lon)
    x2, y2 = _polar(cx, cy, r2, lon)
    attr_text = " ".join(f'{key}="{html.escape(str(value))}"' for key, value in attrs.items())
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {attr_text}/>'


def _circle(cx: float, cy: float, radius: float, **attrs: str) -> str:
    attr_text = " ".join(f'{key}="{html.escape(str(value))}"' for key, value in attrs.items())
    return f'<circle cx="{cx}" cy="{cy}" r="{radius}" {attr_text}/>'


def _text(x: float, y: float, text: str, **attrs: str) -> str:
    attr_text = " ".join(f'{key}="{html.escape(str(value))}"' for key, value in attrs.items())
    return f'<text x="{x:.2f}" y="{y:.2f}" {attr_text}>{html.escape(text)}</text>'


def _directed_midpoint(start: float, end: float) -> float:
    span = (end - start) % 360
    return (start + span / 2) % 360


def _free_line(x1: float, y1: float, x2: float, y2: float, **attrs: str) -> str:
    attr_text = " ".join(f'{key}="{html.escape(str(value))}"' for key, value in attrs.items())
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {attr_text}/>'


def build_post_chart(*, title: str | None, chart_date: str, chart_time: str | None, prefecture: str) -> dict[str, Any]:
    date = datetime.strptime(chart_date, "%Y-%m-%d")
    hour, minute = _parse_time(chart_time)
    place_name, lat, lng = resolve_prefecture(prefecture)
    display_title = (title or "").strip() or f"{chart_date} {place_name}の出生ホロスコープ"

    payload = {
        "year": date.year,
        "month": date.month,
        "day": date.day,
        "hour": hour,
        "minute": minute,
        "lat": lat,
        "lng": lng,
        "city": place_name,
        "tz_offset_hours": 9,
        "include_asteroids": True,
        "include_chiron": True,
        "include_lilith": True,
        "include_vertex": False,
    }
    raw = calc_western_from_payload(payload)
    svg = render_post_chart_svg(raw, title=display_title, chart_date=chart_date, chart_time=f"{hour:02d}:{minute:02d}", place=place_name)
    caption = build_post_caption(raw, title=display_title, chart_date=chart_date, chart_time=f"{hour:02d}:{minute:02d}", place=place_name)
    return {"raw": raw, "svg": svg, "caption": caption, "title": display_title, "place": place_name}


def render_post_chart_svg(raw: dict[str, Any], *, title: str, chart_date: str, chart_time: str, place: str) -> str:
    width = 1080
    height = 1280
    cx = 540
    cy = 640
    outer = 365
    zodiac = 322
    planet_r = 286
    inner = 182
    aspect_r = 140
    house_label_r = 166
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
        "<defs>",
        '<radialGradient id="bg" cx="50%" cy="42%" r="70%"><stop offset="0%" stop-color="#fffaf2"/><stop offset="65%" stop-color="#f3eadc"/><stop offset="100%" stop-color="#e7d5bd"/></radialGradient>',
        '<style>text{font-family:"Segoe UI Symbol","Noto Sans Symbols 2","Noto Sans Symbols",Arial,"Noto Sans JP",sans-serif}.small{font-size:22px;letter-spacing:.08em}.tiny{font-size:16px;letter-spacing:.06em}.planet{font-size:34px;font-weight:400}.angle{font-size:18px;font-weight:700;letter-spacing:.04em}.sign{font-size:34px}.house-number{font-size:24px;font-weight:700}</style>',
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="url(#bg)"/>',
        f'<rect x="52" y="52" width="976" height="{height - 104}" rx="36" fill="none" stroke="#b79b74" stroke-width="2"/>',
        _text(cx, 104, title, fill="#3b2b1d", **{"text-anchor": "middle", "font-size": "42", "font-weight": "700"}),
        _text(cx, 146, f"Natal chart / {chart_date} {chart_time} JST / {place}", fill="#80684a", **{"text-anchor": "middle", "class": "small"}),
        _circle(cx, cy, outer, fill="rgba(255,255,255,.28)", stroke="#9d7c54", **{"stroke-width": "3"}),
        _circle(cx, cy, zodiac, fill="none", stroke="#c8aa82", **{"stroke-width": "1.5"}),
        _circle(cx, cy, inner, fill="rgba(255,255,255,.22)", stroke="#d0b792", **{"stroke-width": "1.2"}),
        _circle(cx, cy, aspect_r, fill="rgba(255,255,255,.12)", stroke="#e0ccb0", **{"stroke-width": "1"}),
    ]

    for lon in range(0, 360, 30):
        parts.append(_line(cx, cy, inner, outer, lon, stroke="#b89a72", **{"stroke-width": "1.4"}))
    for lon in range(0, 360):
        if lon % 10 == 0:
            tick_inner = outer - 24
            stroke_width = "1.4"
            opacity = ".82"
        elif lon % 5 == 0:
            tick_inner = outer - 16
            stroke_width = "1"
            opacity = ".58"
        else:
            tick_inner = outer - 8
            stroke_width = ".7"
            opacity = ".34"
        parts.append(_line(cx, cy, tick_inner, outer, lon, stroke="#d8c4a7", opacity=opacity, **{"stroke-width": stroke_width}))

    for i, label in enumerate(SIGN_LABELS):
        x, y = _polar(cx, cy, 344, i * 30 + 15)
        parts.append(_text(x, y + 11, label, fill="#73593b", **{"text-anchor": "middle", "class": "sign"}))

    houses = sorted(raw.get("houses", []), key=lambda item: int(item.get("house", 0)))
    for house in houses:
        lon = float(house.get("lon", 0))
        width = "2.4" if house.get("house") in {1, 4, 7, 10} else "1"
        parts.append(_line(cx, cy, 92, inner, lon, stroke="#c0a17a", **{"stroke-width": width}))

    bodies = [body for body in raw.get("planets", []) if body.get("name") in POST_BODIES]
    bodies.sort(key=lambda body: float(body.get("lon", 0)))
    visible_bodies = {str(body.get("name")): body for body in bodies}

    for aspect in raw.get("aspects", []):
        if str(aspect.get("planet1")) not in POST_ASPECT_BODIES or str(aspect.get("planet2")) not in POST_ASPECT_BODIES:
            continue
        body1 = visible_bodies.get(str(aspect.get("planet1")))
        body2 = visible_bodies.get(str(aspect.get("planet2")))
        if not body1 or not body2:
            continue
        style = ASPECT_STYLES.get(str(aspect.get("type")))
        if not style:
            continue
        x1, y1 = _polar(cx, cy, aspect_r, float(body1.get("lon", 0)))
        x2, y2 = _polar(cx, cy, aspect_r, float(body2.get("lon", 0)))
        parts.append(_free_line(x1, y1, x2, y2, **style))

    if len(houses) == 12:
        for idx, house in enumerate(houses):
            start = float(house.get("lon", 0))
            end = float(houses[(idx + 1) % 12].get("lon", start))
            mid = _directed_midpoint(start, end)
            x, y = _polar(cx, cy, house_label_r, mid)
            parts.append(_text(x, y + 8, str(house.get("house")), fill="#7d603b", **{"text-anchor": "middle", "class": "house-number"}))

    for idx, body in enumerate(bodies):
        lon = float(body.get("lon", 0))
        radius = planet_r - (idx % 3) * 28
        x, y = _polar(cx, cy, radius, lon)
        name = str(body.get("name"))
        label = PLANET_SYMBOLS.get(name, name)
        klass = "angle" if name in {"ASC", "MC"} else "planet"
        y_offset = 6 if name in {"ASC", "MC"} else 11
        parts.append(_circle(x, y, 28, fill="#fffaf2", stroke="#8e6d44", **{"stroke-width": "1.8"}))
        parts.append(_text(x, y + y_offset, label, fill="#3c2a1a", **{"text-anchor": "middle", "class": klass}))
        parts.append(_line(cx, cy, inner, radius - 32, lon, stroke="#d3b991", **{"stroke-width": "1", "stroke-dasharray": "3 8"}))

    parts.extend([
        _text(cx, 1158, "nanami astro", fill="#8a6c45", **{"text-anchor": "middle", "class": "small"}),
        _text(cx, 1188, "Natal horoscope with asteroids / no transit", fill="#a88d6b", **{"text-anchor": "middle", "class": "tiny"}),
        "</svg>",
    ])
    return "\n".join(parts)


def build_post_caption(raw: dict[str, Any], *, title: str, chart_date: str, chart_time: str, place: str) -> str:
    bodies = {body.get("name"): body for body in raw.get("planets", [])}

    def pos(name: str) -> str:
        body = bodies.get(name)
        if not body:
            return ""
        return f"{name}: {body.get('sign')} {float(body.get('degree', 0)):.1f} deg"

    highlights = [
        item
        for item in [
            pos("Sun"),
            pos("Moon"),
            pos("ASC"),
            pos("MC"),
            pos("Chiron"),
            pos("Ceres"),
            pos("Pallas"),
            pos("Juno"),
            pos("Vesta"),
        ]
        if item
    ]
    lines = [
        title,
        f"{chart_date} {chart_time} JST / {place}",
        "",
        "出生ホロスコープメモ（トランジットなし）",
        *[f"- {item}" for item in highlights],
        "",
        "#占星術 #ホロスコープ #星読み",
    ]
    return "\n".join(lines)
