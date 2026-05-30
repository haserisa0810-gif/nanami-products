from __future__ import annotations

import unittest
from unittest.mock import patch

import services.pg_store as pg_store


class _DummyCursor:
    def __init__(self) -> None:
        self.fetchone_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        self.fetchone_calls += 1
        return {"order_code": "ok"} if self.fetchone_calls == 1 else None


class _DummyConn:
    def __init__(self, cursor: _DummyCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class RedeemAndSaveMetadataTest(unittest.TestCase):
    def test_redemption_metadata_is_accepted_and_embedded_in_chart_options(self) -> None:
        cursor = _DummyCursor()
        seen = {}

        def fake_insert_chart(cur, **kwargs):
            seen.update(kwargs)

        with patch.object(pg_store, "_conn", return_value=_DummyConn(cursor)), patch.object(
            pg_store, "_insert_chart", side_effect=fake_insert_chart
        ):
            ok = pg_store.redeem_and_save(
                order_code="A1",
                email="buyer@example.com",
                buyer_name="Buyer",
                token="tok",
                birth_date="2000-01-01",
                birth_time="12:00",
                birth_place="Tokyo",
                options={"product_type": "western_full"},
                yaml_text="yaml",
                prompt_text="prompt",
                redemption_metadata={"provider": "stores", "note": "audit"},
            )

        self.assertTrue(ok)
        self.assertEqual(
            seen["options"],
            {"product_type": "western_full", "redemption_metadata": {"provider": "stores", "note": "audit"}},
        )


if __name__ == "__main__":
    unittest.main()
