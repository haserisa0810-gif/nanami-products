"""Birth Chart Museum 無料デモ（/birth-chart-museum/demo）。

デモはサンプル出生図固定・YAML読込なし・英語デフォルト。
Web 本線（/house-tour 等）には demo UI が混入しないこと。
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import routes

client = TestClient(routes.app)
ROOT = Path(__file__).resolve().parents[1]


def test_demo_routes_load_with_demo_flag():
    for url in ("/birth-chart-museum/demo", "/birth-chart-museum/demo/architecture"):
        res = client.get(url)
        assert res.status_code == 200, url
        html = res.text
        assert "window.HT_DEMO = true" in html, url
        assert 'window.HT_DEFAULT_LANG = "en"' in html, url
        assert 'id="ht-demo-ribbon"' in html, url
        assert 'id="ht-demo-overlay"' in html, url


def test_demo_has_sample_notice_and_free_download_without_paid_pitch():
    html = client.get("/birth-chart-museum/demo").text
    assert "Sample chart" in html or "サンプル出生図" in html
    assert "Download the free Museum + Dream Sky" in html
    assert "/downloads/birth-chart-museum-free.zip?lang=" in html
    assert "Get the Personal Edition" not in html
    assert "Etsy" not in html
    assert "STORES" not in html


def test_regular_editions_have_no_demo_ui():
    for url in ("/house-tour", "/house-tour-architecture", "/birth-chart-museum"):
        html = client.get(url).text
        assert "HT_DEMO" not in html, url
        assert "ht-demo-ribbon" not in html, url


def test_demo_mode_skips_yaml_sources_in_js():
    """デモは sessionStorage / ?chart= を読まずサンプル固定（JS ガードの存在確認）。"""
    abs_main = (ROOT / "static" / "house-tour" / "js" / "main.js").read_text(encoding="utf-8")
    arch_main = (ROOT / "static" / "house-tour-architecture" / "js" / "main.js").read_text(
        encoding="utf-8"
    )
    for main in (abs_main, arch_main):
        assert "window.HT_DEMO" in main
    # ガードは sessionStorage 読み出しより前にあること
    for main in (abs_main, arch_main):
        assert main.index("window.HT_DEMO") < main.index('sessionStorage.getItem("ht-chart-pref")')


def test_default_lang_priority_hook_exists():
    """配布設定 HT_DEFAULT_LANG が URL/localStorage の後・ブラウザ言語の前に入る。"""
    i18n = (ROOT / "static" / "house-tour" / "js" / "i18n.js").read_text(encoding="utf-8")
    assert "HT_DEFAULT_LANG" in i18n
    assert i18n.index('get("lang")') < i18n.index(
        "const def = window.HT_DEFAULT_LANG"
    ) < i18n.index("navigator.language")
    entrance = (ROOT / "static" / "house-tour" / "museum-entrance.js").read_text(encoding="utf-8")
    assert "HT_DEFAULT_LANG" in entrance
