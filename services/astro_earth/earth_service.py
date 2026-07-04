"""Astro Earth（3Dアストロカートグラフィ地球儀）のバックエンド。

3D表示そのものはフロント（Three.js）で行い、ACGラインは既存の
/api/acg/personal を流用する。ここでは「クリック地点」の洞察だけを担う:
出生YAML＋緯度経度から、近いACGラインとリロケーション概要を計算し、
AI解釈用YAML／プロンプトを返す（ステートレス、保存しない）。

占術計算は旅行アプリ（services.travel）と同じ関数を流用し、ロジックの二重管理を避ける。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import swisseph as swe
import yaml

from services.acg_api import natal_dt_utc_from_yaml
from services.travel.location_engine import normalize_lat_lon
from services.travel.travel_generator import (
    _julday_utc,
    _natal_planets,
    _nearest_acg_lines,
    _relocation,
    _validate_yaml_size,
)
from services.western_calc import configure_ephemeris

SCHEMA_VERSION = "1.0"
APP_NAME = "astro_earth"

EARTH_PROMPT = """あなたは西洋占星術・アストロカートグラフィの解説者です。

以下のYAMLは、出生図・任意地点・その地点に近いACG（アストロカートグラフィ）ライン・
リロケーションチャート概要を含む計算済みデータです。

重要ルール:
- 天体位置・ハウス・ACGライン・リロケーション結果は変更しないでください。
- 生年月日や緯度経度から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- その地点で活性化しやすいテーマを、傾向・活かし方として表現してください。
- 断定・不安を煽る表現（災害・事故・病気など）は避けてください。
- 「必ず良い」「絶対に住むべき」などの断定はしないでください。

出力してほしい内容:
1. この地点で活性化しやすいテーマ
2. 近いACGラインの読み解き
3. リロケーションから見た印象
4. この地点の活かし方
5. ひとことで言うなら

以下のYAMLを読み込んで解釈してください。
"""


def build_earth_prompt() -> str:
    return EARTH_PROMPT.strip() + "\n"


def build_point_insight(
    *,
    natal_yaml_text: str,
    latitude: Any,
    longitude: Any,
    location_name: str = "",
) -> dict[str, Any]:
    """クリック地点の洞察（近いACGライン＋リロケーション＋AI用YAML）を返す。"""
    yaml_text = _validate_yaml_size(natal_yaml_text)
    lat, lon = normalize_lat_lon(latitude, longitude)
    natal_dt_utc = natal_dt_utc_from_yaml(yaml_text)

    flags = configure_ephemeris() | swe.FLG_SPEED
    natal_jd = _julday_utc(natal_dt_utc)
    natal_planets = _natal_planets(natal_jd, flags)

    nearest_lines = _nearest_acg_lines(natal_dt_utc, lat, lon)
    relocation = _relocation(natal_jd, lat, lon, natal_planets)

    doc = {
        "schema_version": SCHEMA_VERSION,
        "app": APP_NAME,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "location": {
            "name": (location_name or "").strip() or None,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        },
        "acg": {"nearest_lines": nearest_lines},
        "relocation": relocation,
        "interpretation": {"summary": "", "themes": [], "how_to_use": []},
    }
    yaml_out = yaml.safe_dump({"astro_earth_point": doc}, allow_unicode=True, sort_keys=False, width=120)

    return {
        "nearest_lines": nearest_lines,
        "relocation": relocation,
        "yaml_text": yaml_out,
        "prompt_text": build_earth_prompt(),
        "location": doc["location"],
    }
