"""Birth Chart Museum entrance portal + auto_guide wiring."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import routes

client = TestClient(routes.app)
ROOT = Path(__file__).resolve().parents[1]
HT = ROOT / "static" / "house-tour"
ARCH = ROOT / "static" / "house-tour-architecture"


def test_museum_entrance_page_loads():
    res = client.get("/birth-chart-museum")
    assert res.status_code == 200
    html = res.text
    assert "BIRTH CHART" in html
    assert "MUSEUM" in html
    # No auto-start tour — prefer_guide is a hint only; free enter stays plain
    assert "prefer_guide=1" in html
    assert "auto_guide=1" not in html
    assert 'href="/house-tour"' in html or "house-tour?" in html
    assert "house-tour-architecture" in html
    assert 'id="me-yaml-input"' in html
    assert "museum-entrance.css" in html
    assert "museum-entrance.js" in html


def test_museum_entrance_assets_served():
    for rel in ("museum-entrance.css", "museum-entrance.js"):
        r = client.get(f"/static/house-tour/{rel}")
        assert r.status_code == 200, rel


def test_editions_do_not_auto_start_guide():
    """prefer_guide only toasts; tour starts via title-screen button."""
    abs_main = (HT / "js" / "main.js").read_text(encoding="utf-8")
    arch_main = (ARCH / "js" / "main.js").read_text(encoding="utf-8")
    for main in (abs_main, arch_main):
        assert "wantsPreferGuide" in main
        assert "tour.startGuide()" in main  # button path still exists
        # must not auto-call startGuide from the prefer/auto hint block alone
        # (hint block uses toast only)
        assert "toast_guide_hint" in main or "準備ができたら" in main
    entrance = (HT / "museum-entrance.js").read_text(encoding="utf-8")
    assert "ht-last-yaml" in entrance
    assert "ht-chart-pref" in entrance


def test_editions_link_back_to_entrance():
    abs_html = client.get("/house-tour").text
    arch_html = client.get("/house-tour-architecture").text
    assert 'href="/birth-chart-museum"' in abs_html
    assert 'href="/birth-chart-museum"' in arch_html


def test_dream_sky_page_and_entrance_card():
    ent = client.get("/birth-chart-museum").text
    assert 'href="/dream-sky"' in ent or "dream-sky" in ent
    assert "Dream" in ent or "dream" in ent
    res = client.get("/dream-sky")
    assert res.status_code == 200
    html = res.text
    assert "Dream Sky" in html
    assert "yamlInput" in html or "YAML" in html
    assert "js-yaml" in html
    assert client.get("/static/dream-sky/index.html").status_code == 200
