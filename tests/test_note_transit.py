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
    _load_note_transit_source_doc,
    _load_note_transit_source_yaml,
    _resolve_note_transit_source,
    note_transit_result_page,
    note_transit_result_yaml,
    note_transit_generate,
)
from services.note_transit import (
    NOTE_TRANSIT_CAMPAIGNS,
    NoteTransitCampaign,
    build_note_transit_yaml,
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

    @patch("services.note_transit.build_product_yaml")
    def test_build_yaml_uses_campaign_dates(self, build_product_yaml_mock) -> None:
        generated_doc = _source_doc()
        generated_doc["systems"]["western"]["transit"] = {
            "period": {
                "start_date": "2026-07-01",
                "days": 38,
            },
            "daily": [{"date": "2026-07-01"}],
        }
        build_product_yaml_mock.return_value = ("", "", generated_doc)
        campaign = get_note_transit_campaign("2026-07")

        result = build_note_transit_yaml(
            campaign=campaign,
            source_doc=_source_doc(),
            calculation_args={
                "title": "Tester",
                "birth_date": "2000-01-01",
                "birth_time": "12:00",
                "prefecture": "東京都",
                "tz_name": "Asia/Tokyo",
            },
        )
        doc = yaml.safe_load(result)

        self.assertEqual(build_product_yaml_mock.call_args.kwargs["transit_days"], 38)
        self.assertEqual(doc["campaign"]["start_date"], "2026-07-01")
        self.assertEqual(doc["campaign"]["end_date"], "2026-08-07")
        self.assertEqual(doc["systems"]["western"]["transit"]["period"]["end_date"], "2026-08-07")

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

    @patch("routes.build_note_transit_yaml", return_value="generated-yaml")
    @patch(
        "routes._save_note_transit_result",
        return_value=("generated-token", datetime(2026, 10, 1, tzinfo=timezone.utc)),
    )
    @patch("routes._addon_args_from_base_doc", return_value={"tz_name": "Asia/Tokyo"})
    @patch("routes._load_note_transit_source_doc", return_value=_source_doc())
    @patch("routes._require_note_transit_campaign")
    def test_api_generates_saves_and_returns_result_url(
        self,
        require_campaign,
        load_source,
        _args,
        save_result,
        _build,
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
        self.assertEqual(payload["result_url"], "https://example.com/note-transit/result/generated-token")
        self.assertEqual(payload["download_url"], "https://example.com/note-transit/result/generated-token.yaml")
        self.assertEqual(payload["source_type"], "url")
        load_source.assert_called_once()
        save_result.assert_called_once_with("generated-yaml")

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

    @patch("routes.build_note_transit_yaml", return_value="generated-from-yaml")
    @patch(
        "routes._save_note_transit_result",
        return_value=("yaml-token", datetime(2026, 10, 1, tzinfo=timezone.utc)),
    )
    @patch("routes._require_note_transit_campaign")
    def test_api_generates_from_yaml_when_url_is_empty(
        self,
        require_campaign,
        _save_result,
        _build,
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

    @patch(
        "routes._load_transit_addon_link",
        return_value=(
            {
                "yaml_text": yaml.safe_dump(
                    {
                        "campaign": {
                            "label": "2026年7月 note特典",
                            "start_date": "2026-07-01",
                            "end_date": "2026-08-07",
                        }
                    },
                    allow_unicode=True,
                )
            },
            False,
        ),
    )
    def test_result_page_and_yaml_use_saved_link(self, _load_link) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/note-transit/result/generated-token",
                "query_string": b"",
                "headers": [],
                "server": ("example.com", 443),
                "scheme": "https",
            }
        )

        page_response = note_transit_result_page(request, "generated-token")
        yaml_response = note_transit_result_yaml("generated-token")

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("2026-07-01", page_response.body.decode())
        self.assertEqual(yaml_response.status_code, 200)
        self.assertIn("2026年7月 note特典", yaml_response.body.decode())


if __name__ == "__main__":
    unittest.main()
