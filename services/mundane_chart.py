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
SIGN_LABELS = ["♈︎", "♉︎", "♊︎", "♋︎", "♌︎", "♍︎", "♎︎", "♏︎", "♐︎", "♑︎", "♒︎", "♓︎"]
SIGN_NAMES = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
NEAR_BODY_CLUSTER_DEGREES = 22
PLANET_RADIAL_STEP = 18
ASPECT_DEFINITIONS = [
    {
        "type": "conjunction",
        "angle": 0,
        "orb": 8,
        "symbol": "☌",
        "style": {"stroke": "#605b54", "stroke_width": "1.35", "opacity": ".32", "stroke_linecap": "round"},
    },
    {
        "type": "sextile",
        "angle": 60,
        "orb": 4,
        "symbol": "✶",
        "style": {"stroke": "#4e86b8", "stroke_width": "1.2", "opacity": ".34", "stroke_linecap": "round"},
    },
    {
        "type": "square",
        "angle": 90,
        "orb": 6,
        "symbol": "□",
        "style": {"stroke": "#c96a5f", "stroke_width": "1.35", "opacity": ".38", "stroke_linecap": "round"},
    },
    {
        "type": "trine",
        "angle": 120,
        "orb": 6,
        "symbol": "△",
        "style": {"stroke": "#3f7fb4", "stroke_width": "1.3", "opacity": ".36", "stroke_linecap": "round"},
    },
    {
        "type": "quincunx",
        "angle": 150,
        "orb": 3,
        "symbol": "⚻",
        "style": {"stroke": "#509476", "stroke_width": "1.15", "opacity": ".34", "stroke_dasharray": "7 8", "stroke_linecap": "round"},
    },
    {
        "type": "opposition",
        "angle": 180,
        "orb": 8,
        "symbol": "☍",
        "style": {"stroke": "#bf555d", "stroke_width": "1.45", "opacity": ".40", "stroke_linecap": "round"},
    },
    {
        "type": "semi-sextile",
        "angle": 30,
        "orb": 2,
        "symbol": "⚺",
        "minor": True,
        "style": {"stroke": "#7aa5c4", "stroke_width": ".85", "opacity": ".20", "stroke_dasharray": "3 7", "stroke_linecap": "round"},
    },
    {
        "type": "semi-square",
        "angle": 45,
        "orb": 2,
        "symbol": "∠",
        "minor": True,
        "style": {"stroke": "#d08b82", "stroke_width": ".85", "opacity": ".22", "stroke_dasharray": "3 7", "stroke_linecap": "round"},
    },
    {
        "type": "sesqui-square",
        "angle": 135,
        "orb": 2,
        "symbol": "⚼",
        "minor": True,
        "style": {"stroke": "#d08b82", "stroke_width": ".85", "opacity": ".22", "stroke_dasharray": "3 7", "stroke_linecap": "round"},
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


def _shorten_label(value: str, limit: int = 28) -> str:
    stripped = value.strip()
    return stripped if len(stripped) <= limit else f"{stripped[: limit - 1]}…"


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
    if not sorted_items:
        return []
    clusters: list[list[dict[str, Any]]] = []
    cluster: list[dict[str, Any]] = []

    previous_lon: float | None = None
    for item in sorted_items:
        lon = float(item["lon"])
        if previous_lon is None or abs(lon - previous_lon) <= NEAR_BODY_CLUSTER_DEGREES:
            cluster.append(item)
        else:
            clusters.append(cluster)
            cluster = [item]
        previous_lon = lon
    clusters.append(cluster)

    if len(clusters) > 1:
        first_lon = float(clusters[0][0]["lon"])
        last_lon = float(clusters[-1][-1]["lon"])
        wrap_distance = (first_lon + 360) - last_lon
        if wrap_distance <= NEAR_BODY_CLUSTER_DEGREES:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    for cluster in clusters:
        cluster_size = len(cluster)
        center = (cluster_size - 1) / 2
        for idx, clustered in enumerate(cluster):
            offset = (idx - center) * PLANET_RADIAL_STEP
            clustered["radial_offset"] = offset
            clustered["label_offset"] = offset * 1.25
            clustered["label_shift"] = (idx - center) * 34
            clustered["cluster_index"] = idx
            clustered["cluster_size"] = cluster_size
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
    target_year = context.get("target_year")
    target_month = context.get("target_month")
    date_label = str(snapshot.get("date") or "")
    time_label = str(snapshot.get("time") or "")
    timezone_label = str(snapshot.get("timezone") or "")

    width = 1280
    height = 670
    cx = 370
    cy = 335
    outer = 294
    zodiac = 232
    sign_r = 266
    planet_r = 194
    inner = 132
    aspect_r = 92
    info_x = 760
    if target_year and target_month:
        chart_title = f"{target_year}年{target_month}月 月次マンデンチャート"
    else:
        chart_title = _shorten_label(title, 22)

    parts: list[str] = [
        f'<svg class="mundane-chart-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="月次マンデンチャート">',
        "<defs>",
        '<style>.mundane-chart-svg text{font-family:"Noto Sans Symbols 2","Noto Sans Symbols","Segoe UI Symbol","Noto Sans JP",Arial,sans-serif}.title{font-size:30px;font-weight:700}.meta{font-size:18px}.caption{font-size:16px}.small{font-size:13px}.sign{font-size:27px}.planet{font-size:25px}.angle-label{font-size:15px;font-weight:700}.retro{font-size:11px;font-weight:700}.degree{font-size:10px;paint-order:stroke;stroke:#fffdf9;stroke-width:3px;stroke-linejoin:round}</style>',
        "</defs>",
        '<rect width="1280" height="670" rx="0" fill="#fffaf5"/>',
        '<rect x="38" y="38" width="1204" height="594" rx="30" fill="#fffdf9" stroke="#eadcc8" stroke-width="1.2"/>',
        _circle(cx, cy, outer, fill="#fff8ed", stroke="#d9c3a8", stroke_width="1.7"),
        _circle(cx, cy, zodiac, fill="#fffdf9", stroke="#ceb18c", stroke_width="1.1"),
        _circle(cx, cy, inner, fill="#fffaf3", stroke="#ead6bc", stroke_width=".9"),
        _circle(cx, cy, aspect_r, fill="none", stroke="#efddc3", stroke_width=".8"),
        _text(info_x, 178, chart_title, fill="#3b2b1d", text_anchor="start", class_="title"),
        _text(info_x, 220, f"{date_label} {time_label} {timezone_label}".strip(), fill="#80684a", text_anchor="start", class_="meta"),
        _text(info_x, 274, "月初の天体配置をもとにした", fill="#6d5a43", text_anchor="start", class_="caption"),
        _text(info_x, 302, "月次マンデン用チャート", fill="#6d5a43", text_anchor="start", class_="caption"),
        _text(info_x, 354, "ハウスなし / 社会全体のテーマを見る参考図", fill="#9a8061", text_anchor="start", class_="small"),
    ]

    for lon in range(0, 360, 30):
        parts.append(_line(cx, cy, inner, zodiac, lon, stroke="#d0b690", stroke_width="1"))
    for lon in range(0, 360, 10):
        tick_inner = zodiac - (16 if lon % 30 == 0 else 9)
        parts.append(_line(cx, cy, tick_inner, zodiac, lon, stroke="#dec9ab", stroke_width=".8", opacity=".62"))
    for i, label in enumerate(SIGN_LABELS):
        x, y = _polar(cx, cy, sign_r, i * 30 + 15)
        parts.append(_text(x, y, label, fill="#7b6347", text_anchor="middle", class_="sign"))

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
        radial_offset = float(item.get("radial_offset", 0))
        radius = planet_r + radial_offset
        x, y = _polar(cx, cy, radius, lon)
        parts.append(f'<g data-body="{html.escape(item["name"])}">')
        circle_radius = 16 if item.get("angle_point") else 18
        if radius >= planet_r:
            leader_start = planet_r
            leader_end = radius - circle_radius - 4
        else:
            leader_start = radius + circle_radius + 4
            leader_end = planet_r
        if abs(radial_offset) > 1 and abs(leader_end - leader_start) > 2:
            parts.append(
                _line(
                    cx,
                    cy,
                    leader_start,
                    leader_end,
                    lon,
                    stroke="#d8bd96",
                    stroke_width=".8",
                    stroke_dasharray="2 6",
                    opacity=".78",
                    data_leader="offset",
                )
            )
        parts.append(_circle(x, y, circle_radius, fill="#fffdf9", stroke="#ad8d62", stroke_width="1", opacity=".88"))
        label_class = "angle-label" if item.get("angle_point") else "planet"
        parts.append(_text(x, y, str(item["symbol"]), fill="#3c2a1a", text_anchor="middle", class_=label_class))
        if item.get("retrograde"):
            parts.append(_text(x + 14, y - 14, "R", fill="#9b3d35", text_anchor="middle", class_="retro"))
        label_radius = min(radius + 34, sign_r - 18)
        label_x, label_y = _polar(cx, cy, label_radius, lon)
        parts.append(
            _text(
                label_x,
                label_y + float(item.get("label_shift", 0)),
                _degree_label(lon),
                fill="#6a5135",
                text_anchor="middle",
                class_="degree",
            )
        )
        parts.append(_line(cx, cy, inner, radius - 22, lon, stroke="#e2c9a6", stroke_width=".75", stroke_dasharray="2 7", opacity=".72"))
        parts.append(f'<title>{html.escape(item["name"])} {_degree_label(lon)}{" R" if item.get("retrograde") else ""}</title>')
        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)
