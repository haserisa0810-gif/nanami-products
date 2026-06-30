from __future__ import annotations

import html
import math
from typing import Any

import yaml

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
ASPECT_DEFINITIONS = [
    {
        "type": "conjunction",
        "angle": 0,
        "orb": 8,
        "symbol": "☌",
        "style": {"stroke": "#5f5b54", "stroke_width": "2.1", "opacity": ".54"},
    },
    {
        "type": "sextile",
        "angle": 60,
        "orb": 4,
        "symbol": "✶",
        "style": {"stroke": "#367cb6", "stroke_width": "1.9", "opacity": ".58"},
    },
    {
        "type": "square",
        "angle": 90,
        "orb": 6,
        "symbol": "□",
        "style": {"stroke": "#c55548", "stroke_width": "2.2", "opacity": ".64"},
    },
    {
        "type": "trine",
        "angle": 120,
        "orb": 6,
        "symbol": "△",
        "style": {"stroke": "#2f70ad", "stroke_width": "2.1", "opacity": ".62"},
    },
    {
        "type": "quincunx",
        "angle": 150,
        "orb": 3,
        "symbol": "⚻",
        "style": {"stroke": "#3c8a65", "stroke_width": "1.8", "opacity": ".58", "stroke_dasharray": "8 7"},
    },
    {
        "type": "opposition",
        "angle": 180,
        "orb": 8,
        "symbol": "☍",
        "style": {"stroke": "#b83e45", "stroke_width": "2.3", "opacity": ".66"},
    },
    {
        "type": "semi-sextile",
        "angle": 30,
        "orb": 2,
        "symbol": "⚺",
        "minor": True,
        "style": {"stroke": "#6fa2c9", "stroke_width": "1.2", "opacity": ".32", "stroke_dasharray": "4 7"},
    },
    {
        "type": "semi-square",
        "angle": 45,
        "orb": 2,
        "symbol": "∠",
        "minor": True,
        "style": {"stroke": "#d1847a", "stroke_width": "1.2", "opacity": ".34", "stroke_dasharray": "4 6"},
    },
    {
        "type": "sesqui-square",
        "angle": 135,
        "orb": 2,
        "symbol": "⚼",
        "minor": True,
        "style": {"stroke": "#d1847a", "stroke_width": "1.2", "opacity": ".34", "stroke_dasharray": "4 6"},
    },
]


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
    attrs.setdefault("dominant_baseline", "middle")
    return f'<text x="{x:.2f}" y="{y:.2f}" {_attrs(**attrs)}>{html.escape(value)}</text>'


def _degree_label(lon: float) -> str:
    normalized = lon % 360
    sign_index = int(normalized // 30)
    degree = normalized - sign_index * 30
    return f"{SIGN_NAMES[sign_index]} {degree:.1f}°"


def _body_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = (doc.get("monthly_snapshot") or {}) if isinstance(doc, dict) else {}
    planets = (snapshot.get("planets") or {}) if isinstance(snapshot, dict) else {}
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
                "angle_point": False,
            }
        )
    angle_sources = [
        ("ascendant", "ASC", "ASC"),
        ("asc", "ASC", "ASC"),
        ("midheaven", "MC", "MC"),
        ("mc", "MC", "MC"),
    ]
    angles = snapshot.get("angles") if isinstance(snapshot, dict) else {}
    houses = snapshot.get("houses") if isinstance(snapshot, dict) else {}
    for source in (angles, houses, snapshot):
        if not isinstance(source, dict):
            continue
        for key, name, symbol in angle_sources:
            raw = source.get(key)
            if isinstance(raw, dict):
                raw = raw.get("longitude")
            if raw is None or any(item["name"] == name for item in items):
                continue
            try:
                lon_float = float(raw)
            except (TypeError, ValueError):
                continue
            items.append(
                {
                    "key": key,
                    "name": name,
                    "symbol": symbol,
                    "lon": lon_float % 360,
                    "retrograde": False,
                    "angle_point": True,
                }
            )
    return items


def _spread_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_items = sorted(items, key=lambda item: item["lon"])
    cluster: list[dict[str, Any]] = []

    def flush_cluster() -> None:
        for idx, clustered in enumerate(cluster):
            clustered["lane"] = idx % 4
            clustered["label_lane"] = idx % 3

    previous_lon: float | None = None
    for item in sorted_items:
        lon = float(item["lon"])
        if previous_lon is None or abs(lon - previous_lon) <= 8:
            cluster.append(item)
        else:
            flush_cluster()
            cluster = [item]
        previous_lon = lon
    flush_cluster()
    return sorted_items


def _angular_distance(lon1: float, lon2: float) -> float:
    diff = abs((lon1 - lon2) % 360)
    return min(diff, 360 - diff)


def _aspects(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    planet_items = [item for item in items if not item.get("angle_point")]
    aspects: list[dict[str, Any]] = []
    for idx, body1 in enumerate(planet_items):
        for body2 in planet_items[idx + 1 :]:
            distance = _angular_distance(float(body1["lon"]), float(body2["lon"]))
            for definition in ASPECT_DEFINITIONS:
                orb = abs(distance - float(definition["angle"]))
                if orb <= float(definition["orb"]):
                    aspects.append(
                        {
                            "planet1": body1["name"],
                            "planet2": body2["name"],
                            "type": definition["type"],
                            "symbol": definition["symbol"],
                            "orb": round(orb, 2),
                            "angle": definition["angle"],
                            "minor": bool(definition.get("minor")),
                            "style": definition["style"],
                        }
                    )
                    break
    return sorted(aspects, key=lambda aspect: (aspect["minor"], aspect["orb"], aspect["angle"]))[:32]


def mundane_aspect_summary_from_yaml(yaml_text: str, *, doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = doc if isinstance(doc, dict) else (yaml.safe_load(yaml_text) or {})
    if not isinstance(doc, dict):
        return []
    items = _spread_items(_body_items(doc))
    return [
        {
            "body1": str(aspect["planet1"]),
            "body2": str(aspect["planet2"]),
            "type": str(aspect["type"]),
            "symbol": str(aspect["symbol"]),
            "orb": float(aspect["orb"]),
            "minor": bool(aspect.get("minor")),
        }
        for aspect in _aspects(items)
    ]


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
        '<style>.mundane-chart-svg text{font-family:"Segoe UI Symbol","Noto Sans Symbols 2","Noto Sans Symbols","Noto Sans JP",Arial,sans-serif}.title{font-size:28px;font-weight:700}.meta{font-size:17px}.sign{font-size:32px}.planet{font-size:30px}.angle-label{font-size:18px;font-weight:700}.retro{font-size:13px;font-weight:700}.degree{font-size:12px}</style>',
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
        style = aspect.get("style")
        if not body1 or not body2 or not style:
            continue
        x1, y1 = _polar(cx, cy, aspect_r, float(body1["lon"]))
        x2, y2 = _polar(cx, cy, aspect_r, float(body2["lon"]))
        attrs = dict(style)
        attrs["data_aspect"] = str(aspect.get("type"))
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {_attrs(**attrs)}/>')

    for item in items:
        lon = float(item["lon"])
        lane = int(item.get("lane", 0))
        radius = planet_r - lane * 32
        x, y = _polar(cx, cy, radius, lon)
        parts.append(f'<g data-body="{html.escape(item["name"])}">')
        circle_radius = 24 if item.get("angle_point") else 26
        parts.append(_circle(x, y, circle_radius, fill="#fffaf2", stroke="#8e6d44", stroke_width="1.8"))
        label_class = "angle-label" if item.get("angle_point") else "planet"
        parts.append(_text(x, y, str(item["symbol"]), fill="#3c2a1a", text_anchor="middle", class_=label_class))
        if item.get("retrograde"):
            parts.append(_text(x + 20, y - 18, "R", fill="#8f2d23", text_anchor="middle", class_="retro"))
        label_radius = radius + 50 + int(item.get("label_lane", 0)) * 12
        label_x, label_y = _polar(cx, cy, label_radius, lon)
        parts.append(_text(label_x, label_y, _degree_label(lon), fill="#6a5135", text_anchor="middle", class_="degree"))
        parts.append(_line(cx, cy, inner, radius - 30, lon, stroke="#d3b991", stroke_width="1", stroke_dasharray="3 8"))
        parts.append(f'<title>{html.escape(item["name"])} {_degree_label(lon)}{" R" if item.get("retrograde") else ""}</title>')
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)
