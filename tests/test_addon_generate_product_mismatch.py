from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import Request

from routes import addon_generate


class TransitAddonMismatchFormTest(unittest.TestCase):
    @patch(
        "routes._redeem_and_save_transit_addon_or_raise",
        side_effect=ValueError(
            "この注文番号はトランジットYAML版用です。"
            "ホロスコープ：38日トランジット追加の生成には使用できません。"
        ),
    )
    @patch("routes._resolve_order_provider", return_value="stores")
    @patch("routes._transit_addon_chart_payload", return_value={"options": {"product_type": "western_31days_transit_addon"}})
    @patch("routes._build_transit_addon_from_base", return_value=("addon-yaml", "", {}, "chart-yaml", "", {}))
    @patch("routes._parse_transit_start_date")
    @patch("routes._load_addon_base_yaml")
    def test_transit_addon_refuses_transit_yaml_order(
        self,
        load_base,
        parse_start,
        _build_addon,
        _chart_payload,
        resolve_provider,
        redeem_error,
    ) -> None:
        load_base.return_value = {"systems": {"western": {"natal": {}}}}
        parse_start.return_value = None
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/addon/generate",
                "headers": [],
                # エラー応答は _resolve_lang() が ?lang を読むため、scope に必須。
                "query_string": b"",
            }
        )

        response = addon_generate(
            request=request,
            addon_type="western_31days_transit_addon",
            order_code="9700000004",
            order_provider="stores",
            payhip_email="",
            payhip_product_code="",
            payhip_order_id="",
            base_yaml="dummy",
            previous_chart_url="",
            transit_start_date="2026-08-19",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("この注文番号はトランジットYAML版用です。", response.body.decode("utf-8"))
        resolve_provider.assert_called_once_with("9700000004", "stores")
        redeem_error.assert_called_once()


