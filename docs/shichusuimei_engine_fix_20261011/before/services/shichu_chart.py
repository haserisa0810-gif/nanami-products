from __future__ import annotations

import html
from typing import Any

import yaml

PILLARS = [
    ("year", "年柱"),
    ("month", "月柱"),
    ("day", "日柱"),
    ("hour", "時柱"),
]

ELEMENT_COLORS = {
    "木": "#6f8f4f",
    "火": "#b65b44",
    "土": "#a98349",
    "金": "#9a8b73",
    "水": "#517c9b",
}


def _attrs(**attrs: Any) -> str:
    normalized = []
    for key, value in attrs.items():
        attr_name = key.rstrip("_").replace("_", "-")
        normalized.append(f'{attr_name}="{html.escape(str(value))}"')
    return " ".join(normalized)


def _text(x: float, y: float, value: Any, **attrs: Any) -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" {_attrs(**attrs)}>{html.escape(_label(value))}</text>'


def _rect(x: float, y: float, width: float, height: float, **attrs: Any) -> str:
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" {_attrs(**attrs)}/>'


def _label(value: Any, fallback: str = "不明") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _display_title(value: Any, fallback: str) -> str:
    title = str(value or "").strip()
    if not title:
        return fallback
    if title.endswith("さん"):
        return title
    return f"{title}さん"


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _hidden_stems_label(items: Any) -> str:
    if isinstance(items, list):
        values = [_label(item, "") for item in items if _label(item, "")]
        return "・".join(values) if values else "不明"
    return _label(items)


def _hidden_ten_gods_label(items: Any) -> str:
    if not isinstance(items, list):
        return "不明"
    labels = []
    for item in items:
        if isinstance(item, dict):
            labels.append(f"{_label(item.get('stem'), '')}{_label(item.get('ten_god'), '')}")
    return " / ".join(label for label in labels if label) or "不明"


def _pillar_ten_god(ten_gods: dict[str, Any], pillar_key: str) -> str:
    if pillar_key == "day":
        return "日主"
    value = _nested(ten_gods, "pillars", pillar_key, "ten_god")
    return _label(value)


def _has_shichu_data(doc: dict[str, Any]) -> bool:
    normalized = _nested(doc, "systems", "shichusuimei", "normalized_data")
    return isinstance(normalized, dict) and isinstance(normalized.get("pillars"), dict)


def has_shichusuimei_chart_data(yaml_text: str) -> bool:
    try:
        doc = yaml.safe_load(yaml_text) or {}
    except Exception:
        return False
    return _has_shichu_data(doc)


def build_shichusuimei_svg_from_yaml(yaml_text: str, *, compact: bool = False, doc: dict[str, Any] | None = None) -> str | None:
    doc = doc if isinstance(doc, dict) else (yaml.safe_load(yaml_text) or {})
    if not _has_shichu_data(doc):
        return None

    shichu = _nested(doc, "systems", "shichusuimei") or {}
    normalized = shichu.get("normalized_data") or {}
    input_block = doc.get("input") or {}
    title = _display_title(input_block.get("title"), "Four pillars")
    birth_date = input_block.get("birth_date") or ""
    calculation_time = input_block.get("calculation_time") or input_block.get("birth_time") or ""
    place = input_block.get("birth_place") or ""

    pillars = normalized.get("pillars") or {}
    hidden_stems = normalized.get("hidden_stems") or {}
    ten_gods = normalized.get("ten_gods") or {}
    hidden_ten_gods = (ten_gods.get("hidden_stems") if isinstance(ten_gods, dict) else {}) or {}
    twelve_fortune = normalized.get("twelve_fortune") or {}
    kubo = normalized.get("kubo") or {}
    five_elements = (normalized.get("five_elements") or {}).get("with_hidden_stems") or (normalized.get("five_elements") or {}).get("visible") or {}
    daiun_items = _nested(normalized, "daiun", "items") or []
    day_master = _label(_nested(ten_gods, "day_master"), "")

    if compact:
        width = 940
        height = 780
        pad = 42
        title_y = 58
        table_y = 118
        table_h = 382
        bar_y = 548
    else:
        width = 1080
        height = 1280
        pad = 74
        title_y = 112
        table_y = 216
        table_h = 470
        bar_y = 770

    table_x = pad
    table_w = width - pad * 2
    label_w = 142 if compact else 160
    col_w = (table_w - label_w) / 4
    row_labels = [
        ("干支", "kanshi"),
        ("天干", "stem"),
        ("地支", "branch"),
        ("蔵干", "hidden_stems"),
        ("通変星", "ten_god"),
        ("蔵干通変", "hidden_ten_god"),
        ("十二運", "twelve_fortune"),
        ("空亡", "kubo"),
    ]
    header_h = 54 if compact else 62
    row_h = (table_h - header_h) / len(row_labels)

    parts: list[str] = [
        f'<svg class="shichu-chart-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="四柱推命 命式図">',
        "<defs>",
        '<style>.shichu-chart-svg text{font-family:"Noto Sans JP","Hiragino Sans","Yu Gothic","Meiryo",sans-serif}.title{font-size:42px;font-weight:700}.meta{font-size:21px;letter-spacing:.03em}.small{font-size:19px}.cell-label{font-size:20px;font-weight:700}.pillar-head{font-size:24px;font-weight:700}.kanshi,.cell-main,.cell-sub{font-size:23px;font-weight:600}.footer{font-size:18px;letter-spacing:.04em}</style>',
        '<radialGradient id="shichuBg" cx="50%" cy="42%" r="72%"><stop offset="0%" stop-color="#fffaf2"/><stop offset="66%" stop-color="#f3eadc"/><stop offset="100%" stop-color="#e7d5bd"/></radialGradient>',
        "</defs>",
    ]

    if compact:
        parts.append(_rect(0, 0, width, height, fill="#fffaf2"))
    else:
        parts.extend([
            _rect(0, 0, width, height, fill="url(#shichuBg)"),
            _rect(52, 52, width - 104, height - 104, rx="36", fill="none", stroke="#b79b74", stroke_width="2"),
        ])

    parts.append(_text(width / 2, title_y, str(title), fill="#3b2b1d", text_anchor="middle", class_="title"))
    parts.append(_text(width / 2, title_y + 40, f"四柱推命 命式図 / {birth_date} {calculation_time} / {place}", fill="#80684a", text_anchor="middle", class_="meta"))
    if day_master:
        parts.append(_text(width / 2, title_y + 76, f"日主: {day_master}", fill="#8a5c24", text_anchor="middle", font_size="24", font_weight="700"))

    parts.append(_rect(table_x, table_y, table_w, table_h, rx="18", fill="rgba(255,255,255,.5)", stroke="#9d7c54", stroke_width="2"))
    parts.append(_rect(table_x, table_y, label_w, header_h, fill="#ead8bd", stroke="#c1a077", stroke_width="1"))
    for idx, (_key, label) in enumerate(PILLARS):
        x = table_x + label_w + idx * col_w
        parts.append(_rect(x, table_y, col_w, header_h, fill="#ead8bd", stroke="#c1a077", stroke_width="1"))
        parts.append(_text(x + col_w / 2, table_y + 38, label, fill="#4a321f", text_anchor="middle", class_="pillar-head"))

    for row_idx, (row_label, field) in enumerate(row_labels):
        y = table_y + header_h + row_idx * row_h
        parts.append(_rect(table_x, y, label_w, row_h, fill="#f5ead8", stroke="#d3b991", stroke_width="1"))
        parts.append(_text(table_x + label_w / 2, y + row_h / 2 + 7, row_label, fill="#74563a", text_anchor="middle", class_="cell-label"))
        for col_idx, (pillar_key, _pillar_label) in enumerate(PILLARS):
            x = table_x + label_w + col_idx * col_w
            fill = "#fffaf2"
            if pillar_key == "day" and field in {"kanshi", "stem"}:
                fill = "#f3dfb7"
            parts.append(_rect(x, y, col_w, row_h, fill=fill, stroke="#d3b991", stroke_width="1"))
            pillar = pillars.get(pillar_key) if isinstance(pillars, dict) else {}
            if not isinstance(pillar, dict):
                pillar = {}
            if field == "hidden_stems":
                value = _hidden_stems_label(hidden_stems.get(pillar_key))
                class_name = "cell-sub"
            elif field == "hidden_ten_god":
                value = _hidden_ten_gods_label(hidden_ten_gods.get(pillar_key))
                class_name = "cell-sub"
            elif field == "ten_god":
                value = _pillar_ten_god(ten_gods, pillar_key)
                class_name = "cell-main"
            elif field == "twelve_fortune":
                value = _label(twelve_fortune.get(pillar_key))
                class_name = "cell-main"
            elif field == "kubo":
                hits = kubo.get("hits") if isinstance(kubo, dict) else {}
                value = "該当" if isinstance(hits, dict) and hits.get(pillar_key) else "なし"
                class_name = "cell-main"
            else:
                value = _label(pillar.get(field))
                class_name = "kanshi" if field == "kanshi" else "cell-main"
            parts.append(_text(x + col_w / 2, y + row_h / 2 + 7, value, fill="#3c2a1a", text_anchor="middle", class_=class_name))

    empty_branches = kubo.get("empty_branches") if isinstance(kubo, dict) else []
    empty_text = "・".join(empty_branches) if isinstance(empty_branches, list) and empty_branches else "不明"
    parts.append(_text(table_x, table_y + table_h + 36, f"空亡: {empty_text}", fill="#705235", class_="small"))

    bar_x = table_x
    bar_w = table_w
    max_value = max([float(v) for v in five_elements.values()] or [1.0])
    parts.append(_text(bar_x, bar_y, "五行バランス", fill="#3b2b1d", font_size="28", font_weight="700"))
    element_y = bar_y + 34
    for idx, element in enumerate(["木", "火", "土", "金", "水"]):
        value = float(five_elements.get(element) or 0)
        y = element_y + idx * 45
        parts.append(_text(bar_x, y + 24, element, fill="#4a321f", font_size="24", font_weight="700"))
        parts.append(_rect(bar_x + 44, y + 4, bar_w - 120, 24, rx="12", fill="#eadbc6", stroke="#d2b991", stroke_width="1"))
        parts.append(_rect(bar_x + 44, y + 4, (bar_w - 120) * (value / max_value if max_value else 0), 24, rx="12", fill=ELEMENT_COLORS[element]))
        parts.append(_text(bar_x + bar_w - 54, y + 24, str(int(value) if value.is_integer() else value), fill="#4a321f", text_anchor="middle", font_size="20"))

    if isinstance(daiun_items, list) and daiun_items:
        daiun_y = element_y + 5 * 45 + 40
        parts.append(_text(bar_x, daiun_y, "大運（先頭のみ）", fill="#3b2b1d", font_size="24", font_weight="700"))
        chips = []
        for item in daiun_items[:5]:
            if isinstance(item, dict):
                age = _label(item.get("start_age"), "")
                kanshi = _label(item.get("kanshi"), "")
                chips.append(f"{age}歳 {kanshi}".strip())
        parts.append(_text(bar_x, daiun_y + 34, " / ".join(chips) or "不明", fill="#705235", class_="small"))

    if not compact:
        parts.append(_text(width / 2, height - 122, "nanami astro", fill="#8a6c45", text_anchor="middle", class_="meta"))
        parts.append(_text(width / 2, height - 92, "Four pillars chart from calculated data", fill="#a88d6b", text_anchor="middle", class_="footer"))

    parts.append("</svg>")
    return "\n".join(parts)


def render_shichusuimei_png_from_svg(svg: str) -> bytes | None:
    try:
        import cairosvg  # type: ignore
    except Exception:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"))
    except Exception:
        return None


def is_shichusuimei_png_renderer_available() -> bool:
    try:
        import cairosvg  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True
