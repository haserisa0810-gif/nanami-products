"""NP-SY05 uses the shared approval and consumption gate; no real DB here."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services import order_holds, order_review, pg_store, product_catalog
from services import stores_mail_sync as sync
from services.purchase_mail_items import analyze_purchase_items


PRODUCT = "shichu_annual_5y_addon"
ITEM = {"line_item_key": "NP-SY05:1", "sku": "NP-SY05",
        "product_type": PRODUCT, "quantity": 1}


def test_annual_purchase_evidence_survives_review_storage():
    parsed = analyze_purchase_items("stores", "Order details", "Product: [NP-SY05]\nQuantity: 1")
    assert product_catalog.verified_identity(PRODUCT, parsed["line_items"][0]["sku"])
    con = MagicMock()
    order_holds.save_candidate(con, {**parsed, "provider": "stores",
        "stores_order_no": "AnnualFixture", "payment_status": "paid"})
    candidate = con.cursor.return_value.__enter__.return_value.execute.call_args.args[1][0].adapted
    assert order_review.validate_candidate(candidate) == [ITEM]


@pytest.mark.parametrize("version", [3, 4])
def test_annual_admin_approval_requires_current_review_version(version):
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = []
    cur.fetchone.return_value = {"order_code": "AnnualFixture"}
    review = {"status": "held", "review_version": version,
        "candidate": {"purchase_evidence": True, "payment_status": "paid",
                      "hold_reason": None, "items": [ITEM]}}
    with patch.object(order_review, "load_locked_review", return_value=(review, [])), \
         patch.object(sync, "_upsert_order_entitlements") as grant, \
         patch.object(order_holds, "resolve_hold") as resolve:
        if version == 4:
            with pytest.raises(order_review.ReviewError, match="REVIEW_CHANGED"):
                order_review.approve(con, provider="stores", order_code="AnnualFixture", expected_version=3)
            grant.assert_not_called()
            resolve.assert_not_called()
            con.commit.assert_not_called()
            con.rollback.assert_called_once()
        else:
            assert order_review.approve(con, provider="stores", order_code="AnnualFixture",
                                        expected_version=3)["ok"]
            assert grant.call_args.args[1]["line_items"] == [ITEM]
            resolve.assert_called_once_with(con, provider="stores", order_code="AnnualFixture", approved_version=3)
            con.commit.assert_called_once()


def test_annual_sku_cannot_approve_a_full_product():
    candidate = {"purchase_evidence": True, "payment_status": "paid", "hold_reason": None,
                 "items": [{**ITEM, "product_type": "shichu_full"}]}
    with pytest.raises(order_review.ReviewError, match="INVALID_REVIEW_ITEMS"):
        order_review.validate_candidate(candidate)


@pytest.mark.parametrize("payment_status", ["paid", "reusable"])
def test_held_annual_addon_cannot_save_or_consume_even_a_reusable_order(payment_status):
    con = MagicMock()
    cur = con.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [
        {"entitlement_table": "entitlements", "marketplace_table": "orders", "hold_table": "holds"},
        {"held": 1}, {"table_name": "orders"},
        {"provider": "stores", "stores_order_no": "AnnualFixture",
         "payment_status": payment_status, "product_type": PRODUCT},
    ]
    with patch.object(pg_store, "_conn") as connect, patch.object(pg_store, "_insert_chart") as insert:
        connect.return_value.__enter__.return_value = con
        status, _ = pg_store.redeem_addon_order_and_save_chart(
            order_code="AnnualFixture", provider="stores", addon_type=PRODUCT,
            token="MustNotExist", expires_at=datetime.now(timezone.utc), chart_payload={})
    assert status == "held"
    insert.assert_not_called()
    statements = [call.args[0] for call in cur.execute.call_args_list]
    assert "pg_advisory_xact_lock" in statements[0]
    assert all(sql.lstrip().startswith("SELECT") for sql in statements)


@pytest.mark.parametrize("entitlement", [None, {"product_type": PRODUCT, "sku": "NP-SY05"}])
def test_annual_issue_requires_an_available_matching_unit(entitlement):
    con = MagicMock()
    con.cursor.return_value.__enter__.return_value.fetchone.return_value = {}
    order = {"provider": "stores", "stores_order_no": "AnnualFixture",
             "payment_status": "paid", "product_type": PRODUCT}
    payload = {"birth_date": "2000-01-01", "options": {"product_type": PRODUCT},
               "yaml_text": "fictional: true\n", "prompt_text": "Fixture"}
    with patch.object(pg_store, "_conn") as connect, \
         patch.object(pg_store, "_select_marketplace_order_for_update", return_value=order), \
         patch.object(pg_store, "_claim_direct_addon_entitlement", return_value=(True, entitlement)), \
         patch.object(pg_store, "_insert_chart") as insert:
        connect.return_value.__enter__.return_value = con
        status, _ = pg_store.redeem_addon_order_and_save_chart(
            order_code="AnnualFixture", provider="stores", addon_type=PRODUCT,
            token="AnnualResult", expires_at=datetime.now(timezone.utc), chart_payload=payload)
    assert status == ("ok" if entitlement else "already_used")
    assert insert.call_count == int(entitlement is not None)
