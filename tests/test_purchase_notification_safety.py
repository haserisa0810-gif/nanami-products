"""Purchase-field and operator-hold regressions, with no live connections."""
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")
import routes
from services import stores_mail_sync as sync, order_holds, pg_store
from services.purchase_mail_items import analyze_purchase_items

FIXTURES = json.loads((Path(__file__).parent / "fixtures/marketplace/notifications_anonymous_20261011.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f"{f['provider']}-{f['sample']}")
def test_anonymous_original_notification_fields(fixture):
    row = getattr(sync, f"_parse_{fixture['provider']}_mail")(
        fixture["subject"], fixture["body"], None, None, f"orders@{fixture['provider']}.com")
    assert [item["sku"] for item in row["line_items"]] == fixture["expected_codes"]
    assert row["hold_reason"] == fixture["expected_hold"]


@pytest.mark.parametrize("provider", ["payhip", "stores", "etsy"])
def test_guide_and_subject_codes_cannot_change_purchased_product(provider):
    body = ("Order ID: Fixture\n注文番号：9123456789\nProduct: [NP-WF]\nQuantity: 2\n"
            "Other products available:\nProduct: [NP-AA]\nQuantity: 10\n[NP-TA]\n")
    row = analyze_purchase_items(provider, "Guide [NP-WB]", body)
    assert row["product_type"] == "western_full" and row["hold_reason"] is None
    assert [(i["sku"], i["quantity"]) for i in row["line_items"]] == [("NP-WF", 2)]


@pytest.mark.parametrize("body,reason", [
    ("Product: [NP-SFULL] Full", "unknown_product_code"),
    ("Product: [NP-WF] [NP-AA]", "ambiguous_product_field"),
    ("Product: Fixture", "product_code_missing"),
    ("Full [NP-WF]", "purchase_fields_missing"),
    ("Product: [NP-WF]\nQuantity: 0", "invalid_quantity"),
    ("Product: [NP-WF]\nQuantity: 101", "invalid_quantity"),
    ("Product: [NP-WF]\nQuantity: many", "invalid_quantity"),
    ("Product: [NP-WF]\nProduct: [NP-SFULL]", "unknown_product_code"),
])
def test_unknown_or_ambiguous_order_has_no_new_rights(body, reason):
    row = analyze_purchase_items("payhip", "You've Sold An Item!", body)
    assert row["line_items"] == [] and row["product_type"] is None
    assert row["hold_reason"] == reason


def test_payhip_price_table_ends_at_total_and_preserves_real_multi_purchase():
    body = ("The following items have been purchased:\nOrder ID: Fixture\n"
            "Fixture [NP-WF]\n&nbsp;\n&#36;1.00\nFixture [NP-AA]\n&#36;1.00\n"
            "Total\n$2.00\nProduct: [NP-WB]\nQuantity: 4")
    row = analyze_purchase_items("payhip", "You've Sold An Item!", body)
    assert [i["sku"] for i in row["line_items"]] == ["NP-WF", "NP-AA"]
    assert row["product_type"] is None and row["hold_reason"] is None


def test_malformed_purchase_table_is_held_whole():
    row = analyze_purchase_items("payhip", "You've Sold An Item!",
        "The following items have been purchased:\nOrder ID: Fixture\n"
        "Fixture [NP-WF]\n$1.00\nFixture [NP-AA]\nunknown price\nTotal\n$1.00")
    assert row["line_items"] == [] and row["hold_reason"] == "purchase_fields_missing"


def test_download_cannot_grant_purchase_rights_even_with_labeled_codes():
    row = sync._parse_payhip_mail("Someone Requested a Download!",
        "Order ID: Fixture\nProduct: [NP-WF]\nTotal: $1.00", None, None, "contact@payhip.com")
    assert row["line_items"] == [] and row["hold_reason"] == "non_purchase_notification"
    assert row["payment_status"] == "ordered"


def test_held_resync_never_updates_existing_rights_or_chart():
    con = MagicMock()
    with patch.object(sync, "_upsert_order_entitlements") as grant, patch.object(order_holds, "record_hold", return_value=True):
        sync._upsert_order(con, {"provider": "payhip", "stores_order_no": "Fixture",
                                "hold_reason": "unknown_product_code", "payment_status": "paid"})
    grant.assert_not_called()
    sql = next(" ".join(call.args[0].split()) for call in con.cursor.return_value.__enter__.return_value.execute.call_args_list
               if "INSERT INTO" in call.args[0])
    assert "ON CONFLICT (provider, order_code) DO NOTHING" in sql
    assert "UPDATE" not in sql and "charts" not in sql and "order_entitlements" not in sql


def test_new_unclassified_order_cannot_escape_atomic_check_via_legacy_redemption():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        {"entitlement_table": "order_entitlements", "marketplace_table": "marketplace_orders"},
        None, None, {"product_type": None, "payment_status": "paid"}]
    assert pg_store._claim_order_entitlement(cur, order_code="Fixture", provider="payhip",
                                            product_type="western_full", chart_token="FixtureToken") == (True, None)


def test_operator_notice_has_id_and_reason_only(caplog):
    with caplog.at_level("WARNING"):
        order_holds.notify_operator(provider="payhip", order_code="Fixture123", reason="product_code_missing")
        order_holds.notify_operator(provider="payhip", order_code="buyer@example.invalid", reason="product_code_missing")
    assert "Fixture123" in caplog.text and "product_code_missing" in caplog.text
    assert "buyer@example.invalid" not in caplog.text and len(caplog.records) == 1


def test_admin_hold_list_is_authenticated_and_does_not_query_without_token():
    with patch.dict(os.environ, {"API_KEY_ADMIN_TOKEN": "FixtureAdmin"}), patch.object(sync, "_get_conn") as conn:
        response = TestClient(routes.app).get("/internal/orders/holds")
    assert response.status_code == 401
    conn.assert_not_called()


def test_admin_hold_list_returns_safe_fields_and_closes_connection():
    con = MagicMock()
    rows = [{"provider": "etsy", "order_code": "Fixture", "reason": "product_code_missing"}]
    with patch.dict(os.environ, {"API_KEY_ADMIN_TOKEN": "FixtureAdmin"}), patch.object(sync, "_get_conn", return_value=con), patch.object(order_holds, "list_holds", return_value=rows):
        response = TestClient(routes.app).get("/internal/orders/holds", headers={"X-Admin-Token": "FixtureAdmin"})
    assert response.status_code == 200 and response.json()["holds"] == rows
    con.close.assert_called_once()


def test_hold_notice_is_emitted_only_after_successful_commit():
    con = MagicMock()
    con.commit.side_effect = RuntimeError("buyer@example.invalid must never be logged")
    raw = b"From: contact@payhip.com\nSubject: You've Sold An Item!\n\nOrder ID: Fixture\nProduct: [NP-SFULL]"
    def upsert(connection, parsed):
        parsed["_new_hold"] = True
        return True
    with patch.dict(os.environ, {"STORES_MAIL_BACKEND": "gmail_api"}), patch("services.gmail_mail_api.fetch_order_messages", return_value=[raw]), patch.object(sync, "_get_conn", return_value=con), patch.object(sync, "_require_stores_orders_table"), patch.object(sync, "_upsert_order", side_effect=upsert), patch.object(order_holds, "notify_operator") as notify:
        result = sync.sync()
    assert not result["ok"] and result["message"] == "RuntimeError"
    assert "buyer@example.invalid" not in str(result)
    notify.assert_not_called()
    con.rollback.assert_called_once()


def test_mime_alternatives_do_not_double_the_purchase_when_html_is_first():
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("<p>Product: [NP-WF]</p><p>Quantity: 2</p>", "html"))
    msg.attach(MIMEText("Product: [NP-WF]\nQuantity: 2", "plain"))
    row = analyze_purchase_items("payhip", "You've Sold An Item!", sync._extract_text(msg))
    assert len(row["line_items"]) == 1 and row["line_items"][0]["quantity"] == 2


def test_html_only_notification_and_attachment_are_separate():
    msg = MIMEMultipart()
    attachment = MIMEText("Product: [NP-AA]\nQuantity: 100", "plain")
    attachment.add_header("Content-Disposition", "attachment", filename="guide.txt")
    msg.attach(attachment)
    msg.attach(MIMEText("<p>Product: [NP-WF]</p><p>Quantity: 1</p>", "html"))
    row = analyze_purchase_items("payhip", "You've Sold An Item!", sync._extract_text(msg))
    assert [item["sku"] for item in row["line_items"]] == ["NP-WF"]


def test_email_delivery_has_only_operator_identity_and_reason():
    config = {"ORDER_HOLD_NOTIFY_TO": "operator@example.invalid",
              "ORDER_HOLD_NOTIFY_FROM": "sender@example.invalid", "ORDER_HOLD_SMTP_HOST": "smtp.example.invalid",
              "ORDER_HOLD_SMTP_USERNAME": "Fixture", "ORDER_HOLD_SMTP_PASSWORD": "FixtureSecret",
              "mode": "ssl", "port": 465}
    row = {"provider": "etsy", "order_code": "FixtureOrder", "reason": "product_code_missing",
           "buyer_email": "private@example.invalid", "body": "Personal note must not leave the order"}
    with patch.object(order_holds.smtplib, "SMTP_SSL") as smtp:
        order_holds.send_notification_mail(config, row)
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert "FixtureOrder" in message.get_content()
    assert "private@example.invalid" not in str(message) and "Personal note" not in message.get_content()
    assert "FixtureSecret" not in str(message)


@pytest.mark.parametrize("send_error,expected_status", [(False, "sent"), (True, "pending")])
def test_delivery_state_retries_failures_without_losing_hold(send_error, expected_status, caplog):
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [{"provider": "payhip", "order_code": "Fixture", "reason": "unknown_product_code"}]
    with patch.object(order_holds, "notification_config", return_value={"configured": True}), patch.object(
        order_holds, "send_notification_mail", side_effect=RuntimeError("private@example.invalid") if send_error else None):
        result = order_holds.dispatch_pending_notices(con)
    assert cur.execute.call_args.args[1][0] == expected_status
    assert result["failed"] == int(send_error) and result["sent"] == int(not send_error)
    assert "private@example.invalid" not in caplog.text
    assert "FOR UPDATE SKIP LOCKED" in cur.execute.call_args_list[0].args[0]
    con.commit.assert_called_once()


def test_missing_email_config_does_not_mark_notice_sent_or_open_smtp():
    con = MagicMock()
    with patch.object(order_holds, "notification_config", return_value=None), patch.object(order_holds.smtplib, "SMTP_SSL") as smtp:
        assert order_holds.dispatch_pending_notices(con)["status"] == "unconfigured"
    smtp.assert_not_called()
    con.cursor.assert_not_called()


def test_changed_replay_quantity_is_held_without_extending_rights():
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = {"is_new": False}
    cur.fetchall.return_value = [{"line_item_key": "NP-WF:1", "sku": "NP-WF",
                                "product_type": "western_full", "unit_index": 1}]
    row = sync._parse_payhip_mail("You've Sold An Item!", "Order ID: Fixture\nProduct: [NP-WF]\nQuantity: 2", None, None, "contact@payhip.com")
    with patch.object(order_holds, "record_hold", return_value=True), patch.object(sync, "_upsert_order_entitlements") as grant:
        sync._upsert_order(con, row)
    assert row["hold_reason"] == "purchase_details_conflict"
    grant.assert_not_called()


def test_stores_partial_table_cannot_grant_only_the_recognized_half():
    row = analyze_purchase_items("stores", "アイテムが購入されました",
        "1. [NP-WF] Fixture\n￥100 x 1 = ￥100\n2. [NP-AA] Fixture\nunknown quantity\n小計：￥100")
    assert row["line_items"] == [] and row["hold_reason"] == "purchase_fields_missing"
