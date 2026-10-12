"""Regression tests for neutral Payhip downloads and the addon hold gate."""
from datetime import datetime, timedelta, timezone
import logging
import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

import routes
from services import pg_store, stores_mail_sync as sync, order_holds


def download(order="DownloadOrder", source="private-source@example.invalid"):
    return sync._parse_payhip_mail("Someone Requested a Download!",
        f"Order ID: {order}\nProduct: [NP-WF]\nBuyer: private@example.invalid",
        source, None, "contact@payhip.com")


def test_download_does_not_enter_any_purchase_database_path(caplog):
    row = download()
    con = MagicMock()
    with caplog.at_level(logging.INFO, logger=order_holds.__name__):
        assert not sync._upsert_order(con, row)
    con.cursor.assert_not_called()
    assert row["_ignored_notice"] is True
    assert "order_code=DownloadOrder" in caplog.text
    assert "kind=download" in caplog.text
    assert "private" not in caplog.text and "NP-WF" not in caplog.text


def test_audit_rejects_untrusted_order_log_text(caplog):
    with caplog.at_level(logging.INFO, logger=order_holds.__name__):
        order_holds.audit_download_notice(order_code="bad\nBuyer: secret", source_id="secret")
    assert "order_code=invalid" in caplog.text and "secret" not in caplog.text


def test_download_sync_does_not_count_hold_or_queue_operator_notification():
    con = MagicMock()
    raw = b"From: contact@payhip.com\nSubject: Someone Requested a Download!\n\nOrder ID: DownloadOrder\nProduct: [NP-WF]"
    with patch.dict(os.environ, {"STORES_MAIL_BACKEND": "gmail_api"}), \
         patch("services.gmail_mail_api.fetch_order_messages", return_value=[raw]), \
         patch.object(sync, "_get_conn", return_value=con), \
         patch.object(sync, "_require_stores_orders_table"), \
         patch.object(order_holds, "dispatch_pending_notices", return_value={"status": "unconfigured"}), \
         patch.object(order_holds, "notify_operator") as notify, \
         patch.object(order_holds, "record_hold") as hold:
        result = sync.sync()
    assert result["ok"] and result["parsed"] == 1 and result["skipped"] == 1
    assert result["held"] == result["new_holds"] == result["inserted"] == 0
    con.cursor.assert_not_called()
    hold.assert_not_called()
    notify.assert_not_called()


@pytest.mark.parametrize("method", ["redeem_addon_order", "redeem_addon_order_and_save_chart",
                                    "redeem_addon_order_and_save_transit_link"])
@pytest.mark.parametrize("provider", ["stores", "payhip", "etsy"])
def test_all_addon_entrypoints_reject_held_order_before_any_consumption(method, provider):
    cur = MagicMock()
    cur.fetchone.side_effect = [
        {"entitlement_table": "entitlements", "marketplace_table": "orders", "hold_table": "holds"},
        {"held": 1}, {"table_name": "orders"},
        {"provider": provider, "stores_order_no": "Held", "payment_status": "paid",
         "product_type": "western_asteroids_addon"},
    ]
    con = MagicMock()
    con.cursor.return_value.__enter__.return_value = cur
    kwargs = dict(order_code="Held", provider=provider, addon_type="western_asteroids_addon")
    if method != "redeem_addon_order":
        kwargs.update(token="must-not-exist", expires_at=datetime.now(timezone.utc))
        if method.endswith("chart"):
            kwargs["chart_payload"] = {}
        else:
            kwargs["yaml_text"] = "unchanged"
    with patch.object(pg_store, "_conn") as connect:
        connect.return_value.__enter__.return_value = con
        status, order = getattr(pg_store, method)(**kwargs)
    assert status == "held" and "_consumption_blocked" not in order
    statements = [args[0] for args, _ in cur.execute.call_args_list]
    assert "pg_advisory_xact_lock" in statements[0]
    assert not any("INSERT" in sql or "UPDATE " in sql for sql in statements)


@pytest.mark.parametrize("path", [".yaml", "/prompt.txt"])
@pytest.mark.parametrize("expired", [False, True])
def test_existing_payhip_original_redownload_is_read_only_and_keeps_expiry(path, expired):
    expiry = datetime.now(timezone.utc) + timedelta(days=-1 if expired else 10)
    chart = {"token": "original-payhip", "order_code": "DownloadOrder",
             "options": {"order_provider": "payhip", "product_type": "western_full"},
             "yaml_text": "saved_original: true\n", "prompt_text": "saved prompt",
             "expires_at": expiry, "created_at": datetime.now(timezone.utc)}
    with patch.object(pg_store, "get_chart", return_value=chart), \
         patch.object(pg_store, "redeem_and_save") as consume, \
         patch.object(pg_store, "save_chart") as save:
        response = TestClient(routes.app).get(f"/chart/original-payhip{path}")
    assert response.status_code == (410 if expired else 200)
    if not expired:
        assert response.text == (chart["yaml_text"] if path == ".yaml" else chart["prompt_text"])
    consume.assert_not_called()
    save.assert_not_called()
