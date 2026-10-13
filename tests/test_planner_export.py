"""Smoke tests for the vendored personal-planner generator (services/planner).

These build a short (1-month) personal planner so the subprocess stays fast.
They run in any environment that has pyswisseph + PyYAML + reportlab (the app's
own dependencies); no database or network is needed.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from services.planner_export import (
    PlannerGenerationError,
    render_personal_planner,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "planner_personal_sample.yaml"


def _pdf_page_count(data: bytes) -> int:
    # Count page objects without a PDF library: reportlab writes uncompressed
    # "/Type /Page" (not /Pages) markers for each page object.
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


class PlannerExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.yaml_text = FIXTURE.read_text(encoding="utf-8")

    def _render(self, lang: str, tmp_name: str) -> Path:
        out = Path(tmp_name)
        result = render_personal_planner(
            yaml_text=self.yaml_text, lang=lang, months=1, out_path=out
        )
        self.addCleanup(lambda: result.exists() and result.unlink())
        return result

    def test_japanese_pdf_is_valid(self) -> None:
        import tempfile

        out = Path(tempfile.mkdtemp()) / "ja.pdf"
        pdf = render_personal_planner(
            yaml_text=self.yaml_text,
            lang="ja",
            months=1,
            out_path=out,
            chart_url="https://chart.example/chart/ja-token/planner-ai",
        )
        data = pdf.read_bytes()
        self.assertTrue(data.startswith(b"%PDF"), "output is not a PDF")
        self.assertGreater(len(data), 20_000, "PDF unexpectedly small")
        self.assertIn(
            b"https://chart.example/chart/ja-token/planner-ai?date=2026-07-01",
            data,
        )
        # cover + guide + index + year + aspects + retro + 2 phases + personal
        # intro + natal + seasons + (month dashboard/calendar/focus + ~30 daily
        # + reflection) + ai + notes — comfortably more than 30 pages.
        self.assertGreater(_pdf_page_count(data), 30, "too few pages")

    def test_english_pdf_is_valid(self) -> None:
        import tempfile

        out = Path(tempfile.mkdtemp()) / "en.pdf"
        pdf = render_personal_planner(
            yaml_text=self.yaml_text,
            lang="en",
            months=1,
            out_path=out,
            chart_url="https://chart.example/chart/en-token/planner-ai?lang=en",
        )
        data = pdf.read_bytes()
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(_pdf_page_count(data), 30)
        self.assertIn(
            b"https://chart.example/chart/en-token/planner-ai?lang=en&date=2026-07-01",
            data,
        )

    def test_pdf_renders_when_optional_name_is_null(self) -> None:
        # The buyer name is optional and an empty field is stored as null.
        import tempfile

        yaml_text = self.yaml_text.replace("  title: Sample\n", "  title: null\n", 1)
        self.assertIn("  title: null\n", yaml_text)
        out = Path(tempfile.mkdtemp()) / "null-name.pdf"
        pdf = render_personal_planner(
            yaml_text=yaml_text, lang="ja", months=1, out_path=out
        )
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))

    def test_profile_turns_null_optional_fields_into_blank_text(self) -> None:
        import tempfile

        from services.planner.compute_ephemeris import personal_from_yaml

        yaml_text = (
            self.yaml_text.replace("  title: Sample\n", "  title: null\n", 1)
            .replace("  birth_time: '20:41'\n", "  birth_time: null\n", 1)
            .replace("  birth_place: 東京都\n", "  birth_place: null\n", 1)
        )
        path = Path(tempfile.mkdtemp()) / "null-fields.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        profile = personal_from_yaml(path)["profile"]
        self.assertEqual(profile["display_name"], "")
        self.assertEqual(profile["birth_display"], "1976-08-10")
        self.assertEqual(profile["birthplace_label"], "")
        self.assertEqual(profile["birth_timezone"], "Asia/Tokyo")

    def test_rejects_unknown_lang(self) -> None:
        with self.assertRaises(ValueError):
            render_personal_planner(yaml_text=self.yaml_text, lang="fr")

    def test_rejects_empty_yaml(self) -> None:
        with self.assertRaises(ValueError):
            render_personal_planner(yaml_text="   ", lang="en")

    def test_reports_generation_failure(self) -> None:
        with self.assertRaises(PlannerGenerationError):
            render_personal_planner(yaml_text="not: a valid chart", lang="en", months=1)


if __name__ == "__main__":
    unittest.main()
