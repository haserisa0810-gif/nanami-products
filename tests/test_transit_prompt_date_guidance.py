import unittest

from services.prompt_builder import WESTERN_FULL_PROMPT
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


if __name__ == "__main__":
    unittest.main()
