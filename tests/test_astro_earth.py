"""Astro Earth（3Dアストロカートグラフィ地球儀）のテスト。

- クリック地点の洞察（近いACGライン＋リロケーション＋AI用YAML）の生成
- ステートレスAPI /api/astro-earth/point の入出力
- 3D用ライブラリ（Three.js）は /astro-earth だけに読み込まれること（他ページ非汚染）
"""
from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

import routes
from services.astro_earth.earth_service import build_point_insight

NATAL_YAML = (
    "systems:\n"
    "  western:\n"
    "    natal:\n"
    "      subject:\n"
    '        datetime: "1990-04-10T14:30:00+09:00"\n'
)

client = TestClient(routes.app)


def test_build_point_insight_returns_lines_and_relocation():
    result = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=40.71, longitude=-74.0, location_name="New York")
    assert result["nearest_lines"]
    assert "house_emphasis" in result["relocation"]
    doc = yaml.safe_load(result["yaml_text"])["astro_earth_point"]
    assert doc["app"] == "astro_earth"
    assert doc["location"]["latitude"] == 40.71
    assert "nearest_lines" in doc["acg"]
    # AI再計算禁止ルールが入っている
    assert "再計算" in result["prompt_text"]
    assert "計算済み" in result["prompt_text"]


def test_build_point_insight_wraps_longitude():
    result = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=40.0, longitude=290.0)
    assert result["location"]["longitude"] == -70.0


def test_build_point_insight_rejects_bad_input():
    with pytest.raises(ValueError):
        build_point_insight(natal_yaml_text="", latitude=1, longitude=1)
    from services.acg_api import AcgYamlFormatError

    with pytest.raises(AcgYamlFormatError):
        build_point_insight(natal_yaml_text="hello: world", latitude=1, longitude=1)


def test_astro_earth_page_loads_three_only_here():
    html = client.get("/astro-earth").text
    assert "three.min.js" in html
    assert 'id="globe-canvas"' in html
    # 既存ページに 3D ライブラリを持ち込まない
    for path in ["/", "/travel", "/redeem/western-basic", "/acg"]:
        assert "three.min.js" not in client.get(path).text, path


def test_point_api_success_and_errors():
    ok = client.post("/api/astro-earth/point", json={"yaml_text": NATAL_YAML, "lat": 40.71, "lon": -74.0})
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True
    assert body["nearest_lines"]
    assert body["relocation"]["ascendant"]

    assert client.post("/api/astro-earth/point", json={"yaml_text": "", "lat": 1, "lon": 1}).status_code == 400
    assert client.post("/api/astro-earth/point", json={"yaml_text": "bad: y", "lat": 1, "lon": 1}).status_code == 422
