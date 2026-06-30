from __future__ import annotations

import html
import math
from typing import Any

import yaml

from services.western_calc import calc_aspects

MUNDANE_CHART_BODIES = [
    ("sun", "Sun", "☉"),
    ("moon", "Moon", "☽"),
    ("mercury", "Mercury", "☿"),
    ("venus", "Venus", "♀"),
    ("mars", "Mars", "♂"),
    ("jupiter", "Jupiter", "♃"),
    ("saturn", "Saturn", "♄"),
    ("uranus", "Uranus", "♅"),
    ("neptune", "Neptune", "♆"),
    ("pluto", "Pluto", "♇"),
]
SIGN_LABELS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
SIGN_NAMES = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
ASPECT_STYLES = {
    "conjunction": {"stroke": "#8a6d3b", "stroke_width": "2.2", "opacity": ".72"},
    "sextile": {"stroke": "#4f8f7b", "stroke_width": "2", "opacity": ".72"},
    "square": {"stroke": "#b45b50", "stroke_width": "2.6", "opacity": ".82"},
    "trine": {"stroke": "#4b7da8", "stroke_width": "2.4", "opacity": ".78"},
    "opposition": {"stroke": "#9b5f9f", "stroke_width": "2.6", "opacity": ".82"},
}


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


def _degree_label(lon: float) -> str:
    normalized = lon % 360
    sign_index = int(normalized // 30)
    degree = normalized - sign_index * 30
    return f"{SIGN_NAMES[sign_index]} {degree:.1f}°"


def _body_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    planets = (((doc.get("monthly_snapshot") or {}).get("planets") or {}) if isinstance(doc, dict) else {})
    if not isinstance(planets, dict):
        return []
    items: list[dict[str, Any]] = []
    for key, name, symbol in MUNDANE_CHART_BODIES:
        body = planets.get(key)
        if not isinstance(body, dict):
            continue
        lon = body.get("longitude")
        if lon is None:
            continue
        try:
            lon_float = float(lon)
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "key": key,
                "name": name,
                "symbol": symbol,
                "lon": lon_float % 360,
                "retrograde": bool(body.get("retrograde")),
            }
        )
    return items


def _spread_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_items = sorted(items, key=lambda item: item["lon"])
    for idx, item in enumerate(sorted_items):
        item["lane"] = idx % 3
    return sorted_items


def _aspects(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aspect_input = [{"name": item["name"], "lon": item["lon"]} for item in items]
    return [
        aspect
        for aspect in calc_aspects(aspect_input)
        if aspect.get("type") in ASPECT_STYLES and float(aspect.get("orb") or 99) <= 4.0
    ][:18]


def build_mundane_chart_svg_from_yaml(yaml_text: str, *, doc: dict[str, Any] | None = None) -> str | None:
    doc = doc if isinstance(doc, dict) else (yaml.safe_load(yaml_text) or {})
    if not isinstance(doc, dict):
        return None
    items = _spread_items(_body_items(doc))
    if not items:
        return None

    context = doc.get("mundane_context") or {}
    snapshot = doc.get("monthly_snapshot") or {}
    title = str(context.get("title") or "Monthly mundane chart").strip()
    date_label = str(snapshot.get("date") or "")
    time_label = str(snapshot.get("time") or "")
    timezone_label = str(snapshot.get("timezone") or "")

    width = 920
    height = 920
    cx = 460
    cy = 460
    outer = 370
    zodiac = 326
    planet_r = 286
    inner = 182
    aspect_r = 132

    parts: list[str] = [
        f'<svg class="mundane-chart-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="月次マンデンチャート">',
        "<defs>",
        '<style>.mundane-chart-svg text{font-family:"Segoe UI Symbol","Noto Sans Symbols 2","Noto Sans Symbols","Noto Sans JP",Arial,sans-serif}.title{font-size:28px;font-weight:700}.meta{font-size:17px}.sign{font-size:32px}.planet{font-size:31px}.retro{font-size:13px;font-weight:700}.degree{font-size:12px}</style>',
        "</defs>",
        '<rect width="920" height="920" rx="18" fill="#fffaf2"/>',
        _circle(cx, cy, outer, fill="rgba(255,255,255,.32)", stroke="#9d7c54", stroke_width="3"),
        _circle(cx, cy, zodiac, fill="none", stroke="#c8aa82", stroke_width="1.5"),
        _circle(cx, cy, inner, fill="rgba(255,255,255,.22)", stroke="#d0b792", stroke_width="1.2"),
        _circle(cx, cy, aspect_r, fill="rgba(255,255,255,.12)", stroke="#e0ccb0", stroke_width="1"),
        _text(cx, 54, title, fill="#3b2b1d", text_anchor="middle", class_="title"),
        _text(cx, 84, f"{date_label} {time_label} {timezone_label}".strip(), fill="#80684a", text_anchor="middle", class_="meta"),
    ]

    for lon in range(0, 360, 30):
        parts.append(_line(cx, cy, inner, outer, lon, stroke="#b89a72", stroke_width="1.4"))
    for lon in range(0, 360, 10):
        tick_inner = outer - (24 if lon % 30 == 0 else 14)
        parts.append(_line(cx, cy, tick_inner, outer, lon, stroke="#d8c4a7", stroke_width="1", opacity=".68"))
    for i, label in enumerate(SIGN_LABELS):
        x, y = _polar(cx, cy, 345, i * 30 + 15)
        parts.append(_text(x, y + 10, label, fill="#73593b", text_anchor="middle", class_="sign"))

    body_by_name = {item["name"]: item for item in items}
    for aspect in _aspects(items):
        body1 = body_by_name.get(str(aspect.get("planet1")))
        body2 = body_by_name.get(str(aspect.get("planet2")))
        style = ASPECT_STYLES.get(str(aspect.get("type")))
        if not body1 or not body2 or not style:
            continue
        x1, y1 = _polar(cx, cy, aspect_r, float(body1["lon"]))
        x2, y2 = _polar(cx, cy, aspect_r, float(body2["lon"]))
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {_attrs(**style)}/>')

    for item in items:
        lon = float(item["lon"])
        radius = planet_r - int(item.get("lane", 0)) * 28
        x, y = _polar(cx, cy, radius, lon)
        parts.append(f'<g data-body="{html.escape(item["name"])}">')
        parts.append(_circle(x, y, 26, fill="#fffaf2", stroke="#8e6d44", stroke_width="1.8"))
        parts.append(_text(x, y + 10, str(item["symbol"]), fill="#3c2a1a", text_anchor="middle", class_="planet"))
        if item.get("retrograde"):
            parts.append(_text(x + 20, y - 18, "R", fill="#8f2d23", text_anchor="middle", class_="retro"))
        label_x, label_y = _polar(cx, cy, radius + 48, lon)
        parts.append(_text(label_x, label_y + 4, _degree_label(lon), fill="#6a5135", text_anchor="middle", class_="degree"))
        parts.append(_line(cx, cy, inner, radius - 30, lon, stroke="#d3b991", stroke_width="1", stroke_dasharray="3 8"))
        parts.append(f'<title>{html.escape(item["name"])} {_degree_label(lon)}{" R" if item.get("retrograde") else ""}</title>')
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)
