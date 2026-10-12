from __future__ import annotations

from typing import Any

import yaml
from copy import deepcopy
from services.yaml_exporter import build_prompt_for_doc


def build_handoff_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)


def build_ai_prompt_context(doc: dict, previous: dict) -> dict:
    """Add system-specific instructions without calculating or changing tags."""
    output = deepcopy(previous)
    systems = doc.get("systems") or {}
    western = systems.get("western") or {}
    shichu = systems.get("shichusuimei") or {}
    output["reading_instructions"] = build_prompt_for_doc(
        doc, include_shichusuimei=bool(shichu),
        include_asteroids=bool(western.get("asteroids")),
        include_transit=bool(western.get("transit")),
    )
    output["source_mapping"] = {
        key: value for key, value in (
            ("systems.western", "raw_data.western"),
            ("systems.shichusuimei", "raw_data.shichu"),
        ) if systems.get(key.split(".")[1])
    }
    if shichu:
        output["role"] = "西洋占星術・四柱推命の構造分析型鑑定" if western else "四柱推命の構造分析型鑑定"
        output["instruction"] = "raw_dataの計算済みデータと構造分析を優先し、interpreted_tagsは補助として扱ってください。reading_instructionsの占術別規則に従い、計算結果と解釈を区別してください。"
        output["caution"] = ["運命断定を避ける", "不安を煽らない", "根拠・暫定フラグ・方式の限界を確認する"]
    return output
