"""O01 regression against an explicit loopback PostgreSQL and UUID schemas.

The shared fixture never reads DATABASE_URL and drops only its own schema.
Original operational probes and their evidence remain unchanged.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re

import psycopg2
import pytest

from test_purchase_notifications_postgres import database


@pytest.fixture
def migration(database, monkeypatch):
    schema = database[1]
    assert re.fullmatch(r"notification_test_[0-9a-f]{32}", schema)
    script = Path(__file__).resolve().parents[1] / "scripts/migrate_marketplace_order_entitlements.py"
    spec = importlib.util.spec_from_file_location("o01_migration", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "SCHEMA", schema)
    for name in ("LEGACY_COLUMN_STATEMENTS", "MIGRATION_STATEMENTS"):
        statements = tuple(sql.replace("nanami_products", schema) for sql in getattr(module, name))
        assert all("nanami_products" not in sql for sql in statements)
        monkeypatch.setattr(module, name, statements)
    return module


def prepare_legacy(db, missing_columns):
    schema = db[1]
    with db[0]() as con:
        with con.cursor() as cur:
            for table in ("marketplace_order_holds", "marketplace_processed_notices",
                          "order_entitlements", "marketplace_orders", "stores_orders"):
                cur.execute(f"DROP TABLE {schema}.{table}")
            cur.execute(f"""CREATE TABLE {schema}.stores_orders (
                stores_order_no TEXT PRIMARY KEY, amount INTEGER, payment_status TEXT,
                mail_subject TEXT, raw_message_id TEXT, mail_received_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)""")
            cur.execute(f"""INSERT INTO {schema}.stores_orders
                (stores_order_no, amount, payment_status, created_at, updated_at)
                VALUES ('Issued', 880, 'paid', '2020-01-01T00:00:00Z', '2020-01-01T00:00:00Z'),
                       ('Unused', 880, 'paid', '2020-01-02T00:00:00Z', '2020-01-02T00:00:00Z')""")
            if not missing_columns:
                cur.execute(f"""ALTER TABLE {schema}.stores_orders ADD COLUMN provider TEXT,
                    ADD COLUMN product_type TEXT, ADD COLUMN buyer_reference TEXT""")
                cur.execute(f"""UPDATE {schema}.stores_orders SET provider='payhip',
                    product_type='western_full', buyer_reference='synthetic-reference' WHERE stores_order_no='Issued'""")
            cur.execute(f"""INSERT INTO {schema}.charts
                (token, order_code, birth_date, yaml_text, prompt_text, share_yaml_text, expires_at, created_at)
                VALUES ('Original', 'Issued', '2000-01-01', 'original: exact bytes\n',
                    'Original prompt', NULL, NULL, '2020-01-01T00:00:00Z')""")
            cur.execute(f"INSERT INTO {schema}.redemptions (order_code, token) VALUES ('Issued','Original')")


def snapshot(db):
    schema = db[1]
    with db[0]() as con:
        with con.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename", (schema,))
            tables = [row['tablename'] for row in cur.fetchall()]
            rows = {}
            for table in tables:
                cur.execute(f'SELECT * FROM {schema}."{table}" ORDER BY 1,2')
                rows[table] = cur.fetchall()
            cur.execute("SELECT table_name, column_name, data_type, is_nullable, column_default "
                        "FROM information_schema.columns WHERE table_schema=%s ORDER BY table_name, ordinal_position", (schema,))
            columns = cur.fetchall()
            cur.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname=%s ORDER BY tablename,indexname", (schema,))
            return {'rows': rows, 'columns': columns, 'indexes': cur.fetchall()}


def run(db, migration, apply):
    with db[0]() as con:
        return migration.run_migration(con, apply=apply)


@pytest.mark.parametrize('missing_columns', [True, False])
def test_o01_dry_run_restores_rows_columns_and_indexes(database, migration, missing_columns):
    prepare_legacy(database, missing_columns)
    before = snapshot(database)
    report = run(database, migration, False)
    assert report['ok'] and not report['committed']
    assert report['legacy_orders_before'] == ({'stores': 2} if missing_columns else {'payhip': 1, 'stores': 1})
    assert snapshot(database) == before


@pytest.mark.parametrize('missing_columns', [True, False])
def test_o01_apply_and_repeat_preserve_values_originals_and_counts(database, migration, missing_columns):
    prepare_legacy(database, missing_columns)
    before = snapshot(database)
    report = run(database, migration, True)
    expected_counts = {'stores': 2} if missing_columns else {'payhip': 1, 'stores': 1}
    assert report['committed'] and report['legacy_orders_before'] == expected_counts
    assert report['marketplace_orders_after'] == expected_counts
    after = snapshot(database)
    for table in ('charts', 'redemptions'):
        assert after['rows'][table] == before['rows'][table]
    for old, new in zip(before['rows']['stores_orders'], after['rows']['stores_orders']):
        assert {key: new[key] for key in old} == old
        if missing_columns:
            assert all(new[key] is None for key in ('provider', 'product_type', 'buyer_reference'))
    assert len(after['rows']['marketplace_orders']) == 2
    assert after['rows']['order_entitlements'] == []
    assert run(database, migration, True)['committed']
    assert snapshot(database) == after


@pytest.mark.parametrize('missing_columns', [True, False])
def test_o01_later_failure_rolls_back_all_ddl_and_rows(database, migration, missing_columns, monkeypatch):
    prepare_legacy(database, missing_columns)
    before = snapshot(database)
    monkeypatch.setattr(migration, 'MIGRATION_STATEMENTS', migration.MIGRATION_STATEMENTS + (
        f'SELECT nonexistent_o01_column FROM {database[1]}.stores_orders',))
    with pytest.raises(psycopg2.errors.UndefinedColumn):
        run(database, migration, True)
    assert snapshot(database) == before
