"""Create provider-scoped marketplace order tables without touching chart data.

The default mode is a transactional dry run. Production application requires both
``--apply`` and the exact confirmation phrase shown by ``--help``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.stores_mail_sync import (  # noqa: E402
    MARKETPLACE_ORDERS_DDL,
    ORDER_ENTITLEMENTS_DDL,
    SCHEMA,
)


CONFIRM_PHRASE = "MIGRATE:marketplace-order-entitlements"
MIGRATION_NAME = "marketplace_order_entitlements_v1"

# Keep the one-time migration deliberately narrower than pg_store.init_db().
# In particular, it must never alter charts, redemptions, expiry values, or URLs.
MIGRATION_STATEMENTS = (
    MARKETPLACE_ORDERS_DDL,
    ORDER_ENTITLEMENTS_DDL,
    f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS product_type TEXT",
    f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS provider TEXT",
    f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS buyer_reference TEXT",
    (
        f"CREATE INDEX IF NOT EXISTS idx_stores_orders_provider_buyer "
        f"ON {SCHEMA}.stores_orders (provider, buyer_reference)"
    ),
    (
        f"CREATE INDEX IF NOT EXISTS idx_marketplace_orders_buyer "
        f"ON {SCHEMA}.marketplace_orders (provider, buyer_reference)"
    ),
    f"""
        INSERT INTO {SCHEMA}.marketplace_orders
            (provider, order_code, product_type, amount, payment_status,
             mail_subject, raw_message_id, buyer_reference,
             mail_received_at, created_at, updated_at)
        SELECT COALESCE(NULLIF(LOWER(provider), ''), 'stores'),
               stores_order_no, product_type, amount, payment_status,
               mail_subject, raw_message_id, buyer_reference,
               mail_received_at, created_at, updated_at
        FROM {SCHEMA}.stores_orders
        ON CONFLICT (provider, order_code) DO NOTHING
    """,
    (
        f"CREATE INDEX IF NOT EXISTS idx_order_entitlements_lookup "
        f"ON {SCHEMA}.order_entitlements "
        f"(order_code, provider, product_type, status)"
    ),
)


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _provider_counts(cur, table: str, provider_column: str) -> dict[str, int]:
    cur.execute(
        f"""
        SELECT COALESCE(NULLIF(LOWER({provider_column}), ''), 'stores') AS provider,
               COUNT(*) AS row_count
        FROM {SCHEMA}.{table}
        GROUP BY 1
        ORDER BY 1
        """
    )
    return {str(row["provider"]): int(row["row_count"]) for row in cur.fetchall()}


def _count(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) AS row_count FROM {SCHEMA}.{table}")
    return int(cur.fetchone()["row_count"])


def run_migration(con, *, apply: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "migration": MIGRATION_NAME,
        "mode": "apply" if apply else "dry_run_rolled_back",
        "committed": False,
        "touches_chart_or_redemption_data": False,
    }
    try:
        with con.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (MIGRATION_NAME,))
            cur.execute("SELECT to_regnamespace(%s) IS NOT NULL AS present", (SCHEMA,))
            if not cur.fetchone()["present"]:
                raise RuntimeError(f"Expected existing schema {SCHEMA!r}")
            cur.execute(
                "SELECT to_regclass(%s) IS NOT NULL AS present",
                (f"{SCHEMA}.stores_orders",),
            )
            if not cur.fetchone()["present"]:
                raise RuntimeError("Expected existing stores_orders table")

            report["legacy_orders_before"] = _provider_counts(cur, "stores_orders", "provider")
            for statement in MIGRATION_STATEMENTS:
                cur.execute(statement)
            report["marketplace_orders_after"] = _provider_counts(
                cur, "marketplace_orders", "provider"
            )
            report["entitlements_after"] = _count(cur, "order_entitlements")

        if apply:
            con.commit()
            report["committed"] = True
            report["mode"] = "applied"
        else:
            con.rollback()
        report["ok"] = True
        return report
    except Exception:
        con.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely create marketplace_orders and order_entitlements only."
    )
    parser.add_argument("--apply", action="store_true", help="Commit instead of rolling back")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply: {CONFIRM_PHRASE}",
    )
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_PHRASE:
        parser.error(f"--apply requires --confirm {CONFIRM_PHRASE}")

    con = psycopg2.connect(_database_url(), cursor_factory=RealDictCursor, connect_timeout=8)
    try:
        con.autocommit = False
        report = run_migration(con, apply=args.apply)
    finally:
        con.close()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
