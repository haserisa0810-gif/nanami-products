from __future__ import annotations

import os
import hashlib
import secrets
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
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            # 旧DDLで order_code が NOT NULL になっている環境のための互換マイグレーション
            cur.execute(f"ALTER TABLE {SCHEMA}.charts ALTER COLUMN order_code DROP NOT NULL")
            ensure_api_tables(cur)


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
            CREATE INDEX IF NOT EXISTS idx_api_usage_logs_key_created
            ON {SCHEMA}.api_usage_logs (api_key_id, created_at DESC)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_api_usage_logs_endpoint_created
            ON {SCHEMA}.api_usage_logs (endpoint, created_at DESC)
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
) -> None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.charts
                    (token, order_code, buyer_name, birth_date, birth_time, birth_place,
                     options, yaml_text, prompt_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token) DO NOTHING
                """,
                (token, order_code, buyer_name, birth_date, birth_time, birth_place,
                 Json(options), yaml_text, prompt_text),
            )


def get_chart(token: str) -> dict[str, Any] | None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.charts WHERE token = %s",
                (token,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


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
                return False

            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.charts
                    (token, order_code, buyer_name, birth_date, birth_time, birth_place,
                     options, yaml_text, prompt_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (token, order_code, buyer_name, birth_date, birth_time, birth_place,
                 Json(options), yaml_text, prompt_text),
            )
    return True
