from __future__ import annotations

from typing import Any

import yaml

BIRTH_TIME_ACCURACY_NOTE = (
    "出生時刻が不明または推定のため、ハウス・ASC・MC・Vertexは参考値として扱ってください。"
    "これらを性格や仕事傾向の中心根拠にせず、サイン配置・天体同士の主要アスペクト・エレメント・モードを中心に解釈してください。"
    "月は日内で度数やサインが変わる可能性があるため、断定しすぎないでください。"
)

APPROXIMATE_TIME_RANGES = {
    "morning": {
        "label": "morning",
        "display": "午前",
        "calculation_time": "09:00",
        "estimated_range": "06:00-11:59",
    },
    "afternoon": {
        "label": "afternoon",
        "display": "午後",
        "calculation_time": "15:00",
        "estimated_range": "12:00-17:59",
    },
    "night": {
        "label": "night",
        "display": "夜",
        "calculation_time": "21:00",
        "estimated_range": "18:00-23:59",
    },
}


def resolve_birth_time_accuracy(*, selected_accuracy: str | None, birth_time: str | None) -> dict[str, Any]:
    selected = (selected_accuracy or "auto").strip()
    raw_time = (birth_time or "").strip()
    if selected == "auto":
        selected = "exact" if raw_time else "unknown"

    if selected == "exact":
        if not raw_time:
            raise ValueError("正確な出生時刻ありを選んだ場合は、出生時刻を入力してください。")
        return {
            "accuracy": "exact",
            "calculation_time": raw_time,
            "birth_time": raw_time,
            "range": None,
            "note": "出生時刻あり。ハウス・ASC・MCを通常通り使用できます。",
        }

    if selected == "unknown":
        return {
            "accuracy": "unknown",
            "calculation_time": "12:00",
            "birth_time": None,
            "range": None,
            "note": "出生時刻不明のため12:00で仮計算しています。ハウス・ASC・MCは参考値です。",
        }

    if selected in APPROXIMATE_TIME_RANGES:
        item = APPROXIMATE_TIME_RANGES[selected]
        return {
            "accuracy": "approximate",
            "calculation_time": item["calculation_time"],
            "birth_time": None,
            "range": {
                "label": item["label"],
                "estimated_range": item["estimated_range"],
            },
            "note": f"出生時刻は{item['display']}の推定レンジです。ハウス・ASC・MCは参考値です。",
        }

    raise ValueError("出生時刻の選択肢が不正です。")


def extract_birth_time_notice(yaml_text: str, *, doc: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = doc if isinstance(doc, dict) else (yaml.safe_load(yaml_text) or {})
    input_block = doc.get("input") or {}
    birth_time_block = doc.get("birth_time") or {}
    accuracy = birth_time_block.get("accuracy") or input_block.get("birth_time_accuracy") or "exact"
    if accuracy == "unknown":
        short = "出生時刻不明のため、一部データは参考値です"
    elif accuracy == "approximate":
        short = "出生時刻が推定のため、一部データは参考値です"
    else:
        short = ""
    return {
        "accuracy": accuracy,
        "calculation_time": birth_time_block.get("calculation_time") or input_block.get("calculation_time") or input_block.get("birth_time"),
        "note": birth_time_block.get("note") or input_block.get("birth_time_note") or "",
        "short": short,
        "show": accuracy in {"unknown", "approximate"},
    }
