import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

import routes
from services.personal_edition_delivery import build_personalized_zip


client = TestClient(routes.app)


def test_activation_page_is_independent_from_redeem():
    response = client.get("/personal-edition/activate?lang=en")
    assert response.status_code == 200
    assert "Create your Personal Edition" in response.text
    assert "/redeem/western-full" not in response.text
    assert "applyAccessCodeFromUrl" in response.text
    assert "location.search" in response.text
    assert 'placeholder="YYYYMMDD or YYYY-MM-DD"' in response.text
    assert 'name="birth_date" type="text"' in response.text
    assert '(?:\\d{8}|\\d{4}-\\d{2}-\\d{2})' in response.text
    assert "normalizePEBirthDate" in response.text


def test_activation_code_is_prefilled_from_query_without_validation(monkeypatch):
    looked_up = []
    monkeypatch.setattr(routes.pg_store, "get_personal_edition_code", lambda code: looked_up.append(code))
    response = client.get("/personal-edition/activate?lang=en&code=%20pe-acg-invalid%20")
    assert response.status_code == 200
    assert 'value="PE-ACG-INVALID"' in response.text
    assert looked_up == []


def test_empty_activation_code_query_keeps_input_empty():
    response = client.get("/personal-edition/activate?lang=en&code=")
    assert response.status_code == 200
    assert 'name="access_code"' in response.text
    assert 'value=""' in response.text


def test_etsy_common_access_package_contains_no_code_or_personal_data(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://chart.nanami-astro.com")
    response = client.get(
        "/admin/personal-edition/common-access-package.zip?lang=en",
        auth=("admin", "secret"),
    )
    assert response.status_code == 200
    assert "nanamiastro-ACG-Premium-Bundle-Access-Package.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "README-FIRST.txt", "ACTIVATION-URL.txt", "OPEN-ACTIVATION-PAGE.url"
        }
        combined = b"\n".join(archive.read(name) for name in archive.namelist()).decode("utf-8-sig")
        assert "ACCESS-CODE.pdf" not in combined
        assert "PE-ACG-" not in combined
        assert "PE-FULL-" not in combined
        assert "This Access Package does not contain your personal activation code." in combined
        assert "Your personal activation code will be sent separately through Etsy Messages after your purchase." in combined
        assert "https://chart.nanami-astro.com/personal-edition/activate?lang=en" in combined


def test_admin_code_page_is_available_locally(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    response = client.get("/admin/personal-edition/codes", auth=("admin", "secret"))
    assert response.status_code == 200
    assert "Personal Edition" in response.text
    assert "Issue access code" in response.text
    assert "Generate Etsy Common Access Package" in response.text


def test_admin_issue_page_builds_etsy_message_and_prefilled_url(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://chart.nanami-astro.com")
    captured = {}

    def issue_codes(**kwargs):
        captured.update(kwargs)
        return [{
            "code": "PE-ACG-7K9M-4X2P-H8RW", "status": "unused",
            "product_type": "acg_bundle", "provider": "etsy", "locale": "en",
            "created_at": "2026-07-19", "expires_at": "2026-08-18", "used_at": None,
            "marketplace_order_id": kwargs["marketplace_order_id"],
            "buyer_note": kwargs["buyer_note"],
        }]

    monkeypatch.setattr(routes.pg_store, "issue_personal_edition_codes", issue_codes)
    response = client.post(
        "/admin/personal-edition/codes", auth=("admin", "secret"),
        data={"provider": "etsy", "product_type": "acg_bundle", "count": "1",
              "expiration_days": "30", "marketplace_order_id": "ETSY-123",
              "buyer_note": "buyer memo"},
    )
    assert response.status_code == 200
    assert "Copy Etsy Message" in response.text
    assert "Thank you for your purchase!" in response.text
    assert "Activate your Personal Edition here:" in response.text
    assert "Personalized Birth Chart" in response.text
    assert "can be used only once after successful activation" in response.text
    assert "?lang=en&amp;code=PE-ACG-7K9M-4X2P-H8RW" in response.text
    assert captured["marketplace_order_id"] == "ETSY-123"
    assert captured["buyer_note"] == "buyer memo"


def test_admin_can_download_copyable_access_code_pdf(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    response = client.post(
        "/admin/personal-edition/code-pdf",
        auth=("admin", "secret"),
        data={
            "code": "PE-ACG-7K9M-4X2P-H8RW",
            "product_type": "acg_bundle",
            "lang": "ja",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "PE-ACG-7K9M-4X2P-H8RW-access.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")
    assert b"/Subtype /Link" in response.content


def test_admin_can_download_all_delivery_pdfs_as_zip(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    codes = "PE-ACG-7K9M-4X2P-H8RW\nPE-ACG-9Q3N-5T6V-K2LD"
    response = client.post(
        "/admin/personal-edition/code-pdfs.zip",
        auth=("admin", "secret"),
        data={"codes": codes, "product_type": "acg_bundle", "lang": "en", "provider": "etsy"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "personal-edition-etsy-acg_bundle-buyer-packages.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        delivery_names = [name for name in archive.namelist() if name.endswith("_BUYER-DELIVERY.zip")]
        assert len(delivery_names) == 2
        assert "ADMIN-README.txt" in archive.namelist()
        with zipfile.ZipFile(io.BytesIO(archive.read(delivery_names[0]))) as buyer_zip:
            assert buyer_zip.read("ACCESS-CODE.pdf").startswith(b"%PDF-")
            assert "README-FIRST.txt" in buyer_zip.namelist()
            assert "ACTIVATION-URL.txt" in buyer_zip.namelist()
            assert "&code=PE-ACG-" in buyer_zip.read("ACTIVATION-URL.txt").decode("utf-8-sig")


def test_single_delivery_download_is_buyer_ready_zip_without_outer_zip(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    code = "PE-ACG-7K9M-4X2P-H8RW"
    response = client.post(
        "/admin/personal-edition/code-pdfs.zip",
        auth=("admin", "secret"),
        data={"codes": code, "product_type": "acg_bundle", "lang": "en", "provider": "etsy"},
    )
    assert response.status_code == 200
    assert f'{code}_BUYER-DELIVERY.zip' in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert "ACCESS-CODE.pdf" in names
        assert "README-FIRST.txt" in names
        assert "ACTIVATION-URL.txt" in names
        assert "OPEN-ACTIVATION-PAGE.url" in names
        assert not any(name.endswith(".zip") for name in names)
        assert "ADMIN-README.txt" not in names


def test_personalized_zip_contains_chart_and_autoload():
    data = build_personalized_zip(yaml_text="version: test\nsystems: {}\n", lang="en", chart_url="https://chart.example/chart/private")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        chart_name = next(name for name in names if name == "app/birth-chart.yaml")
        index_name = next(name for name in names if name == "app/index.html")
        assert archive.read(chart_name).decode("utf-8").startswith("version: test")
        html = archive.read(index_name).decode("utf-8")
        assert "fetch('/birth-chart.yaml'" in html
        assert "ht-last-yaml" in html
        assert "START-MUSEUM-WINDOWS.bat" in names
        assert "START-MUSEUM-MAC.command" in names
        assert "README-FIRST.txt" in names
        assert "PRIVATE-CHART-URL.txt" in names
        assert not any(name.startswith("BirthChartMuseum-PersonalEdition-") for name in names)


def test_acg_bundle_zip_contains_precomputed_lines_and_local_map():
    yaml_text = Path("tests/fixtures/yaml_v1_base.yaml").read_text(encoding="utf-8")
    data = build_personalized_zip(yaml_text=yaml_text, lang="ja", include_acg=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        geojson_name = next(name for name in names if name == "app/acg-personal.geojson")
        acg_page = next(name for name in names if name == "app/acg/index.html")
        index_name = next(name for name in names if name == "app/index.html")
        geojson = archive.read(geojson_name).decode("utf-8")
        assert '"acg_eligible":true' in geojson
        assert '"line_group":"Sun_MC"' in geojson
        assert "acg-personal.geojson" in archive.read(acg_page).decode("utf-8")
        assert "あなたのACG地図を開く" in archive.read(index_name).decode("utf-8")
        assert "START-ACG-WINDOWS.bat" in names
        assert "START-ACG-MAC.command" in names
        assert '-OpenPath "/acg/"' in archive.read("START-ACG-WINDOWS.bat").decode("utf-8")
        assert "--open-path /acg/" in archive.read("START-ACG-MAC.command").decode("utf-8")


def test_successful_activation_creates_chart_page(monkeypatch):
    events = []
    monkeypatch.setattr(routes.pg_store, "get_personal_edition_code", lambda code: {
        "status": "unused", "product_type": "western_full", "locale": "ja"
    })
    monkeypatch.setattr(routes.pg_store, "claim_personal_edition_code", lambda code: {"id": 1})
    monkeypatch.setattr(routes.pg_store, "finish_personal_edition_code", lambda code: events.append("finish") or True)
    monkeypatch.setattr(routes.pg_store, "release_personal_edition_code", lambda code: events.append("release"))
    monkeypatch.setattr(routes.pg_store, "save_chart", lambda **kwargs: events.append(("chart", kwargs)))
    monkeypatch.setattr(routes, "_validate_birth_date", lambda value, lang: value)
    monkeypatch.setattr(routes, "resolve_birth_time_accuracy", lambda **kwargs: {
        "calculation_time": "12:00", "accuracy": "unknown", "range": None, "note": "test"
    })
    monkeypatch.setattr(routes, "_build_birth_location", lambda **kwargs: {
        "birth_place": "Tokyo", "lat": 35.0, "lng": 139.0, "tz_name": "Asia/Tokyo"
    })
    monkeypatch.setattr(routes, "build_product_yaml", lambda **kwargs: ("version: test\n", "prompt", {}))
    monkeypatch.setattr(routes, "build_personalized_zip", lambda **kwargs: events.append("zip") or b"PK-test")
    response = client.post("/personal-edition/activate?lang=ja", data={
        "access_code": "PE-FULL-AAAA-BBBB-CCCC",
        "birth_date": "1990-01-01",
        "birth_time_accuracy": "unknown",
        "prefecture": "Tokyo",
        "agree_final": "1",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/chart/")
    assert "personal_download=1" in response.headers["location"]
    assert events[0] == "zip"
    assert events[1][0] == "chart"
    assert events[1][1]["options"]["personal_edition"] is True
    assert events[2] == "finish"

def test_zip_failure_releases_code(monkeypatch):
    events = []
    monkeypatch.setattr(routes.pg_store, "get_personal_edition_code", lambda code: {
        "status": "unused", "product_type": "western_full", "locale": "ja"
    })
    monkeypatch.setattr(routes.pg_store, "claim_personal_edition_code", lambda code: {"id": 1})
    monkeypatch.setattr(routes.pg_store, "release_personal_edition_code", lambda code: events.append("release"))
    monkeypatch.setattr(routes, "_validate_birth_date", lambda value, lang: value)
    monkeypatch.setattr(routes, "resolve_birth_time_accuracy", lambda **kwargs: {
        "calculation_time": "12:00", "accuracy": "unknown", "range": None, "note": "test"
    })
    monkeypatch.setattr(routes, "_build_birth_location", lambda **kwargs: {
        "birth_place": "Tokyo", "lat": 35.0, "lng": 139.0, "tz_name": "Asia/Tokyo"
    })
    monkeypatch.setattr(routes, "build_product_yaml", lambda **kwargs: ("version: test\n", "", {}))
    monkeypatch.setattr(routes, "build_personalized_zip", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    response = client.post("/personal-edition/activate?lang=ja", data={
        "access_code": "PE-FULL-AAAA-BBBB-CCCC",
        "birth_date": "1990-01-01",
        "birth_time_accuracy": "unknown",
        "prefecture": "東京都",
        "agree_final": "1",
    })
    assert response.status_code == 503
    assert events == ["release"]

def test_chart_personal_edition_zip_and_acg_autoload(monkeypatch):
    chart = {
        "yaml_text": "version: test\n",
        "options": {
            "personal_edition": True,
            "personal_edition_locale": "ja",
            "acg_enabled": True,
        },
    }
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: chart)
    monkeypatch.setattr(routes, "build_personalized_zip", lambda **kwargs: b"PK-personal")
    response = client.get("/chart/test-token/personal-edition.zip")
    assert response.status_code == 200
    assert response.content == b"PK-personal"
    assert "ACG-Bundle.zip" in response.headers["content-disposition"]

    acg_page = client.get("/acg?load=/chart/test-token.yaml")
    assert acg_page.status_code == 200
    assert 'new URLSearchParams(window.location.search).get("load")' in acg_page.text
    assert "loadPersonal();" in acg_page.text
