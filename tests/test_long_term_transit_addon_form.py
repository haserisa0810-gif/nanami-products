from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Request
from fastapi.responses import RedirectResponse

from routes import _load_addon_base_doc_from_previous_chart_url, addon_generate


class LongTermTransitAddonFormTest(unittest.TestCase):
    @patch("routes._validate_addon_base_doc")
    @patch("routes._load_addon_base_yaml", return_value={"systems": {"western": {"natal": {}}}})
    @patch("routes.pg_store.get_chart", return_value={"yaml_text": "version: test", "options": {}})
    def test_previous_chart_url_accepts_page_and_yaml_urls(
        self,
        get_chart,
        _load_yaml,
        _validate,
    ) -> None:
        token = "abcdefghijklmnopqrstuvwxyz"
        for suffix in ("", ".yaml"):
            with self.subTest(suffix=suffix):
                result = _load_addon_base_doc_from_previous_chart_url(
                    f"https://chart.nanami-astro.com/chart/{token}{suffix}",
                    "western_long_term_transits_addon",
                )
                self.assertIn("systems", result)

        self.assertEqual(get_chart.call_count, 2)

    def test_ui_treats_long_term_transits_as_a_transit_addon(self) -> None:
        template = Path("templates/addon_form.html").read_text(encoding="utf-8")

        self.assertIn("'western_long_term_transits_addon'", template)
        self.assertIn("previousChartUrl.disabled = !isTransit", template)
        self.assertIn("transitPeriodSection.hidden = !isTransit", template)
        self.assertIn("baseYaml.required = !isTransit", template)

    @patch("routes._redeem_and_save_transit_addon_or_raise", return_value=("generated-token", None))
    @patch("routes._resolve_order_provider", return_value="stores")
    @patch("routes._long_term_transits_addon_chart_payload", return_value={"options": {}})
    @patch("routes._build_long_term_transits_addon_from_base", return_value=("result", "", {}, "chart", "", {}))
    @patch("routes._parse_transit_start_date")
    @patch("routes._load_addon_base_doc_from_previous_chart_url", return_value={"systems": {"western": {"natal": {}}}})
    def test_previous_chart_url_is_loaded_with_long_term_addon_type(
        self,
        load_previous_chart,
        _parse_start_date,
        _build_addon,
        _chart_payload,
        _resolve_provider,
        _redeem,
    ) -> None:
        request = Request({"type": "http", "method": "POST", "path": "/addon/generate", "headers": []})

        response = addon_generate(
            request,
            addon_type="western_long_term_transits_addon",
            order_code="1234567890",
            order_provider="stores",
            payhip_email="",
            payhip_product_code="",
            payhip_order_id="",
            base_yaml="",
            previous_chart_url="https://chart.nanami-astro.com/chart/abcdefghijklmnopqrstuvwxyz",
            transit_start_date="2026-06-15",
        )

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "/chart/generated-token")
        load_previous_chart.assert_called_once_with(
            "https://chart.nanami-astro.com/chart/abcdefghijklmnopqrstuvwxyz",
            "western_long_term_transits_addon",
        )


if __name__ == "__main__":
    unittest.main()
