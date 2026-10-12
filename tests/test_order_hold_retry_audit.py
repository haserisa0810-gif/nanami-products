"""Manual-only hold release regressions, without live services."""
from unittest.mock import MagicMock, patch

import pytest

from services import order_holds, stores_mail_sync as sync


@pytest.mark.parametrize("provider", ["stores", "payhip", "etsy"])
def test_held_unknown_order_must_not_acquire_rights_on_automatic_valid_resync(provider):
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    unknown = sync._parse_payhip_mail(
        "You've Sold An Item!", "Order ID: AuditHeld\nProduct: [NP-SFULL]",
        None, None, "contact@payhip.com")
    unknown["provider"] = provider
    with patch.object(order_holds, "record_hold", return_value=True), patch.object(order_holds, "get_review", return_value=None):
        sync._upsert_order(con, unknown)
    assert unknown["hold_reason"] == "unknown_product_code"

    # The order already exists, but no previously approved purchase units exist.
    cur.fetchone.return_value = {"is_new": False}
    cur.fetchall.return_value = []
    verified = sync._parse_payhip_mail(
        "You've Sold An Item!", "Order ID: AuditHeld\nProduct: [NP-WF]",
        None, None, "contact@payhip.com")
    assert verified["purchase_evidence"] and verified["hold_reason"] is None
    verified["provider"] = provider
    with patch.object(sync, "_upsert_order_entitlements") as grant, patch.object(
        order_holds, "resolve_hold") as resolve, patch.object(order_holds, "get_review", return_value={
            "status": "held", "reason": "unknown_product_code"}), patch.object(order_holds, "save_candidate") as save:
        sync._upsert_order(con, verified)  # Ordinary sync; no admin action provided.
    # Policy expectations are supplied by the user, not copied from the engine.
    assert grant.call_count == 0 and resolve.call_count == 0
    save.assert_called_once()


@pytest.mark.parametrize("failed", [False, True])
def test_notification_retry_does_not_release_orders_or_grant_products(failed):
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [{"provider": "payhip", "order_code": "AuditHeld",
                                 "reason": "unknown_product_code"}]
    with patch.object(order_holds, "notification_config", return_value={"fixture": True}), patch.object(
        order_holds, "send_notification_mail", side_effect=RuntimeError("fixture") if failed else None
    ), patch.object(sync, "_upsert_order_entitlements") as grant, patch.object(
        order_holds, "resolve_hold") as resolve, patch.object(sync, "_upsert_order") as ingest:
        result = order_holds.dispatch_pending_notices(con)
    grant.assert_not_called()
    resolve.assert_not_called()
    ingest.assert_not_called()
    sql = " ".join(call.args[0] for call in cur.execute.call_args_list)
    assert "order_entitlements" not in sql and "charts" not in sql
    assert result["sent"] == int(not failed) and result["failed"] == int(failed)
