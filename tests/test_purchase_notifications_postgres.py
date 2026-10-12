"""Opt-in real PostgreSQL tests. Only an explicitly provided loopback DSN is allowed.

Run with TEST_ORDER_DATABASE_URL=postgresql://...@127.0.0.1:.../scratch.
Creates and drops its own random schema; never uses DATABASE_URL.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
import threading
from urllib.parse import urlparse
import uuid
from unittest.mock import patch

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services import pg_store, stores_mail_sync as sync, order_holds, order_review


@pytest.fixture
def database(monkeypatch):
    dsn = os.getenv("TEST_ORDER_DATABASE_URL", "")
    if not dsn:
        pytest.skip("未実施: TEST_ORDER_DATABASE_URL is not set; no real PostgreSQL available")
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Only an explicitly configured loopback test PostgreSQL is permitted")
    if parsed.query:
        pytest.fail("Test DSN query options are not allowed (host overrides etc.)")
    schema = "notification_test_" + uuid.uuid4().hex
    def connect():
        con = psycopg2.connect(dsn, cursor_factory=RealDictCursor, connect_timeout=3)
        with con.cursor() as cur:
            cur.execute("SET statement_timeout = '15s'")
        con.commit()
        return con
    @contextmanager
    def transaction(**kwargs):
        con = connect()
        try:
            with con:
                yield con
        finally:
            con.close()
    with transaction() as con:
        with con.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema}")
            for ddl in [sync.STORES_ORDERS_DDL, sync.MARKETPLACE_ORDERS_DDL, sync.ORDER_ENTITLEMENTS_DDL, order_holds.DDL]:
                cur.execute(ddl.replace("nanami_products", schema))
            cur.execute(f"""CREATE TABLE {schema}.redemptions (
                order_code TEXT PRIMARY KEY, email TEXT, buyer_name TEXT, token TEXT UNIQUE NOT NULL,
                used_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())""")
            cur.execute(f"""CREATE TABLE {schema}.charts (
                token TEXT PRIMARY KEY, order_code TEXT, buyer_name TEXT, birth_date TEXT NOT NULL,
                birth_time TEXT, birth_place TEXT, options JSONB, yaml_text TEXT NOT NULL,
                prompt_text TEXT NOT NULL, share_yaml_text TEXT, horoscope_svg TEXT,
                shichusuimei_svg TEXT, expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())""")
    for module in (sync, pg_store, order_holds):
        monkeypatch.setattr(module, "SCHEMA", schema)
    monkeypatch.setattr(pg_store, "_conn", transaction)
    try:
        yield transaction, schema
    finally:
        with transaction() as con:
            with con.cursor() as cur:
                cur.execute(f"DROP SCHEMA {schema} CASCADE")


def ingest(database, body):
    row = sync._parse_payhip_mail("You've Sold An Item!", body, None, None, "contact@payhip.com")
    with database[0]() as con:
        sync._upsert_order(con, row)
    return row


def issue(order, product, token=None):
    return pg_store.redeem_and_save(order_code=order, email=None, buyer_name=None,
        token=token or uuid.uuid4().hex, birth_date="2000-01-01", birth_time=None, birth_place=None,
        options={"order_provider": "payhip", "product_type": product}, yaml_text="fixture: true\n",
        prompt_text="Fixture prompt")


def scalar(database, query):
    with database[0]() as con:
        with con.cursor() as cur:
            cur.execute(query.format(schema=database[1]))
            return next(iter(cur.fetchone().values()))


def test_real_replay_cannot_increase_quantity_or_rewrite_issued_yaml(database):
    body = "Order ID: Replay\nProduct: [NP-WF]\nQuantity: 2"
    for _ in range(3):
        ingest(database, body)
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 2
    assert issue("Replay", "western_full", "First")
    ingest(database, body)
    assert issue("Replay", "western_full", "Second")
    assert not issue("Replay", "western_full", "Third")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 2
    assert scalar(database, "SELECT yaml_text FROM {schema}.charts WHERE token='First'") == "fixture: true\n"


def test_real_parallel_redemption_creates_only_one_chart(database):
    ingest(database, "Order ID: Race\nProduct: [NP-WF]\nQuantity: 1")
    barrier = threading.Barrier(6)
    def worker(_):
        barrier.wait(timeout=5)
        return issue("Race", "western_full")
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(worker, range(6)))
    assert sum(results) == 1
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 1


def test_real_multi_product_order_uses_only_each_purchased_unit(database):
    ingest(database, "Order ID: Multi\nProduct: [NP-WF]\nQuantity: 2\nProduct: [NP-WB]\nQuantity: 1")
    assert issue("Multi", "western_full") and issue("Multi", "western_basic")
    assert issue("Multi", "western_full")
    assert not issue("Multi", "western_basic") and not issue("Multi", "western_asteroids_addon")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 3


def test_real_unknown_order_is_held_and_cannot_use_legacy_first_redemption(database):
    ingest(database, "Order ID: Held\nProduct: [NP-SFULL]")
    assert not issue("Held", "western_full")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 0
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.marketplace_order_holds WHERE status='held'") == 1
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 0


def test_real_failed_chart_insert_rolls_back_consumed_right(database):
    ingest(database, "Order ID: Rollback\nProduct: [NP-WF]")
    with patch.object(pg_store, "_insert_chart", side_effect=ValueError("Fixture failure")):
        with pytest.raises(ValueError):
            issue("Rollback", "western_full")
    assert scalar(database, "SELECT status FROM {schema}.order_entitlements") == "available"
    assert issue("Rollback", "western_full")


def test_real_held_resync_preserves_prior_purchase_and_sent_notice(database):
    ingest(database, "Order ID: Prior\nProduct: [NP-WF]")
    assert issue("Prior", "western_full", "PriorChart")
    ingest(database, "Order ID: Prior\nProduct: [NP-SFULL]")
    ingest(database, "Order ID: Prior\nProduct: [NP-SFULL]")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.marketplace_order_holds") == 1
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 1
    assert scalar(database, "SELECT status FROM {schema}.order_entitlements") == "redeemed"
    assert scalar(database, "SELECT yaml_text FROM {schema}.charts WHERE token='PriorChart'") == "fixture: true\n"


def test_real_changed_replay_does_not_increase_rights(database):
    ingest(database, "Order ID: Changed\nProduct: [NP-WF]\nQuantity: 1")
    row = ingest(database, "Order ID: Changed\nProduct: [NP-WF]\nQuantity: 2")
    assert row["hold_reason"] == "purchase_details_conflict"
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 1


def approve(database, order, version):
    with database[0]() as con:
        return order_review.approve(con, provider="payhip", order_code=order, expected_version=version)


def review_version(database, order):
    with database[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"SELECT review_version FROM {database[1]}.marketplace_order_holds "
                        "WHERE provider = 'payhip' AND order_code = %s", (order,))
            return cur.fetchone()["review_version"]


def test_real_valid_resync_of_held_order_requires_manual_approval(database):
    ingest(database, "Order ID: Review\nProduct: [NP-SFULL]")
    ingest(database, "Order ID: Review\nProduct: [NP-WF]")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 0
    assert not issue("Review", "western_full")
    version = review_version(database, "Review")
    assert approve(database, "Review", version)["ok"]
    assert issue("Review", "western_full")
    assert not issue("Review", "western_full")


def test_real_parallel_approvals_create_only_confirmed_units(database):
    ingest(database, "Order ID: ReviewRace\nProduct: [NP-SFULL]")
    ingest(database, "Order ID: ReviewRace\nProduct: [NP-WF]\nQuantity: 2")
    version = review_version(database, "ReviewRace")
    barrier = threading.Barrier(6)
    def worker(_):
        barrier.wait(timeout=5)
        return approve(database, "ReviewRace", version)
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(worker, range(6)))
    assert sum(not r["already_approved"] for r in results) == 1
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 2


def test_real_new_notice_invalidates_previous_review(database):
    ingest(database, "Order ID: ReviewChanged\nProduct: [NP-SFULL]")
    ingest(database, "Order ID: ReviewChanged\nProduct: [NP-WF]")
    version = review_version(database, "ReviewChanged")
    ingest(database, "Order ID: ReviewChanged\nProduct: [NP-WF]\nQuantity: 2")
    with pytest.raises(order_review.ReviewError, match="REVIEW_CHANGED"):
        approve(database, "ReviewChanged", version)
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 0
    assert scalar(database, "SELECT jsonb_array_length(review_history) FROM {schema}.marketplace_order_holds") == 3


def test_real_approval_failure_rolls_back_granted_units(database):
    ingest(database, "Order ID: ReviewRollback\nProduct: [NP-SFULL]")
    ingest(database, "Order ID: ReviewRollback\nProduct: [NP-WF]")
    with patch.object(order_holds, "resolve_hold", side_effect=RuntimeError("Fixture")):
        with pytest.raises(RuntimeError):
            approve(database, "ReviewRollback", review_version(database, "ReviewRollback"))
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 0
    assert scalar(database, "SELECT status FROM {schema}.marketplace_order_holds") == "held"


def test_real_existing_chart_preserved_and_rights_frozen_until_approved(database):
    ingest(database, "Order ID: ReviewPrior\nProduct: [NP-WF]\nQuantity: 2")
    assert issue("ReviewPrior", "western_full", "ReviewPriorChart")
    ingest(database, "Order ID: ReviewPrior\nProduct: [NP-WF]\nQuantity: 3")
    assert not issue("ReviewPrior", "western_full")
    assert approve(database, "ReviewPrior", review_version(database, "ReviewPrior"))["ok"]
    assert issue("ReviewPrior", "western_full") and issue("ReviewPrior", "western_full")
    assert not issue("ReviewPrior", "western_full")
    assert scalar(database, "SELECT yaml_text FROM {schema}.charts WHERE token = 'ReviewPriorChart'") == "fixture: true\n"


def test_real_old_source_notifications_do_not_reopen_approved_order(database):
    notices = [sync._parse_payhip_mail("You've Sold An Item!", "Order ID: OldSource\nProduct: [NP-SFULL]",
                                      "fixture-unknown", None, "contact@payhip.com"),
               sync._parse_payhip_mail("You've Sold An Item!", "Order ID: OldSource\nProduct: [NP-WF]",
                                      "fixture-corrected", None, "contact@payhip.com")]
    for row in notices:
        with database[0]() as con:
            sync._upsert_order(con, dict(row))
    assert approve(database, "OldSource", review_version(database, "OldSource"))["ok"]
    for row in notices:
        with database[0]() as con:
            sync._upsert_order(con, dict(row))
    assert scalar(database, "SELECT status FROM {schema}.marketplace_order_holds") == "resolved"
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 1
    assert issue("OldSource", "western_full")
