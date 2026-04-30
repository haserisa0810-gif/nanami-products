from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/tmp/nanami_products.db")

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            create table if not exists charts (
                token text primary key,
                created_at text not null,
                title text,
                yaml_text text not null,
                prompt_text text not null,
                options_json text not null
            )
            """
        )

def save_chart(token: str, title: str, yaml_text: str, prompt_text: str, options_json: str) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "insert or replace into charts(token, created_at, title, yaml_text, prompt_text, options_json) values(?,?,?,?,?,?)",
            (token, datetime.now(timezone.utc).isoformat(), title, yaml_text, prompt_text, options_json),
        )

def get_chart(token: str) -> dict | None:
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("select * from charts where token=?", (token,)).fetchone()
    return dict(row) if row else None
