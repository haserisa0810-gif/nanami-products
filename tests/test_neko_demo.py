import re
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

import routes
from services.neko_demo_locales import get_neko_demo_ui


client = TestClient(routes.app)


def test_neko_demo_includes_permanent_planner_experiences():
    response = client.get("/demo/neko")
    assert response.status_code == 200
    html = response.text
    assert "⭐ Demo Version" in html
    assert "Chief Editor Neko" in html
    assert "✅ Birth Chart" in html
    assert "✅ AI Page" in html
    assert "✅ Explore Neko&#39;s ACG" in html
    assert "✅ Museum" not in html
    assert "/acg?lang=en&amp;demo=neko" in html
    assert "/birth-chart-museum/demo" not in html
    assert "/demo/neko/planner.pdf?lang=en" in html
    assert "/demo/neko/planner.pdf?lang=en&amp;download=1" in html
    assert "Open PDF in a new tab" in html
    assert "/demo/neko/personal-edition.zip?lang=en" in html
    assert "fictional sample ACG" in html
    assert "/demo/neko/planner-ai?lang=en&amp;date=2026-08-01" in html
    assert "/demo/neko/planner.pdf?lang=ja" not in html
    assert "/demo/neko/personal-edition.zip?lang=ja" not in html
    assert "/demo/neko/planner-ai?lang=ja" not in html
    assert ".yaml" not in html
    assert "prompt.txt" not in html
    assert 'href="https://www.etsy.com/shop/nanamiastro"' in html
    assert "View personalized editions on Etsy" in html
    assert "The paid ACG Bundle includes your personalized ACG and a 12-month Planner." in html
    assert "This page does not sell the paused standalone Planner." in html
    assert "Chief Editor Neko is not included in any paid download." in html
    assert html.index("ACG Personal Edition") < html.index("Included 12-Month Planner")
    assert html.index("Included 12-Month Planner") < html.index("Free Previews")
    assert html.index("/acg?lang=en&amp;demo=neko") < html.index("/demo/neko/personal-edition.zip?lang=en")
    assert html.index("/demo/neko/planner.pdf?lang=en") < html.index("/demo/neko/planner-ai?lang=en")


def test_neko_demo_separates_japanese_downloads_from_english_page():
    response = client.get("/demo/neko?lang=ja")
    assert response.status_code == 200
    html = response.text
    assert '<html lang="ja">' in html
    assert "/demo/neko/planner.pdf?lang=ja" in html
    assert "/demo/neko/personal-edition.zip?lang=ja" in html
    assert "/demo/neko/planner-ai?lang=ja&amp;date=2026-08-01" in html
    assert "/demo/neko/planner.pdf?lang=en" not in html
    assert "/demo/neko/personal-edition.zip?lang=en" not in html
    assert "新しいタブでPDFを見る" in html
    assert "有料のACG Bundleには、ご本人用ACGと12か月プランナーが含まれます。" in html
    assert 'class="cta"' not in html


@pytest.mark.parametrize(
    ("lang", "title", "planner_copy"),
    [
        ("ja", "ねこ編集長のサンプル鑑定", "同梱12か月プランナー"),
        ("en", "Chief Editor Neko&#39;s Sample Chart", "Included 12-Month Planner"),
        ("es", "Carta de muestra de Jefa Editora Neko", "Planner de 12 meses incluido"),
        ("de", "Beispielhoroskop von Chefredakteurin Neko", "Enthaltener 12-Monats-Planner"),
    ],
)
def test_neko_parent_page_is_fully_localized_and_preserves_lang(
    lang: str, title: str, planner_copy: str,
):
    response = client.get(f"/demo/neko?lang={lang}")
    assert response.status_code == 200
    html = response.text
    assert f'<html lang="{lang}">' in html
    assert title in html
    assert planner_copy in html
    assert f"/acg?lang={lang}&amp;demo=neko" in html
    assert f"/demo/neko/personal-edition.zip?lang={lang}" in html
    assert f"/demo/neko/planner.pdf?lang={lang}" in html
    assert f"/demo/neko/planner-ai?lang={lang}&amp;date=2026-08-01" in html
    assert f'<link rel="canonical" href="http://testserver/demo/neko?lang={lang}">' in html
    assert f'<meta property="og:url" content="http://testserver/demo/neko?lang={lang}">' in html
    expected_ogp = "ogp_acg.jpg" if lang == "ja" else f"ogp_acg_{lang}.jpg"
    assert f"/static/{expected_ogp}" in html
    assert "/birth-chart-museum/demo" not in html
    if lang in {"es", "de"}:
        assert re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", html) is None


def test_neko_es_de_use_complete_native_dictionaries():
    keyset = set(get_neko_demo_ui("en"))
    assert set(get_neko_demo_ui("ja")) == keyset
    assert set(get_neko_demo_ui("es")) == keyset
    assert set(get_neko_demo_ui("de")) == keyset
    assert get_neko_demo_ui("es")["hero"] != get_neko_demo_ui("en")["hero"]
    assert get_neko_demo_ui("de")["hero"] != get_neko_demo_ui("en")["hero"]


def test_neko_language_specific_shop_links_are_hidden_until_configured(monkeypatch):
    import config

    monkeypatch.setattr(config, "NEKO_SHOP_URL_ES", "")
    monkeypatch.setattr(config, "NEKO_SHOP_URL_DE", "")
    assert 'class="cta"' not in client.get("/demo/neko?lang=es").text
    assert 'class="cta"' not in client.get("/demo/neko?lang=de").text

    monkeypatch.setattr(config, "NEKO_SHOP_URL_ES", "https://www.etsy.com/listing/spanish-full")
    es_html = client.get("/demo/neko?lang=es").text
    assert 'href="https://www.etsy.com/listing/spanish-full"' in es_html
    assert "Ver ediciones personalizadas en Etsy" in es_html
    assert "https://www.etsy.com/shop/nanamiastro" not in es_html


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
        es = client.get("/demo/neko/planner-ai?lang=es&date=2026-08-01")
        de = client.get("/demo/neko/planner-ai?lang=de&date=2026-08-01")
    assert en.status_code == 200
    assert ja.status_code == 200
    assert es.status_code == 200
    assert de.status_code == 200
    assert "fixed demo prompt" in en.text
    assert "fixed demo prompt" in ja.text
    assert "Interpreta este día con IA" in es.text
    assert "Copiar prompt para IA" in es.text
    assert '<html lang="es">' in es.text
    assert "Diesen Tag mit KI deuten" in de.text
    assert "KI-Prompt kopieren" in de.text
    assert '<html lang="de">' in de.text
    assert [call.kwargs["lang"] for call in build.call_args_list] == ["en", "ja", "es", "de"]
    load_chart.assert_not_called()

    assert client.get("/demo/neko/planner-ai?lang=en&date=2026-07-31").status_code == 400
    assert client.get("/demo/neko/planner-ai?lang=ja&date=2027-08-01").status_code == 400
    assert client.get("/demo/neko/planner-ai?date=not-a-date").status_code == 400


def test_neko_daily_ai_errors_follow_selected_language():
    invalid_es = client.get("/demo/neko/planner-ai?lang=es&date=not-a-date")
    outside_de = client.get("/demo/neko/planner-ai?lang=de&date=2026-07-31")

    assert invalid_es.status_code == 400
    assert invalid_es.json()["detail"] == "Introduce la fecha en formato AAAA-MM-DD."
    assert outside_de.status_code == 400
    assert outside_de.json()["detail"] == "Das gewählte Datum liegt außerhalb des verfügbaren Zeitraums."


@pytest.mark.parametrize(
    ("lang", "title"),
    [
        ("ja", "この日の星をAIで読む"),
        ("en", "Read this day with AI"),
        ("es", "Interpreta este día con IA"),
        ("de", "Diesen Tag mit KI deuten"),
    ],
)
def test_buyer_daily_ai_route_uses_selected_language(monkeypatch, lang: str, title: str):
    chart = {
        "yaml_text": "version: test\n",
        "options": {
            "product_type": "western_full",
            "western_natal": True,
            "transit_days": 38,
        },
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: chart)
    calls = []
    monkeypatch.setattr(
        routes,
        "build_daily_ai_prompt",
        lambda **kwargs: calls.append(kwargs) or f"buyer-prompt-{lang}",
    )

    response = client.get(f"/chart/private-token/planner-ai?lang={lang}&date=2026-08-01")

    assert response.status_code == 200
    assert f'<html lang="{lang}">' in response.text
    assert title in response.text
    assert f"buyer-prompt-{lang}" in response.text
    assert calls[0]["lang"] == lang


def test_buyer_daily_ai_errors_are_localized(monkeypatch):
    allowed = {
        "yaml_text": "version: test\n",
        "options": {"product_type": "western_full", "western_natal": True, "transit_days": 38},
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: allowed)
    invalid = client.get("/chart/private-token/planner-ai?lang=es&date=not-a-date")
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "Introduce la fecha en formato AAAA-MM-DD."

    denied = {"yaml_text": "version: test\n", "options": {"product_type": "western_basic"}}
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: denied)
    unavailable = client.get("/chart/private-token/planner-ai?lang=de&date=2026-08-01")
    assert unavailable.status_code == 404
    assert unavailable.json()["detail"] == "Der tägliche KI-Prompt ist für dieses Produkt nicht verfügbar."


def test_buyer_daily_ai_failure_masks_private_token(monkeypatch, caplog):
    chart = {
        "yaml_text": "version: test\n",
        "options": {"product_type": "western_full", "western_natal": True, "transit_days": 38},
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: chart)
    monkeypatch.setattr(
        routes,
        "build_daily_ai_prompt",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("prompt failed")),
    )
    token = "private-token-that-must-not-be-logged"

    response = client.get(f"/chart/{token}/planner-ai?lang=en&date=2026-08-01")

    assert response.status_code == 503
    assert response.json()["detail"] == "The daily AI prompt could not be generated."
    assert token not in caplog.text


@pytest.mark.parametrize(
    ("lang", "title", "instruction"),
    [
        ("es", "Interpreta este día con IA", "sin volver a calcularlos"),
        ("de", "Diesen Tag mit KI deuten", "ohne sie neu zu berechnen"),
    ],
)
def test_neko_international_daily_ai_response_has_no_visible_japanese(
    lang: str, title: str, instruction: str,
):
    response = client.get(f"/demo/neko/planner-ai?lang={lang}&date=2026-08-01")

    assert response.status_code == 200
    assert title in response.text
    assert instruction in response.text
    assert "sign_ja:" not in response.text
    assert re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", response.text) is None


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
