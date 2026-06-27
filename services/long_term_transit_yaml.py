from __future__ import annotations

from datetime import date
from typing import Any

import yaml

PRIMARY_TRANSIT_BODIES = ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
AUXILIARY_TRANSIT_BODIES = ("Chiron", "North Node", "South Node")
AI_TRANSIT_BODIES = set(PRIMARY_TRANSIT_BODIES) | set(AUXILIARY_TRANSIT_BODIES)
ASPECT_PRIORITY = {
    "conjunction": 5,
    "opposition": 4,
    "square": 4,
    "trine": 3,
    "sextile": 2,
}
BODY_HINTS = {
    "Jupiter": "拡大や可能性",
    "Saturn": "責任や現実化",
    "Uranus": "変化や独立",
    "Neptune": "理想や直感",
    "Pluto": "深い変容",
    "Chiron": "癒しや弱点の扱い",
    "North Node": "今後伸ばす方向性",
    "South Node": "手放しや過去パターン",
}
ASPECT_HINTS = {
    "conjunction": "強く始動する",
    "opposition": "外部との関係から意識化される",
    "square": "調整課題として表れやすい",
    "trine": "自然に活かしやすい",
    "sextile": "機会として使いやすい",
}

def _safe_load(source: str | None) -> dict[str, Any]:
    if not source:
        return {}
    loaded = yaml.safe_load(source) or {}
    return loaded if isinstance(loaded, dict) else {}


def has_long_term_transits(*, doc: dict[str, Any] | None = None, yaml_text: str | None = None) -> bool:
    payload = doc if isinstance(doc, dict) else _safe_load(yaml_text)
    western = ((payload.get("systems") or {}).get("western") or {})
    long_term = western.get("transit_long_term")
    if isinstance(long_term, dict):
        return bool(long_term)
    if isinstance(long_term, list):
        return bool(long_term)
    return False


def _to_float(value: Any, default: float = 99.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_index(value: Any) -> int:
    raw = str(value or "")
    try:
        return date.fromisoformat(raw).toordinal()
    except ValueError:
        return 0


def _body_rank(body: str) -> int:
    if body in PRIMARY_TRANSIT_BODIES:
        return PRIMARY_TRANSIT_BODIES.index(body)
    if body in AUXILIARY_TRANSIT_BODIES:
        return len(PRIMARY_TRANSIT_BODIES) + AUXILIARY_TRANSIT_BODIES.index(body)
    return 99


def _importance(body: str, aspect: str, orb_min: float, duration_samples: int) -> str:
    score = ASPECT_PRIORITY.get(aspect, 1)
    if body in PRIMARY_TRANSIT_BODIES:
        score += 2
    if orb_min <= 0.3:
        score += 3
    elif orb_min <= 0.8:
        score += 2
    elif orb_min <= 1.5:
        score += 1
    if duration_samples >= 4:
        score += 1
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def _interpretation_hint(transiting_body: str, natal_body: str, aspect: str) -> str:
    body_hint = BODY_HINTS.get(transiting_body, f"{transiting_body}のテーマ")
    aspect_hint = ASPECT_HINTS.get(aspect, "変化として表れる")
    return f"{body_hint}が{natal_body}のテーマに{aspect_hint}時期"


def _retrograde_info(samples: list[dict[str, Any]], body: str) -> dict[str, Any] | None:
    values = []
    for sample in samples:
        bodies = sample.get("transiting_bodies") or {}
        body_data = bodies.get(body) if isinstance(bodies, dict) else None
        if isinstance(body_data, dict) and "retrograde" in body_data:
            values.append(bool(body_data.get("retrograde")))
    if not values:
        return None
    return {
        "any": any(values),
        "all": all(values),
    }


def _compact_existing_item(item: dict[str, Any]) -> dict[str, Any] | None:
    body = str(item.get("transiting_body") or item.get("transit_body") or "")
    if body not in AI_TRANSIT_BODIES:
        return None
    natal_body = str(item.get("natal_body") or item.get("body2") or "")
    aspect = str(item.get("aspect") or "")
    orb_min = _to_float(item.get("orb_min", item.get("min_orb", item.get("orb"))))
    orb_max = _to_float(item.get("orb_max", item.get("orb")), orb_min)
    out = {
        "transiting_body": body,
        "natal_body": natal_body,
        "aspect": aspect,
        "start_date": item.get("start_date") or item.get("date") or item.get("peak_date"),
        "end_date": item.get("end_date") or item.get("date") or item.get("peak_date"),
        "peak_date": item.get("peak_date") or item.get("closest_date") or item.get("date"),
        "orb_min": round(orb_min, 2),
        "orb_max": round(orb_max, 2),
        "importance": item.get("importance") or item.get("priority") or _importance(body, aspect, orb_min, 1),
        "interpretation_hint": item.get("interpretation_hint") or _interpretation_hint(body, natal_body, aspect),
    }
    if "retrograde" in item:
        out["retrograde"] = item.get("retrograde")
    return {key: value for key, value in out.items() if value not in (None, "", {})}


def _events_from_samples(samples: list[dict[str, Any]], *, max_items: int = 32) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    sample_by_date = {str(sample.get("date") or ""): sample for sample in samples if isinstance(sample, dict)}
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        sample_date = str(sample.get("date") or "")
        for aspect_item in sample.get("natal_aspects") or []:
            if not isinstance(aspect_item, dict):
                continue
            body = str(aspect_item.get("transit_body") or aspect_item.get("transiting_body") or "")
            if body not in AI_TRANSIT_BODIES:
                continue
            natal_body = str(aspect_item.get("natal_body") or "")
            aspect = str(aspect_item.get("aspect") or "")
            grouped.setdefault((body, natal_body, aspect), []).append({
                "date": sample_date,
                "orb": _to_float(aspect_item.get("orb")),
                "sample": sample,
            })

    events: list[dict[str, Any]] = []
    for (body, natal_body, aspect), hits in grouped.items():
        hits = sorted(hits, key=lambda item: (_date_index(item.get("date")), item.get("orb", 99)))
        if not hits:
            continue
        segments: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        previous_ord = 0
        for hit in hits:
            current_ord = _date_index(hit.get("date"))
            if current and previous_ord and current_ord - previous_ord > 14:
                segments.append(current)
                current = []
            current.append(hit)
            previous_ord = current_ord
        if current:
            segments.append(current)

        for segment in segments:
            closest = min(segment, key=lambda item: item.get("orb", 99))
            orb_values = [item.get("orb", 99) for item in segment]
            source_samples = [sample_by_date.get(str(item.get("date") or ""), {}) for item in segment]
            retrograde = _retrograde_info(source_samples, body)
            orb_min = min(orb_values)
            event = {
                "transiting_body": body,
                "natal_body": natal_body,
                "aspect": aspect,
                "start_date": segment[0].get("date"),
                "end_date": segment[-1].get("date"),
                "peak_date": closest.get("date"),
                "orb_min": round(orb_min, 2),
                "orb_max": round(max(orb_values), 2),
                "importance": _importance(body, aspect, orb_min, len(segment)),
                "interpretation_hint": _interpretation_hint(body, natal_body, aspect),
            }
            if retrograde:
                event["retrograde"] = retrograde
            events.append(event)

    events.sort(key=lambda item: (
        {"high": 0, "medium": 1, "low": 2}.get(str(item.get("importance")), 3),
        _body_rank(str(item.get("transiting_body") or "")),
        _to_float(item.get("orb_min")),
        str(item.get("peak_date") or ""),
    ))
    return events[:max_items]


def compact_long_term_transits_for_ai(long_term: Any, *, max_items: int = 32) -> Any:
    if not isinstance(long_term, dict):
        return long_term
    period = dict(long_term.get("period") or {})
    if isinstance(long_term.get("items"), list):
        items = [
            compacted
            for item in long_term.get("items") or []
            if isinstance(item, dict) and (compacted := _compact_existing_item(item))
        ][:max_items]
    else:
        items = _events_from_samples(long_term.get("samples") or [], max_items=max_items)
    return {
        "period": period,
        "selection_policy": {
            "format": "ai_compact_events",
            "source": "samples" if isinstance(long_term.get("samples"), list) else "items",
            "primary_transiting_bodies": list(PRIMARY_TRANSIT_BODIES),
            "auxiliary_transiting_bodies": list(AUXILIARY_TRANSIT_BODIES),
            "excluded": ["Moon", "Mercury", "Venus", "Mars", "all weekly sample details"],
        },
        "items": items,
    }


def build_ai_long_term_transits_yaml(*, doc: dict[str, Any] | None = None, yaml_text: str | None = None) -> str:
    payload = doc if isinstance(doc, dict) else _safe_load(yaml_text)
    western = ((payload.get("systems") or {}).get("western") or {})
    long_term = western.get("transit_long_term")
    if not long_term:
        return ""

    product = payload.get("product") or {}
    options = dict(product.get("options") or {})
    options["western_long_term_transits"] = True
    options["transit"] = False

    out = {
        "version": "nanami-products-long-term-transits-ai-v1",
        "generated_at": payload.get("generated_at"),
        "product": {
            **product,
            "options": options,
        },
        "input": payload.get("input") or {},
        "calculation": payload.get("calculation") or {},
        "birth_time": payload.get("birth_time") or {},
        "interpretation_flags": payload.get("interpretation_flags") or {},
        "usage_note": {
            "for_ai": "長期トランジットのAI共有用に、週次samplesから主要イベントだけを抽出した軽量版です。保存・検証にはFULL版を使ってください。",
            "full_yaml": "詳細な週次samplesはlong-term-transits-full.yamlまたはfull.yamlに残っています。",
        },
        "systems": {
            "western": {
                "natal": western.get("natal"),
                "transit_long_term": compact_long_term_transits_for_ai(long_term),
            }
        },
        "assets": {
            **(payload.get("assets") or {}),
            "yaml_long_term_transits_ai": {
                "available": True,
                "merge_path": "systems.western.transit_long_term",
            },
        },
    }
    return yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)


def build_long_term_transits_yaml(*, doc: dict[str, Any] | None = None, yaml_text: str | None = None) -> str:
    payload = doc if isinstance(doc, dict) else _safe_load(yaml_text)
    western = ((payload.get("systems") or {}).get("western") or {})
    long_term = western.get("transit_long_term")
    if not long_term:
        return ""

    product = payload.get("product") or {}
    options = dict(product.get("options") or {})
    options["western_long_term_transits"] = True
    options["transit"] = False

    out = {
        "version": payload.get("version") or "nanami-products-yaml-v1",
        "generated_at": payload.get("generated_at"),
        "product": {
            **product,
            "options": options,
        },
        "input": payload.get("input") or {},
        "calculation": payload.get("calculation") or {},
        "birth_time": payload.get("birth_time") or {},
        "interpretation_flags": payload.get("interpretation_flags") or {},
        "systems": {
            "western": {
                "natal": western.get("natal"),
                "transit_long_term": long_term,
            }
        },
        "assets": {
            **(payload.get("assets") or {}),
            "yaml_long_term_transits": {
                "available": True,
                "merge_path": "systems.western.transit_long_term",
            },
        },
    }
    return yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)
