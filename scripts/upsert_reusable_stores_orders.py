#!/usr/bin/env python
"""Upsert reusable stores test orders used for manual verification."""

from __future__ import annotations

import os
import psycopg2
from psycopg2.extras import execute_batch

SCHEMA = "nanami_products"

TEST_ORDERS = [
    ("9000000001", "western_basic", "reusable", "reusable [NP-WB] order", "stores"),
    ("9000000002", "western_full", "reusable", "reusable [NP-WF] order", "stores"),
    ("9000000003", "shichu", "reusable", "reusable [NP-SC] order", "stores"),
    ("9000000004", "transit_yaml", "reusable", "reusable [NP-TY] transit yaml order", "stores"),
]

# addon（追加部品）のテストは、この表ではなく登録済みの permanent 番号を使う。
#   9700000031 = western_31days_transit_addon
#   9700000032 = western_long_term_transits_addon
#   9700000007 = product_type 未設定のため全addon共通
# addon の消込は addon_redemptions テーブルで行うため、通常商品用の reusable 番号
# （redemptions / charts 側）とは別枠になる。


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    with psycopg2.connect(database_url) as con:
        with con.cursor() as cur:
            execute_batch(
                cur,
                f"""
                INSERT INTO {SCHEMA}.stores_orders
                  (stores_order_no, product_type, amount, payment_status, mail_subject, provider, mail_received_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (stores_order_no) DO UPDATE
                  SET product_type = EXCLUDED.product_type,
                      amount = EXCLUDED.amount,
                      payment_status = 'reusable',
                      mail_subject = EXCLUDED.mail_subject,
                      provider = COALESCE(EXCLUDED.provider, {SCHEMA}.stores_orders.provider),
                      updated_at = NOW();
                """,
                [(order_no, product_type, 0, status, subject, provider) for order_no, product_type, status, subject, provider in TEST_ORDERS],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
