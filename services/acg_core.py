"""アストロカートグラフィ（ACG）天空線の計算コア。

指定時刻（UTC）の天体位置（赤経・赤緯）から、MC/IC/ASC/DSC の4種の天空線を
GeoJSON FeatureCollection として出力する。

- MC/IC 線: 天体が子午線上（南中/北中）に来る経線。2点の縦直線。
- ASC/DSC 線: 天体が地平線上（出/没）に来る地点の曲線。緯度1度刻み（-89〜+89）。
  周極で解なしの緯度はスキップ。
- 1 Feature = 1 線分（LineString）。経度180度またぎは RFC 7946 §3.1.9 に従い
  分割し、複数 Feature にする。論理的な1本は properties.line_group で束ねる。
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import swisseph as swe

from services.western_calc import PLANETS, configure_ephemeris

PLANET_JA = {
    "Sun": "太陽",
    "Moon": "月",
    "Mercury": "水星",
    "Venus": "金星",
    "Mars": "火星",
    "Jupiter": "木星",
    "Saturn": "土星",
    "Uranus": "天王星",
    "Neptune": "海王星",
    "Pluto": "冥王星",
}
PLANET_THEME = {
    "Sun": "自己表現・生命力・存在感",
    "Moon": "感情・安心感・生活リズム",
    "Mercury": "言葉・情報・学び",
    "Venus": "魅力・調和・楽しみ",
    "Mars": "行動力・決断・熱量",
    "Jupiter": "発展・可能性・広がり",
    "Saturn": "責任・継続・安定化",
    "Uranus": "変化・独自性・刷新",
    "Neptune": "感性・想像力・癒やし",
    "Pluto": "集中・再構築・深い変容",
}
ANGLE_THEME = {
    "ASC": "自分の出方・第一印象・新しい始まり",
    "DSC": "出会い・対人関係・協力関係",
    "MC": "仕事・肩書き・社会的な見え方",
    "IC": "住まい・家族・内面の土台",
}

# ASC/DSC 曲線のサンプリング間隔（緯度・度）
LAT_STEP = 1.0
# ASC/DSC のサンプリング緯度範囲（Leaflet の表示範囲が Web メルカトルで ±85 のため）
LAT_MAX = 85.0
# MC/IC 縦直線の端点緯度
MERIDIAN_LAT = 89.0

_COORD_DIGITS = 3


def _norm360(x: float) -> float:
    return x % 360.0


def _norm180(lon: float) -> float:
    """経度を [-180, 180] に正規化する。"""
    return (lon + 180.0) % 360.0 - 180.0


def _julday_utc(dt_utc: datetime) -> float:
    if dt_utc.tzinfo is None:
        utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        utc = dt_utc.astimezone(timezone.utc)
    ut = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    return swe.julday(utc.year, utc.month, utc.day, ut), utc


def _gst_deg(jd: float) -> float:
    """グリニッジ恒星時（度）。"""
    return _norm360(swe.sidtime(jd) * 15.0)


def _equatorial_bodies(jd: float) -> list[dict[str, float | str]]:
    """全対象天体の赤経・赤緯（度）を返す。"""
    flags = configure_ephemeris() | swe.FLG_EQUATORIAL
    bodies: list[dict[str, float | str]] = []
    for name, body_id in PLANETS:
        xx, _ = swe.calc_ut(jd, body_id, flags)
        bodies.append({"name": name, "ra": _norm360(xx[0]), "dec": xx[1]})
    return bodies


def _round_point(lon: float, lat: float) -> list[float]:
    return [round(lon, _COORD_DIGITS), round(lat, _COORD_DIGITS)]


def _split_antimeridian(points: list[tuple[float, float]]) -> list[list[list[float]]]:
    """経度180度をまたぐ線分を RFC 7946 に従って分割する。

    入力は (lon, lat) の列（lon は [-180, 180]）。またぎ位置の緯度は線形補間し、
    片側を ±180、もう片側を ∓180 で開始する複数セグメントに割る。
    """
    if not points:
        return []
    segments: list[list[list[float]]] = []
    current: list[list[float]] = [_round_point(*points[0])]
    for (lon1, lat1), (lon2, lat2) in zip(points, points[1:]):
        if abs(lon2 - lon1) <= 180.0:
            current.append(_round_point(lon2, lat2))
            continue
        # またぎ発生: lon2 を lon1 側に unwrap して交点緯度を補間
        unwrapped = lon2 + 360.0 if lon2 < lon1 else lon2 - 360.0
        edge = 180.0 if unwrapped > lon1 else -180.0
        span = unwrapped - lon1
        t = (edge - lon1) / span if span != 0 else 0.0
        lat_cross = lat1 + t * (lat2 - lat1)
        current.append(_round_point(edge, lat_cross))
        segments.append(current)
        current = [_round_point(-edge, lat_cross), _round_point(lon2, lat2)]
    segments.append(current)
    return [seg for seg in segments if len(seg) >= 2]


def _meridian_points(ra: float, gst: float, angle: str) -> list[tuple[float, float]]:
    """MC/IC 線: 天体の赤経が子午線に一致する経線（2点の縦直線）。"""
    lon = _norm180(ra - gst + (180.0 if angle == "IC" else 0.0))
    return [(lon, -MERIDIAN_LAT), (lon, MERIDIAN_LAT)]


def _horizon_points(ra: float, dec: float, gst: float, angle: str) -> list[tuple[float, float]]:
    """ASC/DSC 線: 天体高度が 0 になる地点を緯度 LAT_STEP 刻みでサンプリング。

    cos(H0) = -tan(緯度) * tan(赤緯) が解を持つ緯度帯のみ点を打つ
    （周極域では天体が出没しないため線が存在しない）。
    """
    dec_rad = math.radians(dec)
    points: list[tuple[float, float]] = []
    steps = int(round(LAT_MAX * 2 / LAT_STEP))
    for i in range(steps + 1):
        lat = -LAT_MAX + i * LAT_STEP
        cos_h0 = -math.tan(math.radians(lat)) * math.tan(dec_rad)
        if abs(cos_h0) > 1.0:
            continue
        h0 = math.degrees(math.acos(cos_h0))
        # 出（ASC）は時角 -H0、没（DSC）は +H0
        lon = _norm180(ra + (h0 if angle == "DSC" else -h0) - gst)
        points.append((lon, lat))
    return points


def _line_features(
    planet: str, angle: str, mode: str, points: list[tuple[float, float]]
) -> list[dict[str, Any]]:
    """1本の論理線を、またぎ分割済みの LineString Feature 群にする。"""
    planet_ja = PLANET_JA.get(planet, planet)
    line_type = "meridian" if angle in {"MC", "IC"} else "horizon"
    properties = {
        "planet": planet,
        "angle": angle,
        "line_type": line_type,
        "mode": mode,
        "label": f"{planet_ja}{angle}線",
        "meaning": f"{PLANET_THEME.get(planet, planet)}が、{ANGLE_THEME.get(angle, angle)}のテーマに表れやすいラインです。",
        "line_group": f"{planet}_{angle}",
    }
    features: list[dict[str, Any]] = []
    for segment in _split_antimeridian(points):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": segment},
                "properties": dict(properties),
            }
        )
    return features


def lines_to_geojson(dt_utc: datetime, natal: bool = False) -> dict[str, Any]:
    """ACG天空線をGeoJSON FeatureCollectionで返す。

    Args:
        dt_utc: 計算基準時刻（UTC）。naive は UTC とみなす。
            - マンデンモード: 対象日の 12:00 UTC など代表時刻
            - パーソナルモード: 出生日時（UTC変換済み）
        natal: True ならネイタル線（出生時刻の天体位置で固定）、
            False ならマンデン線（dt_utc 時点のトランジット天体）。
            計算ロジック自体は両者同一。区別は properties.mode に記録する。

    Returns:
        FeatureCollection。1 Feature = 1 線分（LineString）。
        properties は planet / angle / mode (natal|mundane) / label / line_group。
        経度180度またぎの線は複数 Feature に分割され、line_group で束ねられる。
    """
    jd, utc = _julday_utc(dt_utc)
    gst = _gst_deg(jd)
    mode = "natal" if natal else "mundane"

    features: list[dict[str, Any]] = []
    for body in _equatorial_bodies(jd):
        ra = float(body["ra"])
        dec = float(body["dec"])
        name = str(body["name"])
        for angle in ("MC", "IC"):
            features.extend(_line_features(name, angle, mode, _meridian_points(ra, gst, angle)))
        for angle in ("ASC", "DSC"):
            features.extend(
                _line_features(name, angle, mode, _horizon_points(ra, dec, gst, angle))
            )

    return {
        "type": "FeatureCollection",
        "meta": {
            "mode": mode,
            "datetime_utc": utc.isoformat(),
            "julian_day": round(jd, 6),
            "lat_step_deg": LAT_STEP,
            "lat_range_deg": [-LAT_MAX, LAT_MAX],
        },
        "features": features,
    }
