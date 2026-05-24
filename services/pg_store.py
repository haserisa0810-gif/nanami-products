from __future__ import annotations

import os
import hashlib
import secrets
from datetime import datetime
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
from psycopg2.extras import RealDictCursor, Json

SCHEMA = "nanami_products"


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("環境変数 DATABASE_URL が設定されていません")
    # psycopg2 は postgresql:// のみ受け付ける
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


@contextmanager
def _conn() -> Generator:
    con = psycopg2.connect(_get_url(), cursor_factory=RealDictCursor)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute("SELECT to_regnamespace(%s) AS schema_oid", (SCHEMA,))
            if not cur.fetchone()["schema_oid"]:
                cur.execute(f"CREATE SCHEMA {SCHEMA}")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.redemptions (
                    order_code  TEXT        PRIMARY KEY,
                    email       TEXT,
                    buyer_name  TEXT,
                    token       TEXT        UNIQUE NOT NULL,
                    used_at     TIMESTAMPTZ,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.charts (
                    token       TEXT        PRIMARY KEY,
                    order_code  TEXT,
                    buyer_name  TEXT,
                    birth_date  TEXT        NOT NULL,
                    birth_time  TEXT,
                    birth_place TEXT,
                    options     JSONB,
                    yaml_text   TEXT        NOT NULL,
                    prompt_text TEXT        NOT NULL,
                    share_yaml_text TEXT,
                    horoscope_svg TEXT,
                    shichusuimei_svg TEXT,
                    expires_at  TIMESTAMPTZ,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            _ensure_chart_columns(cur)
            cur.execute(f"""
                UPDATE {SCHEMA}.charts
                SET share_yaml_text = yaml_text
                WHERE share_yaml_text IS NULL
            """)
            cur.execute(f"""
                UPDATE {SCHEMA}.charts
                SET expires_at = created_at + INTERVAL '90 days'
                WHERE expires_at IS NULL
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_charts_expires_at
                ON {SCHEMA}.charts (expires_at)
            """)
            _ensure_addon_redemptions_table(cur)
            _ensure_transit_addon_links_table(cur)
            ensure_api_tables(cur)


def _ensure_chart_columns(cur) -> None:
    # Cloud Run startup intentionally skips init_db(), so write paths must tolerate
    # databases created from older DDL.
    cur.execute(f"ALTER TABLE {SCHEMA}.charts ALTER COLUMN order_code DROP NOT NULL")
    cur.execute(f"ALTER TABLE {SCHEMA}.charts ADD COLUMN IF NOT EXISTS share_yaml_text TEXT")
    cur.execute(f"ALTER TABLE {SCHEMA}.charts ADD COLUMN IF NOT EXISTS horoscope_svg TEXT")
    cur.execute(f"ALTER TABLE {SCHEMA}.charts ADD COLUMN IF NOT EXISTS shichusuimei_svg TEXT")
    cur.execute(f"ALTER TABLE {SCHEMA}.charts ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")


def _ensure_addon_redemptions_table(cur) -> None:
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.addon_redemptions (
            order_code  TEXT        NOT NULL,
            addon_type  TEXT        NOT NULL,
            used_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (order_code, addon_type)
        )
    """)


def _ensure_transit_addon_links_table(cur) -> None:
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.transit_addon_links (
            token      TEXT        PRIMARY KEY,
            yaml_text  TEXT        NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _chart_columns(cur) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = 'charts'
        """,
        (SCHEMA,),
    )
    return {row["column_name"] for row in cur.fetchall()}


def _insert_chart(
    cur,
    *,
    token: str,
    order_code: str | None,
    buyer_name: str | None,
    birth_date: str,
    birth_time: str | None,
    birth_place: str | None,
    options: dict[str, Any],
    yaml_text: str,
    prompt_text: str,
    share_yaml_text: str | None,
    horoscope_svg: str | None,
    shichusuimei_svg: str | None,
    expires_at: datetime | None,
    on_conflict_do_nothing: bool = False,
) -> None:
    available = _chart_columns(cur)
    columns = [
        "token",
        "order_code",
        "buyer_name",
        "birth_date",
        "birth_time",
        "birth_place",
        "options",
        "yaml_text",
        "prompt_text",
    ]
    values: list[Any] = [
        token,
        order_code,
        buyer_name,
        birth_date,
        birth_time,
        birth_place,
        Json(options),
        yaml_text,
        prompt_text,
    ]
    placeholders = ["%s"] * len(columns)

    optional_values = {
        "share_yaml_text": share_yaml_text,
        "horoscope_svg": horoscope_svg,
        "shichusuimei_svg": shichusuimei_svg,
    }
    for column, value in optional_values.items():
        if column in available:
            columns.append(column)
            placeholders.append("%s")
            values.append(value)

    if "expires_at" in available:
        columns.append("expires_at")
        placeholders.append("COALESCE(%s, NOW() + INTERVAL '90 days')")
        values.append(expires_at)

    conflict_clause = " ON CONFLICT (token) DO NOTHING" if on_conflict_do_nothing else ""
    cur.execute(
        f"""
        INSERT INTO {SCHEMA}.charts
            ({", ".join(columns)})
        VALUES ({", ".join(placeholders)})
        {conflict_clause}
        """,
        values,
    )


def ensure_api_tables(cur=None) -> None:
    owns_connection = cur is None
    if owns_connection:
        con_cm = _conn()
        con = con_cm.__enter__()
        cur = con.cursor()
    try:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.api_keys (
                id                BIGSERIAL PRIMARY KEY,
                key_hash          TEXT        UNIQUE NOT NULL,
                key_prefix        TEXT,
                label             TEXT,
                owner_email       TEXT,
                order_code        TEXT        UNIQUE,
                status            TEXT        NOT NULL DEFAULT 'active',
                credits_remaining INTEGER     NOT NULL DEFAULT 0,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_used_at      TIMESTAMPTZ
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.api_usage_logs (
                id           BIGSERIAL PRIMARY KEY,
                api_key_id   BIGINT REFERENCES {SCHEMA}.api_keys(id),
                endpoint     TEXT        NOT NULL,
                credits_used INTEGER     NOT NULL DEFAULT 0,
                status       TEXT        NOT NULL,
                error_code   TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.api_chart_snapshots (
                chart_id   TEXT        PRIMARY KEY,
                api_key_id BIGINT      REFERENCES {SCHEMA}.api_keys(id),
                endpoint   TEXT        NOT NULL,
                yaml_text  TEXT        NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_api_usage_logs_key_created
            ON {SCHEMA}.api_usage_logs (api_key_id, created_at DESC)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_api_usage_logs_endpoint_created
            ON {SCHEMA}.api_usage_logs (endpoint, created_at DESC)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_api_chart_snapshots_key_created
            ON {SCHEMA}.api_chart_snapshots (api_key_id, created_at DESC)
        """)
        cur.execute(f"ALTER TABLE {SCHEMA}.api_keys ADD COLUMN IF NOT EXISTS owner_email TEXT")
        cur.execute(f"ALTER TABLE {SCHEMA}.api_keys ADD COLUMN IF NOT EXISTS order_code TEXT")
        cur.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_order_code_unique
            ON {SCHEMA}.api_keys (order_code)
            WHERE order_code IS NOT NULL
        """)
        if owns_connection:
            cur.close()
            con_cm.__exit__(None, None, None)
    except Exception as exc:
        if owns_connection:
            con_cm.__exit__(type(exc), exc, exc.__traceback__)
        raise


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def create_api_key(
    *,
    label: str = "manual",
    credits: int = 100,
    status: str = "active",
    owner_email: str | None = None,
    order_code: str | None = None,
) -> dict[str, Any]:
    api_key = "np_" + secrets.token_urlsafe(32)
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:10]
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.api_keys
                    (key_hash, key_prefix, label, owner_email, order_code, status, credits_remaining)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, key_prefix, label, owner_email, order_code, status, credits_remaining, created_at
                """,
                (key_hash, key_prefix, label, owner_email, order_code, status, credits),
            )
            row = cur.fetchone()
    result = dict(row)
    result["api_key"] = api_key
    return result


def reissue_api_key(
    *,
    order_code: str,
    credits: int | None = None,
    owner_email: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, key_prefix, label, owner_email, order_code, status, credits_remaining, created_at, last_used_at
                FROM {SCHEMA}.api_keys
                WHERE order_code = %s
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (order_code,),
            )
            old_row = cur.fetchone()
            if not old_row:
                raise LookupError(f"api key not found for order_code={order_code}")

            issue_credits = int(old_row["credits_remaining"] or 0) if credits is None else max(0, int(credits))
            if not issue_credits:
                issue_credits = 0

            cur.execute(
                f"""
                UPDATE {SCHEMA}.api_keys
                SET status = 'inactive',
                    credits_remaining = 0,
                    order_code = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (old_row["id"],),
            )

            api_key = "np_" + secrets.token_urlsafe(32)
            key_hash = hash_api_key(api_key)
            key_prefix = api_key[:10]
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.api_keys
                    (key_hash, key_prefix, label, owner_email, order_code, status, credits_remaining)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, key_prefix, label, owner_email, order_code, status, credits_remaining, created_at
                """,
                (
                    key_hash,
                    key_prefix,
                    (label or old_row["label"] or "manual"),
                    owner_email if owner_email is not None else old_row["owner_email"],
                    order_code,
                    "active",
                    issue_credits,
                ),
            )
            new_row = cur.fetchone()

    result = {
        "old_record": dict(old_row),
        "record": dict(new_row),
        "api_key": api_key,
        "reissued": True,
    }
    return result


def get_api_key_by_order_code(order_code: str) -> dict[str, Any] | None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, key_prefix, label, owner_email, order_code, status, credits_remaining, created_at, last_used_at
                FROM {SCHEMA}.api_keys
                WHERE order_code = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (order_code,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_api_key_for_auth(api_key: str) -> dict[str, Any] | None:
    key_hash = hash_api_key(api_key)
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, key_prefix, label, status, credits_remaining
                FROM {SCHEMA}.api_keys
                WHERE key_hash = %s
                """,
                (key_hash,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def log_api_usage(
    *,
    api_key_id: int | None,
    endpoint: str,
    credits_used: int,
    status: str,
    error_code: str | None = None,
) -> int:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.api_usage_logs
                    (api_key_id, endpoint, credits_used, status, error_code)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (api_key_id, endpoint, credits_used, status, error_code),
            )
            row = cur.fetchone()
    return int(row["id"])


def update_api_usage(
    *,
    usage_id: int,
    credits_used: int,
    status: str,
    error_code: str | None = None,
) -> None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {SCHEMA}.api_usage_logs
                SET credits_used = %s,
                    status = %s,
                    error_code = %s
                WHERE id = %s
                """,
                (credits_used, status, error_code, usage_id),
            )


def count_api_usage_since(*, api_key_id: int, seconds: int, endpoint: str | None = None) -> int:
    with _conn() as con:
        with con.cursor() as cur:
            if endpoint:
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM {SCHEMA}.api_usage_logs
                    WHERE api_key_id = %s
                      AND endpoint = %s
                      AND created_at >= NOW() - (%s * INTERVAL '1 second')
                    """,
                    (api_key_id, endpoint, seconds),
                )
            else:
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM {SCHEMA}.api_usage_logs
                    WHERE api_key_id = %s
                      AND created_at >= NOW() - (%s * INTERVAL '1 second')
                    """,
                    (api_key_id, seconds),
                )
            row = cur.fetchone()
    return int((row or {}).get("count") or 0)


def consume_api_credits(*, api_key_id: int, credits: int) -> bool:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {SCHEMA}.api_keys
                SET credits_remaining = credits_remaining - %s,
                    updated_at = NOW(),
                    last_used_at = NOW()
                WHERE id = %s
                  AND status = 'active'
                  AND credits_remaining >= %s
                RETURNING id
                """,
                (credits, api_key_id, credits),
            )
            return cur.fetchone() is not None


def save_api_chart_snapshot(*, api_key_id: int, endpoint: str, yaml_text: str) -> str:
    chart_id = "ch_" + secrets.token_urlsafe(18)
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.api_chart_snapshots
                    (chart_id, api_key_id, endpoint, yaml_text)
                VALUES (%s, %s, %s, %s)
                RETURNING chart_id
                """,
                (chart_id, api_key_id, endpoint, yaml_text),
            )
            row = cur.fetchone()
    return str(row["chart_id"])


def get_api_chart_snapshot(*, chart_id: str, api_key_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT chart_id, api_key_id, endpoint, yaml_text, created_at
                FROM {SCHEMA}.api_chart_snapshots
                WHERE chart_id = %s
                  AND api_key_id = %s
                """,
                (chart_id, api_key_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def save_chart(
    *,
    token: str,
    order_code: str | None = None,
    buyer_name: str | None = None,
    birth_date: str,
    birth_time: str | None = None,
    birth_place: str | None = None,
    options: dict[str, Any],
    yaml_text: str,
    prompt_text: str,
    share_yaml_text: str | None = None,
    horoscope_svg: str | None = None,
    shichusuimei_svg: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    with _conn() as con:
        with con.cursor() as cur:
            _insert_chart(
                cur,
                token=token,
                order_code=order_code,
                buyer_name=buyer_name,
                birth_date=birth_date,
                birth_time=birth_time,
                birth_place=birth_place,
                options=options,
                yaml_text=yaml_text,
                prompt_text=prompt_text,
                share_yaml_text=share_yaml_text,
                horoscope_svg=horoscope_svg,
                shichusuimei_svg=shichusuimei_svg,
                expires_at=expires_at,
                on_conflict_do_nothing=True,
            )


def get_chart(token: str, *, include_svgs: bool = True) -> dict[str, Any] | None:
    columns = "*"
    if not include_svgs:
        columns = """
            token, order_code, buyer_name, birth_date, birth_time, birth_place,
            options, yaml_text, prompt_text, share_yaml_text, expires_at, created_at
        """
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"SELECT {columns} FROM {SCHEMA}.charts WHERE token = %s",
                (token,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def expired_charts_summary(*, grace_days: int = 0) -> dict[str, Any]:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  COUNT(*) AS expired_count,
                  MIN(expires_at) AS oldest_expires_at,
                  MAX(expires_at) AS newest_expires_at
                FROM {SCHEMA}.charts
                WHERE expires_at < NOW() - (%s * INTERVAL '1 day')
                """,
                (grace_days,),
            )
            row = cur.fetchone() or {}
            cur.execute(
                f"""
                SELECT token, order_code, buyer_name, created_at, expires_at
                FROM {SCHEMA}.charts
                WHERE expires_at < NOW() - (%s * INTERVAL '1 day')
                ORDER BY expires_at ASC
                LIMIT 10
                """,
                (grace_days,),
            )
            samples = cur.fetchall()
    return {
        "expired_count": int(row.get("expired_count") or 0),
        "oldest_expires_at": row.get("oldest_expires_at"),
        "newest_expires_at": row.get("newest_expires_at"),
        "samples": [dict(sample) for sample in samples],
    }


def delete_expired_charts(*, grace_days: int = 0) -> dict[str, Any]:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                DELETE FROM {SCHEMA}.charts
                WHERE expires_at < NOW() - (%s * INTERVAL '1 day')
                RETURNING token, order_code, buyer_name, created_at, expires_at
                """,
                (grace_days,),
            )
            deleted = cur.fetchall()
    return {
        "deleted_count": len(deleted),
        "deleted_samples": [dict(row) for row in deleted[:10]],
    }


def get_redemption_by_order_code(order_code: str) -> dict[str, Any] | None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT order_code, email, buyer_name, token, used_at, created_at
                FROM {SCHEMA}.redemptions
                WHERE order_code = %s
                """,
                (order_code,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def redeem_addon_order(*, order_code: str, addon_type: str) -> tuple[str, dict[str, Any] | None]:
    """
    addon生成用に STORES注文番号 + addon種別 を一回だけ消し込む。

    通常商品の redemptions/charts には書き込まず、貼り付けYAMLも保存しない。
    """
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT *
                FROM {SCHEMA}.stores_orders
                WHERE stores_order_no = %s
                FOR UPDATE
                """,
                (order_code,),
            )
            row = cur.fetchone()
            if not row:
                return "not_found", None

            order = dict(row)
            payment_status = str(order.get("payment_status") or "").lower()
            if payment_status == "cancelled":
                return "cancelled", order

            purchased_type = order.get("product_type")
            if purchased_type and str(purchased_type) != addon_type:
                return "product_mismatch", order

            if payment_status in {"reusable", "test", "permanent"}:
                return "ok", order

            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.addon_redemptions
                    (order_code, addon_type, used_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (order_code, addon_type) DO NOTHING
                RETURNING order_code, addon_type, used_at
                """,
                (order_code, addon_type),
            )
            if cur.fetchone() is None:
                return "already_used", order

            return "ok", order


def redeem_addon_order_and_save_transit_link(
    *,
    order_code: str,
    addon_type: str,
    token: str,
    yaml_text: str,
    expires_at: datetime,
    chart_payload: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """
    31日トランジットaddon用に、注文消込と期限付きYAML保存を同一トランザクションで行う。
    """
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT *
                FROM {SCHEMA}.stores_orders
                WHERE stores_order_no = %s
                FOR UPDATE
                """,
                (order_code,),
            )
            row = cur.fetchone()
            if not row:
                return "not_found", None

            order = dict(row)
            payment_status = str(order.get("payment_status") or "").lower()
            if payment_status == "cancelled":
                return "cancelled", order

            purchased_type = order.get("product_type")
            if purchased_type and str(purchased_type) != addon_type:
                return "product_mismatch", order

            if payment_status not in {"reusable", "test", "permanent"}:
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.addon_redemptions
                        (order_code, addon_type, used_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (order_code, addon_type) DO NOTHING
                    RETURNING order_code, addon_type, used_at
                    """,
                    (order_code, addon_type),
                )
                if cur.fetchone() is None:
                    return "already_used", order

            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.transit_addon_links
                    (token, yaml_text, expires_at)
                VALUES (%s, %s, %s)
                """,
                (token, yaml_text, expires_at),
            )
            if chart_payload:
                _insert_chart(
                    cur,
                    token=token,
                    order_code=order_code,
                    buyer_name=chart_payload.get("buyer_name"),
                    birth_date=str(chart_payload["birth_date"]),
                    birth_time=chart_payload.get("birth_time"),
                    birth_place=chart_payload.get("birth_place"),
                    options=dict(chart_payload["options"]),
                    yaml_text=str(chart_payload["yaml_text"]),
                    prompt_text=str(chart_payload["prompt_text"]),
                    share_yaml_text=chart_payload.get("share_yaml_text"),
                    horoscope_svg=chart_payload.get("horoscope_svg"),
                    shichusuimei_svg=chart_payload.get("shichusuimei_svg"),
                    expires_at=expires_at,
                    on_conflict_do_nothing=False,
                )
            return "ok", order


def save_transit_addon_link(*, token: str, yaml_text: str, expires_at: datetime) -> None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.transit_addon_links
                    (token, yaml_text, expires_at)
                VALUES (%s, %s, %s)
                """,
                (token, yaml_text, expires_at),
            )


def get_transit_addon_link(token: str) -> dict[str, Any] | None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT token, yaml_text, expires_at, created_at
                FROM {SCHEMA}.transit_addon_links
                WHERE token = %s
                """,
                (token,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_redemption_reset_by_order_code(order_code: str) -> dict[str, Any] | None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT stores_order_no AS order_code, payment_status, updated_at
                FROM {SCHEMA}.stores_orders
                WHERE stores_order_no = %s
                  AND payment_status = 'reset_once'
                """,
                (order_code,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def list_charts_by_order_code(order_code: str) -> list[dict[str, Any]]:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT token, order_code, buyer_name, birth_date, birth_time, birth_place, options, created_at
                FROM {SCHEMA}.charts
                WHERE order_code = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (order_code,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def reset_redemption_by_order_code(order_code: str) -> dict[str, Any]:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {SCHEMA}.stores_orders
                SET payment_status = 'reset_once',
                    updated_at = NOW()
                WHERE stores_order_no = %s
                  AND COALESCE(payment_status, '') <> 'cancelled'
                RETURNING stores_order_no AS order_code, payment_status, updated_at
                """,
                (order_code,),
            )
            reset_row = cur.fetchone()
    try:
        charts = list_charts_by_order_code(order_code)
    except Exception as exc:
        charts = []
        charts_error = str(exc)
    else:
        charts_error = None
    return {
        "reset": reset_row is not None,
        "reset_override": dict(reset_row) if reset_row else None,
        "deleted_redemption": None,
        "charts": charts,
        "charts_error": charts_error,
    }


def redeem_and_save(
    *,
    order_code: str,
    email: str | None,
    buyer_name: str | None,
    token: str,
    birth_date: str,
    birth_time: str | None,
    birth_place: str | None,
    options: dict[str, Any],
    yaml_text: str,
    prompt_text: str,
    share_yaml_text: str | None = None,
    horoscope_svg: str | None = None,
    shichusuimei_svg: str | None = None,
    expires_at: datetime | None = None,
) -> bool:
    """
    redemptions と charts を同一トランザクションで挿入する。
    order_code が初回なら True、すでに使用済みなら False を返す。
    """
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.redemptions
                    (order_code, email, buyer_name, token, used_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (order_code) DO NOTHING
                RETURNING order_code
                """,
                (order_code, email, buyer_name, token),
            )
            if cur.fetchone() is None:
                cur.execute(
                    f"""
                    UPDATE {SCHEMA}.stores_orders
                    SET payment_status = 'paid',
                        updated_at = NOW()
                    WHERE stores_order_no = %s
                      AND payment_status = 'reset_once'
                    RETURNING stores_order_no
                    """,
                    (order_code,),
                )
                if cur.fetchone() is None:
                    return False

            _insert_chart(
                cur,
                token=token,
                order_code=order_code,
                buyer_name=buyer_name,
                birth_date=birth_date,
                birth_time=birth_time,
                birth_place=birth_place,
                options=options,
                yaml_text=yaml_text,
                prompt_text=prompt_text,
                share_yaml_text=share_yaml_text,
                horoscope_svg=horoscope_svg,
                shichusuimei_svg=shichusuimei_svg,
                expires_at=expires_at,
            )
    return True
