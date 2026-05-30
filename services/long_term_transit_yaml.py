from __future__ import annotations

from typing import Any

import yaml


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
