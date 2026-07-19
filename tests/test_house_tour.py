"""House Tour（出生図12ハウス 3Dデモ）のテスト。

- ページ /house-tour が配信されること
- ES modules + 固定サンプルで独立動作すること
- 鑑定・注文・YAML 生成に依存しないこと
- ハウス意味の一語矮小化を避けるコピーがあること
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

import routes

client = TestClient(routes.app)
ROOT = Path(__file__).resolve().parents[1]
HT = ROOT / "static" / "house-tour"


def test_house_tour_page_loads():
    res = client.get("/house-tour")
    assert res.status_code == 200
    html = res.text
    assert "BIRTH CHART" in html or "HOUSE TOUR" in html
    assert "three.min.js" in html
    assert 'id="ht-canvas"' in html
    assert "ガイドツアー" in html
    assert "house-tour/js/main.js" in html
    assert 'type="module"' in html
    assert 'id="ht-caption"' in html
    assert "ミュージアム" in html or "MUSEUM" in html


def test_house_tour_assets_isolated_from_other_pages():
    for path in ["/", "/acg", "/redeem/western-basic", "/transit-flight"]:
        res = client.get(path)
        assert res.status_code == 200, path
        assert "house-tour/js/main.js" not in res.text, path


def test_house_tour_does_not_touch_order_or_yaml_flows():
    html = client.get("/house-tour").text
    assert "/redeem" not in html
    assert "yaml_exporter" not in html
    assert "order_code" not in html
    main = client.get("/static/house-tour/js/main.js").text
    assert "yaml_exporter" not in main
    assert "/api/acg" not in main
    assert "sample-chart" in main


def test_static_modules_served():
    files = [
        "js/main.js",
        "js/scene.js",
        "js/controls.js",
        "js/house-builder.js",
        "js/planet-builder.js",
        "js/tour-controller.js",
        "js/ui.js",
        "js/ambient-sound.js",
        "js/data/sample-chart.js",
        "js/data/houses-ja.js",
        "js/data/houses-en.js",
        "js/data/planets-ja.js",
        "house-tour.css",
        "sample-data.json",
    ]
    for rel in files:
        res = client.get(f"/static/house-tour/{rel}")
        assert res.status_code == 200, rel


def test_sample_chart_matches_spec_placement():
    text = (HT / "js" / "data" / "sample-chart.js").read_text(encoding="utf-8")
    # 指示書の固定配置
    assert '"Jupiter"' in text or "'Jupiter'" in text
    assert "2:" in text or "2 :" in text
    # houses map should include Jupiter in 2, Sun+Saturn in 5, etc.
    assert re.search(r"2:\s*\[\s*[\"']Jupiter[\"']", text)
    assert re.search(r"5:\s*\[\s*[\"']Sun[\"']\s*,\s*[\"']Saturn[\"']", text)
    assert re.search(r"6:\s*\[\s*[\"']Mercury[\"']", text)
    assert re.search(r"7:\s*\[\s*[\"']Uranus[\"']", text)
    assert re.search(r"9:\s*\[\s*[\"']Neptune[\"']", text)
    assert re.search(r"11:\s*\[\s*[\"']Moon[\"']", text)


def test_sample_data_json_mirror():
    res = client.get("/static/house-tour/sample-data.json")
    assert res.status_code == 200
    data = res.json()
    assert data["houses"]["2"] == ["Jupiter"]
    assert data["houses"]["5"] == ["Sun", "Saturn"]
    assert data["houses"]["11"] == ["Moon"]
    assert data["houses"]["1"] == []


def test_house_copy_has_depth_not_single_word_trap():
    """第2=金運、第7=結婚、第8=死、第12=不幸 に狭めないこと。"""
    ja = (HT / "js" / "data" / "houses-ja.js").read_text(encoding="utf-8")
    assert "単なる金運" in ja or "金運の部屋ではありません" in ja
    assert "結婚だけ" in ja
    assert "死を恐怖" in ja or "恐怖的に演出" in ja
    assert "不吉" in ja
    assert "保管庫" in ja
    assert "対話" in ja
    # 禁止トーン
    assert "必ず成功" not in ja
    assert "結婚できない" not in ja
    assert "病気になる" not in ja


def test_planet_combo_avoids_fatalism():
    pt = (HT / "js" / "data" / "planets-ja.js").read_text(encoding="utf-8")
    assert "断定" in pt
    assert "傾向" in pt
    assert "comboText" in pt
    assert "Sun" in pt and "5" in pt


def test_guide_tour_and_mobile_hooks_in_ui():
    html = client.get("/house-tour").text
    assert "ht-start-guide" in html
    assert "ht-btn-next" in html
    assert "ht-btn-prev" in html
    assert "ht-stick-base" in html
    assert "ht-planet-panel" in html
    assert "ht-sense-grid" in html
    js_main = (HT / "js" / "main.js").read_text(encoding="utf-8")
    assert "startGuide" in js_main
    assert "createTourController" in js_main
    ctrl = (HT / "js" / "controls.js").read_text(encoding="utf-8")
    assert "stick" in ctrl
    assert "KeyN" in ctrl


def test_template_and_route_contract():
    html = (ROOT / "templates" / "house_tour.html").read_text(encoding="utf-8")
    assert "MUSEUM" in html or "ミュージアム" in html
    assert "ht-caption" in html
    assert "ガイドツアー" in html
    # ホームページへ戻るリンクは置かない（販売用の導線をミュージアム内で完結させる）
    assert 'href="/"' not in html
    assert "ht-back" not in html
    # routes
    routes_src = (ROOT / "routes.py").read_text(encoding="utf-8")
    assert '@app.get("/house-tour"' in routes_src


def test_yaml_parser_module_and_portal_handoff():
    """YAML paste UI lives on entrance only; editions load via sessionStorage + parser."""
    html = client.get("/house-tour").text
    assert "js-yaml" in html  # still needed to parse handoff
    assert 'id="ht-yaml-input"' not in html
    assert 'id="ht-load-yaml"' not in html
    assert "ht-yaml-panel" not in html
    entrance = client.get("/birth-chart-museum").text
    assert 'id="me-yaml-input"' in entrance
    assert client.get("/static/house-tour/js/parse-yaml.js").status_code == 200
    assert client.get("/static/house-tour/js/data/neko-chart.js").status_code == 200
    parser = (HT / "js" / "parse-yaml.js").read_text(encoding="utf-8")
    assert "parseNatalYaml" in parser
    assert "systems.western.natal" in parser
    assert "chartFromDoc" in parser
    main = (HT / "js" / "main.js").read_text(encoding="utf-8")
    assert "parseNatalYaml" in main
    assert "ht-last-yaml" in main
    assert "applyChart" in main
    assert "nekoChart" in main
    assert "createCinematicPlayer" in main
    assert "buildShotsForHouse" in main
    assert "initLang" in main
    assert client.get("/static/house-tour/js/cinematic.js").status_code == 200
    assert client.get("/static/house-tour/js/museum-shots.js").status_code == 200
    assert client.get("/static/house-tour/js/i18n.js").status_code == 200
    assert client.get("/static/house-tour/js/data/ui-strings.js").status_code == 200
    assert client.get("/static/house-tour/js/data/planets-en.js").status_code == 200
    assert client.get("/static/house-tour/js/data/houses-en.js").status_code == 200
    neko = (HT / "js" / "data" / "neko-chart.js").read_text(encoding="utf-8")
    assert "ねこ編集長" in neko
    assert "Moon" in neko and "house: 5" in neko


def test_i18n_has_english_ui_and_houses():
    ui = (HT / "js" / "data" / "ui-strings.js").read_text(encoding="utf-8")
    assert "Guided tour" in ui
    assert "Walk freely" in ui
    assert "Birth Chart Museum" in ui
    en_houses = (HT / "js" / "data" / "houses-en.js").read_text(encoding="utf-8")
    assert "First House" in en_houses or "Identity" in en_houses
    assert "Not merely money" in en_houses or "Value" in en_houses
    planets_en = (HT / "js" / "data" / "planets-en.js").read_text(encoding="utf-8")
    assert "comboTextEn" in planets_en
    assert "Sun" in planets_en
    i18n = (HT / "js" / "i18n.js").read_text(encoding="utf-8")
    assert "setLang" in i18n
    assert "applyDomI18n" in i18n
    html = client.get("/house-tour").text
    assert 'data-lang-set="en"' in html
    assert 'data-lang-set="ja"' in html


def test_yaml_fixture_neko_placement_contract():
    """ねこ編集長サンプルのハウス配置がフィクスチャに保持されていること。"""
    import yaml  # PyYAML in requirements

    path = HT / "fixtures" / "neko-editor-minimal.yaml"
    assert path.is_file()
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    bodies = doc["systems"]["western"]["natal"]["bodies"]
    assert bodies["Sun"]["house"] == 9
    assert bodies["Moon"]["house"] == 5
    assert bodies["Mercury"]["house"] == 8
    assert bodies["Jupiter"]["house"] == 10
    assert bodies["Uranus"]["house"] == 11
    assert bodies["South Node"]["house"] == 6
    assert doc["input"]["title"] == "ねこ編集長"


def test_chart_from_doc_logic_via_python_mirror():
    """parse-yaml.js と同条件で house マップを組み立てられること（サーバ側ミラー検証）。"""
    import yaml

    doc = yaml.safe_load((HT / "fixtures" / "neko-editor-minimal.yaml").read_text(encoding="utf-8"))
    bodies = doc["systems"]["western"]["natal"]["bodies"]
    angle_ids = {"ASC", "MC", "DSC", "IC", "Vertex"}
    tour_ids = {
        "Sun", "Moon", "Mercury", "Venus", "Mars",
        "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
        "North Node", "South Node", "Chiron",
    }
    houses: dict[int, list[str]] = {i: [] for i in range(1, 13)}
    for bid, b in bodies.items():
        if bid in angle_ids or bid not in tour_ids:
            continue
        houses[int(b["house"])].append(bid)
    assert "Sun" in houses[9] and "Saturn" in houses[9]
    assert "Moon" in houses[5]
    assert set(houses[8]) >= {"Mercury", "Venus", "Mars", "Pluto"}
    assert "Jupiter" in houses[10] and "Neptune" in houses[10]
    assert "Uranus" in houses[11]
    assert "North Node" in houses[12]
    assert "South Node" in houses[6]
    # 天体なしハウス
    assert houses[1] == []
    assert houses[2] == []
