"""Plan/apply/restore issued URL expiry extensions. Default: read-only aggregate.

No application import, init_db, dotenv loading, customer payload, or row logging.
See docs/URL_EXPIRY_365_MIGRATION.md before using with an authorized database.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.chart_policy import CHART_EXPIRES_DAYS

TABLES = ("charts", "transit_addon_links")
SCHEMA = "nanami_products"
LOCK_ID = 36520260913
APPLY_CONFIRMATION = "EXTEND_ISSUED_URLS_TO_365_DAYS"
RESTORE_CONFIRMATION = "RESTORE_ISSUED_URL_EXPIRIES"


class MigrationError(RuntimeError):
    """Only fixed, non-sensitive messages may be exposed to the operator."""


def _date(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise MigrationError("Invalid or timezone-less timestamp; no changes applied.")
    return value.astimezone(timezone.utc)


def plan_changes(rows, *, now):
    """Align both representations of one URL without shortening any deadline."""
    grouped = defaultdict(list)
    counts = {
        "rows": len(rows), "tokens": 0, "changed_rows": 0,
        "charts_changed": 0, "transit_addon_links_changed": 0,
        "no_expiry_tokens": 0, "no_expiry_with_deadline_rows": 0,
        "missing_created_at_rows": 0, "mismatched_deadline_tokens": 0,
        "revived_tokens": 0, "null_expiry_rows_filled": 0,
        "still_expired_tokens": 0, "longer_deadline_tokens_preserved": 0,
        "mismatched_created_at_tokens": 0,
    }
    seen = set()
    for row in rows:
        key = (row["table"], row["token"])
        if row["table"] not in TABLES or not row["token"] or key in seen:
            raise MigrationError("Invalid or duplicate row identity; no changes applied.")
        seen.add(key)
        grouped[row["token"]].append(row)
        counts["missing_created_at_rows"] += row["created_at"] is None
    counts["tokens"] = len(grouped)
    changes = []
    for token, group in sorted(grouped.items()):
        if any(row["no_expiry"] for row in group):
            counts["no_expiry_tokens"] += 1
            counts["no_expiry_with_deadline_rows"] += sum(row["expires_at"] is not None for row in group)
            continue
        created = [_date(row["created_at"]) for row in group]
        if None in created:
            continue
        old = [_date(row["expires_at"]) for row in group]
        counts["mismatched_deadline_tokens"] += len(set(old)) > 1
        counts["mismatched_created_at_tokens"] += len(set(created)) > 1
        standard = min(created) + timedelta(days=CHART_EXPIRES_DAYS)
        target = max([standard] + [x for x in old if x is not None])
        counts["still_expired_tokens"] += target <= now
        counts["longer_deadline_tokens_preserved"] += target > standard
        # Audit the pre-release 90-day fallback; it does not control new policy.
        old_effective = [expiry or issued + timedelta(days=90) for expiry, issued in zip(old, created)]
        counts["revived_tokens"] += min(old_effective) <= now < target
        for row, expiry, issued in zip(group, old, created):
            if expiry == target:
                continue
            changes.append({"table": row["table"], "token": token,
                            "created_at": issued, "before": expiry, "after": target})
            counts["null_expiry_rows_filled"] += expiry is None
            counts[f"{row['table']}_changed"] += 1
    counts["changed_rows"] = len(changes)
    return changes, counts


def _read_rows(cur, *, lock=False):
    rows = []
    for table in TABLES:
        policy = "COALESCE(options->>'expires_policy', '') = 'no_expiry'" if table == "charts" else "FALSE"
        cur.execute(
            f"SELECT token, created_at, expires_at, {policy} AS no_expiry "
            f"FROM {SCHEMA}.{table} ORDER BY token" + (" FOR UPDATE" if lock else "")
        )
        rows.extend(dict(row, table=table) for row in cur.fetchall())
    return rows


def _lock(cur):
    cur.execute("SELECT pg_try_advisory_xact_lock(%s) AS acquired", (LOCK_ID,))
    if not cur.fetchone()["acquired"]:
        raise MigrationError("Another expiry migration is running; no changes applied.")


def _identity(con):
    params = con.get_dsn_parameters()
    identity = [params.get(key, "") for key in ("host", "port", "dbname")]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def _safe_ledger_path(value, *, create):
    path = Path(value).expanduser().resolve()
    if not path.is_absolute() or any(part.lower().startswith("onedrive") for part in path.parts):
        raise MigrationError("Recovery ledger must be outside OneDrive.")
    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        synced_root = os.environ.get(variable)
        if synced_root and path.is_relative_to(Path(synced_root).resolve()):
            raise MigrationError("Recovery ledger must be outside OneDrive.")
    if path.is_relative_to(Path(__file__).resolve().parents[1]):
        raise MigrationError("Recovery ledger must be outside this Git repository.")
    if not path.parent.is_dir() or (create and path.exists()):
        raise MigrationError("Recovery ledger needs an existing directory and an unused filename.")
    return path


def _protect_file(path):
    if os.name != "nt":
        os.chmod(path, 0o600)
        return
    # Restrict the EMPTY file before writing tokens. No shell-built path/code.
    env = dict(os.environ, NANAMI_EXPIRY_LEDGER_PATH=str(path))
    script = """
$ErrorActionPreference = 'Stop'
$path = [Environment]::GetEnvironmentVariable('NANAMI_EXPIRY_LEDGER_PATH')
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = New-Object Security.AccessControl.FileSecurity
$acl.SetOwner($sid)
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
$acl.AddAccessRule($rule)
[IO.File]::SetAccessControl($path, $acl)
"""
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                   env=env, check=True, timeout=15,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _canonical(payload):
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _expected_state(rows, changes, *, projected=False):
    """Guard both representations, including unchanged partners and absence."""
    by_key = {(change["table"], change["token"]): change for change in changes}
    tokens = {change["token"] for change in changes}
    state = []
    for row in rows:
        if row["token"] not in tokens:
            continue
        expiry = _date(row["expires_at"])
        change = by_key.get((row["table"], row["token"]))
        if projected and change:
            expiry = change["after"]
        issued = _date(row["created_at"])
        state.append({"table": row["table"], "token": row["token"],
                      "created_at": issued.isoformat() if issued else None,
                      "expires_at": expiry.isoformat() if expiry else None,
                      "no_expiry": bool(row["no_expiry"])})
    return sorted(state, key=lambda row: (row["table"], row["token"]))


def _write_ledger(path, changes, identity, *, rows):
    payload = {"version": 1, "days": CHART_EXPIRES_DAYS, "database": identity, "changes": [
        {key: value.isoformat() if isinstance(value, datetime) else value for key, value in change.items()}
        for change in changes
    ], "expected_after": _expected_state(rows, changes, projected=True)}
    document = {"payload": payload, "sha256": hashlib.sha256(_canonical(payload)).hexdigest()}
    # O_EXCL prevents accidental replacement. Flush and fsync before any UPDATE.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    original = os.fstat(fd)
    os.close(fd)
    fd = None
    try:
        # Close the empty CRT writer before setting its Windows DACL.
        _protect_file(path)
        fd = os.open(path, os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0))
        current = os.fstat(fd)
        if (current.st_dev, current.st_ino, current.st_size) != (original.st_dev, original.st_ino, 0):
            raise MigrationError("Recovery file changed before writing; no changes applied.")
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(_canonical(document))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if fd is not None:
            os.close(fd)


def _load_ledger(path, identity):
    document = json.loads(path.read_text(encoding="utf-8"))
    payload = document["payload"]
    if (document["sha256"] != hashlib.sha256(_canonical(payload)).hexdigest()
            or payload["version"] != 1 or payload["days"] != CHART_EXPIRES_DAYS
            or payload["database"] != identity):
        raise MigrationError("Recovery ledger identity or checksum does not match; no changes applied.")
    changes = payload["changes"]
    seen = set()
    for change in changes:
        key = (change["table"], change["token"])
        if change["table"] not in TABLES or not change["token"] or key in seen:
            raise MigrationError("Invalid recovery row identity; no changes applied.")
        seen.add(key)
        for field in ("created_at", "before", "after"):
            change[field] = _date(change[field])
        if change["created_at"] is None or change["after"] is None:
            raise MigrationError("Incomplete recovery timestamps; no changes applied.")
    return changes, payload["expected_after"]


def _update(cur, changes, *, restore=False):
    for change in changes:
        old, new = (change["after"], change["before"]) if restore else (change["before"], change["after"])
        cur.execute(
            f"UPDATE {SCHEMA}.{change['table']} SET expires_at = %s "
            "WHERE token = %s AND created_at = %s AND expires_at IS NOT DISTINCT FROM %s",
            (new, change["token"], change["created_at"], old),
        )
        if cur.rowcount != 1:
            raise MigrationError("A row changed or disappeared; entire transaction rolled back.")


def run(con, *, apply=False, backup=None, restore=None):
    """Connection supplied explicitly for tests; never uses pg_store or init_db."""
    mutating = apply or restore is not None
    if apply and restore is not None:
        raise MigrationError("Apply and restore cannot be combined.")
    if apply and backup is None:
        raise MigrationError("Apply requires a recovery ledger path.")
    con.set_session(readonly=not mutating, isolation_level="REPEATABLE READ", autocommit=False)
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            if mutating:
                _lock(cur)
            cur.execute("SELECT CURRENT_TIMESTAMP AS now")
            now = cur.fetchone()["now"]
            rows = _read_rows(cur, lock=mutating)
            if restore is not None:
                changes, expected_after = _load_ledger(_safe_ledger_path(restore, create=False), _identity(con))
                if _expected_state(rows, changes) != expected_after:
                    raise MigrationError("A recovery token or its paired row changed; no changes applied.")
                lookup = {(row["table"], row["token"]): row for row in rows}
                no_expiry = {row["token"] for row in rows if row["no_expiry"]}
                for change in changes:
                    row = lookup.get((change["table"], change["token"]))
                    if (not row or row["token"] in no_expiry
                            or _date(row["created_at"]) != change["created_at"]
                            or _date(row["expires_at"]) != change["after"]):
                        raise MigrationError("A recovery row changed or disappeared; no changes applied.")
                _update(cur, changes, restore=True)
                counts = {"restored_rows": len(changes)}
            else:
                changes, counts = plan_changes(rows, now=now)
                if apply:
                    if counts["missing_created_at_rows"]:
                        raise MigrationError("Missing creation timestamps; no changes applied.")
                    ledger = _safe_ledger_path(backup, create=True)
                    if changes:
                        _write_ledger(ledger, changes, _identity(con), rows=rows)
                        _update(cur, changes)
                        remaining, _ = plan_changes(_read_rows(cur, lock=True), now=now)
                        if remaining:
                            raise MigrationError("Expiry verification found remaining changes; transaction rolled back.")
                    counts["remaining_changed_rows"] = 0
        if mutating:
            con.commit()
        else:
            con.rollback()
        return counts
    except BaseException:
        con.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--restore", metavar="LEDGER")
    parser.add_argument("--backup", metavar="NEW_LEDGER")
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    expected = APPLY_CONFIRMATION if args.apply else RESTORE_CONFIRMATION if args.restore else None
    if (expected and args.confirm != expected) or (args.apply and not args.backup):
        parser.error("Mutation requires its confirmation string and apply requires --backup.")
    if not expected and (args.backup or args.confirm):
        parser.error("Read-only mode does not accept backup or confirmation arguments.")
    con = None
    try:
        if not os.environ.get("DATABASE_URL"):
            raise MigrationError("DATABASE_URL must be supplied by the authorized operator; no env files are loaded.")
        if args.apply:
            _safe_ledger_path(args.backup, create=True)
        con = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10,
                               options="-c statement_timeout=60000 -c lock_timeout=5000")
        result = run(con, apply=args.apply, backup=args.backup, restore=args.restore)
        print(json.dumps({"mode": "apply" if args.apply else "restore" if args.restore else "read_only", **result}, sort_keys=True))
        return 0
    except MigrationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Driver/IO errors can contain connection strings, tokens, and paths.
        print("Expiry migration stopped. No success confirmed; inspect aggregate checks and recovery ledger before retrying.", file=sys.stderr)
        return 1
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
