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
        self.assertEqual(I18N["ja"]["copy_yaml_only"], "選んだ版のYAMLをコピー")
        self.assertEqual(I18N["en"]["copy_yaml_only"], "Copy selected version YAML")
        self.assertIn("占いプロンプトを含まない", I18N["ja"]["copy_yaml_only_hint"])
        self.assertIn("without the astrology reading prompt", I18N["en"]["copy_yaml_only_hint"])

    def test_yaml_only_copy_does_not_build_prompt_wrapped_ai_text(self) -> None:
        function = self.template.split("async function copyYamlOnly()", 1)[1].split(
            "async function copySelectedAiChunk()", 1
        )[0]

        self.assertIn("await writeClipboard(yaml, message, { kind:", function)
        self.assertNotIn("buildSelectedAiText", function)
        self.assertNotIn("buildAiTextFromYaml", function)
        self.assertNotIn("COMBINED_PROMPT", function)

    def test_yaml_only_copy_uses_selected_product_yaml(self) -> None:
        self.assertIn("const yaml = HAS_LONG_TERM_TRANSITS ? getYamlOnlyCopyText() : await getSelectedYaml();", self.template)
        self.assertIn('onclick="copyYamlOnly()"', self.template)

    def test_long_term_yaml_only_copy_uses_light_ai_yaml_and_label(self) -> None:
        self.assertIn("function getYamlOnlyCopyText()", self.template)
        self.assertIn("if (HAS_LONG_TERM_TRANSITS) return SHARE_YAML;", self.template)
        self.assertIn("yamlOnlyCopiedLongTerm", self.template)
        self.assertIn("copy_yaml_only_long_term", self.template)
        self.assertIn("copy_yaml_only_hint_long_term", self.template)

    def test_detailed_products_default_to_available_detailed_yaml(self) -> None:
        self.assertIn(
            "selectAiMode(HAS_YAML_MODE_SELECTOR ? (HAS_WESTERN_ASTEROIDS ? 'asteroids' : 'full') : 'paste');",
            self.template,
        )

    def test_yaml_only_button_is_inside_detail_data_not_send_to_ai(self) -> None:
        send_to_ai = self.template.split('<section class="notice-box">', 1)[1].split("</section>", 1)[0]
        fallback = self.template.split('<details class="fallback-share"', 1)[1].split("</details>", 1)[0]
        detail_box = self.template.split('<details class="detail-box" id="detail-box">', 1)[1].split("</details>", 1)[0]
        yaml_panel = self.template.split('<section class="yaml-only-panel"', 1)[1].split("</section>", 1)[0]

        self.assertNotIn('onclick="copyYamlOnly()"', send_to_ai)
        self.assertNotIn('onclick="copyYamlOnly()"', fallback)
        self.assertIn('<section class="yaml-only-panel"', detail_box)
        self.assertIn('onclick="copyYamlOnly()"', yaml_panel)
        self.assertIn(".yaml-only-panel .secondary-action {\n      width: 100%;", self.template)

    def test_write_clipboard_emits_debug_metadata_when_enabled(self) -> None:
        function = self.template.split("async function writeClipboard(text, message = UI_TEXT.copied, debugInfo = {})", 1)[1].split(
            "function getSelectedAiMode", 1
        )[0]

        self.assertIn("debugShare('clipboard', debugPayload);", function)
        self.assertIn("navigatorClipboard", function)
        self.assertIn("execCommandResult", function)

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

    def test_ai_share_and_fallback_controls_are_always_visible(self) -> None:
        self.assertIn('<button class="primary-action" id="primary-ai-action" onclick="shareDefaultAiText()">', self.template)
        self.assertIn('<details class="fallback-share" id="fallback-share">', self.template)
        self.assertNotIn("primaryAction.hidden", self.template)
        self.assertNotIn("fallbackShare.hidden", self.template)
        self.assertNotIn("setDirectShareAvailable", self.template)

    def test_zip_download_uses_regular_link(self) -> None:
        self.assertIn('<a class="download-primary" id="zip-download-button" href="{{ download_zip_url }}" download>', self.template)
        self.assertNotIn("downloadFullArchiveZip", self.template)
        self.assertNotIn("downloadZipFromUrl", self.template)
        self.assertNotIn("fetchZipBlob", self.template)

    def test_can_share_files_is_not_used_for_text_share_support(self) -> None:
        text_share_fn = self.template.split("function canUseTextShare()", 1)[1].split(
            "function buildAiTextFileName", 1
        )[0]

        self.assertIn("typeof navigator.share === 'function'", text_share_fn)
        self.assertNotIn("navigator.canShare", text_share_fn)

    def test_share_cancel_does_not_open_fallback(self) -> None:
        share_payload_fn = self.template.split("async function shareAiTextPayload", 1)[1].split(
            "async function shareSelectedAiText", 1
        )[0]

        self.assertIn("if (isShareAbort(e)) return;", share_payload_fn)
        self.assertIn("showShareFallback(getShareFallbackMessage(shareText));", share_payload_fn)


if __name__ == "__main__":
    unittest.main()
