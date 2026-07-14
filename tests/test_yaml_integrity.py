from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from routes import chart_yaml
from services.light_yaml import build_detail_astrology_yaml, build_light_astrology_yaml
from services.prompt_builder import build_prompt
from services.yaml_exporter import build_product_yaml, validate_yaml_option_section_consistency


COMMON_ARGS = {
    "title": "Integrity Test",
    "birth_date": "2000-01-01",
    "birth_time": "12:00",
    "prefecture": "東京都",
    "birth_place_label": "東京都",
    "birth_lat": 35.6895,
    "birth_lng": 139.6917,
    "tz_name": "Asia/Tokyo",
}


class YamlIntegrityTest(unittest.TestCase):
    def test_transit_slow_body_natal_house_is_stable_for_38_days(self) -> None:
        _yaml_text, _prompt_text, doc = build_product_yaml(
            **COMMON_ARGS,
            include_asteroids=False,
            include_transit=True,
            transit_start_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
            transit_days=38,
        )
        daily = doc["systems"]["western"]["transit"]["daily"]

        for body_name in ("Saturn", "Pluto"):
            houses = {day["transiting_bodies"][body_name]["natal_house"] for day in daily}
            self.assertEqual(len(houses), 1, body_name)
            self.assertNotIn(None, houses)
            for day in daily:
                body = day["transiting_bodies"][body_name]
                self.assertNotIn("house", body)
                self.assertIn("mundane_house", body)

    def test_variant_options_match_western_sections(self) -> None:
        variants = [
            build_product_yaml(**COMMON_ARGS, include_asteroids=False, include_transit=False)[2],
            build_product_yaml(**COMMON_ARGS, include_asteroids=True, include_transit=False)[2],
            build_product_yaml(**COMMON_ARGS, include_asteroids=True, include_transit=True)[2],
        ]

        for doc in variants:
            validate_yaml_option_section_consistency(doc)
            options = doc["product"]["options"]
            western = doc["systems"]["western"]
            self.assertEqual(bool(options["asteroids"]), bool(western["asteroids"]))
            self.assertEqual(bool(options["transit"]), bool(western["transit"]))

    def test_consistency_validator_rejects_option_section_mismatch(self) -> None:
        doc = build_product_yaml(**COMMON_ARGS, include_asteroids=False, include_transit=False)[2]
        doc["product"]["options"]["asteroids"] = True

        with self.assertRaises(ValueError):
            validate_yaml_option_section_consistency(doc)

    def test_transit_prompt_mentions_asteroids_only_when_included(self) -> None:
        without_asteroids = build_prompt(include_asteroids=False, include_transit=True)
        with_asteroids = build_prompt(include_asteroids=True, include_transit=True)

        self.assertNotIn("小惑星", without_asteroids)
        self.assertIn("小惑星", with_asteroids)
        self.assertIn("natal_house", without_asteroids)
        self.assertIn("mundane_house", without_asteroids)

    def test_all_generated_prompts_include_acg_consultation_guidance(self) -> None:
        prompts = (
            build_prompt(),
            build_prompt(include_shichusuimei=True),
            build_prompt(include_transit=True),
            build_prompt(include_asteroids=True, include_transit=True),
        )

        for prompt in prompts:
            self.assertIn("【相談モード（ACG連携）】", prompt)
            self.assertIn("https://chart.nanami-astro.com/acg", prompt)
            self.assertIn("ACGアプリへ貼り付ける占術YAMLをこの会話に表示しますか？", prompt)
            self.assertIn("要約・再計算・書き換えせず", prompt)
            self.assertIn("元のYAMLを正確に参照できない場合は再構成や推測をせず", prompt)
            self.assertIn("ACGアプリから出力されたYAMLを会話へ貼り付けて", prompt)
            self.assertIn("出生図・現在のトランジット・相談内容", prompt)
            self.assertEqual(prompt.count("https://chart.nanami-astro.com/acg"), 1)

    def test_light_detail_full_variants_preserve_addon_role_and_variant(self) -> None:
        _full_yaml, _prompt_text, full_doc = build_product_yaml(
            **COMMON_ARGS,
            include_asteroids=True,
            include_transit=True,
            transit_start_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
            transit_days=38,
            data_role="addon",
        )
        lite = yaml.safe_load(build_light_astrology_yaml(_full_yaml, doc=full_doc))
        detail = yaml.safe_load(build_detail_astrology_yaml(_full_yaml))

        for name, doc in (("lite", lite), ("detail", detail), ("full", full_doc)):
            self.assertEqual(doc["meta"]["yaml_variant"], name)
            self.assertEqual(doc["meta"]["data_role"], "addon")

    def test_light_yaml_normalizes_addon_type_to_addon_role(self) -> None:
        full_yaml, _prompt_text, full_doc = build_product_yaml(
            **COMMON_ARGS,
            include_asteroids=True,
            include_transit=True,
            transit_start_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
            transit_days=38,
        )
        full_doc["meta"]["addon_type"] = "western_31days_transit"
        full_doc["meta"]["data_role"] = "base_chart"

        light_yaml = yaml.safe_dump(full_doc, allow_unicode=True, sort_keys=False)
        light = yaml.safe_load(
            build_detail_astrology_yaml(
                light_yaml,
                current_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")).date(),
            )
        )
        self.assertEqual(light["meta"]["data_role"], "addon")
        self.assertEqual(light["meta"]["addon_type"], "western_31days_transit")

    def test_lite_natal_aspects_only_reference_output_bodies_and_keep_sun_moon(self) -> None:
        chart_args = {
            **COMMON_ARGS,
            "birth_date": "2000-05-18",
            "birth_time": "11:00",
        }
        full_yaml, _prompt_text, full_doc = build_product_yaml(
            **chart_args,
            include_asteroids=True,
            include_transit=True,
            transit_start_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
            transit_days=38,
        )
        lite = yaml.safe_load(build_light_astrology_yaml(full_yaml, doc=full_doc))
        natal = lite["systems"]["western"]["natal"]
        body_names = set(natal["bodies"])
        aspects = natal["aspects"]["items"]

        self.assertTrue(aspects)
        for aspect in aspects:
            self.assertIn(aspect["body1"], body_names)
            self.assertIn(aspect["body2"], body_names)
        self.assertTrue(
            any(
                {aspect["body1"], aspect["body2"]} == {"Sun", "Moon"}
                and aspect["aspect"] == "opposition"
                and 2.5 <= float(aspect["orb"]) <= 2.8
                for aspect in aspects
            )
        )

    def test_chart_yaml_route_returns_complete_full_yaml_not_transit_only(self) -> None:
        from unittest.mock import patch

        _yaml_text, _prompt_text, doc = build_product_yaml(
            **COMMON_ARGS,
            include_asteroids=True,
            include_transit=True,
            transit_start_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
            transit_days=38,
            data_role="addon",
        )
        doc["meta"]["addon_type"] = "western_31days_transit"
        stored_yaml = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
        chart = {"yaml_text": stored_yaml, "options": doc["product"]["options"]}

        with patch("routes._load_chart_or_404", return_value=chart):
            response = chart_yaml("test-token")

        loaded = yaml.safe_load(response.body.decode("utf-8"))
        western = loaded["systems"]["western"]
        self.assertEqual(loaded["meta"]["yaml_variant"], "full")
        self.assertEqual(loaded["meta"]["data_role"], "addon")
        self.assertIsNotNone(western["natal"])
        self.assertIsNotNone(western["asteroids"])
        self.assertIsNotNone(western["transit"])

    def test_validator_rejects_addon_type_with_base_chart_role(self) -> None:
        doc = build_product_yaml(
            **COMMON_ARGS,
            include_asteroids=True,
            include_transit=True,
            transit_start_date=datetime(2026, 7, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
            transit_days=38,
        )[2]
        doc["meta"]["addon_type"] = "western_31days_transit"
        doc["meta"]["data_role"] = "base_chart"

        with self.assertRaises(ValueError):
            validate_yaml_option_section_consistency(doc)


if __name__ == "__main__":
    unittest.main()
