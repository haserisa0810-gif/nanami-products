from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import routes
import services.pg_store as pg_store
import services.stores_mail_sync as sync


def test_etsy_extracts_each_sku_and_expands_quantity() -> None:
    parsed = sync._parse_etsy_mail(
        "Etsy order details",
        """Order details
Order number: 4125350780
Product: [NP-WF-ES] FULL
Quantity: 2
Transaction: 1001
Product: [NP-WF-DE] FULL
Quantity: 1
Transaction: 1002
""",
        "<etsy-multi>",
        None,
        "Etsy <transaction@etsy.com>",
    )

    assert parsed is not None
    assert parsed["line_items"] == [
        {
            "sku": "NP-WF-ES",
            "product_type": "western_full",
            "quantity": 2,
            "line_item_key": "NP-WF-ES:1",
        },
        {
            "sku": "NP-WF-DE",
            "product_type": "western_full",
            "quantity": 1,
            "line_item_key": "NP-WF-DE:1",
        },
    ]


def test_stores_and_payhip_extract_quantity() -> None:
    stores = sync._parse_stores_mail(
        "【STORES】アイテムが購入されました（オーダー番号：9824333454）",
        "商品: [NP-WF] FULL\n数量: 3\n合計（税込）: ¥3,000",
        None,
        None,
        "STORES <hello@stores.jp>",
    )
    payhip = sync._parse_payhip_mail(
        "You've Sold An Item!",
        "Order ID: Multi123\nProduct: [NP-WF] FULL\nQuantity: 2\nTotal: $38.00",
        None,
        None,
        "Payhip <contact@payhip.com>",
    )

    assert stores is not None and stores["line_items"][0]["quantity"] == 3
    assert payhip is not None and payhip["line_items"][0]["quantity"] == 2


def test_entitlement_verification_reports_partial_and_does_not_enforce_sku_locale() -> None:
    order_row = {
        "stores_order_no": "4125350780",
        "provider": "etsy",
        "product_type": "western_full",
        "payment_status": "paid",
    }
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"table_name": "nanami_products.order_entitlements"}
    cursor.fetchall.return_value = [
        {"provider": "etsy", "product_type": "western_full", "status": "redeemed", "unit_count": 1},
        {"provider": "etsy", "product_type": "western_full", "status": "available", "unit_count": 2},
    ]

    with patch.object(sync, "verify_order_no", return_value=("already_used", order_row)), patch.object(
        sync, "_get_conn", return_value=connection
    ):
        status, resolved = sync.verify_order_entitlement(
            "4125350780", provider="etsy", product_type="western_full"
        )

    assert status == "partial"
    assert resolved is not None
    assert resolved["_available_entitlements"] == 2
    assert resolved["_redeemed_entitlements"] == 1
    group_sql, group_params = cursor.execute.call_args_list[-1].args
    assert "WHERE order_code = %s AND provider = %s" in " ".join(group_sql.split())
    assert group_params == ("4125350780", "etsy")


def test_order_verification_uses_provider_scoped_order_and_chart() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        {"table_name": "nanami_products.marketplace_orders"},
        {
            "stores_order_no": "SAME-ORDER",
            "provider": "etsy",
            "product_type": "western_full",
            "payment_status": "paid",
        },
        None,
    ]

    with patch.object(sync, "_get_conn", return_value=connection):
        status, order = sync.verify_order_no("SAME-ORDER", provider="etsy")

    assert status == "ok"
    assert order is not None and order["provider"] == "etsy"
    calls = cursor.execute.call_args_list
    order_sql, order_params = calls[1].args
    used_sql, used_params = calls[2].args
    assert "provider = %s AND order_code = %s" in " ".join(order_sql.split())
    assert order_params == ("etsy", "SAME-ORDER")
    assert "options->>'order_provider' = %s" in " ".join(used_sql.split())
    assert used_params == ("SAME-ORDER", "etsy", "etsy")


class _Cursor:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.executed: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((re.sub(r"\s+", " ", str(sql)).strip(), params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return []


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self.value = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.value


def test_redeem_claims_one_unit_atomically_and_allows_second_chart_for_same_order() -> None:
    cursor = _Cursor(
        [
            {
                "entitlement_table": "nanami_products.order_entitlements",
                "marketplace_table": "nanami_products.marketplace_orders",
            },
            {
                "id": 22,
                "provider": "etsy",
                "order_code": "4125350780",
                "line_item_key": "NP-WF-ES:1",
                "sku": "NP-WF-ES",
                "product_type": "western_full",
                "unit_index": 2,
            },
            {"id": 22},
            None,  # redemptions already contains the order; entitlement still authorizes this chart
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)), patch.object(
        pg_store, "_insert_chart"
    ) as insert_chart:
        ok = pg_store.redeem_and_save(
            order_code="4125350780",
            email=None,
            buyer_name="Second buyer",
            token="second-token",
            birth_date="2001-02-03",
            birth_time="04:05",
            birth_place="Madrid",
            options={"order_provider": "etsy", "product_type": "western_full"},
            yaml_text="yaml",
            prompt_text="prompt",
        )

    assert ok is True
    assert any("FOR UPDATE SKIP LOCKED" in sql for sql, _ in cursor.executed)
    assert not any("payment_status = 'paid'" in sql for sql, _ in cursor.executed)
    saved_options = insert_chart.call_args.kwargs["options"]
    assert saved_options["order_entitlement"]["id"] == 22
    assert saved_options["order_entitlement"]["sku"] == "NP-WF-ES"


def test_redeem_rejects_when_all_units_are_consumed() -> None:
    cursor = _Cursor(
        [
            {
                "entitlement_table": "nanami_products.order_entitlements",
                "marketplace_table": "nanami_products.marketplace_orders",
            },
            None,  # no available matching unit
            {"id": 22},  # this is an entitlement-backed order, so do not use legacy fallback
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)), patch.object(
        pg_store, "_insert_chart"
    ) as insert_chart:
        ok = pg_store.redeem_and_save(
            order_code="4125350780",
            email=None,
            buyer_name=None,
            token="third-token",
            birth_date="2001-02-03",
            birth_time=None,
            birth_place=None,
            options={"order_provider": "etsy", "product_type": "western_full"},
            yaml_text="yaml",
            prompt_text="prompt",
        )

    assert ok is False
    insert_chart.assert_not_called()


def test_quantity_is_expanded_idempotently_by_unit_index() -> None:
    cursor = _Cursor([])
    sync._upsert_order_entitlements(
        _Connection(cursor),
        {
            "provider": "stores",
            "stores_order_no": "9824333454",
            "line_items": [
                {
                    "line_item_key": "NP-WF:1",
                    "sku": "NP-WF",
                    "product_type": "western_full",
                    "quantity": 2,
                },
                {
                    "line_item_key": "NP-WBT:1",
                    "sku": "NP-WBT",
                    "product_type": "western_transit",
                    "quantity": 1,
                },
            ],
        },
    )

    inserts = [params for sql, params in cursor.executed if "INSERT INTO" in sql]
    assert [params[-1] for params in inserts] == [1, 2, 1]
    assert all("ON CONFLICT (provider, order_code, line_item_key, unit_index)" in sql for sql, _ in cursor.executed if "INSERT INTO" in sql)


def test_reset_once_can_reissue_a_redeemed_entitlement() -> None:
    cursor = _Cursor(
        [
            {
                "entitlement_table": "nanami_products.order_entitlements",
                "marketplace_table": "nanami_products.marketplace_orders",
            },
            {
                "id": 22,
                "provider": "etsy",
                "order_code": "4125350780",
                "line_item_key": "NP-WF-ES:1",
                "sku": "NP-WF-ES",
                "product_type": "western_full",
                "unit_index": 1,
                "payment_status": "reset_once",
            },
            {"id": 22},
            None,
            {"table_name": "nanami_products.marketplace_orders"},
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)), patch.object(
        pg_store, "_insert_chart"
    ):
        ok = pg_store.redeem_and_save(
            order_code="4125350780",
            email=None,
            buyer_name="Reissued",
            token="reissued-token",
            birth_date="2001-02-03",
            birth_time=None,
            birth_place=None,
            options={"order_provider": "etsy", "product_type": "western_full"},
            yaml_text="yaml",
            prompt_text="prompt",
        )

    assert ok is True
    assert any("payment_status = 'paid'" in sql for sql, _ in cursor.executed)
    assert any(".redemptions" in sql and sql.startswith("UPDATE") for sql, _ in cursor.executed)


def test_direct_addon_quantity_uses_entitlement_instead_of_order_level_lock() -> None:
    cursor = _Cursor(
        [
            {"table_name": "nanami_products.marketplace_orders"},
            {
                "stores_order_no": "PayhipAddon2",
                "provider": "payhip",
                "payment_status": "paid",
                "product_type": "western_asteroids_addon",
            },
            {"table_name": "nanami_products.order_entitlements"},
            {
                "id": 31,
                "provider": "payhip",
                "order_code": "PayhipAddon2",
                "line_item_key": "NP-AA:1",
                "sku": "NP-AA",
                "product_type": "western_asteroids_addon",
                "unit_index": 2,
            },
            {"id": 31},
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)), patch.object(
        pg_store, "_insert_chart"
    ) as insert_chart:
            status, _order = pg_store.redeem_addon_order_and_save_chart(
                order_code="PayhipAddon2",
                provider="payhip",
            addon_type="western_asteroids_addon",
            token="addon-token-2",
            expires_at=None,
            chart_payload={
                "buyer_name": "Addon buyer",
                "birth_date": "2001-02-03",
                "birth_time": None,
                "birth_place": None,
                "options": {"product_type": "western_asteroids_addon"},
                "yaml_text": "yaml",
                "prompt_text": "prompt",
            },
        )

    assert status == "ok"
    assert not any("INSERT INTO nanami_products.addon_redemptions" in sql for sql, _ in cursor.executed)
    assert insert_chart.call_args.kwargs["options"]["order_entitlement"]["unit_index"] == 2


def test_full_entitlement_does_not_authorize_a_separately_sold_addon() -> None:
    cursor = _Cursor(
        [
            {"table_name": "nanami_products.marketplace_orders"},
            {
                "stores_order_no": "ETSY-FULL-ONLY",
                "provider": "etsy",
                "payment_status": "paid",
                "product_type": "western_full",
            },
            {"table_name": "nanami_products.order_entitlements"},
            None,  # no entitlement for the selected addon
            None,  # no historical entitlement for the selected addon
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)):
        status, _order = pg_store.redeem_addon_order(
            order_code="ETSY-FULL-ONLY",
            provider="etsy",
            addon_type="western_31days_transit_addon",
        )

    assert status == "product_mismatch"
    assert not any(
        "INSERT INTO nanami_products.addon_redemptions" in sql
        for sql, _params in cursor.executed
    )


def test_provider_scoped_chart_lookup_does_not_mix_same_order_number() -> None:
    cursor = _Cursor([])
    connection = _Connection(cursor)
    with patch.object(pg_store, "_conn", return_value=connection):
        pg_store.list_charts_by_order_code(
            "SAME-ORDER", provider="etsy", product_type="western_full"
        )

    sql, params = cursor.executed[0]
    assert "options->>'order_provider' = %s" in sql
    assert "options->>'product_type' = %s" in sql
    assert params == ("SAME-ORDER", "etsy", "etsy", "western_full")


def test_provider_scoped_reset_only_updates_the_selected_marketplace() -> None:
    cursor = _Cursor(
        [
            {"table_name": "nanami_products.marketplace_orders"},
            {
                "order_code": "SAME-ORDER",
                "provider": "etsy",
                "payment_status": "reset_once",
            },
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)):
        result = pg_store.reset_redemption_by_order_code(
            "SAME-ORDER",
            provider="etsy",
        )

    assert result["reset"] is True
    marketplace_updates = [
        (sql, params)
        for sql, params in cursor.executed
        if sql.startswith("UPDATE nanami_products.marketplace_orders")
    ]
    assert len(marketplace_updates) == 1
    assert "WHERE provider = %s AND order_code = %s" in marketplace_updates[0][0]
    assert marketplace_updates[0][1] == ("etsy", "SAME-ORDER")
    legacy_updates = [
        (sql, params)
        for sql, params in cursor.executed
        if sql.startswith("UPDATE nanami_products.stores_orders")
    ]
    assert len(legacy_updates) == 1
    assert "LOWER(provider) = %s" in legacy_updates[0][0]
    assert legacy_updates[0][1] == ("SAME-ORDER", "etsy", "etsy")


def test_reset_override_lookup_uses_provider_and_order_code() -> None:
    cursor = _Cursor(
        [
            {"table_name": "nanami_products.marketplace_orders"},
            {
                "order_code": "SAME-ORDER",
                "provider": "payhip",
                "payment_status": "reset_once",
            },
        ]
    )
    with patch.object(pg_store, "_conn", return_value=_Connection(cursor)):
        row = pg_store.get_redemption_reset_by_order_code(
            "SAME-ORDER",
            provider="payhip",
        )

    assert row is not None and row["provider"] == "payhip"
    sql, params = cursor.executed[1]
    assert "WHERE provider = %s AND order_code = %s" in sql
    assert params == ("payhip", "SAME-ORDER")


def test_entitlement_existence_check_is_scoped_to_provider() -> None:
    cursor = _Cursor(
        [
            {
                "entitlement_table": "nanami_products.order_entitlements",
                "marketplace_table": "nanami_products.marketplace_orders",
            },
            None,
            {"id": 44},
        ]
    )
    entitlement_mode, entitlement = pg_store._claim_order_entitlement(
        cursor,
        order_code="SAME-ORDER",
        provider="etsy",
        product_type="western_full",
        chart_token="token",
    )

    assert entitlement_mode is True
    assert entitlement is None
    sql, params = cursor.executed[-1]
    assert "provider = %s AND order_code = %s" in sql
    assert params == ("etsy", "SAME-ORDER")


def test_issue_next_link_is_carried_into_the_redeem_form() -> None:
    response = TestClient(routes.app).get(
        "/redeem/western-full?lang=es&provider=etsy&order=4125350780&new=1"
    )
    assert response.status_code == 200
    assert '<input type="hidden" name="issue_next" value="1">' in response.text


def test_existing_chart_backfill_is_scoped_to_the_selected_provider() -> None:
    cursor = _Cursor([])
    sync._upsert_order_entitlements(
        _Connection(cursor),
        {
            "provider": "etsy",
            "stores_order_no": "SAME-ORDER",
            "product_type": "western_full",
            "line_items": [
                {
                    "line_item_key": "NP-WF-EN:1",
                    "sku": "NP-WF-EN",
                    "product_type": "western_full",
                    "quantity": 1,
                }
            ],
        },
    )

    chart_queries = [
        (sql, params)
        for sql, params in cursor.executed
        if "FROM nanami_products.charts c" in sql
    ]
    assert len(chart_queries) == 1
    sql, params = chart_queries[0]
    assert "c.options->>'order_provider' = %s" in sql
    assert "COALESCE(c.options->>'order_provider', '') = ''" in sql
    assert params == ("SAME-ORDER", "etsy", "etsy")


def test_addon_form_keeps_language_and_hides_purchase_provider_dropdown() -> None:
    expected_labels = {
        "ja": "オーダー番号",
        "en": "Order number or purchase ID",
        "es": "Número de pedido o ID de compra",
        "de": "Bestellnummer oder Kauf-ID",
    }
    for lang, expected_label in expected_labels.items():
        response = TestClient(routes.app).get(
            f"/addon/new?lang={lang}&addon_type=western_31days_transit_addon"
        )

        assert response.status_code == 200
        assert f'action="/addon/generate?lang={lang}"' in response.text
        assert 'select name="order_provider" id="order-provider"' not in response.text
        assert '<input type="hidden" name="order_provider" value="">' in response.text
        assert 'name="order_code" required' in response.text
        assert expected_label in response.text


def test_addon_auto_resolution_returns_one_provider_without_consuming() -> None:
    def entitlement_lookup(reference: str, *, provider: str, product_type: str):
        assert reference == "SAME-REF"
        assert product_type == "western_asteroids_addon"
        if provider == "etsy":
            return "ok", {
                "stores_order_no": reference,
                "provider": provider,
                "product_type": product_type,
            }
        return "not_found", None

    with patch.object(sync, "verify_order_entitlement", side_effect=entitlement_lookup), patch.object(
        sync, "verify_coconala_buyer", return_value=("not_found", None)
    ), patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}, clear=False):
        result = routes._auto_resolve_addon_purchase(
            "SAME-REF", "western_asteroids_addon", lang="en"
        )

    assert result == ("etsy", "SAME-REF", None, 200, [])


def test_addon_auto_resolution_syncs_once_after_a_complete_miss() -> None:
    lookup_results = [([], []), ([{"provider": "payhip", "order_code": "Payhip123"}], [])]
    with patch.object(routes, "_lookup_addon_purchase_candidates", side_effect=lookup_results) as lookup, patch.object(
        routes, "_sync_stores_orders_for_lookup"
    ) as mail_sync, patch.dict(
        "os.environ",
        {"DATABASE_URL": "postgresql://test", "STORES_MAIL_SYNC_ON_SUBMIT": "1"},
        clear=False,
    ):
        result = routes._auto_resolve_addon_purchase(
            "Payhip123", "western_31days_transit_addon", lang="en"
        )

    assert result == ("payhip", "Payhip123", None, 200, [])
    assert lookup.call_count == 2
    mail_sync.assert_called_once_with()


def test_addon_provider_dropdown_is_rendered_only_after_a_collision() -> None:
    with patch.object(
        routes,
        "_auto_resolve_addon_purchase",
        return_value=(
            "",
            "",
            "This purchase reference matches more than one provider.",
            409,
            ["etsy", "payhip"],
        ),
    ):
        response = TestClient(routes.app).post(
            "/addon/generate?lang=en",
            data={
                "addon_type": "western_asteroids_addon",
                "order_code": "SAME-REF",
                "base_yaml": "version: 1",
            },
        )

    assert response.status_code == 409
    assert 'select name="order_provider" id="order-provider"' in response.text
    assert '<option value="etsy">Etsy</option>' in response.text
    assert '<option value="payhip">Payhip</option>' in response.text
    assert '<option value="stores"' not in response.text
    assert '<option value="coconala"' not in response.text
    assert '<option value="gumroad"' not in response.text


def test_localized_chart_redirect_preserves_non_japanese_language() -> None:
    assert routes._chart_redirect_url("token", lang="es") == "/chart/token?lang=es"
    assert routes._chart_redirect_url("token", lang="de") == "/chart/token?lang=de"
    assert routes._chart_redirect_url("token", lang="ja") == "/chart/token"


def test_next_transit_link_preserves_language_without_guessing_purchase_provider() -> None:
    url = routes._next_transit_addon_url(
        "https://chart.nanami-astro.com/chart/token",
        lang="es",
    )

    assert "lang=es" in url
    assert "provider=" not in url
    assert "previous_chart_url=https%3A%2F%2Fchart.nanami-astro.com%2Fchart%2Ftoken" in url
