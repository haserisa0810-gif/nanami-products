import unittest
from datetime import datetime, timedelta, timezone

import yaml

from routes import _chart_prompt_text
from services.prompt_builder import TRANSIT_DATE_GUIDANCE, WESTERN_FULL_PROMPT, ensure_transit_date_guidance
from services.yaml_exporter import TRANSIT_31DAYS_ADDON_PROMPT


class TransitPromptDateGuidanceTest(unittest.TestCase):
    def test_transit_prompts_treat_selected_date_as_the_current_date(self):
        for prompt in (WESTERN_FULL_PROMPT, TRANSIT_31DAYS_ADDON_PROMPT):
            with self.subTest(prompt=prompt[:30]):
                self.assertIn("today.selected_date を基準日として扱い", prompt)
                self.assertIn("「今後の予定」ではなく「過去の流れ・振り返り」", prompt)
                self.assertIn("today.selected_date 以降の日付を優先", prompt)
                self.assertIn("過去日を無理に未来の予定として書かず", prompt)
                self.assertIn("today と next_few_days を優先", prompt)

    def test_old_saved_full_prompt_is_updated_when_loaded_for_display(self):
        doc = {
            "systems": {
                "western": {
                    "natal": {"bodies": {"Sun": {}}},
                    "transit": {"period": {"days": 31}, "daily": [{}] * 31},
                }
            }
        }
        chart = {
            "options": {"western_natal": True, "transit": True, "product_type": "western_full"},
            "yaml_text": yaml.safe_dump(doc),
            "prompt_text": "重要ルール:\n- 古いルール\n\n出力してほしい内容:\n- 全体像\n\n以下のYAMLを読み込んで鑑定してください。",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        }

        updated_prompt = _chart_prompt_text(chart, doc=doc)

        for line in TRANSIT_DATE_GUIDANCE:
            self.assertIn(line, updated_prompt)
        self.assertLess(updated_prompt.index(TRANSIT_DATE_GUIDANCE[0]), updated_prompt.index("出力してほしい内容:"))

    def test_non_transit_prompt_is_not_updated_when_loaded_for_display(self):
        chart = {
            "options": {"western_natal": True, "transit": False, "product_type": "western_basic"},
            "yaml_text": yaml.safe_dump({"systems": {"western": {"natal": {"bodies": {"Sun": {}}}}}}),
            "prompt_text": "出生図プロンプト",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        }

        self.assertEqual(_chart_prompt_text(chart), "出生図プロンプト")

    def test_guidance_is_not_duplicated(self):
        updated = ensure_transit_date_guidance(WESTERN_FULL_PROMPT)

        for line in TRANSIT_DATE_GUIDANCE:
            self.assertEqual(updated.count(line), 1)


if __name__ == "__main__":
    unittest.main()
