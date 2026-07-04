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


def test_location_has_source_and_labels_in_yaml():
    result = build_point_insight(
        natal_yaml_text=NATAL_YAML, latitude=43.96, longitude=-26.95, source="globe_click"
    )
    loc = yaml.safe_load(result["yaml_text"])["astro_earth_point"]["location"]
    # 1 & 2: source と source_label が YAML に出る
    assert loc["source"] == "globe_click"
    assert loc["source_label"] == "地球儀でクリックした地点"
    # 3: name が null でも display 用の名称がある
    assert loc["name"] is None
    assert loc["name_resolved"] is False
    assert "名称未取得の地点" in loc["display_name"]
    assert "北緯43.96" in loc["display_name"] and "西経26.95" in loc["display_name"]


def test_ai_prompt_states_point_context():
    # 4: AI貼り付け文の冒頭に「出生地ではなく選択地点」等の前提が入る
    globe = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=40.0, longitude=-70.0, source="globe_click")
    assert "出生地ではなく" in globe["prompt_text"]
    assert "選択した地点" in globe["prompt_text"]

    birth = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=40.0, longitude=-70.0, source="birth_place")
    assert "出生地を基準" in birth["prompt_text"]

    manual = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=40.0, longitude=-70.0, source="manual_search")
    assert "検索または手入力" in manual["prompt_text"]


def test_interpretation_summary_and_theme_scores():
    result = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=43.96, longitude=-26.95)
    it = result["interpretation"]
    # 5: summary が空ではない
    assert it["summary"].strip()
    # 6: テーマ別スコアが出る（1〜5）
    assert it["themes"]
    for theme in it["themes"]:
        assert 1 <= theme["score"] <= 5
        assert theme["label"] and theme["reason"]
    assert it["how_to_use"]


def test_existing_acg_and_relocation_are_still_present():
    # 7: 既存のACGライン・リロケーション計算結果はそのまま含まれる（計算は変更しない）
    result = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=40.71, longitude=-74.0)
    assert result["nearest_lines"] and "distance_km" in result["nearest_lines"][0]
    assert result["relocation"]["ascendant"]["sign"]
    assert "house_emphasis" in result["relocation"]


def test_unknown_source_falls_back():
    result = build_point_insight(natal_yaml_text=NATAL_YAML, latitude=1.0, longitude=1.0, source="banana")
    assert result["location"]["source"] == "unknown"
    assert result["location"]["source_label"]


def test_point_api_returns_source_and_interpretation():
    resp = client.post(
        "/api/astro-earth/point",
        json={"yaml_text": NATAL_YAML, "lat": 43.96, "lon": -26.95, "source": "globe_click"},
    ).json()
    assert resp["location"]["source"] == "globe_click"
    assert resp["location"]["source_label"] == "地球儀でクリックした地点"
    assert resp["interpretation"]["summary"]
    assert resp["interpretation"]["themes"]


def test_point_api_success_and_errors():
    ok = client.post("/api/astro-earth/point", json={"yaml_text": NATAL_YAML, "lat": 40.71, "lon": -74.0})
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True
    assert body["nearest_lines"]
    assert body["relocation"]["ascendant"]

    assert client.post("/api/astro-earth/point", json={"yaml_text": "", "lat": 1, "lon": 1}).status_code == 400
    assert client.post("/api/astro-earth/point", json={"yaml_text": "bad: y", "lat": 1, "lon": 1}).status_code == 422
