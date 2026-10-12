"""FULL uses the shared purchase gate; real DB cases remain explicitly opt-in."""
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import MagicMock, patch

import pytest

from services import order_holds, order_review, pg_store, product_catalog
from services import stores_mail_sync as sync
from services.purchase_mail_items import analyze_purchase_items
from test_purchase_notifications_postgres import database, scalar


def test_full_stores_purchase_is_a_registered_review_candidate():
    parsed = analyze_purchase_items("stores", "Order details", "Product: [NP-SCF]\nQuantity: 1")
    assert parsed["product_type"] == "shichu_full"
    assert product_catalog.verified_identity("shichu_full", parsed["line_items"][0]["sku"])
    candidate = {"purchase_evidence": True, "payment_status": "paid", "hold_reason": None,
                 "items": parsed["line_items"]}
    assert order_review.validate_candidate(candidate)[0]["product_type"] == "shichu_full"


def test_full_purchase_cannot_be_approved_as_another_product():
    candidate = {"purchase_evidence": True, "payment_status": "paid", "hold_reason": None,
                 "items": [{"line_item_key": "NP-SCF:1", "sku": "NP-SCF",
                            "product_type": "western_full", "quantity": 1}]}
    with pytest.raises(order_review.ReviewError):
        order_review.validate_candidate(candidate)


def test_held_full_purchase_stops_before_entitlement_or_chart_mutation():
    con = MagicMock()
    cur = con.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [
        {"hold_table": "holds", "entitlement_table": "entitlements", "marketplace_table": "orders"},
        {"present": 1},
    ]
    with patch.object(pg_store, "_conn", return_value=con), \
         patch.object(pg_store, "_insert_chart") as insert:
        assert not pg_store.redeem_and_save(
            order_code="FullFixture", email=None, buyer_name=None, token="FullResult",
            birth_date="2000-01-01", birth_time=None, birth_place=None,
            options={"product_type": "shichu_full", "order_provider": "stores"},
            yaml_text="fictional: full\n", prompt_text="Fixture",
        )
    insert.assert_not_called()
    assert all(call.args[0].lstrip().startswith("SELECT") for call in cur.execute.call_args_list)


def ingest_full_fixture(db, code, sku):
    # The common line-item shape is deliberately reused; no customer mail.
    parsed = sync._parse_payhip_mail("You've Sold An Item!",
        f"Order ID: {code}\nProduct: [{sku}]\nQuantity: 1", None, None, "contact@payhip.com")
    parsed["provider"] = "stores"
    with db[0]() as con:
        sync._upsert_order(con, parsed)


def issue_full_fixture(code, token):
    return pg_store.redeem_and_save(
        order_code=code, email=None, buyer_name=None, token=token,
        birth_date="2000-01-01", birth_time=None, birth_place=None,
        options={"product_type": "shichu_full", "order_provider": "stores"},
        yaml_text="fictional: full\n", prompt_text="Fixture",
    )


def test_full_real_database_requires_approval_before_consumption(database):
    ingest_full_fixture(database, "FullFixture", "NP-SFULL")
    ingest_full_fixture(database, "FullFixture", "NP-SCF")
    assert not issue_full_fixture("FullFixture", "UnapprovedFull")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 0
    with database[0]() as con:
        review = order_holds.get_review(con, provider="stores", order_code="FullFixture")
        assert review["status"] == "held"
        order_review.approve(con, provider="stores", order_code="FullFixture",
                             expected_version=review["review_version"])
    assert issue_full_fixture("FullFixture", "ApprovedFull")
    assert not issue_full_fixture("FullFixture", "RepeatedFull")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 1


def test_full_real_database_parallel_consumption_is_single_use(database):
    ingest_full_fixture(database, "FullRace", "NP-SCF")
    barrier = threading.Barrier(2)

    def consume(index):
        barrier.wait(timeout=5)
        return issue_full_fixture("FullRace", f"FullRace{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2)))
    assert sum(results) == 1
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 1
