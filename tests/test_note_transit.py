from __future__ import annotations

import unittest
from unittest.mock import patch

import yaml

from routes import (
    NoteTransitRequestError,
    _load_note_transit_source_doc,
    note_transit_generate,
)
from services.note_transit import (
    build_note_transit_yaml,
    get_note_transit_campaign,
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

    @patch("routes.build_note_transit_yaml", return_value="generated-yaml")
    @patch("routes._addon_args_from_base_doc", return_value={"tz_name": "Asia/Tokyo"})
    @patch("routes._load_note_transit_source_doc", return_value=_source_doc())
    def test_api_generates_july_from_url_only(self, load_source, _args, _build) -> None:
        response = note_transit_generate(
            "2026-07",
            {"data_url": "https://example.com/chart/abcdefghijklmnopqrstuvwxyz"},
        )
        payload = yaml.safe_load(response.body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["start_date"], "2026-07-01")
        self.assertEqual(payload["end_date"], "2026-08-07")
        self.assertEqual(payload["yaml"], "generated-yaml")
        load_source.assert_called_once()

    def test_api_rejects_undefined_campaign(self) -> None:
        response = note_transit_generate("2026-08", {"data_url": "https://example.com/chart/abcdefghijklmnopqrstuvwxyz"})
        payload = yaml.safe_load(response.body)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload["code"], "campaign_not_found")


if __name__ == "__main__":
    unittest.main()
