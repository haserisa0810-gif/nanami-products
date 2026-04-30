from __future__ import annotations

import os
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
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
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
