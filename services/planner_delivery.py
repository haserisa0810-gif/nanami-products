"""Personal planner delivery — the reusable seam for the FULL bundle (B案) and a
future standalone Planner product (A案).

``build_planner_pdf`` takes the same birth inputs as ``build_product_yaml``,
computes a chart with long-term transits, converts it to the planner's input
YAML (natal + ``transit_long_term`` items), and renders the personal planner
PDF. It has no dependency on the activation/redeem flow, so a standalone
PE-PLAN- code can call it unchanged.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import shutil
from typing import Any

import yaml

from services.yaml_exporter import build_product_yaml, build_transit_for_profile
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
    """International planners show the collective sky in UTC (the neutral
    standard); Japanese planners keep the buyer's local timezone.

    Natal positions are stored as absolute longitudes, so only the planner's
    display/period timezone changes here — birth-chart accuracy is unaffected.
    """
    if lang == "ja":
        return yaml_text
    try:
        doc = yaml.safe_load(yaml_text)
    except Exception:
        return yaml_text
    if not isinstance(doc, dict):
        return yaml_text
    long_term = ((doc.get("systems") or {}).get("western") or {}).get("transit_long_term")
    if isinstance(long_term, dict) and isinstance(long_term.get("period"), dict):
        long_term["period"]["timezone"] = "UTC"
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def build_planner_yaml_from_natal_yaml(
    *,
    chart_yaml: str,
    lang: str,
    months: int = 12,
    transit_start_date: datetime,
) -> str:
    """Add a planner transit layer to a stored natal chart without recalculating it.

    This is used by fixed demos whose natal positions are the source of truth.
    The birth profile retains its original timezone, while the English planner
    may use UTC for its calendar and transit samples.
    """
    if lang not in {"ja", "en", "es", "de"}:
        raise ValueError(f"unsupported planner language: {lang!r}")
    loaded = yaml.safe_load(chart_yaml) or {}
    if not isinstance(loaded, dict):
        raise ValueError("chart YAML must contain a mapping")
    doc = copy.deepcopy(loaded)
    source = doc.get("input") or {}
    western = ((doc.get("systems") or {}).get("western") or {})
    natal = western.get("natal") or {}
    natal_bodies = natal.get("bodies") or {}
    natal_houses = natal.get("houses") or {}
    if not natal_bodies:
        raise ValueError("chart YAML has no stored natal bodies")
    lat = source.get("birth_lat")
    lng = source.get("birth_lng")
    if lat is None or lng is None:
        raise ValueError("chart YAML has no birth coordinates")
    display_tz = str(source.get("timezone") or "Asia/Tokyo") if lang == "ja" else "UTC"
    western["transit_long_term"] = build_transit_for_profile(
        profile="long_term",
        start_date=transit_start_date,
        days=max(31, months * 31),
        lat=float(lat),
        lng=float(lng),
        pref_name=str(source.get("prefecture") or source.get("birth_place") or ""),
        tz_name=display_tz,
        natal_bodies=natal_bodies,
        natal_houses=natal_houses,
    )
    western["transit"] = None
    yaml_text = build_ai_long_term_transits_yaml(doc=doc)
    if not yaml_text.strip():
        raise RuntimeError("long-term transits missing; cannot build planner")
    return yaml_text


def build_planner_pdf_from_yaml(
    *,
    yaml_text: str,
    lang: str = "ja",
    months: int = 12,
    chart_url: str | None = None,
    holiday_country: str | None = None,
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
        chart_url=chart_url,
        holiday_country=holiday_country,
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
    chart_url: str | None = None,
    holiday_country: str | None = None,
) -> bytes:
    """Return personal planner PDF bytes for the given birth data."""
    if lang not in {"ja", "en", "es", "de"}:
        raise ValueError(f"unsupported planner language: {lang!r}")
    # The planner runs in whole calendar months, so the transit scan has to
    # start at the first of the month too — otherwise the days before "today"
    # fall outside the computed windows and read as having no transits.
    start = (transit_start_date or datetime.now(timezone.utc)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
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
        chart_url=chart_url,
        holiday_country=holiday_country,
    )
