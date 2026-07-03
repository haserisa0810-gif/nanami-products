from __future__ import annotations

from pathlib import Path


def _template() -> str:
    return Path("templates/acg_map.html").read_text(encoding="utf-8")


def test_acg_map_uses_leaflet_tile_providers() -> None:
    template = _template()

    assert "var TILE_PROVIDERS = {" in template
    assert "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" in template
    assert "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png" in template
    assert "World_Topo_Map/MapServer/tile/{z}/{y}/{x}" in template
    assert "L.tileLayer(provider.url, provider.options)" in template
    assert "L.control.layers(baseLayers" in template


def test_acg_lines_render_above_tile_map() -> None:
    template = _template()

    assert 'map.createPane("acg-lines").style.zIndex = 450;' in template
    assert 'pane: "acg-lines"' in template
    assert 'switchBaseLayer("osm");' in template
    assert 'switchBaseLayer("gsi");' in template


def test_acg_map_no_longer_fetches_natural_earth_as_base_map() -> None:
    template = _template()

    assert "ne_110m_admin_0_countries.geojson" not in template
    assert "japan_10m.geojson" not in template
    assert "地図データ: Natural Earth" not in template


def test_acg_map_has_japan_orientation_guides() -> None:
    template = _template()

    assert 'map.createPane("japan-guide").style.zIndex = 430;' in template
    assert "var JAPAN_LABEL_LATLNG = [36.2, 148.0];" in template
    assert "var TOKYO_LATLNG = [35.68, 139.76];" in template
    assert "japan-label" in template
    assert "japan-guide" in template
    assert "#btn-zoom-japan" in template
    assert 'switchBaseLayer("gsi");' in template
