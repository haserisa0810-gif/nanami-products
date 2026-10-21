"""Render the real buyer pages and exercise their loading-state JavaScript offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

import routes


def test_final_confirmation_loading_state_and_single_submission(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for submit-handler behavior tests")
    client = TestClient(routes.app)
    fixtures = []
    for slug in ("shichu", "shichu-full", "western-basic", "western-full"):
        for lang in (("ja", "en") if slug != "shichu" else ("ja",)):
            response = client.get(f"/redeem/{slug}?lang={lang}")
            assert response.status_code == 200
            if slug.startswith("western-"):
                loading_text = routes.I18N[lang]["submit_loading_button"]
            elif slug == "shichu-full":
                loading_text = routes.shichu_full_form_text(lang)["submit_busy"]
            else:
                loading_text = "生成中..."
            fixtures.append({"name": f"{slug}:{lang}", "html": response.text, "loadingText": loading_text})
    fixture_path = tmp_path / "rendered-redeem-pages.json"
    fixture_path.write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [node, "--test", "tests/test_redeem_generating_ui.cjs"],
        env={**os.environ, "NANAMI_REDEEM_FIXTURES": str(fixture_path)},
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        encoding="utf-8", timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
