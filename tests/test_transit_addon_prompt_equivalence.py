from __future__ import annotations

import datetime
import os
import unittest
from zoneinfo import ZoneInfo

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")

from services.yaml_exporter import (
    build_31days_transit_addon_yaml,
    build_product_yaml,
    build_prompt_for_doc,
)

TRANSIT_START = datetime.datetime(2026, 9, 1, tzinfo=ZoneInfo("Asia/Tokyo"))

# (birth_time, birth_time_accuracy)
BIRTH_CASES = [
    ("12:34", "exact"),
    (None, "auto"),          # -> unknown に正規化される
    ("07:00", "approximate"),
    (None, "unknown"),
    ("21:15", "auto"),       # -> exact に正規化される
    ("03:00", "morning"),
]


class TransitAddonPromptEquivalenceTest(unittest.TestCase):
    """
    トランジットaddonの鑑定プロンプトは、天体計算をやり直さずに組み立てられる。

    build_prompt() は出生時刻の精度とセクションの有無だけで決まるため、
    build_product_yaml() をフル実行して得ていた文字列と一致しなければならない。
    """

    def test_prompt_matches_full_recomputation(self) -> None:
        for birth_time, accuracy in BIRTH_CASES:
            for include_asteroids in (True, False):
                with self.subTest(birth_time=birth_time, accuracy=accuracy,
                                  include_asteroids=include_asteroids):
                    args = dict(
                        title="t",
                        birth_date="1988-11-23",
                        birth_time=birth_time,
                        prefecture="大阪府",
                        tz_name="Asia/Tokyo",
                        gender="male",
                        birth_time_accuracy=accuracy,
                    )
                    _yaml_text, expected_prompt, _doc = build_product_yaml(
                        **args,
                        include_asteroids=include_asteroids,
                        include_shichusuimei=False,
                        include_transit=True,
                        transit_start_date=TRANSIT_START,
                        transit_days=38,
                    )
                    _addon_yaml, _addon_prompt, addon_doc = build_31days_transit_addon_yaml(
                        **args,
                        transit_start_date=TRANSIT_START,
                        transit_days=38,
                    )
                    actual_prompt = build_prompt_for_doc(
                        addon_doc,
                        include_asteroids=include_asteroids,
                        include_transit=True,
                    )
                    self.assertEqual(actual_prompt, expected_prompt)


if __name__ == "__main__":
    unittest.main()
