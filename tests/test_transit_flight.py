"""Transit Flight（3Dトランジット飛行プロトタイプ）のテスト。

- ページ /transit-flight が配信されること
- Three.js はこのページだけに読み込まれること（他ページ非汚染）
- サンプルデータ JSON が静的配信されること
- テンプレートに必須 UI 要素があること
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import routes

client = TestClient(routes.app)
ROOT = Path(__file__).resolve().parents[1]


def test_transit_flight_page_loads():
    res = client.get("/transit-flight")
    assert res.status_code == 200
    html = res.text
    assert "TRANSIT FLIGHT" in html
    assert "three.min.js" in html
    assert 'id="tf-canvas"' in html
    assert 'id="tf-start"' in html
    assert "FLIGHT START" in html
    assert "transit-flight/transit-flight.js" in html
    assert "transit-flight/transit-flight.css" in html


def test_transit_flight_three_only_on_this_page():
    html = client.get("/transit-flight").text
    assert "three.min.js" in html
    # 既存ページに Transit Flight 用アセット／不要な three を持ち込まない
    # （/astro-earth は独自に three を持つため、専用 JS 非混入のみ確認）
    for path in ["/", "/acg", "/redeem/western-basic", "/astro-earth"]:
        res = client.get(path)
        assert res.status_code == 200, path
        other = res.text
        assert "transit-flight/transit-flight.js" not in other, path
        if path != "/astro-earth":
            assert "three.min.js" not in other, path


def test_sample_data_json_served_and_valid():
    res = client.get("/static/transit-flight/sample-data.json")
    assert res.status_code == 200
    data = res.json()
    assert "profile" in data
    assert "events" in data
    assert data["profile"]["period_start"]
    assert data["profile"]["period_end"]
    assert len(data["events"]) >= 5
    for ev in data["events"]:
        assert "date" in ev
        assert "transit_planet" in ev
        assert "natal_planet" in ev
        assert "aspect" in ev
        assert "level" in ev
        assert ev["level"] in (1, 2, 3)
        assert "theme" in ev


def test_sample_data_file_on_disk_matches_contract():
    path = ROOT / "static" / "transit-flight" / "sample-data.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data["events"], list)
    aspects = {e["aspect"] for e in data["events"]}
    # at least a few aspect types for visual variety
    assert len(aspects) >= 3


def test_static_assets_present():
    assert client.get("/static/transit-flight/transit-flight.js").status_code == 200
    assert client.get("/static/transit-flight/transit-flight.css").status_code == 200
    js = client.get("/static/transit-flight/transit-flight.js").text
    assert "TransitFlight" in js
    assert "prefers-reduced-motion" in js or "reducedMotion" in js
    assert "pagehide" in js
    assert "/api/transit-flight/from-yaml" in js
    assert "tf-load-yaml" in client.get("/transit-flight").text


def _sample_transit_yaml() -> str:
    return """
version: nanami-products-yaml-v1
meta:
  product_type: western_31days_transit_addon
  chart_id: chart_test
input:
  title: Test Person
  birth_date: '1976-08-10'
product:
  type: western_31days_transit_addon
  options:
    transit: true
systems:
  western:
    natal:
      bodies:
        Sun: { sign: Leo, absolute_longitude: 137.9 }
        Venus: { sign: Vir, absolute_longitude: 152.6 }
    transit:
      period:
        start_date: '2026-07-01'
        days: 38
        timezone: Asia/Tokyo
      daily:
        - date: '2026-07-05'
          natal_aspects:
            - transit_body: Jupiter
              natal_body: Sun
              aspect: conjunction
              orb: 0.15
            - transit_body: Moon
              natal_body: Venus
              aspect: trine
              orb: 0.8
        - date: '2026-07-20'
          natal_aspects:
            - transit_body: Uranus
              natal_body: Venus
              aspect: square
              orb: 0.28
            - transit_body: Mars
              natal_body: Sun
              aspect: trine
              orb: 0.4
        - date: '2026-08-01'
          natal_aspects:
            - transit_body: Saturn
              natal_body: Pluto
              aspect: opposition
              orb: 0.35
"""


def test_build_flight_data_from_yaml_extracts_peaks():
    from services.transit_flight_data import build_flight_data_from_yaml

    data = build_flight_data_from_yaml(_sample_transit_yaml())
    assert data["profile"]["name"] == "Test Person"
    assert data["profile"]["birth_date"] == "1976-08-10"
    assert data["profile"]["period_start"] == "2026-07-01"
    assert data["profile"]["period_end"] == "2026-08-07"
    assert len(data["events"]) >= 3
    # Moon with wide orb should be filtered
    moons = [e for e in data["events"] if e["transit_planet"] == "Moon"]
    assert moons == []
    aspects = {e["aspect"] for e in data["events"]}
    assert "conjunction" in aspects or "square" in aspects
    for e in data["events"]:
        assert e["level"] in (1, 2, 3)
        assert e["theme"]


def test_build_flight_data_rejects_natal_only():
    from services.transit_flight_data import TransitFlightDataError, build_flight_data_from_yaml
    import pytest

    natal_only = """
version: nanami-products-yaml-v1
input:
  title: Natal Only
  birth_date: '1976-08-10'
systems:
  western:
    natal:
      bodies:
        Sun: { sign: Leo, absolute_longitude: 100 }
"""
    with pytest.raises(TransitFlightDataError) as exc:
        build_flight_data_from_yaml(natal_only)
    assert "トランジット" in str(exc.value)


def test_api_transit_flight_from_yaml():
    res = client.post(
        "/api/transit-flight/from-yaml",
        json={"yaml_text": _sample_transit_yaml()},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["profile"]["name"] == "Test Person"
    assert len(body["data"]["events"]) >= 3


def test_api_transit_flight_from_yaml_empty():
    res = client.post("/api/transit-flight/from-yaml", json={"yaml_text": ""})
    assert res.status_code == 400
    assert res.json()["ok"] is False


def test_api_transit_flight_from_yaml_natal_only():
    res = client.post(
        "/api/transit-flight/from-yaml",
        json={
            "yaml_text": "systems:\n  western:\n    natal:\n      bodies: {Sun: {sign: Leo}}\n"
        },
    )
    assert res.status_code == 422
    assert "トランジット" in res.json()["error"]


def test_api_accepts_real_fixture_if_present():
    path = ROOT / "hoshiyomi" / "tests" / "fixtures" / "real_data_full.yaml"
    if not path.is_file():
        return
    res = client.post(
        "/api/transit-flight/from-yaml",
        json={"yaml_text": path.read_text(encoding="utf-8"), "max_events": 8},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["profile"]["birth_date"] == "1976-08-10"
    assert 3 <= len(data["events"]) <= 8
    # peaks are ordered by date
    dates = [e["date"] for e in data["events"]]
    assert dates == sorted(dates)


def test_parse_chart_ref_accepts_mcp_style_urls():
    from services.transit_flight_data import TransitFlightDataError, parse_chart_ref
    import pytest

    assert parse_chart_ref("https://chart.nanami-astro.com/chart/chart_c36542f98d2d7e71") == (
        "chart_c36542f98d2d7e71",
        "full",
    )
    assert parse_chart_ref("https://chart.nanami-astro.com/chart/chart_c36542f98d2d7e71.yaml") == (
        "chart_c36542f98d2d7e71",
        "full",
    )
    assert parse_chart_ref("/chart/chart_c36542f98d2d7e71/transit.yaml") == (
        "chart_c36542f98d2d7e71",
        "transit",
    )
    assert parse_chart_ref("/chart/chart_c36542f98d2d7e71/detail.yaml") == (
        "chart_c36542f98d2d7e71",
        "detail",
    )
    assert parse_chart_ref("chart_c36542f98d2d7e71") == ("chart_c36542f98d2d7e71", "full")

    with pytest.raises(TransitFlightDataError):
        parse_chart_ref("https://evil.example/chart/chart_c36542f98d2d7e71")
    with pytest.raises(TransitFlightDataError):
        parse_chart_ref("https://chart.nanami-astro.com/chart/chart_c36542f98d2d7e71/natal.yaml")


def test_api_from_url_requires_ref():
    res = client.get("/api/transit-flight/from-url")
    assert res.status_code == 400
    assert res.json()["ok"] is False


def test_api_from_url_rejects_bad_domain():
    res = client.get(
        "/api/transit-flight/from-url",
        params={"chart_url": "https://evil.example/chart/chart_c36542f98d2d7e71"},
    )
    assert res.status_code == 422
    assert "ドメイン" in res.json()["error"] or "許可" in res.json()["error"]


def test_api_from_yaml_accepts_chart_url_field_shape():
    # unknown chart → 422 not found (or DB error), but must not 400 for missing yaml_text
    res = client.post(
        "/api/transit-flight/from-yaml",
        json={"chart_url": "https://chart.nanami-astro.com/chart/chart_does_not_exist_zzzzz"},
    )
    assert res.status_code in (422, 500)
    body = res.json()
    assert body["ok"] is False
    assert "YAMLテキスト" not in body.get("error", "")


def test_page_has_url_load_ui():
    html = client.get("/transit-flight").text
    assert 'id="tf-url-input"' in html
    assert 'id="tf-load-url"' in html
    js = client.get("/static/transit-flight/transit-flight.js").text
    assert "queryLoadRef" in js
    assert "/api/transit-flight/from-url" in js
