"""Synthetic policy and SQL protocol tests; no actual PostgreSQL connection."""
import copy
from datetime import datetime, timedelta, timezone
import json
import subprocess
from unittest.mock import patch

import pytest

from scripts import migrate_chart_expiry_365 as migration

ISSUED = datetime(2026, 1, 1, tzinfo=timezone.utc)
NOW = ISSUED + timedelta(days=180)


def row(token="synthetic-token", table="charts", days=90, issued=ISSUED, no_expiry=False):
    return dict(table=table, token=token, created_at=issued, no_expiry=no_expiry,
                expires_at=ISSUED + timedelta(days=days) if days is not None else None)


class Connection:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)
        self.original = copy.deepcopy(rows)
        self.sql = []
        self.commits = self.rollbacks = self.updates = 0
        self.acquired = True
        self.fail_update = None

    def set_session(self, **kwargs):
        self.session = kwargs
        self.original = copy.deepcopy(self.rows)

    def get_dsn_parameters(self):
        return dict(host="synthetic.invalid", port="5432", dbname="test")

    def cursor(self, **kwargs):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
        self.rows = copy.deepcopy(self.original)


class Cursor:
    def __init__(self, con):
        self.con = con

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        self.con.sql.append(sql)
        if "pg_try_advisory_xact_lock" in sql:
            self.result = [{"acquired": self.con.acquired}]
        elif "CURRENT_TIMESTAMP" in sql:
            self.result = [{"now": NOW}]
        elif sql.startswith("SELECT token"):
            table = sql.split("FROM nanami_products.")[1].split()[0]
            self.result = [dict(r) for r in self.con.rows if r["table"] == table]
        elif sql.startswith("UPDATE"):
            assert not self.con.session["readonly"]
            assert "IS NOT DISTINCT FROM" in sql and "created_at = %s" in sql
            self.con.updates += 1
            if self.con.updates == self.con.fail_update:
                raise RuntimeError("synthetic failure")
            table = sql.split()[1].split(".")[1]
            new, token, created, old = params
            targets = [r for r in self.con.rows if (r["table"], r["token"], r["created_at"], r["expires_at"]) == (table, token, created, old)]
            self.rowcount = len(targets)
            for target in targets:
                target["expires_at"] = new
        else:
            raise AssertionError("Unexpected SQL")

    def fetchone(self):
        return self.result[0]

    def fetchall(self):
        return self.result


def test_plan_includes_expired_null_standalone_and_preserves_longer_deadlines():
    rows = [row(), row("null", days=None), row("standalone", table="transit_addon_links"),
            row("long", days=500), row("older", issued=ISSUED-timedelta(days=400), days=-310)]
    changes, counts = migration.plan_changes(rows, now=NOW)
    by_token = {change["token"]: change for change in changes}
    assert by_token["synthetic-token"]["after"] == ISSUED + timedelta(days=365)
    assert by_token["null"]["before"] is None
    assert "long" not in by_token
    assert by_token["older"]["after"] == ISSUED - timedelta(days=35)
    assert counts["revived_tokens"] == 3
    assert counts["changed_rows"] == 4


def test_duplicate_token_uses_original_issuance_and_largest_existing_deadline():
    pair = [row(days=90), row(table="transit_addon_links", days=100, issued=ISSUED+timedelta(days=10))]
    changes, counts = migration.plan_changes(pair, now=NOW)
    assert {change["after"] for change in changes} == {ISSUED + timedelta(days=365)}
    assert counts["mismatched_deadline_tokens"] == 1
    pair[1]["expires_at"] = ISSUED + timedelta(days=500)
    changes, _ = migration.plan_changes(pair, now=NOW)
    assert len(changes) == 1 and changes[0]["after"] == pair[1]["expires_at"]


def test_no_expiry_token_excludes_both_tables_and_reports_anomaly():
    changes, counts = migration.plan_changes([row(days=None, no_expiry=True), row(table="transit_addon_links")], now=NOW)
    assert changes == []
    assert counts["no_expiry_tokens"] == counts["no_expiry_with_deadline_rows"] == 1


def test_default_dry_run_is_read_only_select_only_without_ledger(tmp_path):
    con = Connection([row(), row(table="transit_addon_links")])
    with patch.object(migration, "_write_ledger") as write:
        result = migration.run(con)
    assert con.session == dict(readonly=True, isolation_level="REPEATABLE READ", autocommit=False)
    assert all(sql.startswith("SELECT") and "FOR UPDATE" not in sql for sql in con.sql)
    assert con.commits == 0 and con.rollbacks == 1
    assert result["changed_rows"] == 2 and con.rows == con.original
    write.assert_not_called()


def test_apply_writes_before_image_first_is_atomic_idempotent_and_restorable(tmp_path):
    con = Connection([row(days=None), row(table="transit_addon_links")])
    original = copy.deepcopy(con.rows)
    ledger = tmp_path / "recovery.json"
    real_write = migration._write_ledger

    def write_before_updates(*args, **kwargs):
        assert con.updates == 0
        real_write(*args, **kwargs)

    with patch.object(migration, "_write_ledger", side_effect=write_before_updates):
        result = migration.run(con, apply=True, backup=ledger)
    assert result["changed_rows"] == 2 and con.commits == 1
    assert all("FOR UPDATE" in sql for sql in con.sql if sql.startswith("SELECT token"))
    assert ledger.exists()
    result = migration.run(con, apply=True, backup=tmp_path / "second.json")
    assert result["changed_rows"] == 0 and not (tmp_path / "second.json").exists()
    assert migration.run(con, restore=ledger)["restored_rows"] == 2
    assert con.rows == original


@pytest.mark.parametrize("failure", ["second_update", "ledger", "lock", "missing_created"])
def test_failure_rolls_back_both_tables(tmp_path, failure):
    con = Connection([row(), row(table="transit_addon_links")])
    if failure == "second_update":
        con.fail_update = 2
    if failure == "lock":
        con.acquired = False
    if failure == "missing_created":
        con.rows[0]["created_at"] = None
    original = copy.deepcopy(con.rows)
    with patch.object(migration, "_write_ledger", side_effect=OSError("synthetic failure") if failure == "ledger" else None, wraps=migration._write_ledger):
        with pytest.raises((migration.MigrationError, RuntimeError, OSError)):
            migration.run(con, apply=True, backup=tmp_path / "before.json")
    assert con.commits == 0 and con.rollbacks == 1 and con.rows == original


@pytest.mark.parametrize("changed", ["expires_at", "created_at", "no_expiry", "missing", "database", "checksum"])
def test_restore_refuses_subsequent_changes_without_partial_update(tmp_path, changed):
    con = Connection([row(), row(table="transit_addon_links")])
    ledger = tmp_path / "before.json"
    migration.run(con, apply=True, backup=ledger)
    if changed in {"expires_at", "created_at"}:
        con.rows[1][changed] += timedelta(seconds=1)
    elif changed == "no_expiry":
        con.rows[0]["no_expiry"] = True
    elif changed == "missing":
        con.rows.pop()
    elif changed == "database":
        con.get_dsn_parameters = lambda: {"host": "other.invalid"}
    else:
        document = json.loads(ledger.read_text())
        document["sha256"] = "tampered"
        ledger.write_text(json.dumps(document))
    original = copy.deepcopy(con.rows)
    with pytest.raises(migration.MigrationError):
        migration.run(con, restore=ledger)
    assert con.rows == original and con.commits == 1 and con.rollbacks == 1


def test_ledger_path_refuses_onedrive_repository_and_existing_file(tmp_path):
    with pytest.raises(migration.MigrationError):
        migration._safe_ledger_path(tmp_path / "OneDrive" / "before.json", create=True)
    with pytest.raises(migration.MigrationError):
        migration._safe_ledger_path(migration.Path(__file__).resolve().parent / "before.json", create=True)
    existing = tmp_path / "exists.json"
    existing.write_text("keep")
    with pytest.raises(migration.MigrationError):
        migration._safe_ledger_path(existing, create=True)
    assert existing.read_text() == "keep"


def test_cli_requires_confirmation_and_redacts_connection_failures(capsys, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "synthetic-secret")
    with patch.object(migration.psycopg2, "connect") as connect:
        with pytest.raises(SystemExit):
            migration.main(["--apply"])
        connect.assert_not_called()
    with patch.object(migration.psycopg2, "connect", side_effect=RuntimeError("synthetic-secret")):
        assert migration.main([]) == 1
    assert "synthetic-secret" not in capsys.readouterr().err


def test_acl_timeout_rolls_back_before_sensitive_ledger_or_updates(tmp_path):
    con = Connection([row()])
    ledger = tmp_path / "acl-timeout.json"
    with patch.object(migration, "_protect_file", side_effect=subprocess.TimeoutExpired("acl", 15)):
        with pytest.raises(subprocess.TimeoutExpired):
            migration.run(con, apply=True, backup=ledger)
    assert ledger.read_bytes() == b""
    assert con.updates == con.commits == 0 and con.rollbacks == 1


def test_windows_acl_subprocess_has_bounded_wait(tmp_path):
    with patch.object(migration.os, "name", "nt"), patch.object(migration.subprocess, "run") as run:
        migration._protect_file(tmp_path / "empty-ledger.json")
    assert run.call_args.kwargs["timeout"] == 15


@pytest.mark.parametrize("change", ["unchanged_partner", "added_partner", "removed_partner"])
def test_restore_guards_whole_token_including_unchanged_or_absent_partner(tmp_path, change):
    rows = [row(days=500), row(table="transit_addon_links")]
    if change == "added_partner":
        rows = [row()]
    con = Connection(rows)
    ledger = tmp_path / "whole-token.json"
    migration.run(con, apply=True, backup=ledger)
    if change == "unchanged_partner":
        con.rows[0]["expires_at"] += timedelta(days=100)
    elif change == "added_partner":
        con.rows.append(row(table="transit_addon_links", days=365))
    else:
        con.rows.pop(0)
    before = copy.deepcopy(con.rows)
    with pytest.raises(migration.MigrationError):
        migration.run(con, restore=ledger)
    assert con.rows == before and con.commits == 1 and con.rollbacks == 1
