"""redeem 海外版フォームの地図クリックUIの回帰テスト。

- 海外対応の redeem テンプレート（western-basic / western-full / shichu）に
  Leaflet 地図・緯度経度自動入力のスクリプトが差し込まれていること。
- 既定（国内モード）では地図を含む海外パネルが hidden で、国内フォームに影響しないこと。
- 座標欄の name（birth_lat / birth_lng）は従来通りで、手入力導線を壊していないこと。
- transit_yaml フォームには地図を入れていない（対象外）こと。
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import routes

client = TestClient(routes.app)

OVERSEAS_PATHS = ["/redeem/western-basic", "/redeem/western-full", "/redeem/shichu"]


def test_overseas_forms_include_leaflet_map():
    for path in OVERSEAS_PATHS:
        html = client.get(path).text
        assert 'id="overseas-map"' in html, path
        assert "vendor/leaflet/leaflet.css" in html, path
        assert "vendor/leaflet/leaflet.js" in html, path
        assert "redeem_overseas_map.js" in html, path
        # 既存の座標欄は残っている（手入力導線を壊していない）
        assert 'name="birth_lat"' in html, path
        assert 'name="birth_lng"' in html, path


def test_overseas_map_hidden_by_default_domestic():
    # 既定は国内モード。地図は hidden の海外コンテナ内にあり、国内表示に影響しない。
    for path in OVERSEAS_PATHS:
        html = client.get(path).text
        idx = html.find('id="overseas-map"')
        assert idx != -1, path
        # 直前の要素（海外パネル or overseas-only ラッパ）が hidden 指定であること
        preceding = html[:idx]
        container_open = max(
            preceding.rfind("overseas-place-panel"),
            preceding.rfind("overseas-only-field"),
        )
        assert container_open != -1, path
        segment = html[container_open:idx]
        assert "hidden" in segment, path


def test_transit_yaml_form_has_no_map():
    html = client.get("/redeem/transit-yaml").text
    assert 'id="overseas-map"' not in html


def test_shared_map_script_sets_coordinates():
    js = Path("static/redeem_overseas_map.js").read_text(encoding="utf-8")
    assert 'name="birth_lat"' in js
    assert 'name="birth_lng"' in js
    assert 'map.on("click"' in js
    # タイムゾーンは触らない（自動化しすぎない）
    assert "birth_timezone" not in js
