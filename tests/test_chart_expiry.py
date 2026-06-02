from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

import routes


class ChartExpiryTests(unittest.TestCase):
    def test_chart_expiry_falls_back_to_created_at_plus_90_days(self) -> None:
        created_at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

        expires_at = routes._chart_expiry({"created_at": created_at})

        self.assertEqual(expires_at, created_at + timedelta(days=90))

    def test_load_chart_returns_unexpired_chart(self) -> None:
        chart = {
            "token": "tok",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        }

        with patch.object(routes.pg_store, "get_chart", return_value=chart):
            self.assertIs(routes._load_chart_or_404("tok"), chart)

    def test_load_chart_rejects_expired_chart(self) -> None:
        chart = {
            "token": "tok",
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        }

        with patch.object(routes.pg_store, "get_chart", return_value=chart):
            with self.assertRaises(HTTPException) as caught:
                routes._load_chart_or_404("tok")

        self.assertEqual(caught.exception.status_code, 410)
        self.assertEqual(caught.exception.detail, "chart expired")


if __name__ == "__main__":
    unittest.main()
