"""Architecture Edition — separate from abstract /house-tour."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import routes

client = TestClient(routes.app)
ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "static" / "house-tour-architecture"


def test_architecture_page_loads():
    res = client.get("/house-tour-architecture")
    assert res.status_code == 200
    html = res.text
    assert "ARCHITECTURAL COLLECTION" in html
    assert "house-tour-architecture/js/main.js" in html
    assert "three.min.js" in html
    assert 'href="/house-tour"' in html
    assert "arch-builder" not in html  # loaded via module graph


def test_architecture_assets_served():
    for rel in (
        "js/main.js",
        "js/arch-builder.js",
        "js/materials.js",
        "js/life-props.js",
        "arch.css",
        "README.md",
        "LIVED_IN.md",
    ):
        assert client.get(f"/static/house-tour-architecture/{rel}").status_code == 200, rel


def test_lived_in_props_are_optional_layer():
    """生活感は別モジュール＋ON/OFF。建築本体と分離。"""
    life = (ARCH / "js" / "life-props.js").read_text(encoding="utf-8")
    assert "lived_in_props" in life
    assert "isLivedInEnabled" in life
    assert "setLivedInVisible" in life
    for n in range(1, 13):
        assert f"fillHouse{n}" in life, f"missing fillHouse{n}"
    builder = (ARCH / "js" / "arch-builder.js").read_text(encoding="utf-8")
    assert "attachLivedInProps" in builder
    main = (ARCH / "js" / "main.js").read_text(encoding="utf-8")
    assert "toggleLivedIn" in main or "setLivedInVisible" in main
    html = client.get("/house-tour-architecture").text
    assert "ht-btn-lived-in" in html


def test_architecture_does_not_replace_abstract():
    abs_html = client.get("/house-tour").text
    arch_html = client.get("/house-tour-architecture").text
    assert "house-tour/js/main.js" in abs_html
    assert "house-tour-architecture/js/main.js" in arch_html
    assert "house-tour-architecture/js/main.js" not in abs_html
    # abstract still has link out to architecture experiment
    assert "house-tour-architecture" in abs_html


def test_architecture_reuses_abstract_modules():
    main = (ARCH / "js" / "main.js").read_text(encoding="utf-8")
    assert "../../house-tour/js/" in main
    assert "buildCampus" in main
    assert "createCinematicPlayer" in main
    assert "parseNatalYaml" in main
    builder = (ARCH / "js" / "arch-builder.js").read_text(encoding="utf-8")
    for n in range(1, 13):
        assert f"buildHouse{n}" in builder, f"missing buildHouse{n}"


def test_abstract_checkpoint_docs_exist():
    ht = ROOT / "static" / "house-tour"
    assert (ht / "CHECKPOINT.md").is_file()
    assert (ht / "REALISM.md").is_file()
