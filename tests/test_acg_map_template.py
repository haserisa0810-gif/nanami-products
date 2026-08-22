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
    assert "var PLANET_COLORS = {" in template
    assert 'Sun: "#F2C04B"' in template
    assert 'Moon: "#C9D4E8"' in template
    assert 'Mercury: "#7FD0C8"' in template
    assert 'Neptune: "#6A8AE8"' in template
    assert 'Pluto: "#9A7AB8"' in template
    assert "var color = planetColor(props.planet);" in template
    assert 'var isNatal = props.mode === "natal" || props.mode === "personal";' in template
    assert 'switchBaseLayer("osm");' in template
    assert 'switchBaseLayer("gsi");' in template
    assert '<div class="map-legend" aria-hidden="true">' in template
    assert "MC: 実線" in template
    assert "IC: 破線" in template
    assert "ASC: 点線" in template
    assert "DSC: 点線" in template
    assert "太陽 MC" in template
    assert "水星 IC" in template


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


def test_acg_personal_input_explains_prompt_and_code_fence_support() -> None:
    template = _template()

    assert "コピーした占術データを貼り付け" in template
    assert "プロンプト＋YAMLをそのまま貼り付けてください" in template
    assert "鑑定ページでコピーした「プロンプト＋YAML」全文" in template
    assert "ACGが占術YAMLを自動で見つけ" in template
    assert "必要なデータだけを読み込みます。" in template


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
    assert "この場所の星のメッセージをAIに聞く" in template
    assert 'id="btn-copy-yaml" type="button" disabled' in template
    assert "場所を選ぶと、お好きなAIに貼り付ける内容をコピーできます。" in template
    assert 'document.getElementById("btn-copy-yaml").disabled = false;' in template
    assert "AIに貼り付ける内容をコピーしました。" in template


def test_acg_map_uses_shared_planet_labels_line_styles_and_globe_link() -> None:
    template = _template()

    assert "var NAME_JA = EN ? {" in template
    assert 'Sun: "太陽"' in template
    assert '"North Node": "ドラゴンヘッド"' in template
    assert 'MC:  { weight: 2.8, dashArray: null }' in template
    assert 'IC:  { weight: 2.6, dashArray: "8 5" }' in template
    assert 'ASC: { weight: 2.2, dashArray: "1 5" }' in template
    assert 'DSC: { weight: 2.2, dashArray: "2 6" }' in template
    assert "function lineLabel(planet, angle)" in template
    assert "function angleAstronomyText(planet, angle, mode)" in template
    assert "この線の近くでは、\" + name + \"が\" + when + \"に南中する地域です。" in template
    assert "function globeUrl(props)" in template
    assert 'source: "acg-map"' in template
    assert 'href="\' + globeUrl(props) + \'"' in template
