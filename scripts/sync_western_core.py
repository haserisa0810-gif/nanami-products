"""nanami-astro の西洋占星術コアを一方向同期する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


SYNC_FILES = (
    "services/western_core.py",
    "tests/test_western_core_golden.py",
    "tests/fixtures/western_core_golden.json",
)
MANIFEST_PATH = "docs/western_core_sync_manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files_exist(source: Path) -> bool:
    missing = [relative for relative in SYNC_FILES if not (source / relative).is_file()]
    if not source.is_dir() or missing:
        print(f"source not found or incomplete: {source}", file=sys.stderr)
        for relative in missing:
            print(f"missing source file: {relative}", file=sys.stderr)
        return False
    return True


def _load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sync(repo_root: Path, source: Path) -> int:
    if not _source_files_exist(source):
        return 2

    file_records: dict[str, dict[str, str]] = {}
    for relative in SYNC_FILES:
        source_path = source / relative
        local_path = repo_root / relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, local_path)
        file_records[relative] = {"sha256": _sha256(local_path)}
        print(f"synced: {relative}")

    manifest = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source.resolve()),
        "files": file_records,
    }
    manifest_path = repo_root / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {MANIFEST_PATH}")
    return 0


def check(repo_root: Path, source: Path) -> int:
    if not _source_files_exist(source):
        return 2

    manifest = _load_manifest(repo_root / MANIFEST_PATH)
    records = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    mismatches: list[str] = []

    for relative in SYNC_FILES:
        local_path = repo_root / relative
        source_path = source / relative
        record = records.get(relative) if isinstance(records, dict) else None
        recorded_hash = record.get("sha256") if isinstance(record, dict) else None

        if not local_path.is_file():
            mismatches.append(relative)
            continue
        local_hash = _sha256(local_path)
        source_hash = _sha256(source_path)
        if local_hash != recorded_hash or local_hash != source_hash:
            mismatches.append(relative)

    if mismatches:
        for relative in sorted(set(mismatches)):
            print(f"mismatch: {relative}")
        return 1

    print("western core sync check: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="差分検査のみ実行する")
    parser.add_argument("--source", type=Path, help="nanami-astro のルートパス")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source = (args.source or (repo_root.parent / "nanami-astro")).expanduser().resolve()
    return check(repo_root, source) if args.check else sync(repo_root, source)


if __name__ == "__main__":
    raise SystemExit(main())
