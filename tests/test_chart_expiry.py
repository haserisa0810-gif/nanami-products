from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

import routes
from services import pg_store


class _FakeCleanupCursor:
    def __init__(self, rows: list[dict], now: datetime) -> None:
        self.rows = rows
        self.now = now
        self._one: dict | None = None
        self._many: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: tuple[int, ...]) -> None:
        grace_days = int(params[0])
        cutoff = self.now - timedelta(days=grace_days)
        expired = [row for row in self.rows if row["expires_at"] < cutoff]
        if "COUNT(*) AS expired_count" in sql:
            self._one = {
                "expired_count": len(expired),
                "oldest_expires_at": min((row["expires_at"] for row in expired), default=None),
                "newest_expires_at": max((row["expires_at"] for row in expired), default=None),
            }
            self._many = []
            return
        if "DELETE FROM" in sql:
            expired_tokens = {row["token"] for row in expired}
            self.rows[:] = [row for row in self.rows if row["token"] not in expired_tokens]
            self._one = None
            self._many = expired
            return
        self._one = None
        self._many = expired[:10]

    def fetchone(self) -> dict | None:
        return self._one

    def fetchall(self) -> list[dict]:
        return self._many


class _FakeCleanupConnection:
    def __init__(self, rows: list[dict], now: datetime) -> None:
        self.rows = rows
        self.now = now

    def cursor(self) -> _FakeCleanupCursor:
        return _FakeCleanupCursor(self.rows, self.now)


def _fake_cleanup_conn(rows: list[dict], now: datetime):
    @contextmanager
    def _conn():
        yield _FakeCleanupConnection(rows, now)

    return _conn


class ChartExpiryTests(unittest.TestCase):
    def test_chart_expiry_falls_back_to_created_at_plus_90_days(self) -> None:
        created_at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

        expires_at = routes._chart_expiry({"created_at": created_at})

        self.assertEqual(expires_at, created_at + timedelta(days=90))

    def test_chart_expiry_allows_explicit_no_expiry_policy(self) -> None:
        created_at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

        expires_at = routes._chart_expiry(
            {
                "created_at": created_at,
                "expires_at": None,
                "options": {"expires_policy": routes.NO_EXPIRY_CHART_POLICY},
            }
        )

        self.assertIsNone(expires_at)

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

    def test_cleanup_summary_keeps_29_day_expired_chart_outside_grace_period(self) -> None:
        now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "token": "expired_29_days",
                "order_code": "order1",
                "buyer_name": "user",
                "created_at": now - timedelta(days=119),
                "expires_at": now - timedelta(days=29),
            }
        ]

        with patch.object(pg_store, "_conn", _fake_cleanup_conn(rows, now)):
            summary = pg_store.expired_charts_summary(grace_days=30)

        self.assertEqual(summary["expired_count"], 0)
        self.assertEqual(summary["samples"], [])

    def test_cleanup_summary_counts_chart_after_30_day_grace_period(self) -> None:
        now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "token": "expired_30_days_and_1_second",
                "order_code": "order1",
                "buyer_name": "user",
                "created_at": now - timedelta(days=120, seconds=1),
                "expires_at": now - timedelta(days=30, seconds=1),
            }
        ]

        with patch.object(pg_store, "_conn", _fake_cleanup_conn(rows, now)):
            summary = pg_store.expired_charts_summary(grace_days=30)

        self.assertEqual(summary["expired_count"], 1)
        self.assertEqual(summary["samples"][0]["token"], "expired_30_days_and_1_second")

    def test_cleanup_deletes_only_charts_after_grace_period(self) -> None:
        now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "token": "expired_29_days",
                "order_code": "order1",
                "buyer_name": "user",
                "created_at": now - timedelta(days=119),
                "expires_at": now - timedelta(days=29),
            },
            {
                "token": "expired_30_days_and_1_second",
                "order_code": "order2",
                "buyer_name": "user",
                "created_at": now - timedelta(days=120, seconds=1),
                "expires_at": now - timedelta(days=30, seconds=1),
            },
        ]

        with patch.object(pg_store, "_conn", _fake_cleanup_conn(rows, now)):
            result = pg_store.delete_expired_charts(grace_days=30)

        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["deleted_samples"][0]["token"], "expired_30_days_and_1_second")
        self.assertEqual([row["token"] for row in rows], ["expired_29_days"])


if __name__ == "__main__":
    unittest.main()
