from __future__ import annotations

import unittest
from unittest.mock import patch

from services import stores_mail_sync


class _CapturingCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = ()
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None) -> None:
        self.sql = sql
        self.params = params or ()
        self.executed.append((" ".join(sql.split()), self.params))

    def fetchone(self):
        return {"is_new": False}


class _CapturingConnection:
    def __init__(self) -> None:
        self.cursor_instance = _CapturingCursor()

    def cursor(self):
        return self.cursor_instance


class StoresOrderUpsertStatusTest(unittest.TestCase):
    def test_mail_resync_preserves_admin_managed_payment_statuses(self) -> None:
        connection = _CapturingConnection()

        with patch.object(stores_mail_sync, "_upsert_order_entitlements"):
            stores_mail_sync._upsert_order(
                connection,
                {
                    "stores_order_no": "1234567890",
                    "provider": "stores",
                    "product_type": "western_basic",
                    "payment_status": "paid",
                },
            )

        normalized_sql = connection.cursor_instance.executed[0][0]
        protected_status_clause = (
            "WHEN nanami_products.marketplace_orders.payment_status "
            "IN ('reset_once', 'reusable', 'test', 'permanent') "
            "THEN nanami_products.marketplace_orders.payment_status"
        )
        paid_clause = "WHEN EXCLUDED.payment_status = 'paid' THEN 'paid'"

        self.assertIn(protected_status_clause, normalized_sql)
        self.assertIn(paid_clause, normalized_sql)
        self.assertLess(
            normalized_sql.index(protected_status_clause),
            normalized_sql.index(paid_clause),
        )

        legacy_sql = connection.cursor_instance.executed[1][0]
        self.assertIn(
            "ON CONFLICT (stores_order_no) DO UPDATE SET",
            legacy_sql,
        )
        self.assertIn(
            "LOWER(nanami_products.stores_orders.provider) = EXCLUDED.provider",
            legacy_sql,
        )

    def test_marketplace_order_upsert_uses_provider_and_order_code(self) -> None:
        connection = _CapturingConnection()

        with patch.object(stores_mail_sync, "_upsert_order_entitlements"):
            stores_mail_sync._upsert_order(
                connection,
                {
                    "stores_order_no": "SAME-ORDER",
                    "provider": "etsy",
                    "product_type": "western_full",
                },
            )

        sql, params = connection.cursor_instance.executed[0]
        self.assertIn("INSERT INTO nanami_products.marketplace_orders", sql)
        self.assertIn("ON CONFLICT (provider, order_code)", sql)
        self.assertEqual(params[:2], ("etsy", "SAME-ORDER"))


if __name__ == "__main__":
    unittest.main()
