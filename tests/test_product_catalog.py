"""Sale identities use an independent, fixed compatibility table as the oracle."""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")
from services import product_catalog as catalog, stores_mail_sync as sync, pg_store
import routes


EXISTING = {
    "NP-ACG": "acg_bundle", "NP-WBA": "western_asteroids",
    "NP-WBT": "western_transit", "NP-WB": "western_basic",
    "NP-WF": "western_full", "NP-WA": "western_asteroids_addon",
    "NP-AA": "western_asteroids_addon", "NP-WT": "western_31days_transit_addon",
    "NP-TA": "western_31days_transit_addon", "NP-SF": "shichu_fortune_cycles_addon",
    "NP-SC": "shichu", "NP-TY": "transit_yaml",
}


@pytest.mark.parametrize("code,expected", EXISTING.items())
@pytest.mark.parametrize("channel", ["stores", "etsy", "payhip"])
def test_existing_codes_keep_identity_through_notification_parser(code, expected, channel):
    body = f"Product: [{code}]\nOrder ID: X1\n注文番号: 9123456789\nQuantity: 2"
    parser = getattr(sync, f"_parse_{channel}_mail")
    row = parser("Order details STORES", body, None, None, f"orders@{channel}.com")
    assert row["product_type"] == expected
    assert row["line_items"][0]["sku"] == code
    assert row["line_items"][0]["product_type"] == expected
    assert row["line_items"][0]["quantity"] == 2


@pytest.mark.parametrize("code", [
    "NP-SFULL", "NP-SB", "NP-SY10", "NP-SY20", "NP-NEW",
    "NP-SF2", "NP-WBA2", "NP-WF-BOGUS", "NP-WF-ES2", "NP-WF-ES-MORE",
    "NP-SF--ULL", "NP-WF__ES", "NP-SF-", "NP-SF_",
])
def test_unknown_code_is_not_reclassified_by_full_or_basic_words(code):
    for title in [f"[{code}] Full Basic", f"[{code}] 四柱推命 流年追加",
                  f"[{code}] [NP-WF] Full"]:
        assert sync._guess_product_type("", title) is None
        assert catalog.sku_from_text(title) is None
    assert sync._extract_line_items("", f"Product: [{code}] Full Basic") == []


@pytest.mark.parametrize("title", ["四柱推命 Full", "Basic", "FULL", "トランジット追加", "テスト"])
def test_unregistered_title_does_not_create_an_entitlement(title):
    assert sync._etsy_product_type("", f"Product: {title}") is None
    assert sync._extract_line_items("", f"Product: {title}") == []


def test_language_sku_and_spelling_normalization_are_compatible():
    for value in ["NP-WF-ES", "np_wf_es", "NP WF-ES", "NP WF ES"]:
        assert catalog.normalize_sku(value) == "NP-WF-ES"
        assert sync._guess_product_type("", f"[{value}]") == "western_full"
    assert catalog.normalize_sku("[NP-WF]") is None
    assert catalog.normalize_sku("NP-WF extra") is None
    assert catalog.verified_identity("western_full", "NP-WF-ES")
    assert not catalog.verified_identity("western_full", "NP-SFULL")
    assert not catalog.verified_identity("shichu_basic")


def test_multi_product_orders_do_not_choose_a_representative_product():
    body = "Product: [NP-WF-ES]\nQuantity: 2\nProduct: [NP-AA]\nQuantity: 1"
    assert sync._guess_product_type("", body) is None
    items = sync._extract_line_items("", body)
    assert [(item["sku"], item["product_type"], item["quantity"]) for item in items] == [
        ("NP-WF-ES", "western_full", 2), ("NP-AA", "western_asteroids_addon", 1),
    ]


def test_payhip_choices_and_labels_are_unchanged():
    assert list(routes.PAYHIP_PRODUCTS) == ["NP-WB", "NP-WF", "NP-AA", "NP-TA"]
    assert routes.PAYHIP_PRODUCTS["NP-AA"]["label"] == "NP-AA / AI-Readable Asteroid Data Add-on"
    assert routes.PAYHIP_PRODUCTS["NP-TA"]["product_type"] == "western_31days_transit_addon"
    assert catalog.RESERVED_CODES.isdisjoint(catalog.PRODUCTS)
    assert catalog.resolve_text("[NP-WL]") == "western_long_term_transits_addon"


def test_channel_ids_are_namespaced_and_cannot_enable_reserved_codes():
    bindings = (catalog.ChannelProductBinding("etsy", "123", "NP-WF"),
                catalog.ChannelProductBinding("stores", "123", "NP-SC"))
    assert catalog.resolve_channel_product_id("etsy", "123", bindings).code == "NP-WF"
    assert catalog.resolve_channel_product_id("stores", "123", bindings).code == "NP-SC"
    assert catalog.resolve_channel_product_id("payhip", "123", bindings) is None
    with pytest.raises(ValueError):
        catalog.resolve_channel_product_id("etsy", "123", (
            catalog.ChannelProductBinding("etsy", "123", "NP-SFULL"),))


@pytest.mark.parametrize("channel", ["stores", "etsy", "payhip"])
# shichu_full は四柱推命FULL版（NP-SCF）として登録済みのため、未登録の例には使わない。
@pytest.mark.parametrize("product_type", [None, "shichu_years_addon", "unknown"])
def test_unverified_orders_stop_before_calculation_and_consumption(channel, product_type):
    row = {"provider": channel, "product_type": product_type, "payment_status": "paid"}
    with patch.object(sync, "verify_order_entitlement", return_value=("ok", row)), \
         patch.object(routes, "_verify_strict_stores_order", return_value=("ok", row)):
        result = routes._check_order_for_redeem(
            order_id="9123456789", provider=channel, product_type="western_full")
    assert result[0] == "product_unverified"
    assert result[2] and result[3] == 409
    if channel == "payhip":
        assert routes._check_payhip_order_row_for_redeem(
            order_id="X1", order_row=row, product_type="western_full")[0] == "product_unverified"


@pytest.mark.parametrize("method", ["redeem_addon_order", "redeem_addon_order_and_save_chart",
                                    "redeem_addon_order_and_save_transit_link"])
def test_unknown_addon_is_rejected_before_any_mutating_sql(method):
    con = MagicMock()
    cursor = con.__enter__.return_value.cursor.return_value.__enter__.return_value
    kwargs = dict(order_code="9123456789", provider="stores", addon_type="western_asteroids_addon")
    if method != "redeem_addon_order":
        kwargs.update(token="local-token", expires_at=None, chart_payload={})
    if method.endswith("transit_link"):
        kwargs["yaml_text"] = "local"
    with patch.object(pg_store, "_conn", return_value=con), \
         patch.object(pg_store, "_select_marketplace_order_for_update",
                      return_value={"provider": "stores", "product_type": None, "payment_status": "paid"}), \
         patch.object(pg_store, "_claim_direct_addon_entitlement", return_value=(False, None)):
        result = getattr(pg_store, method)(**kwargs)
    assert result[0] == "product_unverified"
    cursor.execute.assert_not_called()


@pytest.mark.parametrize("sku", ["NP-SFULL", "NP-WF", "NP-AA-BOGUS"])
@pytest.mark.parametrize("claim_kind", ["addon", "chart"])
def test_invalid_saved_sku_cannot_consume_an_entitlement(sku, claim_kind):
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        {"table_name": "entitlements", "entitlement_table": "entitlements", "marketplace_table": None},
        {"id": 1, "provider": "stores", "product_type": "western_asteroids_addon", "sku": sku},
    ]
    if claim_kind == "addon":
        result = pg_store._claim_direct_addon_entitlement(
            cursor, order={"provider": "stores", "stores_order_no": "9123456789"},
            addon_type="western_asteroids_addon", chart_token="local-token")
    else:
        result = pg_store._claim_order_entitlement(
            cursor, order_code="9123456789", provider="stores",
            product_type="western_asteroids_addon", chart_token="local-token")
    assert result == (True, None)
    assert all(call.args[0].lstrip().startswith("SELECT") for call in cursor.execute.call_args_list)


def test_multi_product_transit_claim_returns_identity_without_chart_payload():
    con = MagicMock()
    entitlement = {"product_type": "western_31days_transit_addon", "sku": "NP-TA"}
    with patch.object(pg_store, "_conn", return_value=con), \
         patch.object(pg_store, "_select_marketplace_order_for_update", return_value={
             "provider": "payhip", "payment_status": "paid", "product_type": None}), \
         patch.object(pg_store, "_claim_direct_addon_entitlement", return_value=(True, entitlement)), \
         patch.object(pg_store, "_insert_transit_addon_result") as save:
        status, row = pg_store.redeem_addon_order_and_save_transit_link(
            order_code="X1", provider="payhip", addon_type="western_31days_transit_addon",
            token="local-token", yaml_text="local", expires_at=None)
    assert status == "ok" and row["product_type"] == "western_31days_transit_addon"
    assert row["sku"] == "NP-TA"
    save.assert_called_once()
