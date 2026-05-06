from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from services.api_tags import integration_tags, shichu_tags, transit_tags, western_tags
from services.api_yaml import build_handoff_yaml
from services.yaml_exporter import build_product_yaml

API_VERSION = "1.0"
ENGINE_NAME = "nanami-products"


class ApiCalcError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _error(code: str, message: str, *, status_code: int = 400) -> tuple[dict[str, Any], int]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }, status_code


def _success(endpoint: str, input_data: dict[str, Any], doc: dict[str, Any]) -> tuple[dict[str, Any], int]:
    raw_western = doc.get("systems", {}).get("western")
    raw_shichu = doc.get("systems", {}).get("shichusuimei")
    raw_transit = None
    if isinstance(raw_western, dict):
        raw_transit = raw_western.get("transit")

    western = raw_western if raw_western is not None else None
    shichu = raw_shichu if raw_shichu is not None else None

    tags_western = western_tags(western)
    tags_shichu = shichu_tags(shichu)
    tags_transit = transit_tags(raw_transit)
    tags_integration = integration_tags(western, shichu, raw_transit)

    writing = input_data.get("writing", {})
    tone = writing.get("tone", {}) if isinstance(writing, dict) else {}
    focus_areas_raw = writing.get("focus_areas", []) if isinstance(writing, dict) else []
    if isinstance(focus_areas_raw, list):
        focus_areas = [str(item) for item in focus_areas_raw if str(item).strip()]
    elif str(focus_areas_raw).strip():
        focus_areas = [str(focus_areas_raw).strip()]
    else:
        focus_areas = []
    writing_hints = {
        "tone": {
            "sharpness": int(tone.get("sharpness", 50)),
            "warmth": int(tone.get("warmth", 50)),
            "mystical": int(tone.get("mystical", 50)),
        },
        "focus_areas": focus_areas,
        "key_concepts": [
            tag["label"]
            for tag in sorted(
                [*tags_western, *tags_shichu, *tags_transit, *tags_integration],
                key=lambda item: (-int(item.get("strength", 0)), item.get("id", "")),
            )
            if int(tag.get("strength", 0)) > 0
        ][:5],
    }

    response_doc = {
        "meta": {
            "api_version": API_VERSION,
            "engine": ENGINE_NAME,
            "endpoint": endpoint,
        },
        "input": input_data,
        "raw_data": {
            "western": western,
            "shichu": shichu,
            "transit": raw_transit,
        },
        "interpreted_tags": {
            "western": tags_western,
            "shichu": tags_shichu,
            "transit": tags_transit,
            "integration": tags_integration,
        },
        "writing_hints": writing_hints,
        "ai_prompt_context": {
            "role": "構造分析型の占星術鑑定",
            "instruction": "raw_dataを直接断定せず、interpreted_tagsを主軸に鑑定文を作成してください。",
            "caution": [
                "運命断定を避ける",
                "不安を煽らない",
                "basisがあるタグを優先する",
                "strengthが高いタグを優先する",
            ],
        },
    }
    response_doc["handoff_yaml"] = build_handoff_yaml(response_doc)
    return {
        "ok": True,
        **response_doc,
    }, 200


def _normalize_birth_place(payload: dict[str, Any]) -> str:
    birth_place = str(payload.get("birth_place") or payload.get("prefecture") or "").strip()
    if not birth_place:
        raise ApiCalcError("INVALID_INPUT", "birth_place is required", 400)
    return birth_place


def _normalize_timezone(payload: dict[str, Any]) -> str:
    tz = str(payload.get("timezone") or payload.get("tz_name") or "Asia/Tokyo").strip()
    tz = tz or "Asia/Tokyo"
    try:
        ZoneInfo(tz)
    except Exception as exc:
        raise ApiCalcError("INVALID_TIMEZONE", f"invalid timezone: {tz}", 400) from exc
    return tz


def _normalize_day_boundary(payload: dict[str, Any]) -> bool:
    value = str(payload.get("day_boundary") or "").strip().lower()
    return value in {"23:00", "23", "true", "1", "on", "yes"}


def _normalize_period(payload: dict[str, Any]) -> str:
    period = str(payload.get("period") or "month").strip().lower()
    if period not in {"day", "month"}:
        raise ApiCalcError("UNSUPPORTED_PERIOD", "period must be 'day' or 'month'", 400)
    return period


def _normalize_writing(payload: dict[str, Any]) -> dict[str, Any]:
    writing = payload.get("writing")
    return writing if isinstance(writing, dict) else {}


def _optional_float(payload: dict[str, Any], field_name: str) -> float | None:
    value = payload.get(field_name)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ApiCalcError("INVALID_INPUT", f"{field_name} must be a number", 400) from exc


def _parse_date(value: Any, field_name: str) -> date:
    if not value:
        raise ApiCalcError("INVALID_INPUT", f"{field_name} is required", 400)
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ApiCalcError("INVALID_INPUT", f"{field_name} must be YYYY-MM-DD", 400) from exc


def _parse_optional_datetime(value: Any, field_name: str, *, tz_name: str, default_hour: int = 12) -> datetime:
    target_date = _parse_date(value, field_name)
    return datetime.combine(target_date, time(default_hour, 0), tzinfo=ZoneInfo(tz_name))


def _build_doc(
    *,
    title: str | None,
    birth_date: str,
    birth_time: str | None,
    birth_place: str,
    birth_lat: float | None,
    birth_lng: float | None,
    tz_name: str,
    gender: str,
    include_asteroids: bool,
    include_shichusuimei: bool,
    include_transit: bool,
    transit_start_date: datetime | None = None,
    transit_days: int = 31,
    day_change_at_23: bool = False,
) -> dict[str, Any]:
    _yaml_text, _prompt_text, doc = build_product_yaml(
        title=title,
        birth_date=birth_date,
        birth_time=birth_time,
        prefecture=birth_place,
        birth_place_label=birth_place,
        birth_lat=birth_lat,
        birth_lng=birth_lng,
        tz_name=tz_name,
        gender=gender,
        include_asteroids=include_asteroids,
        include_shichusuimei=include_shichusuimei,
        include_transit=include_transit,
        transit_start_date=transit_start_date,
        transit_days=transit_days,
        day_change_at_23=day_change_at_23,
    )
    return {
        "doc": doc,
    }


def calc_western_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        birth_date = str(payload.get("birth_date", "")).strip()
        tz_name = _normalize_timezone(payload)
        writing = _normalize_writing(payload)
        input_data = {
            "name": payload.get("name"),
            "birth_date": birth_date,
            "birth_time": payload.get("birth_time"),
            "birth_place": _normalize_birth_place(payload),
            "timezone": tz_name,
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "writing": writing,
        }
        if not birth_date:
            raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
        result = _build_doc(
            title=payload.get("name"),
            birth_date=birth_date,
            birth_time=str(payload.get("birth_time") or "").strip() or None,
            birth_place=input_data["birth_place"],
            birth_lat=_optional_float(payload, "lat"),
            birth_lng=_optional_float(payload, "lon"),
            tz_name=tz_name,
            gender=str(payload.get("gender") or "unknown"),
            include_asteroids=True,
            include_shichusuimei=False,
            include_transit=False,
        )
        return _success("western", input_data, result["doc"])
    except ApiCalcError as exc:
        return _error(exc.code, exc.message, status_code=exc.status_code)
    except Exception as exc:
        return _error("INTERNAL_ERROR", str(exc), status_code=500)


def calc_shichu_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        birth_date = str(payload.get("birth_date", "")).strip()
        writing = _normalize_writing(payload)
        input_data = {
            "name": payload.get("name"),
            "birth_date": birth_date,
            "birth_time": payload.get("birth_time"),
            "birth_place": _normalize_birth_place(payload),
            "gender": payload.get("gender") or "unknown",
            "day_boundary": payload.get("day_boundary"),
            "writing": writing,
        }
        if not birth_date:
            raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
        result = _build_doc(
            title=payload.get("name"),
            birth_date=birth_date,
            birth_time=str(payload.get("birth_time") or "").strip() or None,
            birth_place=input_data["birth_place"],
            birth_lat=_optional_float(payload, "lat"),
            birth_lng=_optional_float(payload, "lon"),
            tz_name=_normalize_timezone(payload),
            gender=str(payload.get("gender") or "unknown"),
            include_asteroids=False,
            include_shichusuimei=True,
            include_transit=False,
            day_change_at_23=_normalize_day_boundary(payload),
        )
        return _success("shichu", input_data, result["doc"])
    except ApiCalcError as exc:
        return _error(exc.code, exc.message, status_code=exc.status_code)
    except Exception as exc:
        return _error("INTERNAL_ERROR", str(exc), status_code=500)


def calc_transit_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        birth_date = str(payload.get("birth_date", "")).strip()
        if not birth_date:
            raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
        period = _normalize_period(payload)
        tz_name = _normalize_timezone(payload)
        writing = _normalize_writing(payload)
        target_date_value = payload.get("target_date") or birth_date
        target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
        transit_days = 1 if period == "day" else 31
        input_data = {
            "name": payload.get("name"),
            "birth_date": birth_date,
            "birth_time": payload.get("birth_time"),
            "birth_place": _normalize_birth_place(payload),
            "timezone": tz_name,
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "target_date": payload.get("target_date"),
            "period": period,
            "writing": writing,
        }
        result = _build_doc(
            title=payload.get("name"),
            birth_date=birth_date,
            birth_time=str(payload.get("birth_time") or "").strip() or None,
            birth_place=input_data["birth_place"],
            birth_lat=_optional_float(payload, "lat"),
            birth_lng=_optional_float(payload, "lon"),
            tz_name=tz_name,
            gender=str(payload.get("gender") or "unknown"),
            include_asteroids=False,
            include_shichusuimei=False,
            include_transit=True,
            transit_start_date=target_start,
            transit_days=transit_days,
        )
        return _success("transit", input_data, result["doc"])
    except ApiCalcError as exc:
        return _error(exc.code, exc.message, status_code=exc.status_code)
    except Exception as exc:
        return _error("INTERNAL_ERROR", str(exc), status_code=500)


def calc_combined_api(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        birth_date = str(payload.get("birth_date", "")).strip()
        if not birth_date:
            raise ApiCalcError("INVALID_INPUT", "birth_date is required", 400)
        period = _normalize_period(payload)
        tz_name = _normalize_timezone(payload)
        writing = _normalize_writing(payload)
        target_date_value = payload.get("target_date") or birth_date
        target_start = _parse_optional_datetime(target_date_value, "target_date", tz_name=tz_name, default_hour=12)
        transit_days = 1 if period == "day" else 31
        input_data = {
            "name": payload.get("name"),
            "birth_date": birth_date,
            "birth_time": payload.get("birth_time"),
            "birth_place": _normalize_birth_place(payload),
            "timezone": tz_name,
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "gender": payload.get("gender") or "unknown",
            "target_date": payload.get("target_date"),
            "day_boundary": payload.get("day_boundary"),
            "period": period,
            "writing": writing,
        }
        result = _build_doc(
            title=payload.get("name"),
            birth_date=birth_date,
            birth_time=str(payload.get("birth_time") or "").strip() or None,
            birth_place=input_data["birth_place"],
            birth_lat=_optional_float(payload, "lat"),
            birth_lng=_optional_float(payload, "lon"),
            tz_name=tz_name,
            gender=str(payload.get("gender") or "unknown"),
            include_asteroids=True,
            include_shichusuimei=True,
            include_transit=True,
            transit_start_date=target_start,
            transit_days=transit_days,
            day_change_at_23=_normalize_day_boundary(payload),
        )
        return _success("combined", input_data, result["doc"])
    except ApiCalcError as exc:
        return _error(exc.code, exc.message, status_code=exc.status_code)
    except Exception as exc:
        return _error("INTERNAL_ERROR", str(exc), status_code=500)
