"""旅行先の地点を扱う共通エンジン。

travel 専用にしすぎず、将来の Relocation アプリでも使えるように、
緯度経度の正規化・地点情報の生成・簡易タイムゾーン推定・地理距離計算を
ここに集約する。占術計算そのものには依存しない（純粋な地理ユーティリティ）。
"""
from __future__ import annotations

import math
from typing import Any

from services.travel.travel_schema import TravelLocation

EARTH_RADIUS_KM = 6371.0088


class LocationInputError(ValueError):
    """地点入力に起因するエラー（HTTP 400 相当）。"""


def parse_coordinate(value: Any, *, kind: str) -> float:
    """緯度・経度の文字列/数値を float に正規化する。"""
    if value is None or str(value).strip() == "":
        raise LocationInputError(f"{kind}を入力してください。")
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise LocationInputError(f"{kind}は数値で入力してください。") from exc


def normalize_lat_lon(lat: Any, lon: Any) -> tuple[float, float]:
    """緯度経度を検証して (lat, lon) を返す。範囲外は 400。"""
    lat_f = parse_coordinate(lat, kind="緯度")
    lon_f = parse_coordinate(lon, kind="経度")
    if not (-90.0 <= lat_f <= 90.0):
        raise LocationInputError("緯度は -90〜90 の範囲で入力してください。")
    if not (-180.0 <= lon_f <= 180.0):
        raise LocationInputError("経度は -180〜180 の範囲で入力してください。")
    return lat_f, lon_f


def estimate_timezone(longitude: float, provided: str | None = None) -> str:
    """タイムゾーン取得用の入口。

    MVP では、明示指定があればそれを使い、無ければ経度から粗いオフセットを推定する。
    将来的にはここを IANA タイムゾーンDB 逆引きに差し替えられるようにしておく。
    """
    explicit = (provided or "").strip()
    if explicit:
        return explicit
    offset = int(round(longitude / 15.0))
    offset = max(-12, min(14, offset))
    sign = "+" if offset >= 0 else "-"
    return f"UTC{sign}{abs(offset):02d}:00"


def build_location(
    *,
    name: str,
    country: str,
    latitude: Any,
    longitude: Any,
    timezone: str | None = None,
) -> TravelLocation:
    lat_f, lon_f = normalize_lat_lon(latitude, longitude)
    return TravelLocation(
        name=(name or "").strip() or "指定地点",
        country=(country or "").strip(),
        latitude=lat_f,
        longitude=lon_f,
        timezone=estimate_timezone(lon_f, timezone),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2点間の大圏距離（km）。"""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _lon_diff_deg(lon1: float, lon2: float) -> float:
    d = abs((lon1 - lon2 + 180.0) % 360.0 - 180.0)
    return d


def distance_point_to_line_km(
    point_lat: float,
    point_lon: float,
    coords: list[list[float]],
    *,
    is_meridian: bool,
) -> float:
    """地点から ACG 線（GeoJSON coordinates: [lon, lat] の列）への概算距離（km）。

    - 子午線（MC/IC）線: 経度がほぼ一定なので、東西距離で近似する。
    - 地平線（ASC/DSC）曲線: 緯度1度刻みの頂点への最小大圏距離で近似する。
    """
    if not coords:
        return float("inf")
    if is_meridian:
        line_lon = coords[0][0]
        east_west_km = _lon_diff_deg(point_lon, line_lon) * 111.32 * math.cos(math.radians(point_lat))
        return abs(east_west_km)
    best = float("inf")
    for lon, lat in coords:
        best = min(best, haversine_km(point_lat, point_lon, lat, lon))
    return best
