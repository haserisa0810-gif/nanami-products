from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi import Request

from routes import (
    NoteTransitRequestError,
    _build_transit_addon_from_base,
    _load_note_transit_source_doc,
    _load_note_transit_source_yaml,
    _resolve_note_transit_source,
    note_transit_generate,
)
from services.note_transit import (
    NOTE_TRANSIT_CAMPAIGNS,
    NoteTransitCampaign,
    get_note_transit_campaign,
    get_note_transit_campaign_by_access_key,
)


def _source_doc() -> dict:
    return {
        "version": "nanami-products-yaml-v1",
        "input": {
            "title": "Tester",
            "birth_date": "2000-01-01",
            "calculation_time": "12:00",
            "prefecture": "東京都",
            "birth_place": "東京都",
            "timezone": "Asia/Tokyo",
        },
        "product": {
            "type": "personal_ai_astrology_yaml",
            "options": {"product_type": "western_basic", "western_natal": True},
        },
        "systems": {
            "western": {
                "natal": {
                    "bodies": {"Sun": {"sign": "Aries", "degree": 10}},
                    "houses": {},
                    "aspects": [],
                }
            }
        },
    }


class NoteTransitTest(unittest.TestCase):
    def test_july_campaign_has_fixed_period(self) -> None:
        campaign = get_note_transit_campaign("2026-07")

        self.assertIsNotNone(campaign)
        self.assertEqual(campaign.start_date.isoformat(), "2026-07-01")
        self.assertEqual(campaign.end_date.isoformat(), "2026-08-07")
        self.assertEqual(campaign.days, 38)
        self.assertEqual(len(campaign.access_key_hash), 64)

    def test_august_campaign_has_fixed_period(self) -> None:
        campaign = get_note_transit_campaign("2026-08")

        self.assertIsNotNone(campaign)
        self.assertEqual(campaign.start_date.isoformat(), "2026-08-01")
        self.assertEqual(campaign.end_date.isoformat(), "2026-09-07")
        self.assertEqual(campaign.days, 38)
        self.assertEqual(len(campaign.access_key_hash), 64)

    def test_campaign_is_resolved_by_secret_key_not_month(self) -> None:
        test_key = "unit-test-secret"
        test_campaign = NoteTransitCampaign(
            campaign_id="test-campaign",
            access_key_hash=hashlib.sha256(test_key.encode()).hexdigest(),
            label="test",
            start_date=get_note_transit_campaign("2026-07").start_date,
            end_date=get_note_transit_campaign("2026-07").end_date,
            enabled=True,
        )
        with patch.dict(NOTE_TRANSIT_CAMPAIGNS, {"test": test_campaign}, clear=True):
            self.assertEqual(get_note_transit_campaign_by_access_key(test_key), test_campaign)
            self.assertIsNone(get_note_transit_campaign_by_access_key("2026-07"))

    def test_source_url_errors_are_distinct(self) -> None:
        with self.assertRaises(NoteTransitRequestError) as missing:
            _load_note_transit_source_doc("")
        self.assertEqual(missing.exception.code, "url_required")

        with self.assertRaises(NoteTransitRequestError) as invalid:
            _load_note_transit_source_doc("not-a-url")
        self.assertEqual(invalid.exception.code, "invalid_url")

        with self.assertRaises(NoteTransitRequestError) as unsupported:
            _load_note_transit_source_doc("https://example.com/redeem/western-basic")
        self.assertEqual(unsupported.exception.code, "unsupported_url")

    @patch(
        "routes.pg_store.get_chart",
        return_value={
            "yaml_text": yaml.safe_dump(_source_doc(), allow_unicode=True),
            "options": {"product_type": "western_asteroids_addon"},
        },
    )
    def test_source_url_rejects_non_basic_or_full_product(self, _get_chart) -> None:
        with self.assertRaises(NoteTransitRequestError) as unsupported:
            _load_note_transit_source_doc("https://example.com/chart/abcdefghijklmnopqrstuvwxyz")

        self.assertEqual(unsupported.exception.code, "unsupported_url")

    def test_yaml_source_accepts_basic_yaml(self) -> None:
        doc = _load_note_transit_source_yaml(
            yaml.safe_dump(_source_doc(), allow_unicode=True, sort_keys=False)
        )

        self.assertEqual(doc["input"]["birth_date"], "2000-01-01")

    def test_source_resolution_prefers_url_and_warns_when_both_exist(self) -> None:
        with patch("routes._load_note_transit_source_doc", return_value=_source_doc()) as load_url:
            doc, source_type, warning = _resolve_note_transit_source(
                "https://example.com/chart/abcdefghijklmnopqrstuvwxyz",
                yaml.safe_dump(_source_doc(), allow_unicode=True, sort_keys=False),
            )

        self.assertEqual(doc["input"]["birth_date"], "2000-01-01")
        self.assertEqual(source_type, "url")
        self.assertIn("URLを優先", warning)
        load_url.assert_called_once()

    def test_source_resolution_uses_yaml_when_url_is_empty(self) -> None:
        doc, source_type, warning = _resolve_note_transit_source(
            "",
            yaml.safe_dump(_source_doc(), allow_unicode=True, sort_keys=False),
        )

        self.assertEqual(doc["input"]["birth_date"], "2000-01-01")
        self.assertEqual(source_type, "yaml")
        self.assertIsNone(warning)

    def test_source_resolution_rejects_empty_inputs(self) -> None:
        with self.assertRaises(NoteTransitRequestError) as missing:
            _resolve_note_transit_source("", "")

        self.assertEqual(missing.exception.code, "source_required")

    def test_yaml_input_is_collapsed_and_url_is_not_required(self) -> None:
        template = Path("templates/note_transit.html").read_text(encoding="utf-8")

        self.assertIn("<details", template)
        self.assertNotIn("<details open", template)
        self.assertIn("URLが使えない場合：YAMLを直接貼り付ける", template)
        self.assertIn('id="base-yaml"', template)
        self.assertNotIn('id="data-url" required', template)

    @patch(
        "routes._save_note_transit_result",
        return_value=("generated-token", datetime(2026, 10, 1, tzinfo=timezone.utc)),
    )
    @patch(
        "routes._transit_addon_chart_payload",
        return_value={"options": {}},
    )
    @patch(
        "routes._build_transit_addon_from_base",
        return_value=("generated-yaml", "addon-prompt", {}, "chart-yaml", "chart-prompt", {}),
    )
    @patch("routes._load_note_transit_source_doc", return_value=_source_doc())
    @patch("routes._require_note_transit_campaign")
    def test_api_generates_saves_and_returns_result_url(
        self,
        require_campaign,
        load_source,
        build_transit,
        _chart_payload,
        save_result,
    ) -> None:
        require_campaign.return_value = get_note_transit_campaign("2026-07")
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/note-transit/secret-key",
                "query_string": b"",
                "headers": [],
                "server": ("example.com", 443),
                "scheme": "https",
            }
        )
        response = note_transit_generate(
            request,
            "secret-key",
            {
                "data_url": "https://example.com/chart/abcdefghijklmnopqrstuvwxyz",
                "base_yaml": "",
            },
        )
        payload = yaml.safe_load(response.body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["start_date"], "2026-07-01")
        self.assertEqual(payload["end_date"], "2026-08-07")
        self.assertEqual(payload["yaml"], "generated-yaml")
        self.assertEqual(payload["result_url"], "https://example.com/chart/generated-token")
        self.assertEqual(payload["download_url"], "https://example.com/chart/generated-token/transit.yaml")
        self.assertEqual(payload["source_type"], "url")
        load_source.assert_called_once()
        self.assertEqual(build_transit.call_args.kwargs["transit_days"], 38)
        save_result.assert_called_once_with(
            "generated-yaml",
            chart_payload={
                "options": {
                    "order_provider": "note",
                    "order_strict_check": False,
                }
            },
        )

    def test_api_rejects_month_instead_of_secret_key(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/note-transit/2026-08",
                "query_string": b"",
                "headers": [],
                "server": ("example.com", 443),
                "scheme": "https",
            }
        )
        response = note_transit_generate(
            request,
            "2026-08",
            {"data_url": "https://example.com/chart/abcdefghijklmnopqrstuvwxyz"},
        )
        payload = yaml.safe_load(response.body)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload["code"], "campaign_not_found")

    @patch(
        "routes._save_note_transit_result",
        return_value=("yaml-token", datetime(2026, 10, 1, tzinfo=timezone.utc)),
    )
    @patch(
        "routes._transit_addon_chart_payload",
        return_value={"options": {}},
    )
    @patch(
        "routes._build_transit_addon_from_base",
        return_value=("generated-from-yaml", "addon-prompt", {}, "chart-yaml", "chart-prompt", {}),
    )
    @patch("routes._require_note_transit_campaign")
    def test_api_generates_from_yaml_when_url_is_empty(
        self,
        require_campaign,
        _build_transit,
        _chart_payload,
        _save_result,
    ) -> None:
        require_campaign.return_value = get_note_transit_campaign("2026-07")
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/note-transit/secret-key",
                "query_string": b"",
                "headers": [],
                "server": ("example.com", 443),
                "scheme": "https",
            }
        )

        response = note_transit_generate(
            request,
            "secret-key",
            {
                "data_url": "",
                "base_yaml": yaml.safe_dump(_source_doc(), allow_unicode=True, sort_keys=False),
            },
        )
        payload = yaml.safe_load(response.body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["source_type"], "yaml")
        self.assertEqual(payload["yaml"], "generated-from-yaml")

    def test_common_transit_builder_preserves_natal_and_marks_note_campaign(self) -> None:
        campaign = get_note_transit_campaign("2026-07")
        addon_doc = {
            "generated_at": "2026-06-25T00:00:00+09:00",
            "campaign": {
                "id": campaign.campaign_id,
                "start_date": "2026-07-01",
                "end_date": "2026-08-07",
            },
            "systems": {
                "western": {
                    "transit": {
                        "period": {"start_date": "2026-07-01", "end_date": "2026-08-07", "days": 38},
                        "daily": [{"date": "2026-07-01"}],
                    }
                }
            },
        }

        generated_doc = _source_doc()
        generated_doc["systems"]["western"]["transit"] = addon_doc["systems"]["western"]["transit"]
        with (
            patch(
                "routes.build_31days_transit_addon_yaml",
                return_value=(
                    yaml.safe_dump(addon_doc, allow_unicode=True, sort_keys=False),
                    "今後38日間のaddon-prompt",
                    addon_doc,
                ),
            ) as build_addon,
            patch("routes.build_product_yaml", return_value=("", "38日分のchart-prompt", generated_doc)),
        ):
            addon_yaml, addon_prompt, _addon_doc, chart_yaml, chart_prompt, chart_doc = _build_transit_addon_from_base(
                _source_doc(),
                transit_start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
                transit_days=campaign.days,
                extra_meta={"campaign_id": campaign.campaign_id},
                extra_options={"campaign_id": campaign.campaign_id},
                extra_root={"campaign": addon_doc["campaign"]},
            )

        loaded = yaml.safe_load(chart_yaml)
        addon_loaded = yaml.safe_load(addon_yaml)
        self.assertEqual(build_addon.call_args.kwargs["transit_days"], 38)
        self.assertIsNotNone(loaded["systems"]["western"]["natal"])
        self.assertEqual(loaded["systems"]["western"]["transit"]["period"]["days"], 38)
        self.assertEqual(chart_doc["meta"]["product_type"], "western_31days_transit_addon")
        self.assertEqual(addon_loaded["meta"]["campaign_id"], "note-2026-07")
        self.assertIn("38日間", addon_prompt)
        self.assertIn("38日分", chart_prompt)

    def test_common_transit_builder_keeps_standard_addon_defaults(self) -> None:
        addon_doc = {
            "meta": {},
            "product": {"options": {}},
            "systems": {
                "western": {
                    "transit": {
                        "period": {"start_date": "2026-07-01", "days": 31},
                        "daily": [{"date": "2026-07-01"}],
                    }
                }
            },
        }
        generated_doc = _source_doc()
        generated_doc["systems"]["western"]["transit"] = addon_doc["systems"]["western"]["transit"]
        with (
            patch(
                "routes.build_31days_transit_addon_yaml",
                return_value=(
                    yaml.safe_dump(addon_doc, allow_unicode=True, sort_keys=False),
                    "addon-prompt",
                    addon_doc,
                ),
            ),
            patch("routes.build_product_yaml", return_value=("", "chart-prompt", generated_doc)),
        ):
            addon_yaml, _addon_prompt, _addon_doc, _chart_yaml, _chart_prompt, chart_doc = _build_transit_addon_from_base(
                _source_doc(),
                transit_start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )

        addon_loaded = yaml.safe_load(addon_yaml)
        self.assertEqual(addon_loaded["meta"]["product_type"], "western_31days_transit_addon")
        self.assertEqual(addon_loaded["product"]["options"]["transit_days"], 38)
        self.assertEqual(chart_doc["product"]["options"]["product_type"], "western_31days_transit_addon")
        self.assertEqual(chart_doc["product"]["options"]["transit_days"], 38)

    def test_note_specific_result_routes_are_removed(self) -> None:
        template_path = Path("templates/note_transit_result.html")

        self.assertFalse(template_path.exists())


if __name__ == "__main__":
    unittest.main()
