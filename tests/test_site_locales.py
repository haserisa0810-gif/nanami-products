from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes import I18N, _i18n_context, _localized_product, app
from services.prompt_builder import build_prompt


client = TestClient(app)


def _request(path: str, query: bytes) -> Request:
    return Request({
        "type": "http", "method": "GET", "scheme": "https",
        "server": ("chart.nanami-astro.com", 443), "path": path,
        "query_string": query, "headers": [],
    })


@pytest.mark.parametrize(
    ("lang", "button", "planner_title"),
    [
        ("es", "Continuar", "Crear tu Planificador de Tránsitos de 12 meses"),
        ("de", "Weiter", "Deinen 12-Monats-Transitplaner erstellen"),
    ],
)
def test_site_locale_context_includes_full_language_switcher(
    lang: str, button: str, planner_title: str,
) -> None:
    context = _i18n_context(_request("/start/western-full", f"lang={lang}".encode()))
    assert context["lang"] == lang
    assert context["t"]["start_button"] == button
    assert planner_title in context["t"]["create_planner"]
    assert set(context["lang_urls"]) == {"ja", "en", "es", "de"}


@pytest.mark.parametrize(
    ("lang", "product_label", "description_word"),
    [
        ("es", "Carta natal · Edición Personal", "planificador"),
        ("de", "Geburtshoroskop · Personal Edition", "Transitplaner"),
    ],
)
def test_full_product_copy_is_localized(lang: str, product_label: str, description_word: str) -> None:
    product = _localized_product("western_full", lang)
    assert product["label"] == product_label
    assert description_word.lower() in product["description"].lower()


@pytest.mark.parametrize(
    ("lang", "heading", "prompt_phrase"),
    [
        ("es", "Crea tu Edición Personal", "REGLAS DE PRIORIDAD DE LOS DATOS"),
        ("de", "Erstelle deine Personal Edition", "PRIORITÄTSREGELN FÜR DIE DATEN"),
    ],
)
def test_activation_page_and_ai_prompt_are_localized(
    lang: str, heading: str, prompt_phrase: str,
) -> None:
    response = client.get(f"/personal-edition/activate?lang={lang}")
    assert response.status_code == 200
    assert heading in response.text
    assert "Español" in response.text
    assert "Deutsch" in response.text

    prompt = build_prompt(include_asteroids=True, include_transit=True, lang=lang)
    assert prompt_phrase in prompt
    assert "以下のYAML" not in prompt


def test_language_catalogues_preserve_all_existing_keys() -> None:
    assert set(I18N["en"]).issubset(I18N["es"])
    assert set(I18N["en"]).issubset(I18N["de"])


def test_birthplace_region_labels_name_japan_explicitly() -> None:
    assert I18N["ja"]["domestic"] == "日本国内"
    assert I18N["ja"]["international"] == "日本国外"
    assert I18N["en"]["domestic"] == "Japan"
    assert I18N["en"]["international"] == "Outside Japan"
    assert I18N["es"]["domestic"] == "Japón"
    assert I18N["es"]["international"] == "Fuera de Japón"
    assert I18N["de"]["domestic"] == "Japan"
    assert I18N["de"]["international"] == "Außerhalb Japans"


@pytest.mark.parametrize(
    ("lang", "quantity_copy", "confirmation_copy"),
    [
        ("ja", "購入した個数ごとに1回発行できます", "購入分を1件使用します"),
        ("en", "Each purchased copy can be generated once", "uses one purchased copy"),
        ("es", "Cada unidad comprada puede generarse una vez", "se utiliza una unidad comprada"),
        ("de", "Jedes gekaufte Exemplar kann einmal erstellt werden", "wird ein gekauftes Exemplar verwendet"),
    ],
)
def test_redeem_copy_explains_quantity_based_entitlements(
    lang: str, quantity_copy: str, confirmation_copy: str,
) -> None:
    assert quantity_copy in I18N[lang]["precheck_strong"]
    assert confirmation_copy in I18N[lang]["confirm_lead"]


def test_japanese_buyer_templates_do_not_claim_one_order_means_one_generation() -> None:
    for template_name in ("redeem.html", "redeem_shichu.html", "redeem_transit_yaml.html"):
        template = Path("templates", template_name).read_text(encoding="utf-8")
        assert "送信後は同じ注文番号で再生成できません。" not in template
        assert "購入した個数ごとに1回発行できます。" in template
