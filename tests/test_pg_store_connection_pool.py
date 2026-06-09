from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import psycopg2

from services import pg_store


class PgStoreConnectionPoolTest(unittest.TestCase):
    def setUp(self) -> None:
        pg_store._pool = None
        pg_store._pool_url = None

    def tearDown(self) -> None:
        pg_store._pool = None
        pg_store._pool_url = None

    def test_pool_is_lazily_created_once_with_thread_safe_defaults(self) -> None:
        pool = Mock()
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example/db"}, clear=False), patch.object(
            pg_store, "ThreadedConnectionPool", return_value=pool
        ) as pool_class:
            self.assertIs(pg_store._get_pool(), pool)
            self.assertIs(pg_store._get_pool(), pool)

        pool_class.assert_called_once()
        self.assertEqual(pool_class.call_args.args[:2], (1, 10))
        self.assertEqual(pool_class.call_args.kwargs["connect_timeout"], 5)

    def test_connection_is_committed_and_returned_on_success(self) -> None:
        con = Mock(closed=0)
        pool = Mock()
        pool.getconn.return_value = con

        with patch.object(pg_store, "_get_pool", return_value=pool):
            with pg_store._conn() as acquired:
                self.assertIs(acquired, con)

        con.commit.assert_called_once_with()
        con.rollback.assert_not_called()
        pool.putconn.assert_called_once_with(con, close=False)

    def test_connection_is_rolled_back_and_returned_for_application_error(self) -> None:
        con = Mock(closed=0)
        pool = Mock()
        pool.getconn.return_value = con

        with patch.object(pg_store, "_get_pool", return_value=pool):
            with self.assertRaises(ValueError):
                with pg_store._conn():
                    raise ValueError("invalid input")

        con.rollback.assert_called_once_with()
        pool.putconn.assert_called_once_with(con, close=False)

    def test_broken_connection_is_discarded_after_operational_error(self) -> None:
        con = Mock(closed=0)
        pool = Mock()
        pool.getconn.return_value = con

        with patch.object(pg_store, "_get_pool", return_value=pool):
            with self.assertRaises(psycopg2.OperationalError):
                with pg_store._conn():
                    raise psycopg2.OperationalError("connection lost")

        pool.putconn.assert_called_once_with(con, close=True)

    def test_connection_is_discarded_when_rollback_fails(self) -> None:
        con = Mock(closed=0)
        con.rollback.side_effect = psycopg2.InterfaceError("connection closed")
        pool = Mock()
        pool.getconn.return_value = con

        with patch.object(pg_store, "_get_pool", return_value=pool):
            with self.assertRaises(ValueError):
                with pg_store._conn():
                    raise ValueError("query failed")

        pool.putconn.assert_called_once_with(con, close=True)


if __name__ == "__main__":
    unittest.main()
