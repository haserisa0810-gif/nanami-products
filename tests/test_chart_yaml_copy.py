from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from routes import I18N
from services.light_yaml import build_detail_astrology_yaml
from tests.test_light_yaml_transit_summary import _asteroid_dense_full_doc


class ChartYamlCopyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = Path("templates/chart_page.html").read_text(encoding="utf-8")

    def test_yaml_only_copy_has_japanese_and_english_labels(self) -> None:
        self.assertEqual(I18N["ja"]["yaml_only_title"], "AI活用向けYAML")
        self.assertEqual(I18N["en"]["yaml_only_title"], "YAML for AI use")
        self.assertIn("占いプロンプトを含まない", I18N["ja"]["copy_yaml_only_hint"])
        self.assertIn("without the astrology reading prompt", I18N["en"]["copy_yaml_only_hint"])

    def test_yaml_only_copy_does_not_build_prompt_wrapped_ai_text(self) -> None:
        function = self.template.split("async function copyYamlOnly()", 1)[1].split(
            "async function copySelectedAiChunk()", 1
        )[0]

        self.assertIn("await writeClipboard(yaml, UI_TEXT.yamlOnlyCopied)", function)
        self.assertNotIn("buildSelectedAiText", function)
        self.assertNotIn("buildAiTextFromYaml", function)
        self.assertNotIn("COMBINED_PROMPT", function)

    def test_yaml_only_copy_uses_selected_product_yaml(self) -> None:
        self.assertIn("const yaml = await getSelectedYaml();", self.template)
        self.assertIn('onclick="copyYamlOnly()"', self.template)

    def test_detailed_products_default_to_available_detailed_yaml(self) -> None:
        self.assertIn(
            "selectAiMode(HAS_YAML_MODE_SELECTOR ? (HAS_WESTERN_ASTEROIDS ? 'asteroids' : 'full') : 'paste');",
            self.template,
        )

    def test_yaml_only_button_is_independent_from_fallback_actions(self) -> None:
        fallback = self.template.split('<details class="fallback-share"', 1)[1].split("</details>", 1)[0]
        yaml_panel = self.template.split('<section class="yaml-only-panel"', 1)[1].split("</section>", 1)[0]

        self.assertNotIn('onclick="copyYamlOnly()"', fallback)
        self.assertIn('onclick="copyYamlOnly()"', yaml_panel)
        self.assertIn(".yaml-only-panel .secondary-action {\n      width: 100%;", self.template)

    def test_detail_data_selector_is_available_to_standard_products(self) -> None:
        detail_start = self.template.index('<details class="detail-box" id="detail-box">')
        preceding = self.template[max(0, detail_start - 50):detail_start]

        self.assertNotIn("{% if has_yaml_mode_selector %}", preceding)
        self.assertIn('id="mode-paste-card"', self.template)
        self.assertIn('id="mode-paste-input"', self.template)

    def test_only_available_detailed_modes_are_rendered(self) -> None:
        selector = self.template.split('<div class="ai-mode-list"', 1)[1].split("</div>\n            <div class=\"detail-actions\">", 1)[0]

        self.assertIn("{% if has_yaml_mode_selector %}", selector)
        self.assertIn("{% if has_western_asteroids %}", selector)

    def test_detail_and_yaml_labels_avoid_full_only_wording(self) -> None:
        self.assertEqual(I18N["ja"]["details"], "詳細データ・AI活用")
        self.assertEqual(I18N["en"]["details"], "Detailed data and AI use")
        self.assertNotIn("FULL", I18N["ja"]["details"])
        self.assertNotIn("FULL", I18N["ja"]["full_details_title_asteroids"])

    def test_full_detail_yaml_contains_product_data_without_reading_prompt(self) -> None:
        full_yaml = yaml.safe_dump(_asteroid_dense_full_doc(), allow_unicode=True, sort_keys=False)
        detail_yaml = build_detail_astrology_yaml(full_yaml)
        detail_doc = yaml.safe_load(detail_yaml)
        western = detail_doc["systems"]["western"]

        self.assertTrue(western["asteroids"])
        self.assertTrue(western["transit"]["next_31_days_summary"])
        self.assertNotIn("あなたは西洋占星術の鑑定者です", detail_yaml)

    def test_fallback_actions_keep_existing_mobile_friendly_grid(self) -> None:
        self.assertIn('<div class="fallback-actions">', self.template)
        self.assertIn(".fallback-share .fallback-actions {\n      display: grid;", self.template)


if __name__ == "__main__":
    unittest.main()
