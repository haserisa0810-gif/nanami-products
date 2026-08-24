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
    assert "✅ Explore Neko's ACG" in html
    assert "✅ Museum" in html
    assert "/acg?lang=en&amp;demo=neko" in html
    assert "/birth-chart-museum/demo?lang=en" in html
    assert "/demo/neko/planner.pdf?lang=en" in html
    assert "/demo/neko/planner.pdf?lang=ja" in html
    assert "/demo/neko/planner.pdf?lang=en&amp;download=1" in html
    assert "/demo/neko/planner.pdf?lang=ja&amp;download=1" in html
    assert "Open PDF in a new tab" in html
    assert "新しいタブでPDFを見る" in html
    assert "約5MB・432ページ" in html
    assert "/demo/neko/personal-edition.zip?lang=en" in html
    assert "/demo/neko/personal-edition.zip?lang=ja" in html
    assert "fictional sample ACG" in html
    assert "/demo/neko/planner-ai?lang=en&amp;date=2026-08-01" in html
    assert "/demo/neko/planner-ai?lang=ja&amp;date=2026-08-01" in html
    assert ".yaml" not in html
    assert "prompt.txt" not in html
    assert 'href="https://www.etsy.com/shop/nanamiastro"' in html
    assert "Shop ACG &amp; Digital Planner on Etsy" in html
    assert html.index("ACG Personal Edition") < html.index("Digital Planner")
    assert html.index("Digital Planner") < html.index("Free Previews")
    assert html.index("/acg?lang=en&amp;demo=neko") < html.index("/demo/neko/personal-edition.zip?lang=en")
    assert html.index("/demo/neko/planner.pdf?lang=en") < html.index("/demo/neko/planner-ai?lang=en")


def test_neko_personal_edition_zip_is_public_sample_and_language_specific():
    routes._neko_demo_personal_zip_cache.clear()
    try:
        with (
            patch("routes._neko_demo_yaml", return_value="sample: neko\n") as demo_yaml,
            patch("routes.build_personalized_zip", return_value=b"PK-neko-demo") as build,
        ):
            response = client.get("/demo/neko/personal-edition.zip?lang=en")
            cached = client.get("/demo/neko/personal-edition.zip?lang=en")
        assert response.status_code == 200
        assert response.content == b"PK-neko-demo"
        assert cached.content == b"PK-neko-demo"
        assert response.headers["content-type"] == "application/zip"
        assert "Chief-Editor-Neko-Personal-Edition-ACG-Sample-EN.zip" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "public, max-age=86400"
        build.assert_called_once_with(
            yaml_text="sample: neko\n",
            lang="en",
            include_acg=True,
            chart_url="https://chart.nanami-astro.com/demo/neko?lang=en",
        )
        demo_yaml.assert_called_once_with()
    finally:
        routes._neko_demo_personal_zip_cache.clear()


def test_neko_planner_pdf_is_read_only_and_language_specific():
    with patch("routes._neko_demo_planner_pdf", return_value=b"%PDF-demo") as build:
        response = client.get("/demo/neko/planner.pdf?lang=en")
    assert response.status_code == 200
    assert response.content == b"%PDF-demo"
    assert response.headers["content-type"] == "application/pdf"
    assert "Chief-Editor-Neko-Planner-EN.pdf" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].startswith("inline;")
    build.assert_called_once_with("en")

    with patch("routes._neko_demo_planner_pdf", return_value=b"%PDF-demo"):
        download = client.get("/demo/neko/planner.pdf?lang=ja&download=1")
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")
    assert "Chief-Editor-Neko-Planner-JA.pdf" in download.headers["content-disposition"]


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
