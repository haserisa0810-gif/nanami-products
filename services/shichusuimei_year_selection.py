"""Read-only product adapter for selection from an already issued Full YAML.

The tested saved-document extractor is reused; no engine, storage writes,
annual-option prototype, or purchase flow is invoked here.
"""
from __future__ import annotations

import hashlib
import yaml
from services.output_metadata import customer_output_doc
from services.yaml_exporter import build_prompt_for_doc

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


MODES = {"basic", "selected", "years_only", "complete"}
OMISSION_MEANING = (
    "このファイルに入っていない年。該当なし・未計算・別売への移動を意味しない。"
    "同じ会話で先に渡した同じ原本（同じ chart_id）の年データは引き続き使える"
)


def _year_ranges(years: list[int]) -> str:
    """[2026, 2027, 2028, 2031] -> '2026〜2028・2031年'"""
    if not years:
        return ""
    years = sorted(years)
    parts, start, prev = [], years[0], years[0]
    for y in years[1:] + [None]:
        if y is not None and y == prev + 1:
            prev = y
            continue
        parts.append(f"{start}〜{prev}" if prev != start else f"{start}")
        if y is not None:
            start = prev = y
    return "・".join(parts) + "年"


def _daiun_span(base_doc: dict) -> tuple[int, str]:
    daiun = ((base_doc.get("systems") or {}).get("shichusuimei") or {}).get("normalized_data", {}).get("daiun") or {}
    items = daiun.get("items") or []
    if not items:
        return 0, ""
    first = str(items[0].get("approx_start_at") or items[0].get("approx_start_year") or "")[:4]
    last = str(items[-1].get("approx_end_at") or "")[:4]
    return len(items), f"{first}〜{last}年" if first and last else ""


def _chart_id(base_doc: dict) -> str:
    return str((base_doc.get("meta") or {}).get("chart_id") or "")


def content_summary(base_doc: dict, mode: str, years: list[int], all_years: list[int]) -> str:
    """AI用テキストの冒頭に置く「このデータの中身」。AIと利用者の両方が何を渡したか分かるようにする。"""
    count, span = _daiun_span(base_doc)
    chart_id = _chart_id(base_doc)
    daiun = f"大運{count}期{f'（{span}）' if span else ''}をすべて含みます" if count else "大運は保留または未収録です（daiun.status を参照）"
    if mode == "years_only":
        return (f"【このデータの中身】同じ会話で先に渡した四柱推命データ（chart_id: {chart_id}）の続きです。"
                f"年ごとの年運：{_year_ranges(years)}のみ。命式・大運は先に渡したデータを参照してください。\n")
    if mode == "selected":
        annual = f"年ごとの年運：{_year_ranges(years)}"
    elif mode == "complete":
        annual = f"年ごとの年運：{_year_ranges(all_years)}（収録年すべて）" if all_years else "年ごとの年運：含みません"
    else:
        annual = "年ごとの年運：含みません（原本作成時の単年流年のみ）"
    return f"【このデータの中身】命式と、{daiun}。{annual}。（chart_id: {chart_id}）\n"


def _continuation_reference(common: dict) -> dict:
    """続きの年だけを渡すときに、同じ原本かを確かめるための最小限の参照。"""
    shichu = ((common.get("systems") or {}).get("shichusuimei") or {})
    nd = shichu.get("normalized_data") or {}
    daiun = nd.get("daiun") or {}
    return {
        "chart_id": (common.get("meta") or {}).get("chart_id"),
        "engine_version": shichu.get("engine_version"),
        "day_master": shichu.get("day_master"),
        "pillars": {k: (v.get("kanshi") if isinstance(v, dict) else v) for k, v in (nd.get("pillars") or {}).items()},
        "birth_time_accuracy": (common.get("birth_time") or {}).get("accuracy"),
        "daiun_status": daiun.get("status"),
        "daiun_summary": [
            {k: item.get(k) for k in ("index", "kanshi", "age_from", "age_to", "approx_start_at", "approx_end_at")}
            for item in daiun.get("items") or []
        ],
        "note": "命式・大運の詳細は、同じ会話で先に渡した同じ chart_id のデータにあります",
    }


CONTINUATION_PROMPT = """あなたは四柱推命の鑑定者です。以下のYAMLは、この会話で先に渡した四柱推命データの「続きの年」です。
- reference.chart_id が、先に渡したデータの chart_id と同じか確認してください。同じなら同じ人の同じ原本です。異なる・先のデータが会話にない場合は、解釈の前に「命式つきのデータ」の貼り付けを依頼してください。
- 命式・大運・構造分析・読み方の規則は、先に渡したデータと指示を引き続き使ってください。このYAMLは selected_base_forecasts の年だけを含みます。
- 先に渡した年とこの年を組み合わせて読んでかまいません。どの年がどのデータにあったかを明示し、どちらにもない年は推測・再計算しないでください。
- 計算値を変更せず、生年月日から再計算しないでください。
"""


def build_year_selection(yaml_text: str, payload: dict) -> dict:
    """Return YAML and its matching prompt without modifying the saved original."""
    if not isinstance(payload, dict) or set(payload) - {"mode", "years"}:
        raise YearSelectionError("invalid_request", "用途と対象年を指定してください。")
    mode = payload.get("mode")
    if not isinstance(mode, str) or mode not in MODES:
        raise YearSelectionError("invalid_mode", "用途を選択してください。")
    years = payload.get("years", [])
    if not isinstance(years, list) or any(type(y) is not int for y in years):
        raise YearSelectionError("invalid_years", "対象年は整数の一覧で指定してください。")
    needs_years = mode in {"selected", "years_only"}
    if len(set(years)) != len(years) or (needs_years and not years) or (not needs_years and years):
        raise YearSelectionError("invalid_years", "対象年の空指定・重複・用途との不一致を確認してください。")
    info = selection_info(yaml_text)
    missing = [y for y in years if y not in info["available_years"]]
    if missing:
        raise YearSelectionError("years_not_saved", "選んだ年はこのFull YAMLに収録されていません。収録年から選択してください。")
    raw = yaml_text.encode("utf-8")
    base_doc = load_saved_full(raw)
    if mode == "complete":
        output = yaml_text  # Byte-equivalent UTF-8 text, including original newlines.
        prompt = extraction_prompt("complete")
    else:
        try:
            selected, _ = extract_base(raw, years if needs_years else None)
            doc = yaml.safe_load(selected)  # Emitted and verified by extract_base.
            trace = doc.pop("local_year_extraction")
            trace["schema_version"] = "1.0"
            trace["source_kind"] = "issued_shichusuimei_full"
            trace["use"] = "ai_reading_only"
            trace["original_full_required_for_app_import"] = True
            trace["omission_meaning"] = OMISSION_MEANING
            if mode == "years_only":
                trace["purpose"] = "continuation_years_only"
                doc = {"year_selection": trace, "reference": _continuation_reference(doc.pop("common")), **doc}
            else:
                doc = {"year_selection": trace, **doc}
            output = dump_extraction(customer_output_doc(doc)).decode("utf-8")
            prompt = extraction_prompt("selected" if needs_years else mode).replace("local_year_extraction", "year_selection")
        except (ValueError, TypeError, AttributeError, KeyError, RecursionError, IndexError) as exc:
            # Do not expose source paths, chart IDs, raw data, or exception text.
            raise YearSelectionError("invalid_saved_data", "保存データの整合性を確認できませんでした。完全原本をご利用ください。") from exc
    summary = content_summary(base_doc, mode, years, info["available_years"])
    if mode == "years_only":
        prompt = summary + "\n" + CONTINUATION_PROMPT
    else:
        prompt = summary + "\n" + build_prompt_for_doc(base_doc, include_shichusuimei=True) + "\n" + prompt
    if needs_years:
        prompt += (f"解釈対象年: {', '.join(map(str, years))}。このファイルにない年は推測・再計算しないでください。"
                   f"ただし、同じ会話で先に渡した同じ原本（chart_id: {_chart_id(base_doc)}）の年データは使えます。"
                   "どのデータの年かを示して組み合わせてください。\n")
    prompt += "吉凶を一律に決めず、計算結果と占術的解釈を区別してください。\n"
    filename_part = {"selected": "years-", "years_only": "more-years-"}.get(mode)
    return {"mode": mode, "included_years": years, "available_years": info["available_years"],
            "yaml_text": output, "prompt_text": prompt, "content_summary": summary.strip(),
            "ai_text": prompt.rstrip() + "\n\n---\n\n```yaml\n" + output.rstrip("\r\n") + "\n```\n",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(output.encode("utf-8")), "characters": len(output),
            "filename": "nanami-shichusuimei-" + (filename_part + "-".join(map(str, years)) if filename_part else mode)}
