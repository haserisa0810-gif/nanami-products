"""Opt-in real PostgreSQL regression: synthetic data, private UUID schemas only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
from unittest.mock import patch

import pytest
from services import pg_store, stores_mail_sync as sync, order_holds
from test_purchase_notifications_postgres import database, ingest, issue, scalar, approve, review_version


PRODUCTS = {
    "plain": ("shichu_fortune_cycles_addon", "NP-SF"),
    "chart": ("western_asteroids_addon", "NP-AA"),
    "transit": ("western_31days_transit_addon", "NP-TA"),
}


@pytest.fixture
def addon_database(database):
    with database[0]() as con:
        with con.cursor() as cur:
            pg_store._ensure_addon_redemptions_table(cur)
            pg_store._ensure_transit_addon_links_table(cur)
    return database


def add_purchase(database, order, kind, provider="payhip", quantity=1):
    product, sku = PRODUCTS[kind]
    row = sync._parse_payhip_mail("You've Sold An Item!",
        f"Order ID: {order}\nProduct: [{sku}]\nQuantity: {quantity}", None, None, "contact@payhip.com")
    row["provider"] = provider
    with database[0]() as con:
        sync._upsert_order(con, row)
    return product


def addon(order, kind, token="AddonResult", provider="payhip"):
    product, _ = PRODUCTS[kind]
    args = dict(order_code=order, addon_type=product, provider=provider)
    if kind == "plain":
        return pg_store.redeem_addon_order(**args)[0]
    args.update(token=token, expires_at=datetime.now(timezone.utc) + timedelta(days=365))
    if kind == "transit":
        return pg_store.redeem_addon_order_and_save_transit_link(**args, yaml_text="original: addon\n")[0]
    return pg_store.redeem_addon_order_and_save_chart(**args, chart_payload={
        "birth_date": "2000-01-01", "options": {"product_type": product, "order_provider": provider},
        "yaml_text": "original: addon\n", "prompt_text": "Original prompt"})[0]


def snapshot(database):
    with database[0]() as con:
        with con.cursor() as cur:
            result = {}
            for table in ["marketplace_orders", "stores_orders", "order_entitlements",
                          "marketplace_order_holds", "marketplace_processed_notices", "charts", "redemptions"]:
                cur.execute(f"SELECT * FROM {database[1]}.{table} ORDER BY 1, 2")
                result[table] = cur.fetchall()
            return result


def download_notice(database, order):
    row = sync._parse_payhip_mail("Someone Requested a Download!",
        f"Order ID: {order}\nProduct: [NP-WF]\nProduct: [NP-AA]", "same-message", None, "contact@payhip.com")
    with database[0]() as con:
        assert sync._upsert_order(con, row) is False
    assert row["_ignored_notice"]


@pytest.mark.parametrize("kind", PRODUCTS)
@pytest.mark.parametrize("provider", ["stores", "payhip", "etsy"])
@pytest.mark.parametrize("legacy", [False, True])
def test_held_addon_cannot_consume_new_or_legacy_rights(addon_database, kind, provider, legacy):
    db = addon_database
    add_purchase(db, "HeldAddon", kind, provider)
    with db[0]() as con:
        if legacy:
            with con.cursor() as cur:
                cur.execute(f"DELETE FROM {db[1]}.order_entitlements")
        order_holds.record_hold(con, provider=provider, order_code="HeldAddon", reason="unknown_product_code")
    before = snapshot(db)
    assert addon("HeldAddon", kind, provider=provider) == "held"
    assert snapshot(db) == before
    assert scalar(db, "SELECT COUNT(*) FROM {schema}.addon_redemptions") == 0
    assert scalar(db, "SELECT COUNT(*) FROM {schema}.transit_addon_links") == 0


@pytest.mark.parametrize("kind", PRODUCTS)
def test_normal_and_addon_compete_for_same_unit_only_one_wins(addon_database, kind):
    db = addon_database
    product = add_purchase(db, "CrossRace", kind)
    barrier = threading.Barrier(2)
    def worker(normal):
        barrier.wait(timeout=5)
        return issue("CrossRace", product, "NormalResult") if normal else addon("CrossRace", kind) == "ok"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, [True, False]))
    assert sum(results) == 1
    assert scalar(db, "SELECT COUNT(*) FROM {schema}.order_entitlements WHERE status='redeemed'") == 1
    assert scalar(db, "SELECT COUNT(*) FROM {schema}.charts") <= 1


@pytest.mark.parametrize("kind", PRODUCTS)
def test_addon_parallel_consumption_and_repeat_cannot_duplicate(addon_database, kind):
    db = addon_database
    add_purchase(db, "AddonRace", kind, quantity=2)
    barrier = threading.Barrier(4)
    def worker(index):
        barrier.wait(timeout=5)
        return addon("AddonRace", kind, token=f"Addon{index}")
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, range(4)))
    assert results.count("ok") == 2
    assert results.count("already_used") == 2
    assert addon("AddonRace", kind) == "already_used"
    assert scalar(db, "SELECT COUNT(*) FROM {schema}.order_entitlements WHERE status='redeemed'") == 2


@pytest.mark.parametrize("kind", ["chart", "transit"])
def test_addon_save_failure_rolls_back_consumption(addon_database, kind):
    db = addon_database
    add_purchase(db, "AddonRollback", kind)
    target = "_insert_chart" if kind == "chart" else "_insert_transit_addon_result"
    with patch.object(pg_store, target, side_effect=ValueError("Synthetic insert failure")):
        with pytest.raises(ValueError):
            addon("AddonRollback", kind)
    assert scalar(db, "SELECT status FROM {schema}.order_entitlements") == "available"
    assert addon("AddonRollback", kind) == "ok"


@pytest.mark.parametrize("kind", PRODUCTS)
def test_reset_once_does_not_grant_addon_extra_use(addon_database, kind):
    db = addon_database
    add_purchase(db, "ResetAddon", kind)
    assert addon("ResetAddon", kind) == "ok"
    with db[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {db[1]}.marketplace_orders SET payment_status='reset_once'")
    assert addon("ResetAddon", kind) == "already_used"


@pytest.mark.parametrize("kind", PRODUCTS)
@pytest.mark.parametrize("legacy", [False, True])
def test_unpaid_addon_never_consumes_rights(addon_database, kind, legacy):
    db = addon_database
    add_purchase(db, "Unpaid", kind)
    with db[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {db[1]}.marketplace_orders SET payment_status='ordered'")
            if legacy:
                cur.execute(f"DELETE FROM {db[1]}.order_entitlements")
    before = snapshot(db)
    assert addon("Unpaid", kind) == "unpaid"
    assert snapshot(db) == before


def test_invalid_entitlement_identity_cannot_use_legacy_fallback(addon_database):
    db = addon_database
    add_purchase(db, "WrongSku", "chart")
    with db[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {db[1]}.order_entitlements SET sku='NP-WF'")
    before = snapshot(db)
    assert addon("WrongSku", "chart") == "already_used"
    assert snapshot(db) == before


@pytest.mark.parametrize("kind", PRODUCTS)
def test_approval_and_addon_consumption_share_lock_without_deadlock(addon_database, kind):
    db = addon_database
    product, sku = PRODUCTS[kind]
    ingest(db, "Order ID: ApproveAddon\nProduct: [NP-SFULL]")
    ingest(db, f"Order ID: ApproveAddon\nProduct: [{sku}]")
    version = review_version(db, "ApproveAddon")
    barrier = threading.Barrier(2)
    def worker(approval):
        barrier.wait(timeout=5)
        return approve(db, "ApproveAddon", version) if approval else addon("ApproveAddon", kind)
    with ThreadPoolExecutor(max_workers=2) as executor:
        approved, result = list(executor.map(worker, [True, False]))
    assert approved["ok"] and result in {"held", "ok"}
    assert addon("ApproveAddon", kind, token="AfterApproval") == ("ok" if result == "held" else "already_used")
    assert scalar(db, "SELECT COUNT(*) FROM {schema}.order_entitlements WHERE status='redeemed'") == 1


def test_normal_reset_once_remains_one_reissue(database):
    db = database
    ingest(db, "Order ID: ResetNormal\nProduct: [NP-WF]")
    assert issue("ResetNormal", "western_full", "BeforeReset")
    with db[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {db[1]}.marketplace_orders SET payment_status='reset_once'")
    assert issue("ResetNormal", "western_full", "AfterReset")
    assert not issue("ResetNormal", "western_full", "ExtraReset")


@pytest.mark.parametrize("state", ["absent", "paid", "issued", "held", "approved"])
def test_download_never_changes_order_rights_review_or_original(database, state):
    db = database
    if state != "absent":
        ingest(db, "Order ID: Download\nProduct: [NP-WF]\nQuantity: 2")
    if state == "issued":
        assert issue("Download", "western_full", "StoredOriginal")
    if state in {"held", "approved"}:
        ingest(db, "Order ID: Download\nProduct: [NP-SFULL]")
    if state == "approved":
        ingest(db, "Order ID: Download\nProduct: [NP-WF]\nQuantity: 2")
        assert approve(db, "Download", review_version(db, "Download"))["ok"]
    before = snapshot(db)
    for _ in range(3):
        download_notice(db, "Download")
    assert snapshot(db) == before
    if state == "issued":
        assert pg_store.get_chart("StoredOriginal")["yaml_text"] == "fixture: true\n"
        assert issue("Download", "western_full", "Remaining")


def test_download_and_purchase_same_source_id_still_grants_valid_purchase(database):
    download_notice(database, "SameSource")
    row = sync._parse_payhip_mail("You've Sold An Item!", "Order ID: SameSource\nProduct: [NP-WF]",
                                 "same-message", None, "contact@payhip.com")
    with database[0]() as con:
        assert sync._upsert_order(con, row)
    assert issue("SameSource", "western_full")
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.marketplace_order_holds") == 0


def test_parallel_download_purchase_does_not_hold_or_expand_order(database):
    barrier = threading.Barrier(4)
    def worker(index):
        barrier.wait(timeout=5)
        if index % 2:
            download_notice(database, "DownloadRace")
        else:
            ingest(database, "Order ID: DownloadRace\nProduct: [NP-WF]")
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(worker, range(4)))
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.marketplace_order_holds") == 0
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 1
    assert issue("DownloadRace", "western_full")
