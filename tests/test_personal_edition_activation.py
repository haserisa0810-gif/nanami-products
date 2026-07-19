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
    assert "location.hash" in response.text


def test_admin_code_page_is_available_locally(monkeypatch):
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    response = client.get("/admin/personal-edition/codes", auth=("admin", "secret"))
    assert response.status_code == 200
    assert "Personal Edition" in response.text
    assert "引換コード発行" in response.text
    assert "PDF保存" in response.text or "ACG Premium Bundle" in response.text


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
    assert "personal-edition-etsy-acg_bundle-delivery-pdfs.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        pdf_names = [name for name in archive.namelist() if name.endswith(".pdf")]
        assert len(pdf_names) == 2
        assert archive.read(pdf_names[0]).startswith(b"%PDF-")
        assert "README.txt" in archive.namelist()


def test_personalized_zip_contains_chart_and_autoload():
    data = build_personalized_zip(yaml_text="version: test\nsystems: {}\n", lang="en")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        chart_name = next(name for name in names if name.endswith("/app/birth-chart.yaml"))
        index_name = next(name for name in names if name.endswith("/app/index.html"))
        assert archive.read(chart_name).decode("utf-8").startswith("version: test")
        html = archive.read(index_name).decode("utf-8")
        assert "fetch('/birth-chart.yaml'" in html
        assert "ht-last-yaml" in html


def test_acg_bundle_zip_contains_precomputed_lines_and_local_map():
    yaml_text = Path("tests/fixtures/yaml_v1_base.yaml").read_text(encoding="utf-8")
    data = build_personalized_zip(yaml_text=yaml_text, lang="ja", include_acg=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        geojson_name = next(name for name in names if name.endswith("/app/acg-personal.geojson"))
        acg_page = next(name for name in names if name.endswith("/app/acg/index.html"))
        index_name = next(name for name in names if name.endswith("/app/index.html"))
        geojson = archive.read(geojson_name).decode("utf-8")
        assert '"acg_eligible":true' in geojson
        assert '"line_group":"Sun_MC"' in geojson
        assert "acg-personal.geojson" in archive.read(acg_page).decode("utf-8")
        assert "ACG · あなたの天空線" in archive.read(index_name).decode("utf-8")


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
