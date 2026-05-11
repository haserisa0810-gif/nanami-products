from __future__ import annotations

import html
import math
from typing import Any

import yaml

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
    "Vertex": "Vx",
    "ASC": "ASC",
    "MC": "MC",
}

SIGN_LABELS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
CORE_BODIES = [
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
    "North Node",
    "South Node",
    "ASC",
    "MC",
]
ASTEROID_BODIES = ["Lilith", "Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Vertex"]


def _polar(cx: float, cy: float, radius: float, lon: float) -> tuple[float, float]:
    angle = math.radians(180 - lon)
    return cx + radius * math.cos(angle), cy - radius * math.sin(angle)


def _attrs(**attrs: Any) -> str:
    normalized = []
    for key, value in attrs.items():
        attr_name = key.rstrip("_").replace("_", "-")
        normalized.append(f'{attr_name}="{html.escape(str(value))}"')
    return " ".join(normalized)


def _line(cx: float, cy: float, r1: float, r2: float, lon: float, **attrs: Any) -> str:
    x1, y1 = _polar(cx, cy, r1, lon)
    x2, y2 = _polar(cx, cy, r2, lon)
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {_attrs(**attrs)}/>'


def _circle(cx: float, cy: float, radius: float, **attrs: Any) -> str:
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" {_attrs(**attrs)}/>'


def _text(x: float, y: float, value: str, **attrs: Any) -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" {_attrs(**attrs)}>{html.escape(value)}</text>'


def _display_title(value: Any, fallback: str) -> str:
    title = str(value or "").strip()
    if not title:
        return fallback
    if title.endswith("さん"):
        return title
    return f"{title}さん"


def _body_items(bodies: dict[str, Any], names: list[str], *, group: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name in names:
        body = bodies.get(name)
        if not isinstance(body, dict):
            continue
        lon = body.get("absolute_longitude")
        if lon is None:
            continue
        items.append({
            "name": name,
            "lon": float(lon),
            "house": body.get("house"),
            "group": group,
        })
    return items


def _spread_bodies(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_items = sorted(items, key=lambda item: item["lon"])
    for idx, item in enumerate(sorted_items):
        item["lane"] = idx % 3
    return sorted_items


def _directed_midpoint(start: float, end: float) -> float:
    span = (end - start) % 360
    return (start + span / 2) % 360


def build_horoscope_svg_from_yaml(yaml_text: str, *, compact: bool = False) -> str | None:
    doc = yaml.safe_load(yaml_text) or {}
    natal = (((doc.get("systems") or {}).get("western") or {}).get("natal") or {})
    bodies = natal.get("bodies") or {}
    houses = natal.get("houses") or {}
    asteroids = ((doc.get("systems") or {}).get("western") or {}).get("asteroids") or {}
    if not isinstance(bodies, dict) or not isinstance(houses, dict):
        return None
    if not bodies or not houses:
        return None

    input_block = doc.get("input") or {}
    title = _display_title(input_block.get("title"), "Natal chart")
    chart_date = input_block.get("birth_date") or ""
    chart_time = input_block.get("calculation_time") or input_block.get("birth_time") or ""
    place = input_block.get("birth_place") or ""

    if compact:
        width = 860
        height = 860
        cx = 430
        cy = 430
        outer = 350
        zodiac = 308
        planet_r = 274
        inner = 182
        aspect_r = 138
        house_label_r = 166
    else:
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
        f'<svg class="horoscope-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="SVGホロスコープ図">',
        "<defs>",
        '<style>.horoscope-svg text{font-family:"Segoe UI Symbol","Noto Sans Symbols 2","Noto Sans Symbols",Arial,"Noto Sans JP",sans-serif}.small{font-size:22px;letter-spacing:.08em}.tiny{font-size:16px;letter-spacing:.06em}.planet{font-size:34px;font-weight:400}.angle{font-size:18px;font-weight:700;letter-spacing:.04em}.sign{font-size:34px}.house-number{font-size:24px;font-weight:700}.asteroid-body{display:none}.show-asteroids .asteroid-body{display:inline}.hide-houses .house-line,.hide-houses .house-label,.hide-houses .angle-body{display:none}</style>',
        "</defs>",
    ]
    if not compact:
        parts[2:2] = [
            '<radialGradient id="bg" cx="50%" cy="42%" r="70%"><stop offset="0%" stop-color="#fffaf2"/><stop offset="65%" stop-color="#f3eadc"/><stop offset="100%" stop-color="#e7d5bd"/></radialGradient>',
        ]
        parts.extend([
        f'<rect width="{width}" height="{height}" fill="url(#bg)"/>',
        f'<rect x="52" y="52" width="976" height="{height - 104}" rx="36" fill="none" stroke="#b79b74" stroke-width="2"/>',
        _text(cx, 104, str(title), fill="#3b2b1d", text_anchor="middle", font_size="42", font_weight="700"),
        _text(cx, 146, f"Natal chart / {chart_date} {chart_time} / {place}", fill="#80684a", text_anchor="middle", class_="small"),
        ])
    else:
        parts.append(_circle(cx, cy, outer + 18, fill="#fffaf2", stroke="none"))
    parts.extend([
        _circle(cx, cy, outer, fill="rgba(255,255,255,.28)", stroke="#9d7c54", stroke_width="3"),
        _circle(cx, cy, zodiac, fill="none", stroke="#c8aa82", stroke_width="1.5"),
        _circle(cx, cy, inner, fill="rgba(255,255,255,.22)", stroke="#d0b792", stroke_width="1.2"),
        _circle(cx, cy, aspect_r, fill="rgba(255,255,255,.12)", stroke="#e0ccb0", stroke_width="1"),
    ])

    for lon in range(0, 360, 30):
        parts.append(_line(cx, cy, inner, outer, lon, stroke="#b89a72", stroke_width="1.4"))

    tick_step = 10 if compact else 1
    for lon in range(0, 360, tick_step):
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
        parts.append(_line(cx, cy, tick_inner, outer, lon, stroke="#d8c4a7", stroke_width=stroke_width, opacity=opacity))

    for i, label in enumerate(SIGN_LABELS):
        x, y = _polar(cx, cy, 344, i * 30 + 15)
        parts.append(_text(x, y + 11, label, fill="#73593b", text_anchor="middle", class_="sign"))

    house_items: list[tuple[int, float]] = []
    for key, house in houses.items():
        if not isinstance(house, dict) or house.get("absolute_longitude") is None:
            continue
        house_items.append((int(key), float(house["absolute_longitude"])))
    house_items.sort(key=lambda item: item[0])
    for house_num, lon in house_items:
        stroke_width = "2.4" if house_num in {1, 4, 7, 10} else "1"
        parts.append(_line(cx, cy, 92, inner, lon, stroke="#c0a17a", stroke_width=stroke_width, class_="house-line"))
    if len(house_items) == 12:
        for idx, (house_num, lon) in enumerate(house_items):
            next_lon = house_items[(idx + 1) % 12][1]
            mid = _directed_midpoint(lon, next_lon)
            x, y = _polar(cx, cy, house_label_r, mid)
            parts.append(_text(x, y + 8, str(house_num), fill="#7d603b", text_anchor="middle", class_="house-number house-label"))

    body_items = _spread_bodies(
        _body_items(bodies, CORE_BODIES, group="core") + _body_items(asteroids, ASTEROID_BODIES, group="asteroid")
    )
    body_by_name = {item["name"]: item for item in body_items}
    aspect_styles = {
        "conjunction": {"stroke": "#8a6d3b", "stroke_width": "2.2", "opacity": ".72"},
        "sextile": {"stroke": "#4f8f7b", "stroke_width": "2", "opacity": ".72"},
        "square": {"stroke": "#b45b50", "stroke_width": "2.6", "opacity": ".82"},
        "trine": {"stroke": "#4b7da8", "stroke_width": "2.4", "opacity": ".78"},
        "opposition": {"stroke": "#9b5f9f", "stroke_width": "2.6", "opacity": ".82"},
    }
    for aspect in natal.get("aspects") or []:
        if not isinstance(aspect, dict):
            continue
        body1 = body_by_name.get(str(aspect.get("body1")))
        body2 = body_by_name.get(str(aspect.get("body2")))
        style = aspect_styles.get(str(aspect.get("aspect")))
        if not body1 or not body2 or not style:
            continue
        x1, y1 = _polar(cx, cy, aspect_r, float(body1["lon"]))
        x2, y2 = _polar(cx, cy, aspect_r, float(body2["lon"]))
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {_attrs(**style)}/>')

    for item in body_items:
        name = item["name"]
        lon = item["lon"]
        radius = planet_r - int(item.get("lane", 0)) * 28
        x, y = _polar(cx, cy, radius, lon)
        class_name = "asteroid-body" if item["group"] == "asteroid" else "core-body"
        if name in {"ASC", "MC"}:
            class_name += " angle-body"
        label_class = "angle" if name in {"ASC", "MC"} else "planet"
        label = PLANET_SYMBOLS.get(name, name)
        parts.append(f'<g class="{class_name}" data-body="{html.escape(name)}">')
        parts.append(_circle(x, y, 28, fill="#fffaf2", stroke="#8e6d44", stroke_width="1.8"))
        parts.append(_text(x, y + (6 if name in {"ASC", "MC"} else 11), label, fill="#3c2a1a", text_anchor="middle", class_=label_class))
        parts.append(_line(cx, cy, inner, radius - 32, lon, stroke="#d3b991", stroke_width="1", stroke_dasharray="3 8"))
        parts.append(f'<title>{html.escape(name)} {lon:.4f}°</title>')
        parts.append("</g>")

    if not compact:
        parts.append(_text(cx, 1158, "nanami astro", fill="#8a6c45", text_anchor="middle", class_="small"))
        parts.append(_text(cx, 1188, "Natal horoscope with asteroids / no transit", fill="#a88d6b", text_anchor="middle", class_="tiny"))
    parts.append("</svg>")
    return "\n".join(parts)


def has_asteroid_svg_data(yaml_text: str) -> bool:
    doc = yaml.safe_load(yaml_text) or {}
    asteroids = ((doc.get("systems") or {}).get("western") or {}).get("asteroids") or {}
    if not isinstance(asteroids, dict):
        return False
    return any(isinstance(asteroids.get(name), dict) and asteroids[name].get("absolute_longitude") is not None for name in ASTEROID_BODIES)
