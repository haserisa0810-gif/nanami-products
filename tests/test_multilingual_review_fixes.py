import io
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
from pypdf import PdfReader
import pytest
import yaml

import routes
import services.geocoding_service as geocoding
from services.addon_prompt_locales import build_addon_prompt
from services.personal_edition_code_pdf import build_personal_edition_code_pdf
from services.personal_edition_delivery import (
    _buyer_readme,
    build_personalized_zip,
    _localize_personal_acg_geojson,
    _localize_personal_acg_html,
)
from services.transit_yaml import TRANSIT_ONLY_PROMPTS
from services.site_locales import REDEEM_ERROR_MESSAGES, redeem_error


client = TestClient(routes.app)


def test_redeem_error_catalogues_have_identical_keys():
    expected_keys = set(REDEEM_ERROR_MESSAGES["ja"])
    for lang in ("en", "es", "de"):
        assert set(REDEEM_ERROR_MESSAGES[lang]) == expected_keys


def test_redeem_save_failure_uses_selected_language_without_exposing_exception():
    exc = RuntimeError("database detail must stay private")
    for lang in ("en", "es", "de"):
        message = routes._buyer_save_error(exc, lang)
        assert message == redeem_error(lang, "save_failed")
        assert "database detail" not in message
    assert routes._buyer_save_error(exc, "ja") == redeem_error("ja", "save_failed")


def test_invalid_prefecture_and_unusable_exact_time_are_localized_without_narrowing_legacy_time():
    for lang in ("ja", "en", "es", "de"):
        with pytest.raises(ValueError) as prefecture_error:
            routes._build_birth_location(
                prefecture="Not-A-Prefecture",
                birth_place_kind="domestic",
                birth_place_overseas="",
                birth_place_city="",
                birth_lat="",
                birth_lng="",
                birth_timezone="",
                lang=lang,
            )
        assert str(prefecture_error.value) == routes.buyer_error(lang, "prefecture_invalid")

        with pytest.raises(ValueError) as time_error:
            routes._validate_exact_birth_time("25:00", lang)
        assert str(time_error.value) == routes.buyer_error(lang, "exact_time_invalid")

        # The existing calculation uses the first two colon-separated fields;
        # keep accepting its historical one-digit and extra-component forms.
        routes._validate_exact_birth_time("7:5", lang)
        routes._validate_exact_birth_time("07:05:30", lang)


def test_addon_product_labels_and_input_errors_never_expose_internal_slugs():
    for lang in ("en", "es", "de"):
        label = routes._product_label_for_lang("western_31days_transit_addon", lang)
        assert label != "western_31days_transit_addon"
        unknown_label = routes._product_label_for_lang("private_internal_slug", lang)
        assert "private_internal_slug" not in unknown_label

        with pytest.raises(ValueError) as yaml_error:
            routes._load_addon_base_yaml("[not: valid", lang)
        assert str(yaml_error.value) == redeem_error(lang, "addon_yaml_unreadable")

        with pytest.raises(ValueError) as url_error:
            routes._load_addon_base_doc_from_previous_chart_url("not-a-url", lang=lang)
        assert str(url_error.value) == redeem_error(lang, "addon_url_invalid")

        with pytest.raises(ValueError) as date_error:
            routes._parse_transit_start_date("", lang)
        assert str(date_error.value) == redeem_error(lang, "addon_start_date_required")


def test_japanese_chart_keeps_time_only_and_purchase_shop_reissue_copy():
    template = Path("templates/chart_page.html").read_text(encoding="utf-8")
    assert "時刻のみ変更可" in template
    assert "購入したショップからお問い合わせください" in template
    assert "公式LINEからお問い合わせください" not in template


def test_redeem_common_validation_errors_follow_selected_language():
    expected = {
        "ja": (
            "注文番号を入力してください。",
            "注文番号には英数字、ハイフン、アンダースコア、イコールのみ使用できます。",
            "入力後は変更できないことを確認し、チェックを入れてください。",
        ),
        "en": (
            "Enter your order number.",
            "The order number may contain only letters, numbers, hyphens, underscores, and equals signs.",
            "Confirm that the information cannot be changed after submission, then select the checkbox.",
        ),
        "es": (
            "Introduce tu número de pedido.",
            "El número de pedido solo puede contener letras, números, guiones, guiones bajos y signos igual.",
            "Confirma que los datos no se pueden modificar después del envío y marca la casilla.",
        ),
        "de": (
            "Bitte gib deine Bestellnummer ein.",
            "Die Bestellnummer darf nur Buchstaben, Zahlen, Bindestriche, Unterstriche und Gleichheitszeichen enthalten.",
            "Bestätige, dass die Angaben nach dem Absenden nicht mehr geändert werden können, und aktiviere das Kontrollkästchen.",
        ),
    }
    for lang, (required, invalid_format, confirmation) in expected.items():
        missing = client.post(
            f"/redeem/western-full?lang={lang}",
            data={"order_code": "", "agree_final": "1"},
        )
        malformed = client.post(
            f"/redeem/western-full?lang={lang}",
            data={"order_code": "BAD/ORDER", "agree_final": "1"},
        )
        unchecked = client.post(
            f"/redeem/western-full?lang={lang}",
            data={"order_code": "VALID-ORDER"},
        )
        assert missing.status_code == malformed.status_code == unchecked.status_code == 400
        assert required in missing.text
        assert invalid_format in malformed.text
        assert confirmation in unchecked.text


def test_redeem_used_order_error_is_localized_for_every_language():
    expected = {
        "ja": "この注文番号（ORDER-123）はすでに使用済みです。別の注文番号をご確認ください。",
        "en": "This order number (ORDER-123) has already been used. Please check a different order number.",
        "es": "Este número de pedido (ORDER-123) ya se ha utilizado. Comprueba otro número de pedido.",
        "de": "Diese Bestellnummer (ORDER-123) wurde bereits verwendet. Bitte überprüfe eine andere Bestellnummer.",
    }
    for lang, message in expected.items():
        assert redeem_error(lang, "order_already_used", order_code="ORDER-123") == message


def test_order_not_found_and_provider_mismatch_follow_selected_language(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("STORES_MAIL_SYNC_ON_SUBMIT", "0")
    expected_not_found = {
        "ja": "注文番号（ORDER-404）が見つかりません。購入確認メールに記載の番号を確認してください。",
        "en": "Order number (ORDER-404) was not found. Check the number in your purchase confirmation.",
        "es": "No se ha encontrado el número de pedido (ORDER-404). Comprueba el número de la confirmación de compra.",
        "de": "Die Bestellnummer (ORDER-404) wurde nicht gefunden. Prüfe die Nummer in deiner Kaufbestätigung.",
    }
    monkeypatch.setattr(
        routes, "_verify_strict_stores_order", lambda _order_id, **_kwargs: ("not_found", None)
    )
    for lang, expected in expected_not_found.items():
        status, _row, error, code = routes._check_order_for_redeem(
            order_id="ORDER-404",
            provider="etsy",
            product_type="western_full",
            lang=lang,
        )
        assert (status, code, error) == ("not_found", 400, expected)

    monkeypatch.setattr(
        routes,
        "_verify_strict_stores_order",
            lambda _order_id, **_kwargs: ("ok", {"provider": "stores", "product_type": "western_full"}),
    )
    for lang in ("en", "es", "de"):
        status, _row, error, code = routes._check_order_for_redeem(
            order_id="ORDER-WRONG-STORE",
            provider="etsy",
            product_type="western_full",
            lang=lang,
        )
        assert (status, code) == ("not_found", 400)
        assert "Etsy" in error
        assert "注文番号" not in error


def test_product_mismatch_error_is_localized(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(
        routes,
        "_verify_strict_stores_order",
        lambda _order_id, **_kwargs: ("ok", {"provider": "etsy", "product_type": "western_basic"}),
    )
    for lang in ("en", "es", "de"):
        status, _row, error, code = routes._check_order_for_redeem(
            order_id="ORDER-WRONG-PRODUCT",
            provider="etsy",
            product_type="western_full",
            lang=lang,
        )
        assert (status, code) == ("product_mismatch", 409)
        assert "注文番号" not in error
        assert routes._product_label_for_lang("western_basic", lang) in error
        assert routes._product_label_for_lang("western_full", lang) in error


def test_payhip_and_coconala_validation_errors_are_localized(monkeypatch):
    for lang in ("ja", "en", "es", "de"):
        _metadata, payhip_error = routes._payhip_metadata_from_form(
            payhip_email="buyer@example.com",
            payhip_product_code="",
            payhip_order_id="",
            expected_product_type="western_full",
            lang=lang,
        )
        assert payhip_error == redeem_error(lang, "payhip_order_required")

        _code, _row, coconala_error, status = routes._resolve_coconala_order_from_buyer(
            buyer_reference="",
            product_type="western_full",
            lang=lang,
        )
        assert status == 400
        assert coconala_error == redeem_error(lang, "coconala_username_required")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    metadata = {
        "purchaser_email": "buyer@example.com",
        "selected_product_code": "",
        "optional_order_id": "PAYHIP-1",
    }
    for lang in ("en", "es", "de"):
        _code, _row, error, status = routes._resolve_payhip_order_from_metadata(
            metadata, lang=lang
        )
        assert status == 503
        assert error == redeem_error(lang, "payhip_service_unavailable")
        assert "DATABASE_URL" not in error


def test_addon_order_not_found_error_is_localized(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("STORES_MAIL_SYNC_ON_SUBMIT", "0")
    monkeypatch.setattr(
        routes.pg_store,
        "redeem_addon_order",
        lambda **_kwargs: ("not_found", None),
    )
    for lang in ("ja", "en", "es", "de"):
        with pytest.raises(ValueError) as exc_info:
            routes._redeem_addon_order_or_raise(
                "ORDER-404", "etsy", "western_asteroids_addon", lang=lang
            )
        assert str(exc_info.value) == redeem_error(
            lang, "order_not_found", order_code="ORDER-404"
        )


def test_activation_language_switch_preserves_access_code():
    response = client.get("/personal-edition/activate?lang=es&code=PE-FULL-TEST")
    assert response.status_code == 200
    assert "/personal-edition/activate?code=PE-FULL-TEST&amp;lang=de" in response.text


def test_geocode_language_is_part_of_provider_call_and_cache(monkeypatch):
    calls = []

    def provider(query, limit, lang):
        calls.append((query, limit, lang))
        return [{"name": "Munich", "latitude": 48.137, "longitude": 11.575, "display_name": "Munich"}]

    monkeypatch.setattr(geocoding, "_provider", provider)
    geocoding._cache.clear()
    assert client.get("/api/geocode?q=Munich&lang=de").json()["results"][0]["source_label"].startswith("Gesuchter")
    assert client.get("/api/geocode?q=Munich&lang=es").json()["results"][0]["source_label"].startswith("Lugar")
    assert [call[2] for call in calls] == ["de", "es"]


def test_personal_acg_shell_is_localized_without_changing_calculation_markers():
    source = Path("personal-edition/acg/index.html").read_text(encoding="utf-8")
    for lang, heading in (("es", "Tus líneas celestes"), ("de", "Deine Himmelslinien")):
        rendered = _localize_personal_acg_html(source, lang)
        assert f'<html lang="{lang}">' in rendered
        assert heading in rendered
        assert "出生時刻" not in rendered
        assert "例：" not in rendered
        assert "/* PERSONAL_ACG_DATA_START */" in rendered


def test_personal_acg_geojson_localizes_display_data_without_changing_coordinates():
    source = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[139.0, 35.0], [140.0, 36.0]]},
            "properties": {"line_group": "Venus_DSC", "label": "金星DSC線", "meaning": "日本語の説明"},
        }],
        "meta": {"personal_context": {"note": "出生図の詳しい解釈は、別途YAML本文を参照"}},
    }
    for lang, expected in (("es", "Línea Venus DSC"), ("de", "Venus-DC-Linie")):
        localized = _localize_personal_acg_geojson(source, lang)
        assert localized["features"][0]["properties"]["label"] == expected
        assert "日本語" not in localized["features"][0]["properties"]["meaning"]
        assert localized["features"][0]["geometry"]["coordinates"] == source["features"][0]["geometry"]["coordinates"]
        assert localized["meta"]["personal_context"]["note"] != source["meta"]["personal_context"]["note"]
    assert source["features"][0]["properties"]["label"] == "金星DSC線"


def test_transit_only_prompts_exist_in_all_supported_languages():
    assert set(TRANSIT_ONLY_PROMPTS) == {"ja", "en", "es", "de"}
    assert "recalcules" in TRANSIT_ONLY_PROMPTS["es"]
    assert "nicht neu" in TRANSIT_ONLY_PROMPTS["de"]


def test_chart_prompt_keeps_transit_and_addon_product_instructions():
    transit_yaml = yaml.safe_dump({"product": {"type": "transit_only_yaml"}})
    transit = routes._chart_prompt_for_yaml_text(
        {"options": {"product_locale": "ja"}, "prompt_text": "stored"},
        transit_yaml,
        lang="es",
    )
    assert "recalcules" in transit

    addon_yaml = yaml.safe_dump({
        "meta": {"product_type": "western_long_term_transits_addon", "data_role": "addon"},
        "product": {"type": "western_long_term_transits_addon"},
    })
    chart = {"options": {"product_locale": "ja"}, "prompt_text": "専用プロンプト"}
    localized = routes._chart_prompt_for_yaml_text(chart, addon_yaml, lang="de")
    assert "Langzeittransite" in localized
    assert "Basis-YAML" in localized
    assert routes._chart_prompt_for_yaml_text(chart, addon_yaml, lang="ja") == "専用プロンプト"


def test_addon_prompt_never_falls_back_to_general_natal_copy():
    assert "datos de asteroides" in build_addon_prompt("western_asteroids_addon", "es")
    assert "Basisradix" in build_addon_prompt("western_31days_transit_addon", "de")


def test_chart_page_keeps_language_in_download_links_and_referrer_header(monkeypatch):
    chart = {
        "yaml_text": yaml.safe_dump({
            "product": {"type": "western_basic", "options": {"western_natal": True}},
            "systems": {"western": {"natal": {"planets": {}}}},
        }),
        "prompt_text": "prompt",
        "options": {"product_type": "western_basic", "product_locale": "es"},
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=True: chart)
    response = client.get("/chart/multilang-token?lang=es")
    assert response.status_code == 200
    assert "/chart/multilang-token/download.zip?lang=es" in response.text
    assert response.headers["referrer-policy"] == "no-referrer"
    prompt = client.get("/chart/multilang-token/prompt.txt?lang=es")
    assert "No recalcules" in prompt.text
    assert prompt.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    ("lang", "label"),
    [
        ("ja", "あなたのデータでACGを開く"),
        ("en", "Open ACG with your data"),
        ("es", "Abrir ACG con tus datos"),
        ("de", "ACG mit deinen Daten öffnen"),
    ],
)
def test_full_chart_consultation_mode_links_to_acg_with_saved_yaml(
    monkeypatch, lang: str, label: str,
):
    yaml_text = Path("tests/fixtures/yaml_v1_base.yaml").read_text(encoding="utf-8")
    chart = {
        "yaml_text": yaml_text,
        "prompt_text": "prompt",
        "options": {
            "product_type": "western_full",
            "product_locale": lang,
            "western_natal": True,
            "transit_31days_summary": True,
        },
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=True: chart)

    response = client.get(f"/chart/full-token?lang={lang}")

    assert response.status_code == 200
    assert label in response.text
    assert f'href="/acg?lang={lang}&amp;load=%2Fchart%2Ffull-token.yaml"' in response.text
    assert 'id="companion-acg-guide" hidden' in response.text


def test_planner_holiday_selector_is_hidden_until_all_locales_are_ready(monkeypatch):
    chart = {
        "yaml_text": yaml.safe_dump({
            "product": {"type": "western_full", "options": {
                "western_natal": True, "transit_31days_summary": True,
            }},
            "systems": {"western": {"natal": {"planets": {"Sun": {}}}}},
        }),
        "prompt_text": "prompt",
        "options": {
            "product_type": "western_full",
            "product_locale": "es",
            "western_natal": True,
            "transit_31days_summary": True,
        },
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=True: chart)
    for lang in ("ja", "en", "es", "de"):
        response = client.get(f"/chart/planner-selector-hidden?lang={lang}")
        assert response.status_code == 200
        assert 'id="planner-holiday-country"' not in response.text


def test_public_acg_ai_export_has_spanish_and_german_copy():
    source = Path("templates/acg_map.html").read_text(encoding="utf-8")
    assert 'AI_EXPORT = LANG === "es"' in source
    assert "interpreta personal_lines_nearby" in source
    assert "deute personal_lines_nearby" in source
    assert "requested_output_language" in source
    assert "if (AI_EXPORT)" in source
    assert 'var contextNote = LANG === "ja"' in source
    assert 'cleanPageUrl.searchParams.delete("load")' in source


def test_public_acg_response_blocks_referrer_leakage():
    response = client.get("/acg?lang=es&load=/chart/private-token.yaml")
    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "no-referrer"


def test_personal_edition_readmes_are_localized():
    for lang, expected, planner in (
        ("es", "INICIO RÁPIDO", "Planner de 1 año"),
        ("de", "SCHNELLSTART", "1-Jahres-Planer"),
    ):
        readme = _buyer_readme(lang=lang, include_acg=False, chart_url="https://example.test/chart")
        assert expected in readme
        assert planner in readme
        assert "あなた専用" not in readme
        assert "はじめ" not in readme
        assert "Birth Chart Museum" not in readme
        assert "MUSEUM" not in readme


def test_access_code_pdf_is_fully_localized_and_prefills_query_code():
    cases = {
        "es": ("Contenido incluido", "Preguntas frecuentes y avisos"),
        "de": ("Enthaltene Inhalte", "FAQ und wichtige Hinweise"),
    }
    for lang, phrases in cases.items():
        pdf_bytes = build_personal_edition_code_pdf(
            code="PE-ACG-7K9M-4X2P-H8RW",
            activation_url=f"https://chart.nanami-astro.com/personal-edition/activate?lang={lang}",
            product_type="acg_bundle",
            lang=lang,
        )
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) == 4
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert all(phrase in text for phrase in phrases)
        assert ("Aplicación ACG personal" in text) if lang == "es" else ("Persönliche ACG-App" in text)
        assert "Birth Chart Museum" not in text
        assert "START-ACG.html" in text
        assert not any("\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff" for char in text)
        urls = []
        for page in reader.pages:
            for annotation in page.get("/Annots") or []:
                action = annotation.get_object().get("/A")
                if action and action.get("/URI"):
                    urls.append(str(action.get("/URI")))
        assert urls == [
            f"https://chart.nanami-astro.com/personal-edition/activate?lang={lang}&code=PE-ACG-7K9M-4X2P-H8RW"
        ]


def test_acg_bundle_pdf_matches_acg_only_personal_zip():
    yaml_text = Path("tests/fixtures/yaml_v1_base.yaml").read_text(encoding="utf-8")
    zip_bytes = build_personalized_zip(
        yaml_text=yaml_text,
        lang="es",
        include_acg=True,
        chart_url="https://example.test/chart?lang=es",
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
    assert "START-ACG.html" in names
    assert not any("MUSEUM" in name for name in names)

    pdf = build_personal_edition_code_pdf(
        code="PE-ACG-7K9M-4X2P-H8RW",
        activation_url="https://example.test/personal-edition/activate?lang=es",
        product_type="acg_bundle",
        lang="es",
    )
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "START-ACG.html" in text
    assert "Birth Chart Museum" not in text


def test_full_personal_edition_pdf_excludes_museum_in_all_languages():
    expected = {
        "ja": "1年パーソナルPlanner",
        "en": "1-year personalized Planner",
        "es": "Planner personal de 1 año",
        "de": "Persönlicher 1-Jahres-Planer",
    }
    for lang, planner_label in expected.items():
        pdf = build_personal_edition_code_pdf(
            code="PE-FULL-7K9M-4X2P-H8RW",
            activation_url=f"https://example.test/personal-edition/activate?lang={lang}",
            product_type="western_full",
            lang=lang,
        )
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
        assert planner_label in text
        assert "Birth Chart Museum" not in text
        assert "Museum öffnen" not in text
        assert "ミュージアム" not in text
        assert "START-ACG.html" not in text


def test_critical_site_copy_is_not_inherited_from_english():
    keys = {
        "chart_note", "addon_title", "yaml_hint_transit", "svg_load_failed",
        "start_transit_input_items", "time_accuracy_items_variable",
        "ai_usage_items", "addon_usage_items",
    }
    for lang in ("es", "de"):
        for key in keys:
            assert routes.I18N[lang][key] != routes.I18N["en"][key]


def test_addon_product_choices_are_localized():
    assert routes._localized_addon_options("es")[0]["label"] == "Complemento de asteroides"
    assert routes._localized_addon_options("de")[2]["label"] == "Langzeittransit-Add-on (1 Jahr)"


def test_personal_edition_validation_errors_are_localized(monkeypatch):
    monkeypatch.setattr(routes.pg_store, "get_personal_edition_code", lambda code: None)
    for lang, expected in (("es", "El código de acceso no es válido."), ("de", "Der Zugangscode ist ungültig.")):
        response = client.post(
            f"/personal-edition/activate?lang={lang}",
            data={"access_code": "PE-INVALID", "agree_final": "1"},
        )
        assert response.status_code == 404
        assert expected in response.text


def test_free_museum_filename_matches_selected_language():
    response = client.get("/downloads/birth-chart-museum-free.zip?lang=es")
    assert response.status_code == 200
    assert "DreamSky-Free-ES.zip" in response.headers["content-disposition"]
