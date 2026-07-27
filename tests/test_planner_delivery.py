"""End-to-end test for the B案 planner delivery seam.

Exercises birth inputs -> chart with long-term transits -> planner input YAML ->
personal planner PDF, plus inclusion in the Personal Edition ZIP. Runs in any
env with pyswisseph + PyYAML + reportlab; no database needed.
"""

from __future__ import annotations

import io
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from routes import chart_planner_pdf
from services.planner_delivery import build_planner_pdf
from services.planner_delivery import build_planner_pdf_from_yaml
from services.personal_edition_delivery import build_personalized_zip


BIRTH = dict(
    title="Sample",
    birth_date="1976-08-10",
    birth_time="20:41",
    prefecture="東京都",
    birth_place_label="東京都",
    birth_lat=35.6895,
    birth_lng=139.6917,
    tz_name="Asia/Tokyo",
)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "planner_personal_sample.yaml"


def _planner_request(token: str) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "server": ("chart.nanami-astro.com", 443),
        "path": f"/chart/{token}/planner.pdf",
        "query_string": b"",
        "headers": [],
    })


class PlannerDeliveryTest(unittest.TestCase):
    def test_build_planner_from_stored_yaml(self) -> None:
        pdf = build_planner_pdf_from_yaml(
            yaml_text=FIXTURE.read_text(encoding="utf-8"),
            lang="ja",
            months=1,
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 20_000)

    def test_long_term_chart_cannot_download_planner(self) -> None:
        yaml_text = FIXTURE.read_text(encoding="utf-8")
        chart = {
            "token": "longterm-token",
            "options": {},
            "yaml_text": yaml_text,
        }
        with (
            patch("routes._load_chart_or_404", return_value=chart),
            patch("routes._build_personal_planner_pdf", return_value=b"%PDF-test") as build,
            self.assertRaises(HTTPException) as raised,
        ):
            chart_planner_pdf(_planner_request("longterm-token"), "longterm-token")

        self.assertEqual(raised.exception.status_code, 404)
        build.assert_not_called()

    def test_38_day_chart_can_download_planner(self) -> None:
        yaml_text = FIXTURE.read_text(encoding="utf-8").replace(
            "transit_long_term:", "transit:", 1
        ).replace("days: 365", "days: 38", 1)
        chart = {
            "token": "short-transit-token",
            "options": {"product_type": "western_31days_transit_addon"},
            "yaml_text": yaml_text,
        }
        with (
            patch("routes._load_chart_or_404", return_value=chart),
            patch("routes._build_personal_planner_pdf", return_value=b"%PDF-test") as build,
        ):
            response = chart_planner_pdf(
                _planner_request("short-transit-token"), "short-transit-token"
            )

        self.assertEqual(response.media_type, "application/pdf")
        self.assertEqual(response.body, b"%PDF-test")
        build.assert_called_once_with(chart, lang="ja")

    def test_query_lang_en_overrides_stored_locale(self) -> None:
        yaml_text = FIXTURE.read_text(encoding="utf-8").replace(
            "transit_long_term:", "transit:", 1
        ).replace("days: 365", "days: 38", 1)
        chart = {
            "token": "en-token",
            "options": {"product_type": "western_full", "personal_edition_locale": "ja"},
            "yaml_text": yaml_text,
        }
        request = Request({
            "type": "http", "method": "GET", "scheme": "https",
            "server": ("chart.nanami-astro.com", 443),
            "path": "/chart/en-token/planner.pdf",
            "query_string": b"lang=en", "headers": [],
        })
        with (
            patch("routes._load_chart_or_404", return_value=chart),
            patch("routes._build_personal_planner_pdf", return_value=b"%PDF-en") as build,
        ):
            response = chart_planner_pdf(request, "en-token")
        self.assertEqual(response.body, b"%PDF-en")
        build.assert_called_once_with(chart, lang="en")

    def test_concurrent_build_for_same_chart_is_rejected(self) -> None:
        # A buyer clicking the button repeatedly must not queue several
        # 432-page builds on the same CPU.
        import routes

        yaml_text = FIXTURE.read_text(encoding="utf-8").replace(
            "transit_long_term:", "transit:", 1
        ).replace("days: 365", "days: 38", 1)
        chart = {
            "token": "busy-token",
            "options": {"product_type": "western_full"},
            "yaml_text": yaml_text,
        }
        started = threading.Event()
        release = threading.Event()

        def slow_build(_chart, *, lang):
            started.set()
            release.wait(timeout=5)
            return b"%PDF-slow"

        with (
            patch("routes._load_chart_or_404", return_value=chart),
            patch("routes._build_personal_planner_pdf", side_effect=slow_build),
        ):
            worker = threading.Thread(
                target=lambda: chart_planner_pdf(_planner_request("busy-token"), "busy-token")
            )
            worker.start()
            try:
                self.assertTrue(started.wait(timeout=5), "first build never started")
                with self.assertRaises(HTTPException) as raised:
                    chart_planner_pdf(_planner_request("busy-token"), "busy-token")
                self.assertEqual(raised.exception.status_code, 429)
            finally:
                release.set()
                worker.join(timeout=5)

        # the slot is freed once the first build finishes
        self.assertNotIn(("busy-token", "ja"), routes._planner_builds_in_flight)

    def test_yaml_without_long_term_transits_is_rejected(self) -> None:
        # Stored charts without the addon carry `transit_long_term: null`.
        # Rendering those would produce an empty personal layer (every daily
        # page saying "no active transit"), so it must fail loudly instead.
        src = (
            "input:\n  timezone: Asia/Tokyo\n"
            "systems:\n  western:\n    natal:\n      bodies: {}\n"
            "    transit_long_term: null\n"
        )
        with self.assertRaises(ValueError):
            build_planner_pdf_from_yaml(yaml_text=src, lang="ja", months=12)

    def test_english_display_uses_utc(self) -> None:
        import yaml as _yaml
        from services.planner_delivery import _apply_display_timezone
        src = (
            "input:\n  timezone: Asia/Tokyo\n"
            "systems:\n  western:\n    transit_long_term:\n"
            "      period:\n        timezone: Asia/Tokyo\n"
        )
        en = _yaml.safe_load(_apply_display_timezone(src, "en"))
        self.assertEqual(en["input"]["timezone"], "UTC")
        self.assertEqual(
            en["systems"]["western"]["transit_long_term"]["period"]["timezone"], "UTC"
        )
        # Japanese planners keep the local timezone (string returned unchanged).
        self.assertEqual(_apply_display_timezone(src, "ja"), src)

    def test_build_planner_pdf_ja(self) -> None:
        pdf = build_planner_pdf(lang="ja", months=2, **BIRTH)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 20_000)

    def test_build_planner_pdf_en(self) -> None:
        pdf = build_planner_pdf(lang="en", months=2, **BIRTH)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_zip_includes_planner(self) -> None:
        pdf = build_planner_pdf(lang="ja", months=1, **BIRTH)
        zip_bytes = build_personalized_zip(
            yaml_text="version: test\ninput: {}\n", lang="ja", planner_pdf=pdf,
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
        self.assertIn("パーソナル・プランナー.pdf", names)

    def test_rejects_bad_lang(self) -> None:
        with self.assertRaises(ValueError):
            build_planner_pdf(lang="fr", months=1, **BIRTH)


if __name__ == "__main__":
    unittest.main()
