from __future__ import annotations

import unittest

from routes import _build_birth_location
from services.location import resolve_municipality


class BirthLocationTest(unittest.TestCase):
    def test_domestic_prefecture_only_uses_prefecture_coordinates(self) -> None:
        location = _build_birth_location(
            prefecture="東京都",
            birth_place_kind="domestic",
            birth_place_overseas="",
            birth_place_city="",
            birth_lat="",
            birth_lng="",
            birth_timezone="",
        )

        self.assertEqual(location["kind"], "domestic")
        self.assertEqual(location["prefecture"], "東京都")
        self.assertEqual(location["birth_place"], "東京都")
        self.assertEqual(location["lat"], 35.68950)
        self.assertEqual(location["lng"], 139.69170)
        self.assertEqual(location["tz_name"], "Asia/Tokyo")

    def test_domestic_uses_municipality_coordinates_when_city_matches(self) -> None:
        location = _build_birth_location(
            prefecture="東京都",
            birth_place_kind="domestic",
            birth_place_overseas="",
            birth_place_city="新宿区",
            birth_lat="",
            birth_lng="",
            birth_timezone="",
        )

        self.assertEqual(location["birth_place"], "東京都 新宿区")
        self.assertEqual(location["lat"], 35.701835)
        self.assertEqual(location["lng"], 139.716810)

    def test_domestic_uses_coordinates_when_both_are_entered(self) -> None:
        location = _build_birth_location(
            prefecture="東京都",
            birth_place_kind="domestic",
            birth_place_overseas="",
            birth_place_city="新宿区",
            birth_lat="35.6895",
            birth_lng="139.6917",
            birth_timezone="",
        )

        self.assertEqual(location["lat"], 35.6895)
        self.assertEqual(location["lng"], 139.6917)

    def test_domestic_unknown_city_falls_back_to_prefecture_coordinates(self) -> None:
        location = _build_birth_location(
            prefecture="東京都",
            birth_place_kind="domestic",
            birth_place_overseas="",
            birth_place_city="存在しない市",
            birth_lat="",
            birth_lng="",
            birth_timezone="",
        )

        self.assertEqual(location["birth_place"], "東京都 存在しない市")
        self.assertEqual(location["lat"], 35.68950)
        self.assertEqual(location["lng"], 139.69170)

    def test_generated_municipality_csv_contains_major_city_wards(self) -> None:
        cases = [
            ("東京都", "足立区"),
            ("神奈川県", "川崎市高津区"),
            ("大阪府", "大阪市北区"),
            ("北海道", "札幌市中央区"),
        ]

        for prefecture, city in cases:
            with self.subTest(prefecture=prefecture, city=city):
                self.assertIsNotNone(resolve_municipality(prefecture, city))

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
