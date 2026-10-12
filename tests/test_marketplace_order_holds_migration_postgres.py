"""O02: hold/notice DDL migration, using only synthetic UUID test schemas."""
from datetime import datetime, timezone

import psycopg2
import pytest

from services import order_holds, stores_mail_sync as sync
from test_marketplace_order_migration_postgres import (
    database, migration, prepare_legacy, run, snapshot,
)
from test_purchase_notifications_postgres import (
    approve, ingest, issue, review_version, scalar,
)


@pytest.fixture(params=["absent", "legacy", "current"])
def hold_state(database, request):
    prepare_legacy(database, missing_columns=True)
    if request.param != "absent":
        with database[0]() as con:
            with con.cursor() as cur:
                cur.execute(order_holds.DDL.replace("nanami_products", database[1]))
                cur.execute(f"""INSERT INTO {database[1]}.marketplace_order_holds
                    (provider,order_code,reason,notification_status,notification_attempts)
                    VALUES ('payhip','PriorHold','unknown_product_code','sent',2)""")
                cur.execute(f"""INSERT INTO {database[1]}.marketplace_processed_notices
                    (provider,order_code,notice_fingerprint)
                    VALUES ('payhip','PriorHold','synthetic-fingerprint')""")
                if request.param == "legacy":
                    cur.execute(f"""ALTER TABLE {database[1]}.marketplace_order_holds
                        DROP COLUMN candidate, DROP COLUMN review_version,
                        DROP COLUMN review_history, DROP COLUMN approved_version,
                        DROP COLUMN approved_at""")
    return request.param


def assert_hold_contract(db):
    """Check catalog types/nullability/keys, plus actual check-constraint behavior."""
    with db[0]() as con:
        with con.cursor() as cur:
            cur.execute("SELECT column_name,data_type,is_nullable FROM information_schema.columns "
                        "WHERE table_schema=%s AND table_name='marketplace_order_holds'", (db[1],))
            columns = {row['column_name']: (row['data_type'], row['is_nullable']) for row in cur.fetchall()}
            assert columns == {
                'provider': ('text','NO'), 'order_code': ('text','NO'), 'reason': ('text','NO'),
                'status': ('text','NO'), 'first_seen_at': ('timestamp with time zone','NO'),
                'last_seen_at': ('timestamp with time zone','NO'), 'notification_status': ('text','NO'),
                'notification_attempts': ('integer','NO'), 'last_notification_at': ('timestamp with time zone','YES'),
                'candidate': ('jsonb','YES'), 'review_version': ('bigint','NO'),
                'review_history': ('jsonb','NO'), 'approved_version': ('bigint','YES'),
                'approved_at': ('timestamp with time zone','YES'),
            }
            cur.execute("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns "
                        "WHERE table_schema=%s AND table_name='marketplace_processed_notices'", (db[1],))
            assert {r['column_name']: (r['data_type'],r['is_nullable']) for r in cur.fetchall()} == {
                'provider': ('text','NO'), 'order_code': ('text','NO'),
                'notice_fingerprint': ('text','NO'), 'processed_at': ('timestamp with time zone','NO'),
            }
            cur.execute("SELECT tc.table_name,kcu.column_name FROM information_schema.table_constraints tc "
                        "JOIN information_schema.key_column_usage kcu "
                        "ON tc.constraint_catalog=kcu.constraint_catalog AND tc.constraint_schema=kcu.constraint_schema "
                        "AND tc.constraint_name=kcu.constraint_name "
                        "WHERE tc.table_schema=%s AND tc.constraint_type='PRIMARY KEY' "
                        "AND tc.table_name IN ('marketplace_order_holds','marketplace_processed_notices') "
                        "ORDER BY tc.table_name,kcu.ordinal_position", (db[1],))
            assert [(r['table_name'],r['column_name']) for r in cur.fetchall()] == [
                ('marketplace_order_holds','provider'), ('marketplace_order_holds','order_code'),
                ('marketplace_processed_notices','provider'), ('marketplace_processed_notices','order_code'),
                ('marketplace_processed_notices','notice_fingerprint'),
            ]
            for column in ('status','notification_status'):
                cur.execute('SAVEPOINT invalid_status')
                with pytest.raises(psycopg2.errors.CheckViolation):
                    cur.execute(f"INSERT INTO {db[1]}.marketplace_order_holds "
                                f"(provider,order_code,reason,{column}) VALUES ('payhip','Invalid','unknown_product_code','invalid')")
                cur.execute('ROLLBACK TO SAVEPOINT invalid_status')
                cur.execute('RELEASE SAVEPOINT invalid_status')


def test_o02_dry_run_restores_all_schema_and_rows(database, migration, hold_state):
    before = snapshot(database)
    report = run(database, migration, False)
    assert report['ok'] and not report['committed']
    assert snapshot(database) == before


def test_o02_apply_repeat_retains_prior_hold_rows_and_creates_contract(database, migration, hold_state):
    before = snapshot(database)
    assert run(database, migration, True)['committed']
    after = snapshot(database)
    for table in before['rows']:
        if table == 'stores_orders' or table == 'marketplace_order_holds':
            assert len(before['rows'][table]) == len(after['rows'][table])
            for old, new in zip(before['rows'][table], after['rows'][table]):
                assert {key:new[key] for key in old} == old
        else:
            assert after['rows'][table] == before['rows'][table]
    assert len(after['rows']['marketplace_orders']) == 2
    assert after['rows']['order_entitlements'] == []
    assert_hold_contract(database)
    assert run(database, migration, True)['committed']
    assert snapshot(database) == after


def test_o02_later_failure_rolls_back_hold_ddl_columns_and_copy(database, migration, hold_state, monkeypatch):
    before = snapshot(database)
    monkeypatch.setattr(migration, 'MIGRATION_STATEMENTS', migration.MIGRATION_STATEMENTS + (
        f'SELECT nonexistent_o02_column FROM {database[1]}.marketplace_order_holds',))
    with pytest.raises(psycopg2.errors.UndefinedColumn):
        run(database, migration, True)
    assert snapshot(database) == before


@pytest.mark.parametrize('with_source_id', [False, True])
@pytest.mark.parametrize('missing_columns', [False, True])
def test_o02_migration_alone_accepts_purchase_replay_and_requires_held_approval(
        database, migration, with_source_id, missing_columns):
    prepare_legacy(database, missing_columns)
    assert run(database, migration, True)['committed']
    def notify(order, sku):
        row = sync._parse_payhip_mail("You've Sold An Item!", f"Order ID: {order}\nProduct: [{sku}]",
            'synthetic-' + order + '-' + sku if with_source_id else None, None, 'contact@payhip.com')
        with database[0]() as con:
            sync._upsert_order(con, row)
    notify('AfterMigration', 'NP-WF')
    notify('AfterMigration', 'NP-WF')
    assert scalar(database, 'SELECT COUNT(*) FROM {schema}.order_entitlements') == 1
    assert issue('AfterMigration', 'western_full', 'AfterMigrationOriginal')
    assert not issue('AfterMigration', 'western_full', 'Duplicate')
    notify('HeldAfterMigration', 'NP-SFULL')
    assert not issue('HeldAfterMigration', 'western_full')
    notify('HeldAfterMigration', 'NP-WF')
    assert scalar(database, 'SELECT COUNT(*) FROM {schema}.order_entitlements') == 1
    assert not issue('HeldAfterMigration', 'western_full')
    assert approve(database, 'HeldAfterMigration', review_version(database, 'HeldAfterMigration'))['ok']
    assert issue('HeldAfterMigration', 'western_full', 'ApprovedOriginal')
    assert not issue('HeldAfterMigration', 'western_full')
    expected = 3 if with_source_id else 0
    assert scalar(database, 'SELECT COUNT(*) FROM {schema}.marketplace_processed_notices') == expected


def test_o02_existing_rights_review_history_notice_and_nonnull_original_are_preserved(database, migration):
    ingest(database, 'Order ID: Prior\nProduct: [NP-WF]\nQuantity: 2')
    assert issue('Prior', 'western_full', 'PriorOriginal')
    ingest(database, 'Order ID: Prior\nProduct: [NP-WF]\nQuantity: 3')
    ingest(database, 'Order ID: Prior\nProduct: [NP-WF]\nQuantity: 4')
    with database[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {database[1]}.charts SET share_yaml_text='Original shared YAML', expires_at=%s",
                        (datetime(2030,1,1,tzinfo=timezone.utc),))
            cur.execute(f"UPDATE {database[1]}.marketplace_order_holds SET notification_status='sent', notification_attempts=2")
            cur.execute(f"INSERT INTO {database[1]}.marketplace_processed_notices "
                        "(provider,order_code,notice_fingerprint) VALUES ('payhip','Prior','prior-fingerprint')")
    before = snapshot(database)
    rights = before['rows']['order_entitlements']
    assert sorted(r['status'] for r in rights) == ['available','redeemed']
    assert before['rows']['marketplace_order_holds'][0]['review_history']
    assert run(database, migration, False)['ok']
    assert snapshot(database) == before
    assert run(database, migration, True)['committed']
    after = snapshot(database)
    assert after['rows'] == before['rows']
    assert after['columns'] == before['columns']
    def index_definitions(state):
        return {(r['tablename'],r['indexname'],r['indexdef']) for r in state['indexes']}
    old_indexes, new_indexes = index_definitions(before), index_definitions(after)
    assert old_indexes <= new_indexes
    assert new_indexes - old_indexes == {
        ('stores_orders','idx_stores_orders_provider_buyer',
         f'CREATE INDEX idx_stores_orders_provider_buyer ON {database[1]}.stores_orders USING btree (provider, buyer_reference)'),
        ('marketplace_orders','idx_marketplace_orders_buyer',
         f'CREATE INDEX idx_marketplace_orders_buyer ON {database[1]}.marketplace_orders USING btree (provider, buyer_reference)'),
        ('order_entitlements','idx_order_entitlements_lookup',
         f'CREATE INDEX idx_order_entitlements_lookup ON {database[1]}.order_entitlements USING btree (order_code, provider, product_type, status)'),
    }
    assert run(database, migration, True)['committed']
    assert snapshot(database) == after
    assert not issue('Prior', 'western_full')


def test_o02_old_issued_unit_stays_consumed_and_unused_unit_is_issued_once(database, migration):
    prepare_legacy(database, missing_columns=False)
    with database[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {database[1]}.stores_orders SET provider='payhip',product_type='western_full'")
            cur.execute(f"UPDATE {database[1]}.charts SET options='{{\"product_type\":\"western_full\",\"order_provider\":\"payhip\"}}'")
    before = snapshot(database)
    assert run(database, migration, True)['committed']
    for _ in range(2):
        ingest(database, 'Order ID: Issued\nProduct: [NP-WF]')
    assert not issue('Issued','western_full')
    assert issue('Unused','western_full','FirstLegacyUse')
    assert not issue('Unused','western_full','DuplicateLegacyUse')
    after = snapshot(database)
    assert len(after['rows']['charts']) == len(before['rows']['charts']) + 1
    assert next(row for row in after['rows']['charts'] if row['token']=='Original') == before['rows']['charts'][0]
    assert next(row for row in after['rows']['redemptions'] if row['order_code']=='Issued') == before['rows']['redemptions'][0]
