from __future__ import annotations

import unittest

from services import stores_mail_sync


class _CapturingCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None) -> None:
        self.sql = sql
        self.params = params or ()

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

        stores_mail_sync._upsert_order(
            connection,
            {
                "stores_order_no": "1234567890",
                "provider": "stores",
                "product_type": "western_basic",
                "payment_status": "paid",
            },
        )

        normalized_sql = " ".join(connection.cursor_instance.sql.split())
        protected_status_clause = (
            "WHEN nanami_products.stores_orders.payment_status "
            "IN ('reset_once', 'reusable', 'test', 'permanent') "
            "THEN nanami_products.stores_orders.payment_status"
        )
        paid_clause = "WHEN EXCLUDED.payment_status = 'paid' THEN 'paid'"

        self.assertIn(protected_status_clause, normalized_sql)
        self.assertIn(paid_clause, normalized_sql)
        self.assertLess(
            normalized_sql.index(protected_status_clause),
            normalized_sql.index(paid_clause),
        )


if __name__ == "__main__":
    unittest.main()
