from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import routes
from services import stores_mail_sync


def _request(token: str = "admin-secret"):
    return SimpleNamespace(
        headers={"X-Admin-Token": token},
        client=SimpleNamespace(host="203.0.113.10"),
    )


def _json(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def _stub_redemption_details(monkeypatch) -> None:
    monkeypatch.setattr(routes.pg_store, "get_redemption_by_order_code", lambda _code: None)
    monkeypatch.setattr(routes.pg_store, "get_redemption_reset_by_order_code", lambda _code: None)
    monkeypatch.setattr(routes.pg_store, "list_charts_by_order_code", lambda _code: [])


def test_etsy_order_number_can_be_looked_up(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY_ADMIN_TOKEN", "admin-secret")
    row = {
        "stores_order_no": "4125350780",
        "provider": "etsy",
        "product_type": "western_full",
        "payment_status": "paid",
    }
    monkeypatch.setattr(routes.stores_mail_sync, "verify_order_no", lambda _code: ("ok", row))
    _stub_redemption_details(monkeypatch)

    response = routes.internal_lookup_redemption(
        _request(),
        {"provider": "etsy", "order_reference": "4125350780"},
    )

    assert response.status_code == 200
    body = _json(response)
    assert body["provider"] == "etsy"
    assert body["order_reference"] == "4125350780"
    assert body["order_code"] == "4125350780"
    assert body["stores_order"]["provider"] == "etsy"


def test_etsy_lookup_rejects_a_stores_order(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY_ADMIN_TOKEN", "admin-secret")
    row = {
        "stores_order_no": "4125350780",
        "provider": "stores",
        "product_type": "western_full",
    }
    monkeypatch.setattr(routes.stores_mail_sync, "verify_order_no", lambda _code: ("ok", row))

    response = routes.internal_lookup_redemption(
        _request(),
        {"provider": "etsy", "order_reference": "4125350780"},
    )

    assert response.status_code == 409
    assert _json(response)["error"]["code"] == "PROVIDER_MISMATCH"


def test_coconala_username_and_product_resolve_to_internal_order(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY_ADMIN_TOKEN", "admin-secret")
    row = {
        "stores_order_no": "COCONALA-1234567890abcdef12345678",
        "provider": "coconala",
        "buyer_reference": "nanami_user",
        "product_type": "acg_bundle",
        "payment_status": "paid",
    }
    calls: list[tuple[str, str]] = []

    def verify_coconala(username: str, *, product_type: str):
        calls.append((username, product_type))
        return "already_used", row

    monkeypatch.setattr(routes.stores_mail_sync, "verify_coconala_buyer", verify_coconala)
    _stub_redemption_details(monkeypatch)

    response = routes.internal_lookup_redemption(
        _request(),
        {
            "provider": "coconala",
            "order_reference": "nanami_user",
            "product_type": "acg_bundle",
        },
    )

    assert response.status_code == 200
    body = _json(response)
    assert calls == [("nanami_user", "acg_bundle")]
    assert body["provider"] == "coconala"
    assert body["order_reference"] == "nanami_user"
    assert body["order_code"] == row["stores_order_no"]
    assert body["order_status"] == "already_used"


def test_coconala_reset_confirms_username_and_resets_internal_order(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY_ADMIN_TOKEN", "admin-secret")
    internal_code = "COCONALA-1234567890abcdef12345678"
    row = {
        "stores_order_no": internal_code,
        "provider": "coconala",
        "buyer_reference": "nanami_user",
        "product_type": "acg_bundle",
    }
    reset_codes: list[str] = []
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "verify_coconala_buyer",
        lambda _username, *, product_type: ("already_used", row),
    )
    monkeypatch.setattr(
        routes.pg_store,
        "reset_redemption_by_order_code",
        lambda code: reset_codes.append(code) or {"reset": True},
    )
    monkeypatch.setattr(
        routes.stores_mail_sync,
        "verify_order_no",
        lambda _code: ("ok", {**row, "payment_status": "reset_once"}),
    )

    response = routes.internal_reset_redemption(
        _request(),
        {
            "provider": "coconala",
            "order_reference": "nanami_user",
            "product_type": "acg_bundle",
            "confirm": "nanami_user",
        },
    )

    assert response.status_code == 200
    body = _json(response)
    assert reset_codes == [internal_code]
    assert body["provider"] == "coconala"
    assert body["order_reference"] == "nanami_user"
    assert body["order_code"] == internal_code
    assert body["order_status"] == "ok"


def test_coconala_requires_product_type(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY_ADMIN_TOKEN", "admin-secret")

    response = routes.internal_lookup_redemption(
        _request(),
        {"provider": "coconala", "order_reference": "nanami_user"},
    )

    assert response.status_code == 400
    assert _json(response)["error"]["code"] == "INVALID_PRODUCT_TYPE"


def test_coconala_lookup_honors_reset_once_override(monkeypatch) -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        {
            "stores_order_no": "COCONALA-reset-order",
            "payment_status": "reset_once",
            "already_used": False,
        }
    ]
    monkeypatch.setattr(stores_mail_sync, "_get_conn", lambda: connection)

    status, row = stores_mail_sync.verify_coconala_buyer(
        "nanami_user",
        product_type="acg_bundle",
    )

    assert status == "ok"
    assert row["stores_order_no"] == "COCONALA-reset-order"
    sql = cursor.execute.call_args.args[0]
    assert "COALESCE(o.payment_status, '') <> 'reset_once'" in sql


def test_admin_page_has_marketplace_controls() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "templates" / "test_site.html"
    ).read_text(encoding="utf-8")

    assert 'id="redemptionProviderInput"' in html
    assert '<option value="etsy">Etsy</option>' in html
    assert '<option value="coconala">ココナラ</option>' in html
    assert 'id="redemptionProductTypeInput"' in html
