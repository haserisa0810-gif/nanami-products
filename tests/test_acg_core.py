from __future__ import annotations

import math
from datetime import datetime, timezone

from services.acg_core import (
    LAT_MAX,
    MERIDIAN_LAT,
    _norm180,
    _split_antimeridian,
    lines_to_geojson,
)

DT_2026_07_02 = datetime(2026, 7, 2, 3, 0, tzinfo=timezone.utc)

ALL_PLANETS = {
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
}


def _features_of(fc: dict, group: str) -> list[dict]:
    return [f for f in fc["features"] if f["properties"]["line_group"] == group]


def test_mundane_geojson_structure():
    fc = lines_to_geojson(DT_2026_07_02)
    assert fc["type"] == "FeatureCollection"
    assert fc["meta"]["mode"] == "mundane"
    assert fc["meta"]["datetime_utc"] == "2026-07-02T03:00:00+00:00"

    groups = {f["properties"]["line_group"] for f in fc["features"]}
    # 10天体×4アングル=40本（分割でFeature数はそれ以上になり得る）
    assert len(groups) == 40
    assert len(fc["features"]) >= 40
    planets = {f["properties"]["planet"] for f in fc["features"]}
    assert planets == ALL_PLANETS

    for f in fc["features"]:
        p = f["properties"]
        # 1 Feature = 1 LineString（MultiLineString は使わない）
        assert f["geometry"]["type"] == "LineString"
        assert p["mode"] == "mundane"
        assert p["line_group"] == f"{p['planet']}_{p['angle']}"
        assert p["label"].endswith(f"{p['angle']}線")
        assert p["angle"] in {"ASC", "DSC", "MC", "IC"}
        assert p["line_type"] in {"meridian", "horizon"}
        assert p["meaning"]
        assert {"planet", "angle", "line_type", "label", "meaning"} <= set(p)


def test_labels_have_no_space():
    fc = lines_to_geojson(DT_2026_07_02)
    labels = {f["properties"]["label"] for f in fc["features"]}
    assert "太陽MC線" in labels
    assert "金星MC線" in labels
    for label in labels:
        assert " " not in label


def test_natal_mode_flag():
    fc = lines_to_geojson(DT_2026_07_02, natal=True)
    assert fc["meta"]["mode"] == "natal"
    assert all(f["properties"]["mode"] == "natal" for f in fc["features"])


def test_naive_datetime_treated_as_utc():
    fc = lines_to_geojson(datetime(2026, 7, 2, 3, 0))
    assert fc["meta"]["datetime_utc"] == "2026-07-02T03:00:00+00:00"


def test_mc_is_vertical_two_point_line_and_ic_opposite():
    fc = lines_to_geojson(DT_2026_07_02)
    for planet in ("Sun", "Moon", "Saturn"):
        mc = _features_of(fc, f"{planet}_MC")
        ic = _features_of(fc, f"{planet}_IC")
        assert len(mc) == 1 and len(ic) == 1
        mc_coords = mc[0]["geometry"]["coordinates"]
        assert len(mc_coords) == 2
        assert mc_coords[0][1] == -MERIDIAN_LAT and mc_coords[1][1] == MERIDIAN_LAT
        assert mc_coords[0][0] == mc_coords[1][0]
        diff = abs(_norm180(mc_coords[0][0] - ic[0]["geometry"]["coordinates"][0][0]))
        assert math.isclose(diff, 180.0, abs_tol=0.01)


def test_all_coordinates_within_bounds_and_no_jumps():
    fc = lines_to_geojson(DT_2026_07_02)
    for feature in fc["features"]:
        seg = feature["geometry"]["coordinates"]
        angle = feature["properties"]["angle"]
        lat_limit = MERIDIAN_LAT if angle in ("MC", "IC") else LAT_MAX
        assert len(seg) >= 2
        for lon, lat in seg:
            assert -180.0 <= lon <= 180.0
            assert -lat_limit <= lat <= lat_limit
        # 1つの LineString 内で経度が180度以上飛ばない（またぎは分割済み）
        for (lon1, _), (lon2, _) in zip(seg, seg[1:]):
            assert abs(lon2 - lon1) <= 180.0


def test_antimeridian_splitting_produces_multiple_features():
    """40本のうちどれかは180度をまたぎ、同一line_groupの複数Featureになる。"""
    fc = lines_to_geojson(DT_2026_07_02)
    group_counts: dict[str, int] = {}
    for f in fc["features"]:
        g = f["properties"]["line_group"]
        group_counts[g] = group_counts.get(g, 0) + 1
    assert any(count > 1 for count in group_counts.values())


def test_split_antimeridian_crossing():
    points = [(178.0, 10.0), (-178.0, 12.0)]
    segments = _split_antimeridian(points)
    assert len(segments) == 2
    assert segments[0][-1][0] == 180.0
    assert segments[1][0][0] == -180.0
    # 交点緯度は線形補間で 11.0
    assert math.isclose(segments[0][-1][1], 11.0, abs_tol=0.01)
    assert math.isclose(segments[1][0][1], 11.0, abs_tol=0.01)


def test_split_antimeridian_no_crossing():
    points = [(10.0, -30.0), (20.0, 30.0)]
    segments = _split_antimeridian(points)
    assert segments == [[[10.0, -30.0], [20.0, 30.0]]]


def test_asc_dsc_symmetric_at_equator():
    """赤道上では出没の時角が ±90度 なので、ASC/DSC 経度は MC から等距離。"""
    fc = lines_to_geojson(DT_2026_07_02)
    for planet in ("Sun", "Jupiter"):
        mc_lon = _features_of(fc, f"{planet}_MC")[0]["geometry"]["coordinates"][0][0]

        def lon_at_equator(group: str) -> float | None:
            for f in _features_of(fc, group):
                for lon, lat in f["geometry"]["coordinates"]:
                    if lat == 0.0:
                        return lon
            return None

        asc_lon = lon_at_equator(f"{planet}_ASC")
        dsc_lon = lon_at_equator(f"{planet}_DSC")
        assert asc_lon is not None and dsc_lon is not None
        assert math.isclose(abs(_norm180(mc_lon - asc_lon)), 90.0, abs_tol=1.0)
        assert math.isclose(abs(_norm180(mc_lon - dsc_lon)), 90.0, abs_tol=1.0)


def test_regression_2026_08_13_eclipse_mc_longitude():
    """2026-08-13（食）の MC 線経度回帰テスト。

    基準値 136.238°E は独立検算で照合済み・確定（2026-07-02）:
    定義式 MC経度 = 太陽視赤経 142.809° − グリニッジ視恒星時 6.572° の直計算と
    完全一致。恒星時側も IAU 式で独立に整合確認済み。
    食の前後のため太陽MCと月MCが近接している点も妥当性の傍証。
    """
    fc = lines_to_geojson(datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc))
    sun_mc = _features_of(fc, "Sun_MC")[0]["geometry"]["coordinates"][0][0]
    moon_mc = _features_of(fc, "Moon_MC")[0]["geometry"]["coordinates"][0][0]
    assert math.isclose(sun_mc, 136.238, abs_tol=0.01)
    assert math.isclose(moon_mc, 141.477, abs_tol=0.01)
    assert abs(_norm180(sun_mc - moon_mc)) < 10.0
