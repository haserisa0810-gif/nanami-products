import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import routes


def _request(path: str, query: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": query.encode("ascii"),
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
            "root_path": "",
        }
    )


def _personal_chart() -> dict:
    return {
        "yaml_text": Path("tests/fixtures/yaml_v1_base.yaml").read_text(encoding="utf-8"),
        "options": {"personal_edition": True, "acg_enabled": True},
    }


def test_personal_acg_app_page_is_installable_and_self_contained(monkeypatch):
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: _personal_chart())
    response = routes.personal_acg_app(
        _request("/chart/private-token/acg-app/", "lang=ja"),
        "private-token",
    )
    html = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private, no-store")
    assert 'rel="manifest" href="/chart/private-token/acg-app/manifest.webmanifest?lang=ja"' in html
    assert 'id="pwa-install"' in html
    assert "ホーム画面に追加" in html
    assert "serviceWorker.register" in html
    assert '"line_group":"Sun_MC"' in html
    assert "MAX_PLACES=3" in html
    assert "cities.min.json" not in html
    assert "nanami-personal-acg-places-v1" not in html


def test_personal_acg_manifest_and_worker_are_scoped_to_one_buyer(monkeypatch):
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: _personal_chart())
    manifest_response = routes.personal_acg_manifest(
        _request("/chart/private-token/acg-app/manifest.webmanifest", "lang=en"),
        "private-token",
    )
    manifest = json.loads(manifest_response.body)
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/chart/private-token/acg-app/"
    assert manifest["start_url"].startswith("/chart/private-token/acg-app/")

    worker_response = routes.personal_acg_service_worker(
        _request("/chart/private-token/acg-app/sw.js", "lang=en"),
        "private-token",
    )
    worker = worker_response.body.decode("utf-8")
    assert "caches.open(CACHE_NAME)" in worker
    assert 'const APP_PATH="/chart/private-token/acg-app/"' in worker
    assert "tile.openstreetmap.org" not in worker


def test_personal_acg_app_rejects_non_personal_chart(monkeypatch):
    chart = {"yaml_text": "version: test\n", "options": {"acg_enabled": True}}
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda token, include_svgs=False: chart)
    with pytest.raises(HTTPException) as error:
        routes._personal_acg_app_chart("not-personal")
    assert error.value.status_code == 404
