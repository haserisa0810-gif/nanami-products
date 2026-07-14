from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import logging
import os
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from services.long_term_transit_yaml import compact_long_term_transits_for_ai
from services.yaml_exporter import validate_yaml_option_section_consistency

logger = logging.getLogger(__name__)

KEY_BODY_NAMES = {"Sun", "Moon", "ASC", "MC", "Saturn", "Uranus", "Neptune", "Pluto"}
POSITIVE_ASPECTS = {"trine", "sextile", "conjunction"}
CAUTION_ASPECTS = {"square", "opposition"}


def _natal_output(
    natal: dict[str, Any],
    *,
    aspects: Any,
) -> dict[str, Any]:
    output = {
        "bodies": natal.get("bodies") or {},
        "aspects": aspects,
        "summary": natal.get("summary") or {},
    }
    if "houses" in natal:
        output["houses"] = natal.get("houses") or {}
    provisional = natal.get("time_sensitive_provisional")
    if isinstance(provisional, dict):
        output["time_sensitive_provisional"] = provisional
    return output

MEANING_HINTS = {
    "Sun": "自己表現",
    "Moon": "感情調整",
    "Mercury": "思考整理",
    "Venus": "対人調整",
    "Mars": "行動力",
    "Jupiter": "拡大しすぎ注意",
    "Saturn": "責任と整理",
    "Uranus": "変化対応",
    "Neptune": "直感と境界",
    "Pluto": "深い切り替え",
    "ASC": "見せ方",
    "MC": "仕事の方向性",
}


def _safe_load_yaml(yaml_text: str) -> dict[str, Any]:
    doc = yaml.safe_load(yaml_text) or {}
    return doc if isinstance(doc, dict) else {}


def _transit_timezone_name(doc: dict[str, Any]) -> str:
    western = ((doc.get("systems") or {}).get("western") or {})
    period = ((western.get("transit") or {}).get("period") or {})
    calculation = doc.get("calculation") or {}
    input_block = doc.get("input") or {}
    return str(period.get("timezone") or calculation.get("timezone") or input_block.get("timezone") or "Asia/Tokyo")


def _today_for_doc(doc: dict[str, Any], today: date | None = None) -> date:
    if today:
        return today
    try:
        return datetime.now(ZoneInfo(_transit_timezone_name(doc))).date()
    except Exception:
        return date.today()


def _copy_common_blocks(
    doc: dict[str, Any],
    *,
    product_type: str,
    yaml_variant: str,
    data_role: str | None = None,
    addon_type: str | None = None,
) -> dict[str, Any]:
    source_meta = doc.get("meta") or {}
    resolved_data_role = data_role or source_meta.get("data_role") or "base_chart"
    if resolved_data_role == "base_chart" and source_meta.get("addon_type"):
        resolved_data_role = "addon"
    meta = {
        **source_meta,
        "schema_version": source_meta.get("schema_version") or "1.1",
        "product_type": product_type,
        "data_role": resolved_data_role,
        "yaml_variant": yaml_variant,
    }
    if addon_type:
        meta["addon_type"] = addon_type
    return {
        "meta": meta,
        "base": doc.get("base"),
        "generated_at": doc.get("generated_at"),
        "calculation": doc.get("calculation") or {},
        "birth_time": doc.get("birth_time") or {},
        "interpretation_flags": doc.get("interpretation_flags") or {},
        "assets": {
            **(doc.get("assets") or {}),
            "yaml_base": {"available": True},
            "yaml_lite": {"available": True},
            "yaml_detail": {"available": True},
            "yaml_full": {"available": True},
        },
        "input": doc.get("input") or {},
    }


def transit_period_status(full_yaml_text: str, *, today: date | None = None) -> dict[str, Any]:
    doc = _safe_load_yaml(full_yaml_text)
    period = (((doc.get("systems") or {}).get("western") or {}).get("transit") or {}).get("period") or {}
    start_raw = period.get("start_date")
    days_raw = period.get("days")
    if not start_raw or not days_raw:
        return {"available": False, "expired": False}
    try:
        start_date = date.fromisoformat(str(start_raw))
        days = int(days_raw)
    except (TypeError, ValueError):
        return {"available": False, "expired": False}
    end_date = start_date + timedelta(days=max(days, 1) - 1)
    today_date = _today_for_doc(doc, today)
    return {
        "available": True,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
        "expired": today_date > end_date,
        "today": today_date.isoformat(),
    }


def _orb_limit(item: dict[str, Any]) -> float:
    names = {str(item.get("transit_body") or item.get("body1") or ""), str(item.get("natal_body") or item.get("body2") or "")}
    return 1.5 if names & KEY_BODY_NAMES else 1.0


def _is_key_aspect(item: dict[str, Any]) -> bool:
    orb = item.get("orb")
    if orb is None:
        return False
    try:
        return float(orb) <= _orb_limit(item)
    except (TypeError, ValueError):
        return False


def _meaning_hint(item: dict[str, Any]) -> str:
    transit_body = str(item.get("transit_body") or item.get("body1") or "")
    aspect = str(item.get("aspect") or "")
    base = MEANING_HINTS.get(transit_body, "流れの変化")
    if aspect in CAUTION_ASPECTS:
        return f"{base}、調整"
    if aspect in POSITIVE_ASPECTS:
        return f"{base}、活用"
    return base


def _compact_aspect(item: dict[str, Any], *, include_date: str | None = None) -> dict[str, Any]:
    out = {}
    if include_date:
        out["date"] = include_date
    for key in ("transit_body", "natal_body", "body1", "body2", "aspect", "orb"):
        if key in item:
            out[key] = item[key]
    out["meaning_hint"] = _meaning_hint(item)
    return out


def _natal_aspects_for_output(natal: dict[str, Any]) -> list[dict[str, Any]]:
    body_names = set((natal.get("bodies") or {}).keys())
    aspects = []
    for item in natal.get("aspects", []):
        if not isinstance(item, dict):
            continue
        if item.get("body1") not in body_names or item.get("body2") not in body_names:
            continue
        aspects.append(item)
    return aspects


def _day_score(aspects: list[dict[str, Any]]) -> tuple[int, int]:
    easy = sum(1 for item in aspects if item.get("aspect") in POSITIVE_ASPECTS)
    caution = sum(1 for item in aspects if item.get("aspect") in CAUTION_ASPECTS)
    return easy, caution


def _aspect_date_key(item: dict[str, Any]) -> tuple[str, float]:
    return str(item.get("date") or ""), float(item.get("orb") or 99)


def _aspect_signature(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("transit_body") or item.get("body1") or ""),
        str(item.get("natal_body") or item.get("body2") or ""),
        str(item.get("aspect") or ""),
    )


def _representative_aspects(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    sorted_items = sorted(items, key=_aspect_date_key)
    if len(sorted_items) <= limit:
        return sorted_items

    representatives = [sorted_items[0]]
    if limit >= 2:
        tightest = min(sorted_items, key=lambda item: float(item.get("orb") or 99))
        if tightest not in representatives:
            representatives.append(tightest)
    if limit >= 3 and sorted_items[-1] not in representatives:
        representatives.append(sorted_items[-1])
    return representatives[:limit]


def _active_periods(key_aspects: list[dict[str, Any]], *, source_limit: int = 2) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in key_aspects:
        grouped[(str(item.get("transit_body")), str(item.get("natal_body")), str(item.get("aspect")))].append(item)

    periods: list[dict[str, Any]] = []
    for (_transit, _natal, _aspect), items in grouped.items():
        if len(items) < 2:
            continue
        dates = sorted(str(item.get("date")) for item in items if item.get("date"))
        if not dates:
            continue
        periods.append({
            "start_date": dates[0],
            "end_date": dates[-1],
            "theme": _meaning_hint(items[0]),
            "source_aspects": _representative_aspects(items, limit=source_limit),
        })
    return periods[:8]


def _date_range_from_daily(daily: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    dates = sorted(
        str(item.get("date"))
        for item in daily
        if isinstance(item, dict) and _parse_date(item.get("date"))
    )
    if not dates:
        return None, None
    return dates[0], dates[-1]


def _overall_theme(key_aspects: list[dict[str, Any]], daily: list[dict[str, Any]]) -> str:
    if not key_aspects:
        return "期間全体では、主要アスペクトが比較的少なく、日々の月の動きや基本的な生活リズムを整えやすい流れです。"
    easy_count = sum(1 for item in key_aspects if item.get("aspect") in POSITIVE_ASPECTS)
    caution_count = sum(1 for item in key_aspects if item.get("aspect") in CAUTION_ASPECTS)
    if caution_count > easy_count:
        return "この31日間は、調整・見直し・境界線の整理が継続しやすい時期です。短期的な勢いより、違和感を確かめながら進めると扱いやすくなります。"
    if easy_count > caution_count:
        return "この31日間は、意思表示や行動に移すきっかけを拾いやすい流れです。勢いだけで進めず、日ごとの強弱を見ながら予定を組むと使いやすくなります。"
    return "この31日間は、動きが出やすい日と調整が必要な日が混在します。焦って結論を出すより、流れの強弱を見ながら進めると扱いやすい時期です。"


def _key_dates(
    key_aspects: list[dict[str, Any]],
    *,
    limit: int,
    source_limit: int,
    exclude_signatures: set[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    exclude_signatures = exclude_signatures or set()
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in key_aspects:
        if item.get("date"):
            by_date[str(item["date"])].append(item)

    out: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for date_key, aspects in sorted(by_date.items()):
        sorted_aspects = sorted(aspects, key=lambda item: float(item.get("orb") or 99))
        focused = [item for item in sorted_aspects if _aspect_signature(item) not in exclude_signatures]
        tight = [item for item in focused if float(item.get("orb") or 99) <= 0.5]
        source = (tight or focused)[:source_limit]
        fallback_source = sorted_aspects[:source_limit]
        item = {
            "date": date_key,
            "theme": _meaning_hint((source or fallback_source)[0]),
            "reason": "タイトな主要アスペクト" if tight else "主要アスペクトが重なる日",
            "source_aspects": source,
        }
        fallback.append({**item, "source_aspects": fallback_source})
        if source:
            out.append(item)
    if not out:
        out = fallback[: min(3, limit)]
    return sorted(out, key=lambda item: (str(item["date"]), len(item["source_aspects"])))[:limit]


def _recent_days(daily: list[dict[str, Any]], selected_date: date, *, limit: int = 3, source_limit: int = 1) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for day in daily:
        day_date = _parse_date(day.get("date")) if isinstance(day, dict) else None
        if not day_date or day_date < selected_date:
            continue
        aspects = sorted([
            _compact_aspect(item, include_date=day_date.isoformat())
            for item in day.get("natal_aspects", [])
            if isinstance(item, dict) and _is_key_aspect(item)
        ], key=lambda item: float(item.get("orb") or 99))[:source_limit]
        out.append({
            "date": day_date.isoformat(),
            "theme": _meaning_hint(aspects[0]) if aspects else "大きな切り替わりは少なめ",
            "source_aspects": aspects,
        })
        if len(out) >= limit:
            break
    return out


def _action_hints(easy_days: list[dict[str, Any]], caution_days: list[dict[str, Any]]) -> list[str]:
    hints = []
    if easy_days:
        hints.append("動きが出やすい日は、連絡・相談・意思表示などを前に進める候補日として使えます。")
    if caution_days:
        hints.append("注意日には、即断よりも確認・調整・境界線の見直しを優先してください。")
    hints.append("当日分の詳細を主根拠にし、31日サマリーは流れの強弱を読む補助として使ってください。")
    return hints


def _summary_key_aspects(
    key_aspects: list[dict[str, Any]],
    *,
    limit: int,
    source_limit: int,
    exclude_signatures: set[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    exclude_signatures = exclude_signatures or set()
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in key_aspects:
        signature = _aspect_signature(item)
        if signature in exclude_signatures:
            continue
        grouped[signature].append(item)

    out: list[dict[str, Any]] = []
    for (_transit, _natal, _aspect), items in grouped.items():
        out.extend(_representative_aspects(items, limit=source_limit))
    return sorted(out, key=_aspect_date_key)[:limit]


def _build_31day_summary(
    *,
    transit: dict[str, Any],
    daily: list[dict[str, Any]],
    key_aspects: list[dict[str, Any]],
    easy_days: list[dict[str, Any]],
    caution_days: list[dict[str, Any]],
    selected_date: date,
    max_key_aspects: int,
    max_key_dates: int,
    max_easy_days: int,
    max_caution_days: int,
    max_active_periods: int,
    max_next_few_days: int,
    source_aspect_limit: int,
) -> dict[str, Any]:
    period = dict(transit.get("period") or {})
    start_date, end_date = _date_range_from_daily(daily)
    if start_date:
        period.setdefault("start_date", start_date)
    if end_date:
        period.setdefault("end_date", end_date)
    if daily:
        period.setdefault("days", len(daily))

    active_periods = _active_periods(key_aspects, source_limit=source_aspect_limit)[:max_active_periods]
    period_signatures = {
        _aspect_signature(aspect)
        for period in active_periods
        for aspect in period.get("source_aspects", [])
        if isinstance(aspect, dict)
    }
    key_dates = _key_dates(
        key_aspects,
        limit=max_key_dates,
        source_limit=source_aspect_limit,
        exclude_signatures=period_signatures,
    )
    summary = {
        "period": period,
        "overall_theme": _overall_theme(key_aspects, daily),
        "key_periods": active_periods,
        "key_dates": key_dates,
        "caution_dates": caution_days[:max_caution_days],
        "easy_to_move_days": easy_days[:max_easy_days],
        "next_few_days": _recent_days(
            daily,
            selected_date,
            limit=max_next_few_days,
            source_limit=source_aspect_limit,
        ),
        "action_hints": _action_hints(easy_days, caution_days),
        "key_aspects": _summary_key_aspects(
            key_aspects,
            limit=max_key_aspects,
            source_limit=source_aspect_limit,
            exclude_signatures=period_signatures,
        ),
    }
    if daily and not key_aspects:
        logger.warning("transit_31days_summary_has_daily_but_no_key_aspects days=%s", len(daily))
    return summary


def _summary_log_shape(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {"type": type(summary).__name__, "truthy": bool(summary)}
    return {
        "type": "dict",
        "truthy": bool(summary),
        "keys": sorted(str(key) for key in summary.keys()),
        "period": bool(summary.get("period")),
        "key_periods": len(summary.get("key_periods") or []),
        "key_dates": len(summary.get("key_dates") or []),
        "caution_dates": len(summary.get("caution_dates") or []),
        "easy_to_move_days": len(summary.get("easy_to_move_days") or []),
        "key_aspects": len(summary.get("key_aspects") or []),
    }


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _select_today_entry(
    daily: list[dict[str, Any]],
    doc: dict[str, Any],
    *,
    today: date | None = None,
) -> tuple[dict[str, Any], date, str]:
    today_date = _today_for_doc(doc, today)
    dated_entries = [
        (day_date, day)
        for day in daily
        if isinstance(day, dict) and (day_date := _parse_date(day.get("date")))
    ]
    if not dated_entries:
        return {}, today_date, "no_daily_data"

    for day_date, day in dated_entries:
        if day_date == today_date:
            return day, today_date, "current_date"

    first_date, first_day = dated_entries[0]
    last_date, _last_day = dated_entries[-1]
    if today_date < first_date:
        return first_day, today_date, "before_period_uses_first_day"
    return {}, today_date, "out_of_period"


def build_light_astrology_yaml(
    full_yaml_text: str = "",
    *,
    doc: dict[str, Any] | None = None,
    include_asteroids: bool = False,
    max_key_aspects: int = 5,
    max_key_dates: int = 6,
    max_daily_aspects: int = 2,
    max_easy_days: int = 3,
    max_caution_days: int = 3,
    max_active_periods: int = 3,
    max_next_few_days: int = 3,
    source_aspect_limit: int = 1,
    version: str = "nanami-products-yaml-light-v1",
    product_type: str = "personal_ai_astrology_yaml_light",
    current_date: date | None = None,
) -> str:
    doc = doc if isinstance(doc, dict) else _safe_load_yaml(full_yaml_text)
    western = ((doc.get("systems") or {}).get("western") or {})
    natal = western.get("natal") or {}
    transit = western.get("transit") or {}
    long_term_transit = western.get("transit_long_term") or None
    ai_long_term_transit = compact_long_term_transits_for_ai(long_term_transit) if long_term_transit else None
    daily = transit.get("daily") or []
    today, selected_date, selection_status = _select_today_entry(daily, doc, today=current_date)

    natal_aspects = _natal_aspects_for_output(natal)
    today_aspects = [item for item in today.get("natal_aspects", []) if isinstance(item, dict) and _is_key_aspect(item)]

    key_aspects: list[dict[str, Any]] = []
    easy_days: list[dict[str, Any]] = []
    caution_days: list[dict[str, Any]] = []
    for day in daily:
        date = str(day.get("date") or "")
        aspects = [
            _compact_aspect(item, include_date=date)
            for item in day.get("natal_aspects", [])
            if isinstance(item, dict) and _is_key_aspect(item)
        ]
        aspects = sorted(aspects, key=lambda item: float(item.get("orb") or 99))[:max_daily_aspects]
        key_aspects.extend(aspects)
        if aspects:
            easy, caution = _day_score(aspects)
            if easy >= caution:
                easy_reason = "動きが出やすい配置がある日"
                if caution > 0:
                    easy_reason = "動きが出やすい一方で、調整も必要な日"
                easy_days.append({"date": date, "reason": easy_reason, "source_aspects": aspects[:source_aspect_limit]})
            if caution > 0:
                caution_days.append({"date": date, "reason": "調整が必要な配置がある日", "source_aspects": aspects[:source_aspect_limit]})

    asteroids = western.get("asteroids") if include_asteroids else None
    light = {
        "version": version,
        **_copy_common_blocks(
            doc,
            product_type=product_type,
            yaml_variant="detail" if include_asteroids else "lite",
        ),
        "product": {
            "type": product_type,
            "options": {
                "western_natal": bool(natal),
                "asteroids": bool(asteroids),
                "transit_today": bool(today),
                "transit_31days_summary": bool(daily),
                "western_long_term_transits": bool(long_term_transit),
            },
        },
        "usage_note": {
            "for_ai": "このYAMLはFULL版の計算済みデータから抽出したAI貼り付け用データです。生年月日から再計算せず、この値を根拠にしてください。",
            "full_yaml": "完全版YAMLは検証・保存用です。AI貼り付けにはAI貼り付け版を優先してください。",
        },
        "systems": {
            "western": {
                "natal": _natal_output(
                    natal,
                    aspects={
                        "major_only": True,
                        "items": natal_aspects,
                    },
                ),
                "asteroids": {"bodies": asteroids or {}} if asteroids else None,
                "transit": {
                    "period": transit.get("period") or {},
                    "today": {
                        "selected_date": selected_date.isoformat(),
                        "selection_status": selection_status,
                        "date": today.get("date"),
                        "transiting_bodies": today.get("transiting_bodies") or {},
                        "natal_aspects": today_aspects,
                        "moon_timepoints": {
                            str(item.get("label")): {
                                "time": item.get("time"),
                                "moon": item.get("body"),
                                "natal_aspects": [
                                    aspect for aspect in item.get("natal_aspects", [])
                                    if isinstance(aspect, dict) and _is_key_aspect(aspect)
                                ],
                            }
                            for item in today.get("moon_timepoints", [])
                            if isinstance(item, dict) and item.get("label")
                        },
                    } if today else None,
                    "next_31_days_summary": {} if daily else None,
                } if transit else None,
                "transit_long_term": ai_long_term_transit,
            },
            "shichusuimei": None,
        },
    }
    summary = light["systems"]["western"]["transit"]["next_31_days_summary"] if transit and daily else None
    if summary is not None:
        light["systems"]["western"]["transit"]["next_31_days_summary"] = _build_31day_summary(
            transit=transit,
            daily=daily,
            key_aspects=key_aspects,
            easy_days=easy_days,
            caution_days=caution_days,
            selected_date=selected_date,
            max_key_aspects=max_key_aspects,
            max_key_dates=max_key_dates,
            max_easy_days=max_easy_days,
            max_caution_days=max_caution_days,
            max_active_periods=max_active_periods,
            max_next_few_days=max_next_few_days,
            source_aspect_limit=source_aspect_limit,
        )
    final_summary = None
    if light["systems"]["western"].get("transit"):
        final_summary = light["systems"]["western"]["transit"].get("next_31_days_summary")
    logger.warning(
        "light_yaml_31day_summary_result code_version=%s chart_id=%s product_type=%s version=%s daily_count=%s "
        "today_present=%s transit_31days_summary=%s summary_shape=%s",
        os.getenv("ASSET_VERSION") or os.getenv("K_REVISION") or "local",
        (((doc.get("meta") or {}).get("chart_id")) or ""),
        product_type,
        version,
        len(daily),
        bool(today),
        bool(light["product"]["options"].get("transit_31days_summary")),
        _summary_log_shape(final_summary),
    )
    validate_yaml_option_section_consistency(light)
    return yaml.safe_dump(light, allow_unicode=True, sort_keys=False, width=120)


def build_detail_astrology_yaml(full_yaml_text: str, *, current_date: date | None = None) -> str:
    return build_light_astrology_yaml(
        full_yaml_text,
        include_asteroids=True,
        max_key_aspects=5,
        max_key_dates=7,
        max_daily_aspects=3,
        max_easy_days=5,
        max_caution_days=5,
        max_active_periods=5,
        max_next_few_days=3,
        source_aspect_limit=1,
        version="nanami-products-yaml-detail-v1",
        product_type="personal_ai_astrology_yaml_detail",
        current_date=current_date,
    )


def _build_natal_yaml(full_yaml_text: str, *, include_asteroids: bool, version: str, product_type: str) -> str:
    doc = _safe_load_yaml(full_yaml_text)
    western = ((doc.get("systems") or {}).get("western") or {})
    natal = western.get("natal") or {}
    asteroids = western.get("asteroids") or None
    base = {
        "version": version,
        **_copy_common_blocks(
            doc,
            product_type=product_type,
            yaml_variant="natal_asteroids" if include_asteroids else "natal",
        ),
        "product": {
            "type": product_type,
            "options": {
                "western_natal": bool(natal),
                "asteroids": bool(asteroids) if include_asteroids else False,
                "transit_today": False,
                "transit_31days_summary": False,
            },
        },
        "usage_note": {
            "for_ai": "この基礎YAMLはネイタルデータ中心の継続利用用データです。生年月日から再計算せず、この値を根拠にしてください。",
            "transit_updates": "月次トランジット追加データと組み合わせる場合は、このYAMLを土台として使用してください。",
        },
        "systems": {
            "western": {
                "natal": _natal_output(
                    natal,
                    aspects=natal.get("aspects") or [],
                ),
                "asteroids": {"bodies": asteroids or {}} if include_asteroids and asteroids else None,
                "transit": None,
            },
            "shichusuimei": None,
        },
    }
    validate_yaml_option_section_consistency(base)
    return yaml.safe_dump(base, allow_unicode=True, sort_keys=False, width=120)


def build_base_astrology_yaml(full_yaml_text: str) -> str:
    return _build_natal_yaml(
        full_yaml_text,
        include_asteroids=False,
        version="nanami-products-yaml-natal-v1",
        product_type="personal_ai_astrology_yaml_natal",
    )


def build_natal_asteroids_yaml(full_yaml_text: str) -> str:
    return _build_natal_yaml(
        full_yaml_text,
        include_asteroids=True,
        version="nanami-products-yaml-natal-asteroids-v1",
        product_type="personal_ai_astrology_yaml_natal_asteroids",
    )


def build_transit_astrology_yaml(full_yaml_text: str) -> str:
    doc = _safe_load_yaml(full_yaml_text)
    western = ((doc.get("systems") or {}).get("western") or {})
    transit = western.get("transit") or None
    out = {
        "version": "nanami-products-yaml-transit-v1",
        **_copy_common_blocks(
            doc,
            product_type="personal_ai_astrology_yaml_transit",
            yaml_variant="transit",
            data_role="addon",
            addon_type="western_31days_transit",
        ),
        "product": {
            "type": "personal_ai_astrology_yaml_transit",
            "options": {
                "western_natal": False,
                "asteroids": False,
                "transit_today": bool((transit or {}).get("today")),
                "transit_31days_summary": bool((transit or {}).get("daily")),
            },
        },
        "usage_note": {
            "for_ai": "このYAMLはトランジット追加データです。ネイタル保存用YAMLと組み合わせて使用してください。",
            "base_yaml": "出生図の解釈は、別保存したネイタルYAMLを土台にしてください。",
        },
        "systems": {
            "western": {
                "natal": None,
                "asteroids": None,
                "transit": transit,
            },
            "shichusuimei": None,
        },
    }
    validate_yaml_option_section_consistency(out)
    return yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)
