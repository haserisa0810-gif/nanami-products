from __future__ import annotations

import json
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import yaml

import routes
from services.mcp_chart_service import (
    ChartMcpError,
    available_sections_for_doc,
    chart_expiry,
    extract_chart_id_from_url,
    get_astrology_prompt,
    get_chart_yaml_from_url,
)


CHART_ID = "abcde12345ABCDE67890"
CHART_URL = f"https://chart.nanami-astro.com/chart/{CHART_ID}"


def _doc() -> dict:
    return {
        "version": "nanami-products-yaml-v1",
        "meta": {"chart_id": "chart_sample"},
        "product": {"options": {"western_natal": True, "asteroids": True, "transit": True}},
        "input": {"title": "sample"},
        "systems": {
            "western": {
                "natal": {"bodies": {"Sun": {"sign": "Cancer"}}, "houses": {}, "aspects": []},
                "asteroids": {"Ceres": {"sign": "Leo"}},
                "transit": {"period": {"days": 31}, "daily": [{"date": "2026-07-01"}]},
                "transit_long_term": {"items": [{"planet": "Saturn"}]},
            },
            "shichusuimei": {"day_master": "甲"},
            "indian": {"lagna": "Meṣa"},
        },
    }


def _chart(*, expires_delta: timedelta = timedelta(days=20)) -> dict:
    return {
        "token": CHART_ID,
        "options": {"product_type": "western_full"},
        "yaml_text": yaml.safe_dump(_doc(), allow_unicode=True, sort_keys=False),
        "prompt_text": "prompt",
        "share_yaml_text": None,
        "created_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "expires_at": datetime.now(timezone.utc) + expires_delta,
    }


class McpChartServiceTest(unittest.TestCase):
    def test_extract_chart_id_accepts_only_chart_domain_and_path(self) -> None:
        self.assertEqual(extract_chart_id_from_url(CHART_URL), CHART_ID)
        with self.assertRaises(ChartMcpError):
            extract_chart_id_from_url(f"https://example.com/chart/{CHART_ID}")
        with self.assertRaises(ChartMcpError):
            extract_chart_id_from_url(f"https://chart.nanami-astro.com/other/{CHART_ID}")

    def test_available_sections_detects_supported_sections(self) -> None:
        self.assertEqual(
            available_sections_for_doc(_doc()),
            ["natal", "transit_31days", "long_term", "asteroid", "shichu", "indian"],
        )

    def test_get_chart_yaml_filters_sections_and_reports_missing(self) -> None:
        with patch("services.mcp_chart_service.pg_store.get_chart", return_value=_chart()):
            result = get_chart_yaml_from_url(
                chart_url=CHART_URL,
                sections=["natal", "asteroid", "not_real"],
                format="full",
            )

        loaded = yaml.safe_load(result["yaml"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["returned_sections"], ["natal", "asteroid"])
        self.assertEqual(result["missing_sections"], ["not_real"])
        self.assertIn("natal", loaded["systems"]["western"])
        self.assertIn("asteroids", loaded["systems"]["western"])
        self.assertNotIn("transit", loaded["systems"]["western"])

    def test_get_chart_yaml_default_returns_complete_full_yaml(self) -> None:
        with patch("services.mcp_chart_service.pg_store.get_chart", return_value=_chart()):
            result = get_chart_yaml_from_url(chart_url=CHART_URL)

        loaded = yaml.safe_load(result["yaml"])
        western = loaded["systems"]["western"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["format"], "full")
        self.assertIsNotNone(western["natal"])
        self.assertIsNotNone(western["asteroids"])
        self.assertIsNotNone(western["transit"])
        self.assertEqual(result["returned_sections"], ["natal", "transit_31days", "long_term", "asteroid", "shichu", "indian"])

    def test_get_chart_yaml_returns_no_yaml_when_expired(self) -> None:
        with patch("services.mcp_chart_service.pg_store.get_chart", return_value=_chart(expires_delta=timedelta(seconds=-1))):
            result = get_chart_yaml_from_url(chart_url=CHART_URL)

        self.assertFalse(result["ok"])
        self.assertEqual(result["yaml"], "")
        self.assertEqual(result["error_code"], "chart_expired")
        self.assertIn("期限切れ", result["notice"])

    def test_chart_expiry_allows_explicit_no_expiry_policy(self) -> None:
        chart = _chart(expires_delta=timedelta(seconds=-1))
        chart["expires_at"] = None
        chart["options"] = {"product_type": "western_full", "expires_policy": "no_expiry"}

        self.assertIsNone(chart_expiry(chart))

    def test_notice_changes_for_near_expiry(self) -> None:
        with patch("services.mcp_chart_service.pg_store.get_chart", return_value=_chart(expires_delta=timedelta(days=6))):
            result = get_chart_yaml_from_url(chart_url=CHART_URL)

        self.assertIn("ローカル保存", result["notice"])

    def test_get_astrology_prompt_returns_required_rules(self) -> None:
        result = get_astrology_prompt(purpose="today_fortune", product_type="western_31days_transit_addon")

        self.assertTrue(result["ok"])
        self.assertEqual(result["recommended_sections"], ["natal", "asteroid", "transit_31days"])
        self.assertIn("生年月日から再計算しないでください。", result["prompt"])
        self.assertIn("moon_timepoints", result["prompt"])
        self.assertIn("today.selected_date", result["prompt"])
        self.assertIn("get_astrology_prompt", "\n".join(result["usage_order"]))


class McpEndpointTest(unittest.TestCase):
    def _call_endpoint(self, body: dict):
        class _Request:
            async def json(self):
                return body

        return asyncio.run(routes.mcp_endpoint(_Request()))

    def test_tools_list_and_call(self) -> None:
        listed = self._call_endpoint({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(listed.status_code, 200)
        tool_names = {tool["name"] for tool in json.loads(listed.body)["result"]["tools"]}
        self.assertIn("get_chart_yaml_from_url", tool_names)
        self.assertIn("get_astrology_prompt", tool_names)

        with patch("services.mcp_chart_service.pg_store.get_chart", return_value=_chart()):
            called = self._call_endpoint(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "get_available_sections_from_url",
                        "arguments": {"chart_url": CHART_URL},
                    },
                }
            )

        self.assertEqual(called.status_code, 200)
        text = json.loads(called.body)["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertTrue(payload["ok"])
        self.assertIn("natal", payload["available_sections"])

    def test_tools_call_get_astrology_prompt(self) -> None:
        called = self._call_endpoint(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_astrology_prompt",
                    "arguments": {
                        "purpose": "today_fortune",
                        "product_type": "western_31days_transit_addon",
                    },
                },
            }
        )

        self.assertEqual(called.status_code, 200)
        text = json.loads(called.body)["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertTrue(payload["ok"])
        self.assertIn("YAML内の計算結果を唯一の根拠", payload["prompt"])

    def test_tools_call_rejects_bad_domain_without_internal_error(self) -> None:
        called = self._call_endpoint(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_chart_summary_from_url",
                    "arguments": {"chart_url": f"https://evil.example/chart/{CHART_ID}"},
                },
            }
        )

        self.assertEqual(called.status_code, 200)
        result = json.loads(called.body)["result"]
        self.assertTrue(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["error_code"], "domain_not_allowed")


if __name__ == "__main__":
    unittest.main()
