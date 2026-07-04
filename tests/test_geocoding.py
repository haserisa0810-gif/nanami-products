"""地名検索（ジオコーディング）と Astro Earth への受け渡しのテスト。

外部ネットワークは叩かない。プロバイダ関数をモックして内部共通形式・
エラー処理・source=manual_search の受け渡しを確認する。
"""
from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

import routes
import services.geocoding_service as geo
from services.astro_earth.earth_service import build_point_insight

client = TestClient(routes.app)

NATAL_YAML = (
    "systems:\n"
    "  western:\n"
    "    natal:\n"
    "      subject:\n"
    '        datetime: "1990-04-10T14:30:00+09:00"\n'
)


@pytest.fixture(autouse=True)
def _reset_geo(monkeypatch):
    geo._cache.clear()
    yield
    geo._cache.clear()


def _mock_provider(results):
    def provider(query, limit):
        return list(results)
    return provider


def test_geocode_endpoint_returns_internal_format(monkeypatch):
    monkeypatch.setattr(geo, "_provider", _mock_provider([
        {"name": "Tokyo, Japan", "latitude": 35.6764, "longitude": 139.65, "display_name": "Tokyo, Japan"},
    ]))
    body = client.get("/api/geocode?q=Tokyo").json()
    assert body["results"], "results should not be empty"
    item = body["results"][0]
    # 内部共通形式
    assert set(["name", "latitude", "longitude", "display_name", "source", "source_label"]).issubset(item.keys())
    assert item["source"] == "manual_search"
    assert item["source_label"] == "検索・手入力した地点"
    assert item["latitude"] == 35.6764 and item["longitude"] == 139.65


def test_geocode_empty_and_short_query(monkeypatch):
    monkeypatch.setattr(geo, "_provider", _mock_provider([]))
    assert client.get("/api/geocode?q=").status_code == 400
    assert client.get("/api/geocode?q=x").status_code == 400


def test_geocode_not_found_returns_empty_with_error(monkeypatch):
    monkeypatch.setattr(geo, "_provider", _mock_provider([]))
    resp = client.get("/api/geocode?q=zzzzzznowhere")
    body = resp.json()
    assert body["results"] == []
    assert body.get("error")


def test_geocode_provider_failure_is_safe(monkeypatch):
    def boom(query, limit):
        raise geo.GeocodingError("network down")
    monkeypatch.setattr(geo, "_provider", boom)
    resp = client.get("/api/geocode?q=Somewhere")
    assert resp.status_code == 502
    assert resp.json()["results"] == []
    assert resp.json().get("error")


def test_geocode_caches_repeated_queries(monkeypatch):
    calls = {"n": 0}

    def provider(query, limit):
        calls["n"] += 1
        return [{"name": "Paris", "latitude": 48.85, "longitude": 2.35, "display_name": "Paris, France"}]

    monkeypatch.setattr(geo, "_provider", provider)
    client.get("/api/geocode?q=Paris")
    client.get("/api/geocode?q=Paris")
    assert calls["n"] == 1, "second identical query should be served from cache"


def test_search_result_feeds_astro_earth_with_manual_source():
    # 検索結果を Astro Earth 解析に渡すと name が埋まり、manual_search になる
    result = build_point_insight(
        natal_yaml_text=NATAL_YAML,
        latitude=35.6764,
        longitude=139.65,
        location_name="Tokyo, Japan",
        source="manual_search",
    )
    loc = yaml.safe_load(result["yaml_text"])["astro_earth_point"]["location"]
    assert loc["name"] == "Tokyo, Japan"
    assert loc["name_resolved"] is True
    assert loc["source"] == "manual_search"
    assert loc["source_label"] == "検索・手入力した地点"
    # AI貼り付け文は manual_search 用
    assert "検索または手入力" in result["prompt_text"]


def test_globe_click_default_source_still_works():
    # 既存の地球儀クリック導線（source未指定→globe_click）が壊れていない
    resp = client.post("/api/astro-earth/point", json={"yaml_text": NATAL_YAML, "lat": 40.0, "lon": -70.0}).json()
    assert resp["location"]["source"] == "globe_click"
    assert resp["interpretation"]["summary"]
