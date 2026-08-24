from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.knowledge_sync import (
    KnowledgeDocument,
    chunk_document,
    infer_title,
    load_documents,
    parse_markdown,
    search_documents,
)


class KnowledgeSyncTest(unittest.TestCase):
    def test_markdown_front_matter_is_separated_from_body(self) -> None:
        metadata, body = parse_markdown(
            "---\ntitle: テスト\nstatus: active\nupdated_at: 2026-08-20\ntags: [one, two]\n---\n# 本文\n内容"
        )
        self.assertEqual(metadata["title"], "テスト")
        self.assertEqual(metadata["tags"], ["one", "two"])
        self.assertEqual(infer_title(body, "fallback"), "本文")

    def test_inbox_is_excluded_unless_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            product = root / "product"
            content = root / "content"
            (product / "knowledge").mkdir(parents=True)
            (content / "knowledge" / "operations").mkdir(parents=True)
            (content / "knowledge" / "inbox").mkdir(parents=True)
            (content / "knowledge" / "operations" / "active.md").write_text(
                "---\ntitle: Active\nstatus: active\nupdated_at: 2026-08-20\ntags: [ops]\n---\n# Active",
                encoding="utf-8",
            )
            (content / "knowledge" / "inbox" / "draft.md").write_text(
                "---\ntitle: Draft\nstatus: draft\n---\n# Draft",
                encoding="utf-8",
            )
            config = product / "knowledge" / "sources.yaml"
            config.write_text(
                """
collections:
  - id: operations
    fallback_root: ../content
    defaults: {kind: source, status: active, owner: test}
    include: [knowledge/**/*.md]
""".strip(),
                encoding="utf-8",
            )

            normal = load_documents(config, content_root=content)
            with_inbox = load_documents(config, content_root=content, include_inbox=True)

        self.assertEqual([doc.title for doc in normal], ["Active"])
        self.assertEqual(normal[0].metadata["updated_at"], "2026-08-20")
        self.assertEqual({doc.title for doc in with_inbox}, {"Active", "Draft"})

    def test_chunks_split_on_headings_and_search_honors_collection(self) -> None:
        document = KnowledgeDocument(
            source_key="operations:test.md",
            collection="operations",
            source_path="test.md",
            absolute_path=Path("test.md"),
            title="運用",
            kind="playbook",
            status="active",
            owner="test",
            tags=["etsy"],
            updated_at="2026-08-20",
            metadata={"summary": "full archive content", "category": "operations"},
            content="# Etsy\n注文確認\n## DB\n登録手順",
            content_sha256="hash",
            git_commit=None,
        )
        chunks = chunk_document(document)
        self.assertEqual([chunk["heading"] for chunk in chunks], ["Etsy", "DB"])
        self.assertEqual(document.catalog_record()["metadata"], {"category": "operations"})
        self.assertEqual(search_documents([document], "Etsy 注文", "operations"), [document])
        self.assertEqual(search_documents([document], "Etsy", "product"), [])


if __name__ == "__main__":
    unittest.main()
