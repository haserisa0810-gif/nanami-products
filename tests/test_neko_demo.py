from unittest.mock import patch

from fastapi.testclient import TestClient

import routes


client = TestClient(routes.app)


def test_neko_demo_includes_permanent_planner_experiences():
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
    assert "/demo/neko/planner.pdf?lang=en" in html
    assert "/demo/neko/planner.pdf?lang=ja" in html
    assert "/demo/neko/planner-ai?lang=en&amp;date=2026-08-01" in html
    assert "/demo/neko/planner-ai?lang=ja&amp;date=2026-08-01" in html
    assert ".yaml" not in html
    assert "prompt.txt" not in html
    assert ".zip" not in html


def test_neko_planner_pdf_is_read_only_and_language_specific():
    with patch("routes._neko_demo_planner_pdf", return_value=b"%PDF-demo") as build:
        response = client.get("/demo/neko/planner.pdf?lang=en")
    assert response.status_code == 200
    assert response.content == b"%PDF-demo"
    assert response.headers["content-type"] == "application/pdf"
    assert "Chief-Editor-Neko-Planner-EN.pdf" in response.headers["content-disposition"]
    build.assert_called_once_with("en")


def test_neko_daily_ai_is_fixed_range_and_does_not_load_customer_chart():
    with (
        patch("routes._load_chart_or_404") as load_chart,
        patch("routes.build_daily_ai_prompt", return_value="fixed demo prompt") as build,
    ):
        en = client.get("/demo/neko/planner-ai?lang=en&date=2026-08-01")
        ja = client.get("/demo/neko/planner-ai?lang=ja&date=2027-07-31")
    assert en.status_code == 200
    assert ja.status_code == 200
    assert "fixed demo prompt" in en.text
    assert "fixed demo prompt" in ja.text
    assert [call.kwargs["lang"] for call in build.call_args_list] == ["en", "ja"]
    load_chart.assert_not_called()

    assert client.get("/demo/neko/planner-ai?lang=en&date=2026-07-31").status_code == 400
    assert client.get("/demo/neko/planner-ai?lang=ja&date=2027-08-01").status_code == 400
    assert client.get("/demo/neko/planner-ai?date=not-a-date").status_code == 400


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
