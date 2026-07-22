from fastapi.testclient import TestClient

import routes


client = TestClient(routes.app)


def test_neko_demo_has_only_the_four_preview_experiences():
    response = client.get("/demo/neko")
    assert response.status_code == 200
    html = response.text
    assert "⭐ Demo Version" in html
    assert "Chief Editor Neko" in html
    assert "✅ Birth Chart" in html
    assert "✅ AI Page" in html
    assert "✅ ACG" in html
    assert "✅ Museum" in html
    assert "/acg?lang=en&amp;demo=neko" in html
    assert "/birth-chart-museum/demo?lang=en" in html
    assert ".yaml" not in html
    assert "prompt.txt" not in html
    assert ".zip" not in html


def test_neko_demo_chart_is_view_only_svg():
    response = client.get("/demo/neko/horoscope.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "attachment" not in response.headers.get("content-disposition", "")
    assert 'viewBox="0 0 1080 1280"' in response.text
    assert "nanami astro" in response.text


def test_neko_acg_returns_geojson_without_source_yaml():
    response = client.get("/api/acg/demo/neko")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"]
    assert "yaml_text" not in response.text


def test_neko_acg_page_marks_sample_data_and_autoloads_demo():
    response = client.get("/acg?lang=en&demo=neko")
    assert response.status_code == 200
    assert "Sample Data" in response.text
    assert 'var DEMO_MODE = true;' in response.text
    assert 'fetch("/api/acg/demo/neko")' in response.text


def test_museum_demo_is_marked_preview():
    response = client.get("/birth-chart-museum/demo?lang=en")
    assert response.status_code == 200
    assert "Preview — Chief Editor Neko" in response.text
