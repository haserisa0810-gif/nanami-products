from __future__ import annotations

import unittest
from datetime import date, timedelta

import yaml

from services.light_yaml import build_detail_astrology_yaml, build_light_astrology_yaml


def _daily_entry(day: date, *, aspect: str = "trine", orb: float = 0.4) -> dict:
    return {
        "date": day.isoformat(),
        "time": "12:00",
        "timezone": "Asia/Tokyo",
        "transiting_bodies": {"Mars": {"sign": "Aries", "absolute_longitude": 10.0}},
        "natal_aspects": [
            {
                "transit_body": "Mars",
                "natal_body": "Sun",
                "aspect": aspect,
                "orb": orb,
                "transit_longitude": 10.0,
                "natal_longitude": 10.0,
            }
        ],
        "moon_timepoints": [],
    }


def _dense_daily_entry(day: date, *, aspect: str = "square", orb: float = 0.35) -> dict:
    entry = _daily_entry(day, aspect=aspect, orb=orb)
    entry["natal_aspects"] = [
        {
            "transit_body": "Uranus",
            "natal_body": "Venus",
            "aspect": "square",
            "orb": orb,
            "transit_longitude": 45.0,
            "natal_longitude": 135.0,
        },
        {
            "transit_body": "Mars",
            "natal_body": "Sun",
            "aspect": "trine",
            "orb": 0.45,
            "transit_longitude": 10.0,
            "natal_longitude": 10.0,
        },
        {
            "transit_body": "Saturn",
            "natal_body": "Moon",
            "aspect": "opposition",
            "orb": 0.6,
            "transit_longitude": 190.0,
            "natal_longitude": 10.0,
        },
    ]
    return entry


def _full_doc() -> dict:
    start = date(2026, 5, 6)
    daily = []
    for offset in range(31):
        day = start + timedelta(days=offset)
        if offset in {3, 9, 18}:
            daily.append(_daily_entry(day, aspect="square", orb=0.35))
        else:
            daily.append(_daily_entry(day, aspect="trine", orb=0.45))
    return {
        "version": "nanami-products-yaml-v1",
        "generated_at": "2026-05-06T00:00:00+09:00",
        "input": {"birth_date": "2000-01-01", "timezone": "Asia/Tokyo"},
        "product": {"options": {"western_natal": True, "transit": True}},
        "systems": {
            "western": {
                "natal": {
                    "bodies": {"Sun": {"sign": "Aries", "absolute_longitude": 10.0}},
                    "houses": {},
                    "aspects": [],
                    "summary": {},
                },
                "transit": {
                    "period": {
                        "start_date": start.isoformat(),
                        "days": 31,
                        "timezone": "Asia/Tokyo",
                    },
                    "daily": daily,
                },
            }
        },
    }


def _dense_full_doc() -> dict:
    doc = _full_doc()
    start = date(2026, 5, 6)
    doc["systems"]["western"]["transit"]["daily"] = [
        _dense_daily_entry(start + timedelta(days=offset), orb=0.25 + (offset % 5) * 0.05)
        for offset in range(31)
    ]
    return doc


class LightYamlTransitSummaryTest(unittest.TestCase):
    def test_light_yaml_has_non_empty_31day_summary_when_flag_true(self) -> None:
        doc = _full_doc()
        light = yaml.safe_load(build_light_astrology_yaml(doc=doc, current_date=date(2026, 5, 6)))
        transit = light["systems"]["western"]["transit"]

        self.assertTrue(light["product"]["options"]["transit_today"])
        self.assertTrue(light["product"]["options"]["transit_31days_summary"])
        self.assertIsNotNone(transit["today"])
        self.assertNotEqual(transit["next_31_days_summary"], {})
        self.assertEqual(transit["next_31_days_summary"]["period"]["start_date"], "2026-05-06")
        self.assertEqual(transit["next_31_days_summary"]["period"]["end_date"], "2026-06-05")
        self.assertTrue(transit["next_31_days_summary"]["key_dates"])
        self.assertIn("overall_theme", transit["next_31_days_summary"])

    def test_detail_yaml_keeps_today_and_summary_roots(self) -> None:
        detail = yaml.safe_load(build_detail_astrology_yaml(yaml.safe_dump(_full_doc()), current_date=date(2026, 5, 6)))
        transit = detail["systems"]["western"]["transit"]
        summary = transit["next_31_days_summary"]

        self.assertIsNotNone(transit["today"])
        self.assertTrue(summary["period"])
        self.assertTrue(summary["key_periods"] or summary["key_dates"])
        self.assertTrue(summary["action_hints"])

    def test_light_summary_stays_compact(self) -> None:
        light_yaml = build_light_astrology_yaml(doc=_dense_full_doc(), current_date=date(2026, 5, 6))
        light = yaml.safe_load(light_yaml)
        summary = light["systems"]["western"]["transit"]["next_31_days_summary"]

        self.assertLess(len(light_yaml), 18000)
        self.assertLessEqual(len(summary["key_dates"]), 8)
        self.assertLessEqual(len(summary["caution_dates"]), 5)
        self.assertLessEqual(len(summary["easy_to_move_days"]), 5)
        self.assertLessEqual(len(summary["key_aspects"]), 12)
        self.assertEqual(len(summary["key_periods"]), 2)

        for collection_name in ("key_periods", "key_dates", "caution_dates", "easy_to_move_days", "next_few_days"):
            for item in summary[collection_name]:
                self.assertLessEqual(len(item.get("source_aspects") or []), 1, collection_name)

        uranus_periods = [
            item for item in summary["key_periods"]
            if any(aspect.get("transit_body") == "Uranus" for aspect in item.get("source_aspects") or [])
        ]
        self.assertEqual(len(uranus_periods), 1)
        self.assertEqual(uranus_periods[0]["start_date"], "2026-05-06")
        self.assertEqual(uranus_periods[0]["end_date"], "2026-06-05")


if __name__ == "__main__":
    unittest.main()
