"""Read-only observations of existing Western ZIP behavior; no fixes here."""
import io
import zipfile
from unittest.mock import patch

import yaml
from starlette.requests import Request

from routes import chart_download_zip
from services.prompt_builder import build_prompt
from tests.test_light_yaml_transit_summary import _asteroid_dense_full_doc


def observed_zip(query=b""):
    doc = _asteroid_dense_full_doc()
    raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    chart = {"options": {"product_type": "western_full"}, "yaml_text": raw,
             "prompt_text": build_prompt(include_shichusuimei=False, include_asteroids=True, include_transit=True),
             "share_yaml_text": None, "horoscope_svg": None, "shichusuimei_svg": None}
    request = Request({"type": "http", "method": "GET", "scheme": "https",
                       "server": ("chart.nanami-astro.com", 443), "path": "/chart/localfiction/download.zip",
                       "query_string": query, "headers": []})
    with patch("routes._load_chart_or_404", return_value=chart):
        response = chart_download_zip(request, "localfiction")
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        files = {name: archive.read(name).decode("utf-8") for name in archive.namelist()}
    return doc, raw, files


def paste_yaml(text):
    return yaml.safe_load(text.split("```yaml\n", 1)[1].rsplit("```", 1)[0])


def test_existing_zip_uses_server_share_mode_not_ui_selection():
    doc, raw, files = observed_zip()
    _, _, selected = observed_zip(b"mode=asteroids")
    assert files == selected
    assert files["full.yaml"] == raw
    assert yaml.safe_load(files["detail.yaml"])["systems"]["western"].get("asteroids")
    assert not paste_yaml(files["ai_paste.txt"])["systems"]["western"].get("asteroids")


def test_existing_readme_is_fixed_38_days_for_a_saved_31_day_fixture():
    doc, _, files = observed_zip()
    transit = yaml.safe_load(files["transit.yaml"])["systems"]["western"]["transit"]
    assert doc["systems"]["western"]["transit"]["period"]["days"] == 31
    assert len(transit["daily"]) == 31
    assert "transit.yaml: 38日分" in files["README.txt"]


def test_saved_full_prompt_and_regenerated_lite_prompt_have_different_inputs():
    _, _, files = observed_zip()
    prompt_in_paste = files["ai_paste.txt"].split("\n\n---", 1)[0]
    assert files["prompt.txt"].strip() != prompt_in_paste.strip()
    assert "小惑星" in files["prompt.txt"].splitlines()[0]
    assert "小惑星" not in prompt_in_paste.splitlines()[0]
