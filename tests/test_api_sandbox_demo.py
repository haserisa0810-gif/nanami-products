from __future__ import annotations

import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
