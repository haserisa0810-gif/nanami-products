from __future__ import annotations

import io
import unittest
import zipfile
from unittest.mock import patch

import yaml

from routes import chart_download_zip
from tests.test_light_yaml_transit_summary import _full_doc


class ChartDownloadZipTest(unittest.TestCase):
    def test_zip_regenerates_ai_files_from_full_yaml_when_stored_share_yaml_is_stale(self) -> None:
        full_yaml = yaml.safe_dump(_full_doc(), allow_unicode=True, sort_keys=False)
        stale_share_yaml = """
version: nanami-products-yaml-light-v1
product:
  options:
    transit_today: true
    transit_31days_summary: true
systems:
  western:
    transit:
      today:
        date: '2026-05-06'
      next_31_days_summary: {}
""".strip()
        chart = {
            "token": "testtoken",
            "options": {"western_natal": True, "transit": True, "product_type": "western_full"},
            "yaml_text": full_yaml,
            "prompt_text": "AI prompt",
            "share_yaml_text": stale_share_yaml,
            "horoscope_svg": None,
            "shichusuimei_svg": None,
        }

        with patch("routes._load_chart_or_404", return_value=chart):
            response = chart_download_zip("testtoken")

        with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
            detail_yaml = archive.read("detail.yaml").decode("utf-8")
            ai_paste = archive.read("ai_paste.txt").decode("utf-8")
            full_yaml_in_zip = archive.read("full.yaml").decode("utf-8")

        self.assertEqual(yaml.safe_load(full_yaml_in_zip), yaml.safe_load(full_yaml))
        self.assertNotIn("next_31_days_summary: {}", detail_yaml)
        self.assertNotIn("next_31_days_summary: {}", ai_paste)
        self.assertIn("overall_theme", detail_yaml)
        self.assertIn("overall_theme", ai_paste)
        self.assertIn("key_dates", detail_yaml)
        self.assertIn("key_dates", ai_paste)


if __name__ == "__main__":
    unittest.main()
