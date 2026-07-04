"""Astro Travel の入出力型定義。

MVP では厳密なバリデーションライブラリを持ち込まず、軽量な dataclass と
定数辞書で入力・出力の形を固定する。travel_report YAML の schema_version は
"1.0"。将来の Relocation アプリでも location / relocation ブロックを再利用できる
構造にしている。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"
APP_NAME = "astro_travel"

# 旅行目的（内部キー: 表示ラベル）。UI・スコアリング・YAML すべてでこの辞書を唯一の
# 出典にする。順序は画面表示順。
TRAVEL_PURPOSES: dict[str, str] = {
    "healing": "癒やし",
    "love": "恋愛",
    "work": "仕事",
    "creativity": "創作",
    "learning": "学び",
    "adventure": "冒険",
    "fan_activity": "推し活",
    "money": "金運",
    "solo": "一人旅",
    "family": "家族旅行",
}


def purpose_label(key: str | None) -> str:
    return TRAVEL_PURPOSES.get(str(key or "").strip(), "")


def is_valid_purpose(key: str | None) -> bool:
    return str(key or "").strip() in TRAVEL_PURPOSES


@dataclass
class TravelLocation:
    """旅行先の地点情報。Relocation アプリと共通で使う想定。"""

    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "country": self.country,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "timezone": self.timezone,
        }


@dataclass
class TravelStay:
    """滞在期間。"""

    arrival_date: str
    departure_date: str
    days: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "arrival_date": self.arrival_date,
            "departure_date": self.departure_date,
            "days": self.days,
        }


@dataclass
class TravelPurpose:
    key: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label}


@dataclass
class TravelInput:
    """診断リクエストの正規化済み入力。"""

    natal_yaml_text: str
    purpose: TravelPurpose
    location: TravelLocation
    stay: TravelStay


@dataclass
class TravelReport:
    """travel_report のトップレベル構造（YAML 化前の中間表現）。"""

    input: TravelInput
    acg: dict[str, Any] = field(default_factory=dict)
    relocation: dict[str, Any] = field(default_factory=dict)
    transit: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    interpretation: dict[str, Any] = field(default_factory=dict)
