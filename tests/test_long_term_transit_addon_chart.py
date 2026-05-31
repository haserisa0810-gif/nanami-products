from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import yaml

from routes import (
    _build_long_term_transits_addon_from_base,
    _chart_has_31day_transit,
    _chart_has_western_asteroids,
    _chart_share_yaml_text,
)
from services.long_term_transit_yaml import has_long_term_transits


def _base_doc(*, include_transit: bool = False, include_asteroids: bool = False) -> dict:
    western = {
        "natal": {
            "bodies": {"Sun": {"sign": "Aries", "degree": 10}},
            "houses": {"1": {"sign": "Aries"}},
            "aspects": [],
            "summary": {},
        }
    }
    if include_transit:
        western["transit"] = {
            "period": {"start_date": "2026-05-01", "days": 31},
            "daily": [
                {
                    "date": "2026-05-01",
                    "natal_aspects": [
                        {"transit_body": "Mars", "natal_body": "Sun", "aspect": "trine", "orb": 0.4}
                    ],
                }
                for _ in range(31)
            ],
        }
    if include_asteroids:
        western["asteroids"] = {"Ceres": {"sign": "Taurus", "degree": 5}}

    return {
        "version": "nanami-products-yaml-v1",
        "generated_at": "2026-05-01T00:00:00+09:00",
        "input": {
            "title": "Tester",
            "birth_date": "2000-01-01",
            "birth_time": "12:00",
            "calculation_time": "12:00",
            "prefecture": "東京都",
            "birth_place": "東京都",
            "timezone": "Asia/Tokyo",
            "gender": "unknown",
        },
        "product": {
            "type": "personal_ai_astrology_yaml",
            "options": {
                "western_natal": True,
                "asteroids": include_asteroids,
                "transit": include_transit,
                "shichusuimei": False,
            },
        },
        "systems": {"western": western},
    }


def _generated_long_term_doc() -> dict:
    doc = _base_doc()
    doc["systems"]["western"]["transit"] = {
        "period": {"start_date": "2026-05-01", "days": 365},
        "daily": [{"date": "2026-05-01", "natal_aspects": []}],
    }
    return doc


class LongTermTransitAddonChartTest(unittest.TestCase):
    def test_basic_source_builds_integrated_chart_for_normal_chart_page(self) -> None:
        with patch("routes.build_product_yaml", return_value=("", "", _generated_long_term_doc())):
            _, _, _, chart_yaml_text, _, chart_doc = _build_long_term_transits_addon_from_base(
                _base_doc(),
                transit_start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )
        chart = {
            "options": chart_doc["product"]["options"],
            "yaml_text": chart_yaml_text,
            "share_yaml_text": None,
        }

        self.assertTrue(has_long_term_transits(doc=chart_doc))
        self.assertEqual(chart_doc["product"]["options"]["product_type"], "western_long_term_transits_addon")

        share_doc = yaml.safe_load(_chart_share_yaml_text(chart, doc=chart_doc))
        western_share = share_doc["systems"]["western"]
        self.assertIsNotNone(western_share["natal"])
        self.assertIsNotNone(western_share["transit_long_term"])

    def test_full_source_preserves_existing_transit_and_asteroids(self) -> None:
        with patch("routes.build_product_yaml", return_value=("", "", _generated_long_term_doc())):
            _, _, _, chart_yaml_text, _, chart_doc = _build_long_term_transits_addon_from_base(
                _base_doc(include_transit=True, include_asteroids=True),
                transit_start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )
        chart = {
            "options": chart_doc["product"]["options"],
            "yaml_text": chart_yaml_text,
            "share_yaml_text": None,
        }

        self.assertTrue(_chart_has_31day_transit(chart, doc=chart_doc))
        self.assertTrue(_chart_has_western_asteroids(chart, doc=chart_doc))
        self.assertTrue(has_long_term_transits(doc=chart_doc))

        share_doc = yaml.safe_load(_chart_share_yaml_text(chart, doc=chart_doc))
        western_share = share_doc["systems"]["western"]
        self.assertIsNotNone(western_share["asteroids"])
        self.assertIsNotNone(western_share["transit"])
        self.assertIsNotNone(western_share["transit_long_term"])


if __name__ == "__main__":
    unittest.main()
