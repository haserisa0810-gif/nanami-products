from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request

import routes
from services.mundane_yaml import generate_mundane_yaml


def _request(path: str = "/mundane/2026-07") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "scheme": "https",
            "server": ("example.test", 443),
            "client": ("127.0.0.1", 12345),
            "query_string": b"",
        }
    )


class MundanePostsTest(unittest.TestCase):
    def test_parse_mundane_form_normalizes_and_validates_yaml(self) -> None:
        values = routes._parse_mundane_form(
            title=" ホロスコープで読む、2026年7月の社会の流れ ",
            slug="2026-07",
            target_year=2026,
            target_month=7,
            summary="短い説明",
            yaml_content="month: 2026-07\nfocus:\n  - society\n",
            body_markdown="## 解説\n本文",
            status="published",
            published_at="2026-07-01T09:30",
        )

        self.assertEqual(values["title"], "ホロスコープで読む、2026年7月の社会の流れ")
        self.assertEqual(values["slug"], "2026-07")
        self.assertEqual(values["target_month"], 7)
        self.assertEqual(values["status"], "published")
        self.assertEqual(values["published_at"], datetime(2026, 7, 1, 9, 30, tzinfo=ZoneInfo("Asia/Tokyo")))

    def test_parse_mundane_form_rejects_invalid_yaml(self) -> None:
        with self.assertRaisesRegex(ValueError, "YAML"):
            routes._parse_mundane_form(
                title="title",
                slug="2026-07",
                target_year=2026,
                target_month=7,
                summary="",
                yaml_content="broken: [",
                body_markdown="",
                status="draft",
                published_at="",
            )

    def test_markdown_renderer_escapes_html(self) -> None:
        html = str(routes._render_simple_markdown("## 見出し\n<script>alert(1)</script>\n\n- item"))

        self.assertIn("<h2>見出し</h2>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("<li>item</li>", html)
        self.assertNotIn("<script>", html)

    def test_public_route_404s_when_no_published_post_exists(self) -> None:
        with patch.object(routes.pg_store, "get_published_mundane_post_by_slug", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                routes.mundane_public(_request(), "2026-07")

        self.assertEqual(raised.exception.status_code, 404)

    def test_public_template_has_yaml_copy_controls(self) -> None:
        template = Path("templates/mundane_page.html").read_text(encoding="utf-8")

        self.assertIn("YAMLをコピー", template)
        self.assertIn("const MUNDANE_YAML", template)
        self.assertIn("id=\"copy-status\"", template)

    def test_generate_mundane_yaml_returns_monthly_context(self) -> None:
        yaml_text = generate_mundane_yaml(
            title="ホロスコープで読む、2026年7月の社会の流れ",
            slug="2026-07",
            target_year=2026,
            target_month=7,
        )

        self.assertIn("format: mundane-monthly-yaml-v1", yaml_text)
        self.assertIn("target_year: 2026", yaml_text)
        self.assertIn("target_month: 7", yaml_text)
        self.assertIn("lunar_events:", yaml_text)
        self.assertIn("major_aspects:", yaml_text)

    def test_generate_endpoint_returns_yaml_content(self) -> None:
        result = routes.mundane_generate_yaml(
            {
                "title": "ホロスコープで読む、2026年7月の社会の流れ",
                "slug": "2026-07",
                "target_year": 2026,
                "target_month": 7,
            }
        )

        self.assertTrue(result["ok"])
        self.assertIn("mundane_context:", result["yaml_content"])

    def test_admin_form_has_generation_controls_and_no_paste_placeholder(self) -> None:
        template = Path("templates/mundane_form.html").read_text(encoding="utf-8")

        self.assertIn("マンデンYAMLを生成", template)
        self.assertIn("/admin/mundane/generate-yaml", template)
        self.assertIn("生成中", template)
        self.assertNotIn("貼り付けてください", template)


if __name__ == "__main__":
    unittest.main()
