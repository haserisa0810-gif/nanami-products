from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from services import pg_store


class _RecordingCursor:
    def __init__(self, fetchone_results: list) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone_results = list(fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None) -> None:
        self.executed.append((" ".join(sql.split()), params or ()))

    def fetchone(self):
        return self._fetchone_results.pop(0)


class _RecordingConnection:
    def __init__(self, fetchone_results: list) -> None:
        self.cursor_instance = _RecordingCursor(fetchone_results)

    def cursor(self):
        return self.cursor_instance


@contextmanager
def _connection_context(connection):
    yield connection


def _chart_payload() -> dict:
    return {
        "buyer_name": "Test Buyer",
        "birth_date": "2000-01-01",
        "birth_time": "12:00",
        "birth_place": "Tokyo",
        "options": {"product_type": "western_asteroids_addon"},
        "yaml_text": "version: test\n",
        "prompt_text": "test",
        "share_yaml_text": "version: test\n",
        "horoscope_svg": None,
        "shichusuimei_svg": None,
    }


class AddonIdempotencyTest(unittest.TestCase):
    def test_existing_chart_lookup_is_scoped_to_order_and_addon_type(self) -> None:
        existing = {
            "token": "existing-token",
            "order_code": "1234567890",
            "options": {"product_type": "western_asteroids_addon"},
            "expires_at": None,
        }
        connection = _RecordingConnection([existing])
        with patch.object(pg_store, "_conn", return_value=_connection_context(connection)):
            result = pg_store.get_addon_chart_by_order_code(
                order_code="1234567890",
                addon_type="western_asteroids_addon",
            )

        self.assertEqual(result, existing)
        sql, params = connection.cursor_instance.executed[0]
        self.assertIn("options->>'product_type' = %s", sql)
        self.assertEqual(params, ("1234567890", "western_asteroids_addon"))

    def test_first_redemption_saves_chart_in_same_transaction(self) -> None:
        connection = _RecordingConnection(
            [
                {
                    "stores_order_no": "1234567890",
                    "payment_status": "paid",
                    "product_type": "western_asteroids_addon",
                },
                {"order_code": "1234567890"},
            ]
        )
        with patch.object(
            pg_store,
            "_conn",
            return_value=_connection_context(connection),
        ), patch.object(pg_store, "_insert_chart") as insert_chart:
            status, _order = pg_store.redeem_addon_order_and_save_chart(
                order_code="1234567890",
                addon_type="western_asteroids_addon",
                token="new-token",
                expires_at=None,
                chart_payload=_chart_payload(),
            )

        self.assertEqual(status, "ok")
        executed_sql = "\n".join(sql for sql, _params in connection.cursor_instance.executed)
        self.assertIn("INSERT INTO nanami_products.addon_redemptions", executed_sql)
        insert_chart.assert_called_once()

    def test_duplicate_redemption_does_not_create_another_chart(self) -> None:
        connection = _RecordingConnection(
            [
                {
                    "stores_order_no": "1234567890",
                    "payment_status": "paid",
                    "product_type": "western_asteroids_addon",
                },
                None,
            ]
        )
        with patch.object(
            pg_store,
            "_conn",
            return_value=_connection_context(connection),
        ), patch.object(pg_store, "_insert_chart") as insert_chart:
            status, _order = pg_store.redeem_addon_order_and_save_chart(
                order_code="1234567890",
                addon_type="western_asteroids_addon",
                token="duplicate-token",
                expires_at=None,
                chart_payload=_chart_payload(),
            )

        self.assertEqual(status, "already_used")
        insert_chart.assert_not_called()


if __name__ == "__main__":
    unittest.main()
