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


def test_post_chart_bulk_new_requires_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")

    response = routes.post_chart_bulk_new(_request())

    assert response.status_code == 401


def test_post_chart_bulk_generate_issues_multiple_no_expiry_transit_urls(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    build_calls: list[dict[str, object]] = []
    saved: list[dict[str, object]] = []
    tokens = iter(["tok-one", "tok-two"])

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

    monkeypatch.setattr(routes, "build_product_yaml", fake_build_product_yaml)
    monkeypatch.setattr(routes, "_build_chart_artifacts", lambda **_kwargs: {})
    monkeypatch.setattr(routes.secrets, "token_urlsafe", lambda _n: next(tokens))
    monkeypatch.setattr(routes.pg_store, "save_chart", lambda **kwargs: saved.append(kwargs))

    response = routes.post_chart_bulk_generate(
        _request(_basic_auth()),
        bulk_input=(
            "トヨタ自動車工業株式会社,1937-08-28,12:00,愛知県 豊田市\n"
            "\n"
            "日付不正,1982/06/08,,広島県 広島市\n"
            "カンマ不足,2020-01-01\n"
            "ハイエレコン,1982-06-08,,広島県 広島市\n"
        ),
    )

    assert response.status_code == 200
    assert response.template.name == "post_chart_bulk_form.html"
    rows = response.context["rows"]
    assert len(rows) == 4
    assert [row["status"] for row in rows] == ["ok", "error", "error", "ok"]
    assert rows[0]["url"] == "https://chart.nanami-astro.com/chart/tok-one"
    assert rows[1]["error"] == "生年月日はYYYY-MM-DDで入力してください。"
    assert rows[2]["error"] == "カンマ区切りで 名前,生年月日,出生時間,出生地 を入力してください。"
    assert rows[3]["birth_time"] == ""
    assert rows[3]["birth_time_accuracy"] == "unknown"
    assert rows[3]["url"] == "https://chart.nanami-astro.com/chart/tok-two"
    assert len(build_calls) == 2
    assert all(call["include_transit"] is True for call in build_calls)
    assert len(saved) == 2
    assert all(item["expires_at"] is None for item in saved)
    assert all(item["options"]["expires_policy"] == routes.NO_EXPIRY_CHART_POLICY for item in saved)
    assert all(item["options"]["url_purpose"] == "post_sample" for item in saved)
    assert all(item["options"]["transit"] is True for item in saved)
    assert all(item["options"]["transit_today"] is True for item in saved)
    assert all(item["options"]["transit_31days_summary"] is True for item in saved)
    assert saved[1]["birth_time"] is None
    assert build_calls[1]["birth_time"] is None
    assert build_calls[1]["birth_time_accuracy"] == "unknown"
    assert "line,name,birth_date,birth_time,birth_time_accuracy,birth_place,url,status,error" in response.context["csv_output"]
    assert "3,日付不正,1982/06/08,,,広島県 広島市,,error,生年月日はYYYY-MM-DDで入力してください。" in response.context["csv_output"]
    assert "4,,,,,,,error,\"カンマ区切りで 名前,生年月日,出生時間,出生地 を入力してください。\"" in response.context["csv_output"]


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
