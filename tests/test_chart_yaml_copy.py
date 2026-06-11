from __future__ import annotations

import unittest
from pathlib import Path

from routes import I18N


class ChartYamlCopyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = Path("templates/chart_page.html").read_text(encoding="utf-8")

    def test_yaml_only_copy_has_japanese_and_english_labels(self) -> None:
        self.assertEqual(I18N["ja"]["copy_yaml_only"], "YAMLだけコピー")
        self.assertEqual(I18N["en"]["copy_yaml_only"], "Copy YAML only")
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

    def test_yaml_only_copy_uses_complete_product_yaml_for_detailed_pages(self) -> None:
        self.assertIn(
            "HAS_YAML_MODE_SELECTOR ? await getFullYaml() : (FULL_YAML_INLINE || SHARE_YAML)",
            self.template,
        )
        self.assertIn('onclick="copyYamlOnly()"', self.template)

    def test_yaml_only_button_uses_existing_mobile_friendly_action_grid(self) -> None:
        self.assertIn('<div class="fallback-actions">', self.template)
        self.assertIn(".fallback-share .fallback-actions {\n      display: grid;", self.template)


if __name__ == "__main__":
    unittest.main()
