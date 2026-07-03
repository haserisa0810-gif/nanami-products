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
    assert "var ROLE_COLOR = {" in template
    assert 'mundane: "#3B82F6"' in template
    assert 'natal: "#F59E0B"' in template
    assert 'var weight = style.weight + (props.mode === "natal" ? 1 : 0);' in template
    assert 'opacity: 0.84' in template
    assert 'switchBaseLayer("osm");' in template
    assert 'switchBaseLayer("gsi");' in template
    assert '<div class="map-legend" aria-hidden="true">' in template
    assert '青線: 今日の空（マンデン）' in template
    assert '橙線: あなたの出生図（ACG）' in template


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


def test_acg_export_yaml_supports_combined_personal_and_mundane_lines() -> None:
    template = _template()

    assert "var featureSets = { mundane: [], personal: [] };" in template
    assert 'featureSets[mode] = features;' in template
    assert 'mode: " + (combined ? "combined"' in template
    assert "appendPersonalContext(lines);" in template
    assert 'appendLineList(lines, "personal_lines_nearby", lastQuery.personal_results, preset, "personal");' in template
    assert 'appendLineList(lines, "mundane_lines_nearby", lastQuery.mundane_results, preset, "mundane");' in template
    assert "personal_context:" in template
    assert "context_for_ai:" in template
    assert "reading_mode: location_context" in template
    assert "interpretation_order:" in template
    assert "selected_theme:" in template
    assert "selected_preset:" in template
    assert "interpretation_scope:" in template
    assert "included_line_rules:" in template
    assert "category_match:" in template
    assert "meaning:" in template
    assert "short_hint:" in template
    assert "typical_topics:" in template
    assert "work: {" in template
    assert "relation: {" in template
    assert "suggested_questions:" in template
    assert "この場所は仕事や発信の場所としてどう読めますか？" in template
    assert "この場所は人間関係や出会いの場としてどう読めますか？" in template
    assert "このYAMLは、ACG地図上の地点と選択中プリセットをもとにした場所コンテキストです。" in template
    assert "解釈はAI側で行ってください。" in template
    assert "keywords:" in template
    assert 'key + ": >-"' in template
    assert "出生図の関連配置と組み合わせて読む。" in template
    assert "function yamlString(value)" in template
    assert "function appendFoldedScalar(lines, indent, key, text)" in template
    assert "AIへ場所コンテキストをコピー" in template
