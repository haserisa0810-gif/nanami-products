"""Build a provider-neutral, date-specific AI prompt for planner buyers."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import yaml

from services.yaml_exporter import build_transit_for_profile


def build_daily_ai_prompt(*, chart_yaml: str, target_date: date, lang: str = "ja") -> str:
    source_doc = yaml.safe_load(chart_yaml) or {}
    source = source_doc.get("input") or {}
    # English planners display the international sky in UTC. Keep the
    # date-specific prompt on that same calendar day instead of silently
    # recalculating it in the buyer's local timezone.
    tz_name = "UTC" if lang == "en" else str(source.get("timezone") or "Asia/Tokyo")
    western = ((source_doc.get("systems") or {}).get("western") or {})
    natal = western.get("natal") or {}
    natal_bodies = natal.get("bodies") or {}
    natal_houses = natal.get("houses") or {}
    lat = source.get("birth_lat")
    lng = source.get("birth_lng")
    if not natal_bodies or lat is None or lng is None:
        raise ValueError("chart YAML is missing stored natal data or birth coordinates")
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=ZoneInfo(tz_name))
    transit = build_transit_for_profile(
        profile="standard",
        start_date=start,
        days=1,
        lat=float(lat),
        lng=float(lng),
        pref_name=str(source.get("prefecture") or source.get("birth_place") or ""),
        tz_name=tz_name,
        natal_bodies=natal_bodies,
        natal_houses=natal_houses,
    )
    daily = transit.get("daily") or []
    day_data = daily[0] if daily else {}
    ai_data = {
        "target_date": target_date.isoformat(),
        "timezone": tz_name,
        "natal_bodies": natal.get("bodies") or {},
        "transit": {
            "date": day_data.get("date"),
            "time": day_data.get("time"),
            "transiting_bodies": day_data.get("transiting_bodies") or {},
            "natal_aspects": day_data.get("natal_aspects") or [],
            "moon_timepoints": day_data.get("moon_timepoints") or [],
        },
    }
    data_text = yaml.safe_dump(ai_data, allow_unicode=True, sort_keys=False)
    if lang == "en":
        instruction = (
            "Interpret the calculated astrology data below without recalculating it. "
            "Explain this person's day in plain language under: overall theme, work, "
            "relationships, emotional/physical condition, helpful actions, and cautions. "
            "Treat astrology as a reflective aid, not a certainty or professional advice."
        )
    else:
        instruction = (
            "以下の計算済み占星術データを再計算せずに読み解いてください。専門用語を減らし、"
            "この人の一日について「全体テーマ・仕事・人間関係・心身の状態・おすすめの行動・"
            "気をつけたいこと」に分けて説明してください。断定や不安をあおる表現を避け、"
            "占星術は振り返りのヒントとして扱ってください。"
        )
    return f"{instruction}\n\n```yaml\n{data_text}```\n"
