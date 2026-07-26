"""Personal planner delivery — the reusable seam for the FULL bundle (B案) and a
future standalone Planner product (A案).

``build_planner_pdf`` takes the same birth inputs as ``build_product_yaml``,
computes a chart with long-term transits, converts it to the planner's input
YAML (natal + ``transit_long_term`` items), and renders the personal planner
PDF. It has no dependency on the activation/redeem flow, so a standalone
PE-PLAN- code can call it unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
from typing import Any

import yaml

from services.yaml_exporter import build_product_yaml
from services.long_term_transit_yaml import build_ai_long_term_transits_yaml
from services.planner_export import render_personal_planner


def _long_term_items(yaml_text: str) -> list:
    """The transit_long_term items in a chart YAML (empty list when absent).

    Stored charts without the addon carry ``transit_long_term: null``, so a
    plain key lookup is not enough to tell "has data" from "has the key".
    """
    try:
        doc = yaml.safe_load(yaml_text)
    except Exception:
        return []
    if not isinstance(doc, dict):
        return []
    long_term = ((doc.get("systems") or {}).get("western") or {}).get("transit_long_term")
    if not isinstance(long_term, dict):
        return []
    items = long_term.get("items")
    return items if isinstance(items, list) else []


def _apply_display_timezone(yaml_text: str, lang: str) -> str:
    """English planners show the collective sky in UTC (the neutral
    international standard); Japanese planners keep the buyer's local timezone.

    Natal positions are stored as absolute longitudes, so only the planner's
    display/period timezone changes here — birth-chart accuracy is unaffected.
    """
    if lang != "en":
        return yaml_text
    try:
        doc = yaml.safe_load(yaml_text)
    except Exception:
        return yaml_text
    if not isinstance(doc, dict):
        return yaml_text
    if not isinstance(doc.get("input"), dict):
        doc["input"] = {}
    doc["input"]["timezone"] = "UTC"
    long_term = ((doc.get("systems") or {}).get("western") or {}).get("transit_long_term")
    if isinstance(long_term, dict) and isinstance(long_term.get("period"), dict):
        long_term["period"]["timezone"] = "UTC"
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def build_planner_pdf_from_yaml(
    *,
    yaml_text: str,
    lang: str = "ja",
    months: int = 12,
) -> bytes:
    """Render planner bytes from stored natal + long-term-transit YAML.

    Raises ValueError when the YAML carries no long-term transits: without them
    the personal layer (transit seasons, monthly focus dates, the daily "your
    active transits" box) would be silently empty, which is worse than failing.
    """
    if not _long_term_items(yaml_text):
        raise ValueError("YAML has no long-term transit items; personal layer would be empty")
    yaml_text = _apply_display_timezone(yaml_text, lang)
    pdf_path = render_personal_planner(
        yaml_text=yaml_text,
        lang=lang,
        months=months,
    )
    try:
        return pdf_path.read_bytes()
    finally:
        shutil.rmtree(pdf_path.parent, ignore_errors=True)


def build_planner_pdf(
    *,
    title: str | None,
    birth_date: str,
    birth_time: str | None,
    prefecture: str,
    birth_place_label: str | None,
    birth_lat: float | None,
    birth_lng: float | None,
    tz_name: str,
    lang: str = "ja",
    months: int = 12,
    birth_time_accuracy: str = "exact",
    birth_time_range: dict[str, Any] | None = None,
    birth_time_note: str | None = None,
    transit_start_date: datetime | None = None,
) -> bytes:
    """Return personal planner PDF bytes for the given birth data."""
    if lang not in {"ja", "en"}:
        raise ValueError(f"lang must be ja or en, got {lang!r}")
    start = transit_start_date or datetime.now(timezone.utc)
    # A chart doc carrying long-term (weekly-sampled) transits. build_product_yaml
    # stores the block under "transit"; the long-term addon convention remaps it
    # to "transit_long_term" before serialisation.
    _yaml, _prompt, doc = build_product_yaml(
        title=title,
        birth_date=birth_date,
        birth_time=birth_time,
        prefecture=prefecture,
        birth_place_label=birth_place_label,
        birth_lat=birth_lat,
        birth_lng=birth_lng,
        tz_name=tz_name,
        gender="unknown",
        include_asteroids=False,
        include_shichusuimei=False,
        include_transit=True,
        transit_profile="long_term",
        transit_days=max(31, months * 31),
        transit_start_date=start,
        birth_time_accuracy=birth_time_accuracy,
        birth_time_range=birth_time_range,
        birth_time_note=birth_time_note,
    )
    western = ((doc.get("systems") or {}).get("western") or {})
    western["transit_long_term"] = western.get("transit")
    western["transit"] = None
    yaml_text = build_ai_long_term_transits_yaml(doc=doc)
    if not yaml_text.strip():
        raise RuntimeError("long-term transits missing; cannot build planner")
    return build_planner_pdf_from_yaml(
        yaml_text=yaml_text,
        lang=lang,
        months=months,
    )
