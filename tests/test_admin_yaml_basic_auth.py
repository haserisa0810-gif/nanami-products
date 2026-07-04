from __future__ import annotations

import base64
from datetime import datetime, timezone
from types import SimpleNamespace

import routes


class DummyUrl:
    def include_query_params(self, **_kwargs):
        return self

    def __str__(self) -> str:
        return "https://chart.nanami-astro.com/admin/yaml/new"


def _request(auth: str = "", host: str = "203.0.113.10"):
    return SimpleNamespace(
        headers={"Authorization": auth} if auth else {},
        client=SimpleNamespace(host=host),
        query_params={},
        base_url="https://chart.nanami-astro.com/",
        url=DummyUrl(),
    )


def _basic_auth(username: str = "admin", password: str = "secret") -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def test_admin_basic_auth_fails_closed_when_env_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_BASIC_USER", raising=False)
    monkeypatch.delenv("ADMIN_BASIC_PASSWORD", raising=False)

    response = routes._admin_basic_auth_error(_request())

    assert response is not None
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith('Basic realm="nanami-products admin"')


def test_admin_basic_auth_allows_local_dev_when_env_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_BASIC_USER", raising=False)
    monkeypatch.delenv("ADMIN_BASIC_PASSWORD", raising=False)

    assert routes._admin_basic_auth_error(_request(host="127.0.0.1")) is None


def test_admin_yaml_new_requires_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")

    response = routes.yaml_new(_request())

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith('Basic realm="nanami-products admin"')


def test_admin_yaml_new_accepts_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")

    response = routes.yaml_new(_request(_basic_auth()))

    assert response.status_code == 200
    assert response.template.name == "yaml_form.html"


def test_admin_yaml_generate_accepts_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    build_calls: list[dict[str, object]] = []

    def fake_build_product_yaml(**kwargs):
        build_calls.append(kwargs)
        return (
            "product:\n  options:\n    western_natal: true\n    transit: true\n    transit_today: true\n    transit_31days_summary: true\n",
            "prompt text",
            {
                "product": {
                    "options": {
                        "western_natal": True,
                        "transit": True,
                        "transit_today": True,
                        "transit_31days_summary": True,
                    }
                }
            },
        )

    monkeypatch.setattr(
        routes,
        "build_product_yaml",
        fake_build_product_yaml,
    )
    monkeypatch.setattr(routes, "_build_chart_artifacts", lambda **_kwargs: {})
    saved: dict[str, object] = {}

    def fake_save_chart(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(routes.pg_store, "save_chart", fake_save_chart)

    response = routes.yaml_generate(
        _request(_basic_auth()),
        title="admin test",
        birth_date="1990-01-01",
        birth_time="12:00",
        prefecture="東京都",
        gender="unknown",
        include_asteroids=None,
        include_shichusuimei=None,
        include_transit=None,
        day_change_at_23=None,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/yaml/result/")
    assert saved["order_code"] is None
    assert saved["expires_at"] is None
    assert saved["options"]["expires_policy"] == routes.NO_EXPIRY_CHART_POLICY
    assert saved["options"]["url_purpose"] == "post_sample"
    assert saved["options"]["product_type"] == "western_full"
    assert saved["options"]["transit"] is True
    assert saved["options"]["transit_today"] is True
    assert saved["options"]["transit_31days_summary"] is True
    assert build_calls[0]["include_transit"] is True


def test_admin_yaml_generate_can_use_standard_90_day_expiry(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    build_calls: list[dict[str, object]] = []

    def fake_build_product_yaml(**kwargs):
        build_calls.append(kwargs)
        return (
            "product:\n  options: {}\n",
            "prompt text",
            {"product": {"options": {}}},
        )

    monkeypatch.setattr(
        routes,
        "build_product_yaml",
        fake_build_product_yaml,
    )
    monkeypatch.setattr(routes, "_build_chart_artifacts", lambda **_kwargs: {})
    standard_expiry = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(routes, "_chart_expires_at", lambda: standard_expiry)

    saved: dict[str, object] = {}
    monkeypatch.setattr(routes.pg_store, "save_chart", lambda **kwargs: saved.update(kwargs))

    response = routes.yaml_generate(
        _request(_basic_auth()),
        title="admin test",
        birth_date="1990-01-01",
        birth_time="12:00",
        prefecture="東京都",
        gender="unknown",
        include_asteroids=None,
        include_shichusuimei=None,
        include_transit=None,
        day_change_at_23=None,
        url_expiry_policy="standard",
    )

    assert response.status_code == 303
    assert saved["expires_at"] is standard_expiry
    assert "expires_policy" not in saved["options"]
    assert saved["options"]["product_type"] == "western_basic"
    assert build_calls[0]["include_transit"] is False


def test_admin_yaml_result_requires_basic_auth_before_loading_chart(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    monkeypatch.setattr(routes, "_load_chart_or_404", lambda _token: (_ for _ in ()).throw(AssertionError))

    response = routes.admin_yaml_result(_request(), "test-token")

    assert response.status_code == 401


def test_admin_yaml_result_accepts_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    monkeypatch.setattr(
        routes,
        "_load_chart_or_404",
        lambda token: {
            "token": token,
            "yaml_text": "product: {}\n",
            "prompt_text": "prompt text",
            "options": {},
        },
    )

    response = routes.admin_yaml_result(_request(_basic_auth()), "test-token")

    assert response.status_code == 200
    assert response.template.name == "admin_result.html"
