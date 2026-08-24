from __future__ import annotations

import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import routes
from services import acg_api
from services.acg_api import (
    ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR,
    ACG_TIMEZONE_NOT_CONFIRMED_ERROR,
    AcgInputError,
    AcgYamlFormatError,
    YAML_AMBIGUOUS_DOCUMENT_ERROR,
    YAML_MISSING_BIRTH_DATA_ERROR,
    natal_dt_utc_from_yaml,
    parse_acg_yaml_document,
    personal_context_from_yaml,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOBUNAGA_YAML = (FIXTURES / "oda_nobunaga_yaml_v1.yaml").read_text(encoding="utf-8")

INPUT_ONLY_YAML = """
version: nanami-products-yaml-v1
input:
  birth_date: "1990-01-15"
  birth_time: "08:30"
  birth_time_accuracy: exact
  birth_place: "Tokyo, Japan"
  timezone: Asia/Tokyo
  timezone_offset_hours: 9.0
"""

CONTEXT_YAML = """
version: nanami-products-yaml-v1
input:
  birth_date: "1990-01-15"
  birth_time: "08:30"
  timezone_offset_hours: 9.0
systems:
  western:
    natal:
      bodies:
        Sun:
          sign: Leo
          house: 5
        Moon:
          sign: Aquarius
          house: 11
        ASC:
          sign: Aries
          house: 1
        MC:
          sign: Capricorn
          house: 10
"""

PROMPT_ENRICHED_YAML = """
input:
  birth_date: "1990-01-15"
  birth_time: "08:30"
  birth_time_accuracy: exact
  birth_place: "Tokyo, Japan"
  timezone: Asia/Tokyo
  timezone_offset_hours: 9.0
assistant_profile:
  name: Chart Companion
  role: 西洋占星術の相談AI
prompt:
  system_instruction: >
    出生図とトランジットを根拠に相談へ回答してください。
consultation_mode:
  enabled: true
  instruction: 旅行や移住の相談ではACGを利用してください。
interpretation_flags:
  avoid_deterministic_language: true
output_instruction:
  format: conversational
related_resources:
  acg_url: https://chart.nanami-astro.com/acg
future_feature:
  description: 将来用の説明
systems:
  western:
    natal:
      subject:
        datetime: "1990-01-15T08:30:00+09:00"
      bodies:
        Sun:
          sign: Capricorn
          absolute_longitude: 294.5
        Moon:
          sign: Virgo
          absolute_longitude: 174.5
    transit:
      selected_date: "2026-07-14"
      note: ACG入力では使用しない
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

    def test_prompt_enriched_yaml_ignores_non_acg_sections(self) -> None:
        doc = parse_acg_yaml_document(PROMPT_ENRICHED_YAML)
        dt = natal_dt_utc_from_yaml(PROMPT_ENRICHED_YAML)

        self.assertNotIn("prompt", doc)
        self.assertNotIn("consultation_mode", doc)
        self.assertEqual(set(doc), {"systems", "input", "birth_time"})
        self.assertEqual(dt, datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc))

    def test_prompt_sections_can_follow_birth_data(self) -> None:
        yaml_text = INPUT_ONLY_YAML + """
prompt:
  system_instruction: この文章はACGでは使用しない
dynamic_resources:
  url: https://example.invalid/never-fetch
"""
        dt = natal_dt_utc_from_yaml(yaml_text)
        self.assertEqual(dt, datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc))

    def test_accepts_complete_markdown_yaml_fences(self) -> None:
        for opening in ("```yaml", "```yml", "```"):
            with self.subTest(opening=opening):
                fenced = f"{opening}\n{INPUT_ONLY_YAML.strip()}\n```"
                self.assertEqual(
                    natal_dt_utc_from_yaml(fenced),
                    datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
                )

    def test_accepts_one_explicit_yaml_fence_with_surrounding_body(self) -> None:
        text = f"コピーしたYAMLです。\n```yaml\n{INPUT_ONLY_YAML.strip()}\n```"
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_accepts_one_explicit_yml_fence_with_surrounding_body(self) -> None:
        text = f"コピーしたYAMLです。\n```yml\n{INPUT_ONLY_YAML.strip()}\n```"
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_accepts_markdown_quoted_prompt_and_yaml(self) -> None:
        quoted_yaml = "\n".join(f"> {line}" for line in INPUT_ONLY_YAML.strip().splitlines())
        text = (
            "AIからコピーした占術データです。\n"
            "> ```yaml\n"
            f"{quoted_yaml}\n"
            "> ```\n"
            "この下はAIの説明文です。"
        )
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_accepts_indented_yaml_after_prompt(self) -> None:
        indented_yaml = textwrap.indent(INPUT_ONLY_YAML.strip(), "    ")
        text = f"プロンプト全文です。\n\n{indented_yaml}\nAIの説明文が続きます。"
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_accepts_unfenced_yaml_with_trailing_ai_text(self) -> None:
        text = INPUT_ONLY_YAML.strip() + "\nこの後はAIが追加した説明文です。"
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_ignores_yaml_like_text_outside_explicit_fence(self) -> None:
        text = (
            "input:\n  birth_date: '1900-01-01'\nこれは説明文です。\n"
            f"```yaml\n{INPUT_ONLY_YAML.strip()}\n```"
        )
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_accepts_unlabelled_fence_with_surrounding_body(self) -> None:
        text = f"コピーしたYAMLです。\n```\n{INPUT_ONLY_YAML.strip()}\n```"
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_multiple_blocks_selects_only_block_with_birth_data(self) -> None:
        text = (
            "参考例です。\n```text\n相談テーマ: 引っ越し\n```\n"
            f"以下が占術データです。\n```yaml\n{INPUT_ONLY_YAML.strip()}\n```"
        )
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_multiple_birth_blocks_are_rejected_as_ambiguous(self) -> None:
        block = f"```yaml\n{INPUT_ONLY_YAML.strip()}\n```"
        with self.assertRaisesRegex(AcgYamlFormatError, YAML_AMBIGUOUS_DOCUMENT_ERROR):
            natal_dt_utc_from_yaml(block + "\n説明\n" + block)

    def test_accepts_prompt_followed_by_raw_yaml_without_fence(self) -> None:
        text = (
            "あなたは占星術師です。次のデータだけを使って読んでください。\n\n"
            "以下がYAMLデータです。\n\n"
            + INPUT_ONLY_YAML.strip()
        )
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_prompt_with_multiple_raw_birth_documents_is_ambiguous(self) -> None:
        text = "説明文です。\n" + INPUT_ONLY_YAML + "\n---\n" + INPUT_ONLY_YAML
        with self.assertRaisesRegex(AcgYamlFormatError, YAML_AMBIGUOUS_DOCUMENT_ERROR):
            natal_dt_utc_from_yaml(text)

    def test_rejects_invalid_yaml_inside_embedded_fence(self) -> None:
        text = "説明文です。\n```yaml\ninput:\n birth_date: [broken\n```"
        with self.assertRaisesRegex(AcgYamlFormatError, "YAMLを解析できません"):
            natal_dt_utc_from_yaml(text)

    def test_multiple_documents_selects_only_birth_document(self) -> None:
        text = """
---
prompt:
  system_instruction: この文書は無視する
---
input:
  birth_date: "1990-01-15"
  birth_time: "08:30"
  timezone_offset_hours: 9
"""
        self.assertEqual(
            natal_dt_utc_from_yaml(text),
            datetime(1990, 1, 14, 23, 30, tzinfo=timezone.utc),
        )

    def test_multiple_birth_documents_are_rejected_as_ambiguous(self) -> None:
        text = INPUT_ONLY_YAML + "\n---\n" + INPUT_ONLY_YAML
        with self.assertRaisesRegex(AcgYamlFormatError, YAML_AMBIGUOUS_DOCUMENT_ERROR):
            natal_dt_utc_from_yaml(text)

    def test_unsafe_yaml_tag_is_rejected_without_execution(self) -> None:
        text = INPUT_ONLY_YAML + "\npayload: !!python/object/apply:os.system ['echo unsafe']\n"
        with patch("os.system") as system_call:
            with self.assertRaisesRegex(AcgYamlFormatError, "YAMLを解析できません"):
                natal_dt_utc_from_yaml(text)
        system_call.assert_not_called()

    def test_excessive_yaml_nesting_is_rejected(self) -> None:
        nested = "root:\n" + "".join("  " * i + f"level_{i}:\n" for i in range(1, 45))
        with self.assertRaisesRegex(AcgYamlFormatError, "YAMLを解析できません"):
            natal_dt_utc_from_yaml(nested)

    def test_rejects_empty(self) -> None:
        with self.assertRaises(AcgYamlFormatError):
            natal_dt_utc_from_yaml("   ")

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(AcgYamlFormatError):
            natal_dt_utc_from_yaml("- just\n- a\n- list\n")

    def test_rejects_missing_birth_info(self) -> None:
        with self.assertRaisesRegex(AcgYamlFormatError, YAML_MISSING_BIRTH_DATA_ERROR):
            natal_dt_utc_from_yaml("version: nanami-products-yaml-v1\n")

    def test_personal_context_extracts_minimal_natal_summary(self) -> None:
        context = personal_context_from_yaml(CONTEXT_YAML)

        self.assertEqual(context["source"], "uploaded_birth_yaml")
        self.assertEqual(context["natal_summary"]["sun"], "Leo 5H")
        self.assertEqual(context["natal_summary"]["moon"], "Aquarius 11H")
        self.assertEqual(context["natal_summary"]["asc"], "Aries")
        self.assertEqual(context["natal_summary"]["mc"], "Capricorn")
        self.assertIn("別途YAML本文", context["note"])


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
        self.assertEqual(body["meta"]["personal_context"]["source"], "uploaded_birth_yaml")
        # subject.datetime（LMT）が優先され、UTC変換されている
        self.assertEqual(body["meta"]["datetime_utc"], "1534-06-22T18:41:01+00:00")
        groups = {f["properties"]["line_group"] for f in body["features"]}
        self.assertEqual(len(groups), 40)
        self.assertGreaterEqual(len(body["features"]), 40)
        basis = body["meta"]["acg_calculation_basis"]
        self.assertTrue(basis["acg_eligible"])
        self.assertEqual(basis["birth_time_status"], "confirmed")
        self.assertEqual(basis["timezone"], "Asia/Tokyo")
        self.assertEqual(basis["birth_datetime_utc"], "1534-06-22T18:41:01Z")
        self.assertIn("no-store", res.headers.get("cache-control", ""))

    def test_personal_endpoint_rejects_unknown_or_provisional_birth_time(self) -> None:
        yaml_text = INPUT_ONLY_YAML.replace(
            "birth_time_accuracy: exact", "birth_time_accuracy: unknown"
        )
        res = self.client.post("/api/acg/personal", json={"yaml_text": yaml_text})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"], ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR)

        provisional = INPUT_ONLY_YAML + """
systems:
  western:
    natal:
      time_sensitive_provisional:
        reason: unknown_birth_time
"""
        res = self.client.post("/api/acg/personal", json={"yaml_text": provisional})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"], ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR)

    def test_personal_endpoint_rejects_missing_timezone_instead_of_jst_fallback(self) -> None:
        yaml_text = INPUT_ONLY_YAML.replace("  timezone: Asia/Tokyo\n", "")
        res = self.client.post("/api/acg/personal", json={"yaml_text": yaml_text})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"], ACG_TIMEZONE_NOT_CONFIRMED_ERROR)

        yaml_text = INPUT_ONLY_YAML.replace("  timezone_offset_hours: 9.0\n", "")
        res = self.client.post("/api/acg/personal", json={"yaml_text": yaml_text})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"], ACG_TIMEZONE_NOT_CONFIRMED_ERROR)

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

    def test_personal_endpoint_accepts_prompt_enriched_yaml(self) -> None:
        res = self.client.post(
            "/api/acg/personal", json={"yaml_text": PROMPT_ENRICHED_YAML}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["meta"]["datetime_utc"], "1990-01-14T23:30:00+00:00")

    def test_personal_endpoint_accepts_fenced_yaml(self) -> None:
        fenced = f"```yaml\n{PROMPT_ENRICHED_YAML.strip()}\n```"
        res = self.client.post("/api/acg/personal", json={"yaml_text": fenced})
        self.assertEqual(res.status_code, 200)

    def test_personal_endpoint_accepts_full_copied_prompt_and_yaml(self) -> None:
        copied = (
            "この出生図を再計算せずに読み解いてください。\n\n---\n\n"
            "以下がYAMLデータです。\n\n"
            f"```yaml\n{PROMPT_ENRICHED_YAML.strip()}\n```\n"
        )
        res = self.client.post("/api/acg/personal", json={"yaml_text": copied})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["meta"]["datetime_utc"], "1990-01-14T23:30:00+00:00")

    def test_personal_endpoint_unsupported_yaml_is_422(self) -> None:
        res = self.client.post("/api/acg/personal", json={"yaml_text": "version: 1\n"})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"], YAML_MISSING_BIRTH_DATA_ERROR)

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
