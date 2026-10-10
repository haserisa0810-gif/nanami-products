from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes


def _request(authorization: str = ""):
    return SimpleNamespace(headers={"Authorization": authorization})


def test_init_db_is_disabled_when_auth_token_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("STORES_MAIL_SYNC_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/test")
    monkeypatch.setattr(routes.pg_store, "init_db", lambda: pytest.fail("must not run"))
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "ensure_table",
        lambda: pytest.fail("must not run"),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.internal_init_db(_request())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "DB initialization is disabled"


def test_init_db_rejects_an_invalid_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("STORES_MAIL_SYNC_TOKEN", "expected-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/test")
    monkeypatch.setattr(routes.pg_store, "init_db", lambda: pytest.fail("must not run"))
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "ensure_table",
        lambda: pytest.fail("must not run"),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.internal_init_db(_request("Bearer wrong-secret"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "unauthorized"


def test_init_db_runs_both_initializers_with_the_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("STORES_MAIL_SYNC_TOKEN", "expected-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/test")
    calls: list[str] = []
    monkeypatch.setattr(routes.pg_store, "init_db", lambda: calls.append("pg_store"))
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "ensure_table",
        lambda: calls.append("marketplace_orders"),
    )

    response = routes.internal_init_db(_request("Bearer expected-secret"))

    assert response == {"ok": True, "message": "DB initialized"}
    assert calls == ["pg_store", "marketplace_orders"]


def test_mail_sync_is_disabled_when_auth_token_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("STORES_MAIL_SYNC_TOKEN", raising=False)
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "sync",
        lambda **_kwargs: pytest.fail("must not sync"),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.internal_mail_sync(_request())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Mail synchronization is disabled"


def test_mail_sync_rejects_an_invalid_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("STORES_MAIL_SYNC_TOKEN", "expected-secret")
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "sync",
        lambda **_kwargs: pytest.fail("must not sync"),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.internal_mail_sync(_request("Bearer wrong-secret"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "unauthorized"


def test_mail_sync_accepts_the_configured_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("STORES_MAIL_SYNC_TOKEN", "expected-secret")
    expected = {"ok": True, "fetched": 2, "parsed": 2}
    monkeypatch.setattr(routes.stores_mail_sync, "sync", lambda **_kwargs: expected)

    response = routes.internal_mail_sync(_request("Bearer expected-secret"))

    assert response.body
    assert b'"ok":true' in response.body
