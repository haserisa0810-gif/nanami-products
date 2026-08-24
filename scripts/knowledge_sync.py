"""Build and optionally sync the Nanami cross-repository knowledge catalog.

Git-tracked Markdown/YAML files remain the source of truth.  The database is a
derived search index.  ``sync-db`` is a dry run unless ``--apply`` is supplied.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


VALID_STATUSES = {"draft", "active", "superseded", "archived"}
SUPPORTED_SUFFIXES = {".md", ".markdown", ".yaml", ".yml", ".txt"}
FRONT_MATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class KnowledgeDocument:
    source_key: str
    collection: str
    source_path: str
    absolute_path: Path
    title: str
    kind: str
    status: str
    owner: str
    tags: list[str]
    updated_at: str
    metadata: dict[str, Any]
    content: str
    content_sha256: str
    git_commit: str | None

    def catalog_record(self) -> dict[str, Any]:
        record = asdict(self)
        record.pop("absolute_path", None)
        record.pop("content", None)
        # The Git catalog is an index, not a second copy of conversation archives.
        # Keep only routing/provenance fields; full metadata and content belong to
        # the source file and the optional database index.
        allowed_metadata = {
            "category",
            "topic",
            "superseded_by",
            "source_files",
            "related_files",
            "decision_date",
            "event_date",
        }
        record["metadata"] = {
            key: value for key, value in self.metadata.items() if key in allowed_metadata
        }
        return record


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return value


def parse_markdown(text: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    parsed = yaml.safe_load(match.group(1)) or {}
    if not isinstance(parsed, dict):
        raise ValueError("Markdown front matter must be a mapping")
    return dict(parsed), text[match.end():]


def infer_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            return match.group(2).strip()
    return fallback


def _matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def _resolve_root(
    collection: dict[str, Any],
    *,
    product_root: Path,
    content_root: Path | None,
) -> Path:
    if collection.get("id", "").startswith("operations") and content_root is not None:
        return content_root.resolve()
    env_name = str(collection.get("root_env") or "")
    if env_name and os.getenv(env_name):
        return Path(os.environ[env_name]).expanduser().resolve()
    if collection.get("root"):
        return (product_root / str(collection["root"])).resolve()
    return (product_root / str(collection.get("fallback_root") or ".")).resolve()


def _git_commit(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status.stdout.strip():
            return None
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _load_document(
    *,
    path: Path,
    root: Path,
    collection: dict[str, Any],
    git_commit: str | None,
) -> KnowledgeDocument:
    text = path.read_text(encoding="utf-8-sig")
    relative = path.relative_to(root).as_posix()
    defaults = dict(collection.get("defaults") or {})
    if path.suffix.lower() in {".yaml", ".yml"}:
        parsed = yaml.safe_load(text) or {}
        metadata = dict(parsed) if isinstance(parsed, dict) else {}
        body = text
    else:
        metadata, body = parse_markdown(text)
    metadata = _json_safe(metadata)

    status = str(metadata.get("status") or defaults.get("status") or "active").strip().lower()
    if "/inbox/" in f"/{relative.lower()}/":
        status = "draft"
    if status not in VALID_STATUSES:
        raise ValueError(f"{relative}: invalid status {status!r}")

    title = str(metadata.get("title") or infer_title(body, path.stem)).strip()
    kind = str(metadata.get("kind") or metadata.get("type") or defaults.get("kind") or "source").strip()
    owner = str(metadata.get("owner") or defaults.get("owner") or "").strip()
    tags = _as_string_list(metadata.get("tags"))
    updated_at = str(metadata.get("updated_at") or metadata.get("date") or "").strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    collection_id = str(collection["id"])
    return KnowledgeDocument(
        source_key=f"{collection_id}:{relative}",
        collection=collection_id,
        source_path=relative,
        absolute_path=path,
        title=title,
        kind=kind,
        status=status,
        owner=owner,
        tags=tags,
        updated_at=updated_at,
        metadata=metadata,
        content=text,
        content_sha256=digest,
        git_commit=git_commit,
    )


def load_documents(
    config_path: Path,
    *,
    content_root: Path | None = None,
    include_inbox: bool = False,
) -> list[KnowledgeDocument]:
    config_path = config_path.resolve()
    product_root = config_path.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    collections = config.get("collections") or []
    if not isinstance(collections, list):
        raise ValueError("collections must be a list")

    documents: list[KnowledgeDocument] = []
    seen_keys: set[str] = set()
    seen_paths: dict[Path, str] = {}
    for collection in collections:
        if not isinstance(collection, dict) or not collection.get("id"):
            raise ValueError("every collection requires an id")
        root = _resolve_root(collection, product_root=product_root, content_root=content_root)
        if not root.is_dir():
            raise FileNotFoundError(f"collection {collection['id']}: root not found: {root}")
        includes = _as_string_list(collection.get("include"))
        excludes = _as_string_list(collection.get("exclude"))
        if not include_inbox:
            excludes.append("knowledge/inbox/**")
        commit = _git_commit(root)
        candidates: set[Path] = set()
        for pattern in includes:
            candidates.update(path for path in root.glob(pattern) if path.is_file())
        for path in sorted(candidates, key=lambda item: item.as_posix().casefold()):
            relative = path.relative_to(root).as_posix()
            if path.suffix.lower() not in SUPPORTED_SUFFIXES or _matches(relative, excludes):
                continue
            resolved_path = path.resolve()
            if resolved_path in seen_paths:
                raise ValueError(
                    f"source file belongs to multiple collections: {resolved_path} "
                    f"({seen_paths[resolved_path]}, {collection['id']})"
                )
            document = _load_document(
                path=path,
                root=root,
                collection=collection,
                git_commit=commit,
            )
            if document.source_key in seen_keys:
                raise ValueError(f"duplicate source key: {document.source_key}")
            seen_keys.add(document.source_key)
            seen_paths[resolved_path] = str(collection["id"])
            documents.append(document)
    return documents


def chunk_document(document: KnowledgeDocument, *, max_chars: int = 3500) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    heading = document.title
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            chunks.append({
                "chunk_no": len(chunks),
                "heading": heading,
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            })
        buffer = []

    for line in document.content.splitlines():
        match = HEADING_RE.match(line)
        if match and buffer:
            flush()
        if match:
            heading = match.group(2).strip()
        projected = sum(len(item) + 1 for item in buffer) + len(line)
        if buffer and projected > max_chars:
            flush()
        buffer.append(line)
    flush()
    return chunks or [{
        "chunk_no": 0,
        "heading": document.title,
        "content": document.content,
        "content_sha256": document.content_sha256,
    }]


def validate_documents(documents: list[KnowledgeDocument]) -> list[str]:
    warnings: list[str] = []
    for document in documents:
        if not document.title:
            raise ValueError(f"{document.source_key}: title is empty")
        if document.status == "active" and document.source_path.startswith("knowledge/"):
            if not document.updated_at:
                warnings.append(f"{document.source_key}: active curated knowledge has no updated_at")
            if not document.tags:
                warnings.append(f"{document.source_key}: active curated knowledge has no tags")
    return warnings


def write_catalog(documents: list[KnowledgeDocument], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "catalog.jsonl"
    index_path = output_dir / "INDEX.md"
    catalog_lines = [json.dumps(doc.catalog_record(), ensure_ascii=False, default=str) for doc in documents]
    catalog_path.write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")

    grouped: dict[str, list[KnowledgeDocument]] = {}
    for document in documents:
        grouped.setdefault(document.collection, []).append(document)
    lines = ["# Generated Knowledge Index", "", "このファイルは`scripts/knowledge_sync.py catalog`で生成されます。", ""]
    for collection, items in sorted(grouped.items()):
        lines.extend([f"## {collection}", ""])
        for document in sorted(items, key=lambda item: item.title.casefold()):
            tags = f" — {', '.join(document.tags)}" if document.tags else ""
            lines.append(
                f"- **{document.title}** (`{document.status}` / `{document.kind}`)  "
                f"`{document.source_path}`{tags}"
            )
        lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def search_documents(documents: list[KnowledgeDocument], query: str, collection: str | None) -> list[KnowledgeDocument]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    results: list[tuple[int, KnowledgeDocument]] = []
    for document in documents:
        if collection and document.collection != collection:
            continue
        haystack = "\n".join([document.title, " ".join(document.tags), document.content]).casefold()
        if terms and all(term in haystack for term in terms):
            score = sum(haystack.count(term) for term in terms)
            results.append((score, document))
    return [item[1] for item in sorted(results, key=lambda item: (-item[0], item[1].title.casefold()))]


def sync_database(documents: list[KnowledgeDocument], *, apply: bool, product_root: Path) -> None:
    chunk_count = sum(len(chunk_document(document)) for document in documents)
    print(f"documents={len(documents)} chunks={chunk_count} apply={apply}")
    if not apply:
        print("dry-run only: add --apply to write DATABASE_URL")
        return
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required with --apply")
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]

    import psycopg2
    from psycopg2.extras import Json

    ddl = (product_root / "scripts" / "create_knowledge_tables.sql").read_text(encoding="utf-8")
    with psycopg2.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(ddl)
            for document in documents:
                cursor.execute(
                    """
                    INSERT INTO nanami_products.knowledge_documents
                        (source_key, collection, source_path, title, kind, status, owner, tags,
                         metadata, content, content_sha256, source_updated_at, git_commit, indexed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (source_key) DO UPDATE SET
                        collection = EXCLUDED.collection,
                        source_path = EXCLUDED.source_path,
                        title = EXCLUDED.title,
                        kind = EXCLUDED.kind,
                        status = EXCLUDED.status,
                        owner = EXCLUDED.owner,
                        tags = EXCLUDED.tags,
                        metadata = EXCLUDED.metadata,
                        content = EXCLUDED.content,
                        content_sha256 = EXCLUDED.content_sha256,
                        source_updated_at = EXCLUDED.source_updated_at,
                        git_commit = EXCLUDED.git_commit,
                        indexed_at = NOW()
                    """,
                    (
                        document.source_key,
                        document.collection,
                        document.source_path,
                        document.title,
                        document.kind,
                        document.status,
                        document.owner or None,
                        Json(document.tags),
                        Json(document.metadata),
                        document.content,
                        document.content_sha256,
                        document.updated_at or None,
                        document.git_commit,
                    ),
                )
                cursor.execute(
                    "DELETE FROM nanami_products.knowledge_chunks WHERE source_key = %s",
                    (document.source_key,),
                )
                for chunk in chunk_document(document):
                    cursor.execute(
                        """
                        INSERT INTO nanami_products.knowledge_chunks
                            (source_key, chunk_no, heading, content, content_sha256, indexed_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            document.source_key,
                            chunk["chunk_no"],
                            chunk["heading"],
                            chunk["content"],
                            chunk["content_sha256"],
                        ),
                    )
    print("database sync completed; missing source files were not deleted")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("knowledge/sources.yaml"))
    parser.add_argument("--content-root", type=Path)
    parser.add_argument("--include-inbox", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    catalog = subparsers.add_parser("catalog")
    catalog.add_argument("--output-dir", type=Path, default=Path("knowledge/generated"))
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--collection")
    search.add_argument("--limit", type=int, default=20)
    sync = subparsers.add_parser("sync-db")
    sync.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config.resolve()
    product_root = config_path.parent.parent
    documents = load_documents(
        config_path,
        content_root=args.content_root,
        include_inbox=args.include_inbox,
    )
    warnings = validate_documents(documents)
    if args.command == "validate":
        counts: dict[str, int] = {}
        for document in documents:
            counts[document.collection] = counts.get(document.collection, 0) + 1
        print(json.dumps({"documents": len(documents), "collections": counts}, ensure_ascii=False))
        for warning in warnings:
            print(f"warning: {warning}")
    elif args.command == "catalog":
        write_catalog(documents, args.output_dir)
        print(f"catalog written: {args.output_dir.resolve()} ({len(documents)} documents)")
        for warning in warnings:
            print(f"warning: {warning}")
    elif args.command == "search":
        results = search_documents(documents, args.query, args.collection)
        for document in results[: max(1, args.limit)]:
            print(f"[{document.collection}] {document.title} :: {document.source_path}")
        print(f"matches={len(results)}")
    elif args.command == "sync-db":
        sync_database(documents, apply=args.apply, product_root=product_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
