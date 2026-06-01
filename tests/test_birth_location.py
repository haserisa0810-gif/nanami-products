from __future__ import annotations

import unittest

from routes import _build_birth_location


class BirthLocationTest(unittest.TestCase):
    def test_domestic_prefecture_can_omit_coordinates(self) -> None:
        location = _build_birth_location(
            prefecture="東京都",
            birth_place_kind="domestic",
            birth_place_overseas="",
            birth_place_city="新宿区",
            birth_lat="",
            birth_lng="",
            birth_timezone="",
        )

        self.assertEqual(location["kind"], "domestic")
        self.assertEqual(location["prefecture"], "東京都")
        self.assertEqual(location["birth_place"], "東京都 新宿区")
        self.assertIsNone(location["lat"])
        self.assertIsNone(location["lng"])
        self.assertEqual(location["tz_name"], "Asia/Tokyo")

    def test_domestic_uses_coordinates_when_both_are_entered(self) -> None:
        location = _build_birth_location(
            prefecture="東京都",
            birth_place_kind="domestic",
            birth_place_overseas="",
            birth_place_city="",
            birth_lat="35.6895",
            birth_lng="139.6917",
            birth_timezone="",
        )

        self.assertEqual(location["lat"], 35.6895)
        self.assertEqual(location["lng"], 139.6917)

    def test_overseas_requires_coordinates_and_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError, "タイムゾーン"):
            _build_birth_location(
                prefecture="",
                birth_place_kind="overseas",
                birth_place_overseas="New York, USA",
                birth_place_city="",
                birth_lat="40.7128",
                birth_lng="-74.0060",
                birth_timezone="",
            )

        with self.assertRaisesRegex(ValueError, "緯度・経度"):
            _build_birth_location(
                prefecture="",
                birth_place_kind="overseas",
                birth_place_overseas="New York, USA",
                birth_place_city="",
                birth_lat="",
                birth_lng="",
                birth_timezone="America/New_York",
            )


if __name__ == "__main__":
    unittest.main()
