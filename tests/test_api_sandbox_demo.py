from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import routes
from services.api_calc import calc_western_api
from services.api_demo import build_demo_response


ROOT = Path(__file__).resolve().parents[1]


class ApiSandboxDemoTest(unittest.TestCase):
    def test_api_sandbox_contains_data_creation_ui(self) -> None:
        html = (ROOT / "templates" / "api_sandbox.html").read_text(encoding="utf-8")

        self.assertIn("占術データ作成デモ", html)
        self.assertIn('value="western"', html)
        self.assertIn('value="shichu"', html)
        self.assertIn('value="transit"', html)
        self.assertIn('value="combined"', html)
        self.assertIn("AIに貼るプロンプト", html)
        self.assertIn('"X-API-Key"', html)
        self.assertIn('fetch(`/api/${mode === "live" ? "calc" : "demo"}/${type}`', html)
        self.assertIn("body: JSON.stringify(payload())", html)
        self.assertNotIn("localStorage", html)

    def test_demo_combined_returns_json_and_yaml_without_api_key(self) -> None:
        body = build_demo_response(
            "combined",
            {
                "name": "テスト太郎",
                "birth_date": "1990-01-01",
                "birth_time": "12:00",
                "birth_place": "東京都",
                "timezone": "Asia/Tokyo",
                "target_date": "2026-06-10",
                "period": "day",
            },
            base_url="http://test",
        )

        self.assertTrue(body["ok"])
        self.assertEqual(body["meta"]["endpoint"], "combined")
        self.assertTrue(body["handoff_yaml"])

    def test_live_routes_forward_payload_and_api_key_to_real_calculators(self) -> None:
        request = Mock()
        payload = {
            "birth_date": "1990-01-01",
            "birth_time": "12:00",
            "birth_place": "東京都",
            "timezone": "Asia/Tokyo",
        }
        cases = [
            (routes.api_calc_western, "western", routes.calc_western_api),
            (routes.api_calc_shichu, "shichu", routes.calc_shichu_api),
            (routes.api_calc_transit, "transit", routes.calc_transit_api),
            (routes.api_calc_combined, "combined", routes.calc_combined_api),
        ]

        for route, endpoint, calculator in cases:
            with self.subTest(endpoint=endpoint), patch.object(routes, "_handle_calc_api") as handle:
                route(request, payload, "np_test_key")

                handle.assert_called_once_with(
                    request=request,
                    endpoint=endpoint,
                    payload=payload,
                    api_key="np_test_key",
                    calc_func=calculator,
                )

    def test_real_western_calculation_changes_when_form_values_change(self) -> None:
        first, first_status = calc_western_api(
            {
                "birth_date": "1990-01-01",
                "birth_time": "12:00",
                "birth_place": "東京都",
                "timezone": "Asia/Tokyo",
            }
        )
        second, second_status = calc_western_api(
            {
                "birth_date": "1991-02-03",
                "birth_time": "08:30",
                "birth_place": "大阪府",
                "timezone": "Asia/Tokyo",
            }
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["input"]["birth_place"], "東京都")
        self.assertEqual(second["input"]["birth_place"], "大阪府")
        self.assertNotEqual(
            first["raw_data"]["western"]["natal"]["bodies"]["Sun"]["absolute_longitude"],
            second["raw_data"]["western"]["natal"]["bodies"]["Sun"]["absolute_longitude"],
        )


if __name__ == "__main__":
    unittest.main()
