from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import yaml

from routes import (
    LONG_TERM_TRANSITS_ADDON_CHART_PROMPT,
    _build_long_term_transits_addon_from_base,
    _chart_has_31day_transit,
    _chart_has_western_asteroids,
    _chart_share_yaml_text,
)
from services.light_yaml import build_light_astrology_yaml
from services.long_term_transit_yaml import build_ai_long_term_transits_yaml, build_long_term_transits_yaml, has_long_term_transits
from services.yaml_exporter import (
    LONG_TERM_TRANSIT_AUXILIARY_BODIES,
    LONG_TERM_TRANSIT_PRIMARY_BODIES,
    _build_long_term_transit_block,
    _build_transit_block,
)


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


def _samples_long_term_doc() -> dict:
    doc = _base_doc(include_asteroids=True)
    start = date(2028, 8, 10)
    samples = []
    for index in range(8):
        day = (start + timedelta(days=index * 7)).isoformat()
        samples.append({
            "date": day,
            "transiting_bodies": {
                "Jupiter": {"sign": "Lib", "degree": 10 + index, "retrograde": index >= 4},
                "Saturn": {"sign": "Tau", "degree": 20 + index, "retrograde": False},
                "Mars": {"sign": "Leo", "degree": 5 + index, "retrograde": False},
            },
            "natal_aspects": [
                {"transit_body": "Jupiter", "natal_body": "Sun", "aspect": "sextile", "orb": max(0.05, 0.8 - index * 0.1)},
                {"transit_body": "Saturn", "natal_body": "Moon", "aspect": "square", "orb": 0.4 + index * 0.05},
                {"transit_body": "Mars", "natal_body": "Venus", "aspect": "trine", "orb": 0.2},
            ],
        })
    doc["systems"]["western"]["transit_long_term"] = {
        "period": {
            "start_date": "2028-08-10",
            "end_date": "2028-09-28",
            "days": 50,
            "sample_interval_days": 7,
            "primary_bodies": ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"],
            "auxiliary_bodies": ["Chiron", "North Node", "South Node"],
        },
        "samples": samples,
    }
    doc["product"]["options"]["western_long_term_transits"] = True
    return doc


class LongTermTransitAddonChartTest(unittest.TestCase):
    @patch("services.yaml_exporter.calc_western_from_payload")
    def test_long_term_block_uses_weekly_outer_planet_samples_without_moon_timepoints(self, calc_western) -> None:
        calc_western.return_value = {
            "planets": [
                {"name": "Moon", "sign": "Ari", "degree": 1, "lon": 1},
                {"name": "Jupiter", "sign": "Can", "degree": 2, "lon": 92},
                {"name": "Saturn", "sign": "Ari", "degree": 3, "lon": 3},
                {"name": "Chiron", "sign": "Ari", "degree": 4, "lon": 4},
                {"name": "North Node", "sign": "Pis", "degree": 5, "lon": 335},
            ]
        }

        block = _build_long_term_transit_block(
            start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            days=365,
            lat=35.0,
            lng=139.0,
            pref_name="東京都",
            tz_name="Asia/Tokyo",
            natal_bodies={"Sun": {"absolute_longitude": 92}},
            natal_houses={"1": {"absolute_longitude": 0}},
        )

        self.assertEqual(len(block["samples"]), 53)
        self.assertEqual(calc_western.call_count, 53)
        self.assertEqual(block["period"]["sample_interval_days"], 7)
        self.assertEqual(block["period"]["primary_bodies"], LONG_TERM_TRANSIT_PRIMARY_BODIES)
        self.assertEqual(block["period"]["auxiliary_bodies"], LONG_TERM_TRANSIT_AUXILIARY_BODIES)
        self.assertNotIn("daily", block)
        self.assertNotIn("moon_timepoints", block["period"])
        self.assertNotIn("Moon", block["samples"][0]["transiting_bodies"])
        self.assertIn("Jupiter", block["samples"][0]["transiting_bodies"])
        self.assertIn("Chiron", block["samples"][0]["transiting_bodies"])

    @patch("services.yaml_exporter.calc_western_from_payload")
    def test_standard_31day_block_keeps_daily_moon_timepoints(self, calc_western) -> None:
        calc_western.return_value = {
            "planets": [
                {"name": "Moon", "sign": "Ari", "degree": 1, "lon": 1},
                {"name": "Jupiter", "sign": "Can", "degree": 2, "lon": 92},
            ]
        }

        block = _build_transit_block(
            start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            days=31,
            lat=35.0,
            lng=139.0,
            pref_name="東京都",
            tz_name="Asia/Tokyo",
            natal_bodies={"Sun": {"absolute_longitude": 92}},
            natal_houses={"1": {"absolute_longitude": 0}},
        )

        self.assertEqual(len(block["daily"]), 31)
        self.assertEqual(calc_western.call_count, 124)
        self.assertEqual(len(block["daily"][0]["moon_timepoints"]), 3)

    def test_prompt_explains_weekly_samples_and_body_priority(self) -> None:
        self.assertIn("約7日間隔", LONG_TERM_TRANSITS_ADDON_CHART_PROMPT)
        self.assertIn("Jupiter", LONG_TERM_TRANSITS_ADDON_CHART_PROMPT)
        self.assertIn("Chiron", LONG_TERM_TRANSITS_ADDON_CHART_PROMPT)

    def test_basic_source_builds_integrated_chart_for_normal_chart_page(self) -> None:
        with patch("routes.build_product_yaml", return_value=("", "", _generated_long_term_doc())) as build_product_yaml:
            _, _, _, chart_yaml_text, _, chart_doc = _build_long_term_transits_addon_from_base(
                _base_doc(),
                transit_start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )
        self.assertEqual(build_product_yaml.call_args.kwargs["transit_profile"], "long_term")
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

    def test_ai_share_yaml_compacts_long_term_samples_to_items(self) -> None:
        doc = _samples_long_term_doc()
        light_yaml = build_light_astrology_yaml(doc=doc, include_asteroids=True)
        light_doc = yaml.safe_load(light_yaml)
        long_term = light_doc["systems"]["western"]["transit_long_term"]

        self.assertIn("items", long_term)
        self.assertNotIn("samples", long_term)
        self.assertLess(len(light_yaml.encode("utf-8")), 50000)
        self.assertTrue(long_term["items"])
        self.assertTrue(all(item["transiting_body"] in {"Jupiter", "Saturn"} for item in long_term["items"]))
        self.assertTrue(all("interpretation_hint" in item for item in long_term["items"]))
        self.assertTrue(any(item.get("retrograde", {}).get("any") for item in long_term["items"]))

    def test_ai_and_full_long_term_yaml_are_separate_outputs(self) -> None:
        doc = _samples_long_term_doc()
        full_doc = yaml.safe_load(build_long_term_transits_yaml(doc=doc))
        ai_yaml = build_ai_long_term_transits_yaml(doc=doc)
        ai_doc = yaml.safe_load(ai_yaml)

        full_long_term = full_doc["systems"]["western"]["transit_long_term"]
        ai_long_term = ai_doc["systems"]["western"]["transit_long_term"]
        self.assertIn("samples", full_long_term)
        self.assertIn("items", ai_long_term)
        self.assertNotIn("samples", ai_long_term)
        self.assertLess(len(ai_yaml.encode("utf-8")), len(yaml.safe_dump(full_doc, allow_unicode=True, sort_keys=False).encode("utf-8")))


if __name__ == "__main__":
    unittest.main()
