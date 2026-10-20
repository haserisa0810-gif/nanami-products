"""Share the actual product payloads through the production JavaScript offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

import routes
from services.yaml_exporter import build_product_yaml
from services.shichusuimei_year_selection import build_year_selection
from tests.test_light_yaml_transit_summary import _asteroid_dense_full_doc


def test_native_share_uses_complete_real_product_payloads_without_duplicate_text(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for native-share behavior tests")
    fixtures = {}
    for edition in ("basic", "full"):
        text, prompt, doc = build_product_yaml(
            title="Fictional share test", birth_date="1985-09-05", birth_time="10:00",
            prefecture="東京都", gender="female", include_shichusuimei=True,
            shichusuimei_edition=edition,
        )
        chart = {"yaml_text": text, "prompt_text": prompt,
                 "options": {"product_type": "shichu_full" if edition == "full" else "shichu",
                             "shichusuimei": True}}
        share_yaml = routes._chart_share_yaml_text(chart, doc=doc)
        fixtures[f"shichu_{edition}"] = {
            "yaml": share_yaml,
            "prompt": routes._chart_prompt_for_yaml_text(chart, share_yaml, fallback_doc=doc, lang="ja"),
        }
        if edition == "full":
            basic = build_year_selection(text, {"mode": "basic"})
            years = basic["available_years"]
            assert years
            selected = build_year_selection(text, {"mode": "selected", "years": years[:1]})
            for name, result in (("basic", basic), ("selected", selected)):
                fixtures[f"shichu_full_{name}"] = {"yaml": result["yaml_text"], "prompt": result["prompt_text"]}
    doc = _asteroid_dense_full_doc()
    chart = {"yaml_text": yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
             "prompt_text": "Fictional western test", "options": {"product_type": "western_full"}}
    share_yaml = routes._chart_share_yaml_text(chart, doc=doc)
    fixtures["western_full_light"] = {
        "yaml": share_yaml,
        "prompt": routes._chart_prompt_for_yaml_text(chart, share_yaml, fallback_doc=doc, lang="ja"),
    }
    fixture_path = tmp_path / "fictional-share-cases.json"
    fixture_path.write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [node, "--test", "tests/test_chart_ai_share_ui.cjs"],
        env={**os.environ, "NANAMI_SHARE_FIXTURES": str(fixture_path)},
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        encoding="utf-8", timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
