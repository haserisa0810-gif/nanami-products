from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

import yaml

from services.api_yaml import build_handoff_yaml
from services.chart_svg import build_horoscope_svg_from_yaml
from services.shichu_chart import build_shichusuimei_svg_from_yaml
from services.yaml_exporter import build_product_yaml

DEMO_CHART_ID = "demo_western_19910101"
DEMO_SHICHU_CHART_ID = "demo_shichu_19910101"

DEMO_WESTERN_YAML = """version: nanami-products-yaml-v1
product:
  type: personal_ai_astrology_yaml
  options:
    western_natal: true
    asteroids: false
    transit: false
    shichusuimei: false
generated_at: '2026-05-10T00:22:05.787697+00:00'
input:
  title: テスト太郎
  birth_date: '1991-01-01'
  birth_time: '12:00'
  calculation_time: '12:00'
  birth_time_accuracy: exact
  birth_time_note: 出生時刻あり。ハウス・ASC・MCを通常通り使用できます。
  prefecture: 東京都
  birth_place_kind: domestic
  birth_place: 東京都
  timezone: Asia/Tokyo
  timezone_offset_hours: 9.0
  gender: unknown
usage_note:
  for_ai: このYAMLは計算済みデータです。AIに解釈させる場合、生年月日から再計算させず、この値を根拠にしてください。
  not_included: 鑑定本文は含みません。AI解釈用の構造化データです。
systems:
  western:
    natal:
      engine: Swiss Ephemeris
      house_system: P
      subject:
        datetime: '1991-01-01T12:00:00+09:00'
        location:
          lat: 35.6895
          lng: 139.6917
          city: 東京
      bodies:
        Sun: {sign: Cap, sign_ja: 山羊座, degree: 10.1826, absolute_longitude: 280.1826, house: 9, retrograde: false}
        Moon: {sign: Can, sign_ja: 蟹座, degree: 15.1186, absolute_longitude: 105.1186, house: 4, retrograde: false}
        Mercury: {sign: Sag, sign_ja: 射手座, degree: 24.257, absolute_longitude: 264.257, house: 9, retrograde: true}
        Venus: {sign: Cap, sign_ja: 山羊座, degree: 24.8785, absolute_longitude: 294.8785, house: 10, retrograde: false}
        Mars: {sign: Tau, sign_ja: 牡牛座, degree: 27.7543, absolute_longitude: 57.7543, house: 2, retrograde: true}
        Jupiter: {sign: Leo, sign_ja: 獅子座, degree: 11.9703, absolute_longitude: 131.9703, house: 5, retrograde: true}
        Saturn: {sign: Cap, sign_ja: 山羊座, degree: 25.6773, absolute_longitude: 295.6773, house: 10, retrograde: false}
        Uranus: {sign: Cap, sign_ja: 山羊座, degree: 9.7371, absolute_longitude: 279.7371, house: 9, retrograde: false}
        Neptune: {sign: Cap, sign_ja: 山羊座, degree: 14.1216, absolute_longitude: 284.1216, house: 10, retrograde: false}
        Pluto: {sign: Sco, sign_ja: 蠍座, degree: 19.595, absolute_longitude: 229.595, house: 7, retrograde: false}
        North Node: {sign: Cap, sign_ja: 山羊座, degree: 28.0419, absolute_longitude: 298.0419, house: 10, retrograde: true}
        South Node: {sign: Can, sign_ja: 蟹座, degree: 28.0419, absolute_longitude: 118.0419, house: 4, retrograde: true}
        ASC: {sign: Ari, sign_ja: 牡羊座, degree: 23.2634, absolute_longitude: 23.2634, house: 1, retrograde: false}
        MC: {sign: Cap, sign_ja: 山羊座, degree: 13.7778, absolute_longitude: 283.7778, house: 10, retrograde: false}
      houses:
        '1': {sign: Ari, sign_ja: 牡羊座, degree: 23.2634, absolute_longitude: 23.2634}
        '2': {sign: Tau, sign_ja: 牡牛座, degree: 27.0814, absolute_longitude: 57.0814}
        '3': {sign: Gem, sign_ja: 双子座, degree: 21.6718, absolute_longitude: 81.6718}
        '4': {sign: Can, sign_ja: 蟹座, degree: 13.7778, absolute_longitude: 103.7778}
        '5': {sign: Leo, sign_ja: 獅子座, degree: 7.9734, absolute_longitude: 127.9734}
        '6': {sign: Vir, sign_ja: 乙女座, degree: 9.5405, absolute_longitude: 159.5405}
        '7': {sign: Lib, sign_ja: 天秤座, degree: 23.2634, absolute_longitude: 203.2634}
        '8': {sign: Sco, sign_ja: 蠍座, degree: 27.0814, absolute_longitude: 237.0814}
        '9': {sign: Sag, sign_ja: 射手座, degree: 21.6718, absolute_longitude: 261.6718}
        '10': {sign: Cap, sign_ja: 山羊座, degree: 13.7778, absolute_longitude: 283.7778}
        '11': {sign: Aqu, sign_ja: 水瓶座, degree: 7.9734, absolute_longitude: 307.9734}
        '12': {sign: Pis, sign_ja: 魚座, degree: 9.5405, absolute_longitude: 339.5405}
      aspects:
        - {body1: North Node, body2: South Node, aspect: opposition, orb: 0.0}
        - {body1: Neptune, body2: MC, aspect: conjunction, orb: 0.34}
        - {body1: Sun, body2: Uranus, aspect: conjunction, orb: 0.45}
        - {body1: Venus, body2: Saturn, aspect: conjunction, orb: 0.8}
        - {body1: Mercury, body2: ASC, aspect: trine, orb: 0.99}
        - {body1: Moon, body2: Neptune, aspect: opposition, orb: 1.0}
        - {body1: Venus, body2: ASC, aspect: square, orb: 1.62}
        - {body1: Mars, body2: Saturn, aspect: trine, orb: 2.08}
        - {body1: Sun, body2: Moon, aspect: opposition, orb: 4.94}
      summary:
        elements: {fire: 2, earth: 6, air: 0, water: 2}
        modes: {cardinal: 6, fixed: 3, mutable: 1}
        dominant_signs:
          - {sign: Cap, sign_ja: 山羊座, count: 5}
          - {sign: Can, sign_ja: 蟹座, count: 1}
          - {sign: Leo, sign_ja: 獅子座, count: 1}
      skipped_bodies: []
    asteroids: null
    transit: null
  shichusuimei: null
"""


def demo_western_doc() -> dict[str, Any]:
    return yaml.safe_load(DEMO_WESTERN_YAML)


@lru_cache(maxsize=1)
def demo_shichu_doc() -> dict[str, Any]:
    _yaml_text, _prompt_text, doc = build_product_yaml(
        title="テスト太郎",
        birth_date="1991-01-01",
        birth_time="12:00",
        prefecture="東京都",
        birth_place_label="東京都",
        gender="unknown",
        include_shichusuimei=True,
    )
    return doc


@lru_cache(maxsize=1)
def demo_shichu_yaml() -> str:
    yaml_text, _prompt_text, _doc = build_product_yaml(
        title="テスト太郎",
        birth_date="1991-01-01",
        birth_time="12:00",
        prefecture="東京都",
        birth_place_label="東京都",
        gender="unknown",
        include_shichusuimei=True,
    )
    return yaml_text


def build_demo_response(endpoint: str, payload: dict[str, object], *, base_url: str) -> dict[str, Any]:
    doc = demo_western_doc()
    western = doc["systems"]["western"] if endpoint in {"western", "combined"} else None
    shichu = demo_shichu_doc()["systems"]["shichusuimei"] if endpoint in {"shichu", "combined"} else None
    response = {
        "ok": True,
        "meta": {
            "api_version": "1.0",
            "engine": "nanami-products",
            "endpoint": endpoint,
            "mode": "demo",
            "mock": True,
        },
        "input": payload,
        "raw_data": {
            "western": western,
            "shichu": shichu,
            "transit": {"days": [{"date": str(payload.get("target_date") or "2026-05-01"), "active_aspects": []}]} if endpoint in {"transit", "combined"} else None,
        },
        "interpreted_tags": {"western": [], "shichu": [], "transit": [], "integration": []},
        "writing_hints": {"key_concepts": ["demo"]},
        "ai_prompt_context": {
            "role": "構造分析型の占星術鑑定",
            "instruction": "raw_dataを直接断定せず、interpreted_tagsを主軸に鑑定文を作成してください。",
            "caution": ["運命断定を避ける", "不安を煽らない"],
        },
    }
    if western:
        response["chart"] = {
            "svg_available": True,
            "chart_id": DEMO_CHART_ID,
            "svg_url": f"{base_url}/api/demo/charts/{DEMO_CHART_ID}.svg",
        }
    if shichu:
        response["shichusuimei_chart"] = {
            "svg_available": True,
            "png_available": False,
            "chart_id": DEMO_SHICHU_CHART_ID,
            "svg_url": f"{base_url}/api/demo/shichusuimei/{DEMO_SHICHU_CHART_ID}/chart.svg",
            "png_url": None,
        }
    response["handoff_yaml"] = build_handoff_yaml({key: value for key, value in response.items() if key != "ok"})
    return response


def build_demo_svg(chart_id: str) -> str | None:
    if chart_id != DEMO_CHART_ID:
        return None
    return build_horoscope_svg_from_yaml(DEMO_WESTERN_YAML, compact=True)


def build_demo_shichu_svg(chart_id: str) -> str | None:
    if chart_id != DEMO_SHICHU_CHART_ID:
        return None
    return build_shichusuimei_svg_from_yaml(demo_shichu_yaml(), compact=True)
