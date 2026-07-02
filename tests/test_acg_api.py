from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import routes
from services import acg_api
from services.acg_api import (
    AcgInputError,
    AcgYamlFormatError,
    natal_dt_utc_from_yaml,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOBUNAGA_YAML = (FIXTURES / "oda_nobunaga_yaml_v1.yaml").read_text(encoding="utf-8")

INPUT_ONLY_YAML = """
version: nanami-products-yaml-v1
input:
  birth_date: "1990-01-15"
  birth_time: "08:30"
  timezone_offset_hours: 9.0
"""


class NatalDtUtcFromYamlTest(unittest.TestCase):
    def test_subject_datetime_with_lmt_seconds_offset(self) -> None:
        """仕様指定の LMT 秒オフセット文字列そのものをテストする。"""
        yaml_text = """
systems:
  western:
    natal:
      subject:
        datetime: "1534-06-23T04:00:00+09:18:59"
"""
        dt = natal_dt_utc_from_yaml(yaml_text)
        self.assertEqual(dt, datetime(1534, 6, 22, 18, 41, 1, tzinfo=timezone.utc))

    def test_subject_datetime_takes_priority_over_input(self) -> None:
        yaml_text = """
input:
  birth_date: "2000-01-01"
  birth_time: "00:00"
  timezone_offset_hours: 0
systems:
  western:
    natal:
      subject:
        datetime: "1990-01-15T08:30:00+09:00"
"""
        dt = natal_dt_utc_from_yaml(yaml_text)
        self.assertEqual(dt, datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc))

    def test_input_block_fallback(self) -> None:
        dt = natal_dt_utc_from_yaml(INPUT_ONLY_YAML)
        self.assertEqual(dt, datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc))

    def test_version_mismatch_is_ok_if_paths_exist(self) -> None:
        yaml_text = """
version: some-other-format
input:
  birth_date: "1990-01-15"
  birth_time: "08:30"
  timezone_offset_hours: 9.0
"""
        dt = natal_dt_utc_from_yaml(yaml_text)
        self.assertEqual(dt.year, 1990)

    def test_rejects_empty(self) -> None:
        with self.assertRaises(AcgYamlFormatError):
            natal_dt_utc_from_yaml("   ")

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(AcgYamlFormatError):
            natal_dt_utc_from_yaml("- just\n- a\n- list\n")

    def test_rejects_missing_birth_info(self) -> None:
        with self.assertRaises(AcgYamlFormatError):
            natal_dt_utc_from_yaml("version: nanami-products-yaml-v1\n")


class MundaneCacheTest(unittest.TestCase):
    def test_same_date_returns_cached_object(self) -> None:
        acg_api._mundane_cache.clear()
        first = acg_api.mundane_geojson("2026-07-02")
        second = acg_api.mundane_geojson("2026-07-02")
        self.assertIs(first, second)

    def test_mundane_uses_0300_utc(self) -> None:
        acg_api._mundane_cache.clear()
        fc = acg_api.mundane_geojson("2026-07-02")
        self.assertEqual(fc["meta"]["datetime_utc"], "2026-07-02T03:00:00+00:00")
        self.assertEqual(fc["meta"]["mode"], "mundane")

    def test_invalid_date_raises(self) -> None:
        with self.assertRaises(AcgInputError):
            acg_api.mundane_geojson("2026/07/02")

    def test_mundane_range_is_ephemeris_range(self) -> None:
        """範囲チェックはマンデン側のみ（sepl_18.se1 系: 1800〜2399年）。"""
        with self.assertRaises(AcgInputError):
            acg_api.mundane_geojson("1799-12-31")
        with self.assertRaises(AcgInputError):
            acg_api.mundane_geojson("2400-01-01")
        acg_api.mundane_geojson("1800-01-01")
        acg_api.mundane_geojson("2399-12-31")


class AcgEndpointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(routes.app)

    def test_mundane_endpoint(self) -> None:
        res = self.client.get("/api/acg/mundane", params={"date": "2026-07-02"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("max-age=86400", res.headers.get("cache-control", ""))
        body = res.json()
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertEqual(body["meta"]["mode"], "mundane")
        groups = {f["properties"]["line_group"] for f in body["features"]}
        self.assertEqual(len(groups), 40)

    def test_mundane_endpoint_bad_date(self) -> None:
        res = self.client.get("/api/acg/mundane", params={"date": "not-a-date"})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["ok"])

    def test_personal_endpoint_nobunaga_yaml(self) -> None:
        """検収基準: 織田信長YAMLで200が返り、40本（分割込みでそれ以上）のFeature。"""
        res = self.client.post("/api/acg/personal", json={"yaml_text": NOBUNAGA_YAML})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["meta"]["mode"], "natal")
        # subject.datetime（LMT）が優先され、UTC変換されている
        self.assertEqual(body["meta"]["datetime_utc"], "1534-06-22T18:41:01+00:00")
        groups = {f["properties"]["line_group"] for f in body["features"]}
        self.assertEqual(len(groups), 40)
        self.assertGreaterEqual(len(body["features"]), 40)
        self.assertIn("no-store", res.headers.get("cache-control", ""))

    def test_personal_endpoint_matches_core_for_same_datetime(self) -> None:
        """検収基準: 同一日時を直接指定した計算出力とMC線経度が一致。"""
        from services.acg_core import lines_to_geojson

        res = self.client.post("/api/acg/personal", json={"yaml_text": NOBUNAGA_YAML})
        api_fc = res.json()
        cli_fc = lines_to_geojson(
            datetime(1534, 6, 22, 18, 41, 1, tzinfo=timezone.utc), natal=True
        )

        def sun_mc_lon(fc: dict) -> float:
            for f in fc["features"]:
                if f["properties"]["line_group"] == "Sun_MC":
                    return f["geometry"]["coordinates"][0][0]
            raise AssertionError("Sun_MC not found")

        self.assertEqual(sun_mc_lon(api_fc), sun_mc_lon(cli_fc))

    def test_personal_endpoint_raw_yaml_body(self) -> None:
        res = self.client.post(
            "/api/acg/personal",
            content=INPUT_ONLY_YAML.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["meta"]["mode"], "natal")

    def test_personal_endpoint_unsupported_yaml_is_422(self) -> None:
        res = self.client.post("/api/acg/personal", json={"yaml_text": "version: 1\n"})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"], "対応していないYAML形式です")

    def test_personal_endpoint_oversized_body_is_413(self) -> None:
        big = "a" * (acg_api.MAX_YAML_BYTES + 1)
        res = self.client.post(
            "/api/acg/personal",
            content=big.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(res.status_code, 413)


if __name__ == "__main__":
    unittest.main()
