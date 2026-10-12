from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_marketplace_order_entitlements.py"
SPEC = importlib.util.spec_from_file_location("marketplace_order_migration", SCRIPT)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class FakeCursor:
    def __init__(self):
        self.statements: list[str] = []
        self._last = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self._last = str(statement)
        self.statements.append(self._last)

    def fetchone(self):
        if "to_regnamespace" in self._last or "to_regclass" in self._last:
            return {"present": True}
        return {"row_count": 0}

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_migration_sql_is_limited_to_order_tables():
    sql = "\n".join(migration.LEGACY_COLUMN_STATEMENTS + migration.MIGRATION_STATEMENTS).lower()
    assert "marketplace_orders" in sql
    assert "order_entitlements" in sql
    assert "stores_orders" in sql
    assert "marketplace_order_holds" in sql
    assert "marketplace_processed_notices" in sql
    for forbidden in ("charts", "redemptions", "expires_at", "yaml_text", "drop table", "truncate"):
        assert forbidden not in sql


def test_dry_run_always_rolls_back():
    con = FakeConnection()
    report = migration.run_migration(con, apply=False)
    assert report["ok"] is True
    assert report["committed"] is False
    assert report["touches_chart_or_redemption_data"] is False
    assert con.commits == 0
    assert con.rollbacks == 1


def test_apply_commits_once_without_rollback():
    con = FakeConnection()
    report = migration.run_migration(con, apply=True)
    assert report["ok"] is True
    assert report["committed"] is True
    assert con.commits == 1
    assert con.rollbacks == 0


def test_apply_confirmation_phrase_is_deliberately_specific():
    assert migration.CONFIRM_PHRASE == "MIGRATE:marketplace-order-entitlements"


def test_missing_provider_is_added_before_count_and_copy():
    class MissingProviderCursor(FakeCursor):
        provider_exists = False

        def execute(self, statement, params=None):
            super().execute(statement, params)
            if "ADD COLUMN IF NOT EXISTS provider" in self._last:
                self.provider_exists = True
            if "LOWER(provider)" in self._last:
                assert self.provider_exists, "provider used before it exists"

    con = FakeConnection()
    con.cursor_instance = MissingProviderCursor()
    migration.run_migration(con, apply=True)
    sql = con.cursor_instance.statements
    count = next(i for i, statement in enumerate(sql) if "FROM nanami_products.stores_orders" in statement)
    copy = next(i for i, statement in enumerate(sql) if "INSERT INTO nanami_products.marketplace_orders" in statement)
    assert all(sql.index(statement) < count for statement in migration.LEGACY_COLUMN_STATEMENTS)
    assert count < copy


def test_failure_after_column_preparation_rolls_back_without_commit():
    class FailingCursor(FakeCursor):
        def execute(self, statement, params=None):
            super().execute(statement, params)
            if "INSERT INTO nanami_products.marketplace_orders" in self._last:
                raise RuntimeError("Synthetic migration failure")

    con = FakeConnection()
    con.cursor_instance = FailingCursor()
    with pytest.raises(RuntimeError, match="Synthetic migration failure"):
        migration.run_migration(con, apply=True)
    assert all(statement in con.cursor_instance.statements for statement in migration.LEGACY_COLUMN_STATEMENTS)
    assert con.commits == 0
    assert con.rollbacks == 1


def test_hold_ddl_failure_rolls_back_instead_of_committing_partial_migration():
    class FailingHoldCursor(FakeCursor):
        def execute(self, statement, params=None):
            super().execute(statement, params)
            if "CREATE TABLE IF NOT EXISTS nanami_products.marketplace_order_holds" in self._last:
                raise RuntimeError("Synthetic hold DDL failure")

    con = FakeConnection()
    con.cursor_instance = FailingHoldCursor()
    with pytest.raises(RuntimeError, match="Synthetic hold DDL failure"):
        migration.run_migration(con, apply=True)
    assert con.commits == 0
    assert con.rollbacks == 1
