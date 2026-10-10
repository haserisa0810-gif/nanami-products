"""Read-only product adapter for selection from an already issued Full YAML.

The tested saved-document extractor is reused; no engine, storage writes,
annual-option prototype, or purchase flow is invoked here.
"""
from __future__ import annotations

import hashlib
import yaml

from services.shichusuimei_full_prototype import load_saved_full
from services.shichusuimei_year_extract_prototype import (
    _base_index, dump_extraction, extract_base, extraction_prompt,
)


class YearSelectionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def selection_info(yaml_text: str) -> dict:
    """Read saved IDs only. Old charts without annual records remain usable."""
    try:
        doc = load_saved_full(yaml_text.encode("utf-8"))
        nd = doc["systems"]["shichusuimei"].get("normalized_data") or {}
        pillars = nd.get("pillars") or {}
        if not isinstance(pillars, dict) or not {"year", "month", "day"} <= pillars.keys():
            raise ValueError("not a base chart")
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        raise YearSelectionError("invalid_base", "出生の命式を含む四柱推命Full YAMLが必要です。") from exc
    try:
        index, _ = _base_index(doc)
        return {"available_years": sorted(index), "year_selection_available": bool(index)}
    except (ValueError, TypeError, AttributeError, KeyError):
        # Full original can still be obtained; never guess a year from position.
        return {"available_years": [], "year_selection_available": False,
                "saved_forecasts_invalid": True}


def build_year_selection(yaml_text: str, payload: dict) -> dict:
    """Return YAML and its matching prompt without modifying the saved original."""
    if not isinstance(payload, dict) or set(payload) - {"mode", "years"}:
        raise YearSelectionError("invalid_request", "用途と対象年を指定してください。")
    mode = payload.get("mode")
    if not isinstance(mode, str) or mode not in {"basic", "selected", "complete"}:
        raise YearSelectionError("invalid_mode", "用途を選択してください。")
    years = payload.get("years", [])
    if not isinstance(years, list) or any(type(y) is not int for y in years):
        raise YearSelectionError("invalid_years", "対象年は整数の一覧で指定してください。")
    if len(set(years)) != len(years) or (mode == "selected" and not years) or (mode != "selected" and years):
        raise YearSelectionError("invalid_years", "対象年の空指定・重複・用途との不一致を確認してください。")
    info = selection_info(yaml_text)
    missing = [y for y in years if y not in info["available_years"]]
    if missing:
        raise YearSelectionError("years_not_saved", "選んだ年はこのFull YAMLに収録されていません。収録年から選択してください。")
    raw = yaml_text.encode("utf-8")
    if mode == "complete":
        output = yaml_text  # Byte-equivalent UTF-8 text, including original newlines.
        prompt = extraction_prompt("complete")
    else:
        try:
            selected, _ = extract_base(raw, years if mode == "selected" else None)
            doc = yaml.safe_load(selected)  # Emitted and verified by extract_base.
            trace = doc.pop("local_year_extraction")
            trace["schema_version"] = "1.0"
            trace["source_kind"] = "issued_shichusuimei_full"
            trace["use"] = "ai_reading_only"
            trace["original_full_required_for_app_import"] = True
            doc = {"year_selection": trace, **doc}
            output = dump_extraction(doc).decode("utf-8")
            prompt = extraction_prompt(mode).replace("local_year_extraction", "year_selection")
        except (ValueError, TypeError, AttributeError, KeyError, RecursionError, IndexError) as exc:
            # Do not expose source paths, chart IDs, raw data, or exception text.
            raise YearSelectionError("invalid_saved_data", "保存データの整合性を確認できませんでした。完全原本をご利用ください。") from exc
    prompt += "吉凶を一律に決めず、計算結果と占術的解釈を区別してください。\n"
    return {"mode": mode, "included_years": years, "available_years": info["available_years"],
            "yaml_text": output, "prompt_text": prompt,
            "ai_text": prompt.rstrip() + "\n\n---\n\n```yaml\n" + output.rstrip("\r\n") + "\n```\n",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(output.encode("utf-8")), "characters": len(output),
            "filename": "nanami-shichusuimei-" + ("years-" + "-".join(map(str, years)) if mode == "selected" else mode)}
