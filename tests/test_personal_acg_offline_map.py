"""START-ACG.html shows OpenStreetMap online and never goes blank when tiles are unavailable."""

from __future__ import annotations

import json
import re

import services.personal_edition_delivery as delivery
from services.personal_edition_delivery import PE_DIR, ROOT, _standalone_acg_html

OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def _sample_acg_data() -> dict:
    features = []
    for index, planet in enumerate(["Sun", "Moon", "Venus", "Jupiter", "Saturn"]):
        lon = -150 + index * 60
        for angle, line_lon in (("MC", lon), ("IC", lon + 180 if lon < 0 else lon - 180)):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[line_lon, -80], [line_lon, 80]]},
                    "properties": {
                        "planet": planet,
                        "angle": angle,
                        "line_group": f"{planet}_{angle}",
                        "label": f"{planet} {angle}",
                        "meaning": "sample",
                    },
                }
            )
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {"datetime_utc": "1990-01-01T00:00:00Z"},
    }


def _build(lang: str = "en", chart_url: str | None = None) -> str:
    leaflet_dir = ROOT / "static" / "vendor" / "leaflet"
    return _standalone_acg_html(
        acg_html=(PE_DIR / "acg" / "index.html").read_text(encoding="utf-8"),
        leaflet_css=(leaflet_dir / "leaflet.css").read_text(encoding="utf-8"),
        leaflet_js=(leaflet_dir / "leaflet.js").read_text(encoding="utf-8"),
        acg_data=_sample_acg_data(),
        city_data=json.loads((PE_DIR / "acg" / "cities.min.json").read_text(encoding="utf-8")),
        world_data=json.loads(
            (ROOT / "static" / "geo" / "ne_50m_admin_0_countries.geojson").read_text(encoding="utf-8")
        ),
        chart_url=chart_url,
        lang=lang,
    )


def test_standalone_acg_loads_only_osm_tiles_from_the_network() -> None:
    for lang in ("ja", "en", "es", "de"):
        html = _build(lang)
        assert html.count("L.tileLayer(") == 1
        assert f"var OSM_TILE_URL='{OSM_TILE_URL}';" in html
        # The only fetch is the one-tile OSM probe; all personal and map data is embedded.
        assert html.count("fetch(") == 1
        assert "fetch(OSM_TILE_URL.replace(" in html
        assert not re.search(r"<script[^>]+src=", html)
        assert not re.search(r"<link[^>]+rel=[\"']stylesheet", html)
        assert not re.search(r"url\(\s*[\"']?https?:", html)
        assert not re.search(r"@import", html)


def test_osm_tiles_send_only_the_origin_as_referer() -> None:
    # The app page itself is served with Referrer-Policy: no-referrer, which OSM rejects.
    html = _build("en")
    assert "referrerPolicy:'strict-origin'" in html


def test_built_in_map_sits_under_the_tiles_and_shows_when_they_fail() -> None:
    html = _build("en")
    # Leaflet's tile pane is z-index 200; the built-in land layer must stay below it.
    assert "getPane('landPane').style.zIndex=150" in html
    assert "getPane('landPane').style.opacity=0" not in html
    assert "fillOpacity:1" in html
    assert "#map.leaflet-container{background:#cfdde3}" in html
    assert "graticuleLayer" in html
    assert "tileLayer.on('tileerror',function(){if(!builtInLabels)setBuiltInLabels(true);});" in html
    assert "cityCatalog=[" in html and "renderCities();" in html


def test_tiles_are_added_only_after_osm_serves_a_probe_tile() -> None:
    # OSM refuses with a readable "403 Access blocked" image, so the layer must not be added up front.
    html = _build("en")
    assert "attribution:'© OpenStreetMap contributors'}).addTo(map)" not in html
    assert "if(settled||!r.ok)return;settled=true;tileLayer.addTo(map);setBuiltInLabels(false);" in html
    assert "mode:'cors'" in html and "credentials:'omit'" in html
    assert "useOnlineTilesIfServed();" in html


def test_built_in_map_uses_natural_earth_50m(monkeypatch) -> None:
    monkeypatch.setattr(delivery, "personal_geojson", lambda _yaml: _sample_acg_data())
    html = delivery.build_personal_acg_html(yaml_text="unused", lang="en")
    assert "Admin 0 Countries 1:50m" in html
    assert "ne_50m_admin_0_countries.geojson" not in html


def test_standalone_acg_only_links_out_through_navigation_and_tiles() -> None:
    html = _build("en", chart_url="https://chart.example/chart/private?lang=en")
    urls = set(re.findall(r"https?://[^\s\"'<>)\\]+", html))
    allowed = {
        OSM_TILE_URL,
        # Leaflet's attribution link, SVG namespace, and bug references in CSS comments: none are fetched.
        "https://leafletjs.com",
        "http://www.w3.org/2000/svg",
        "https://bugs.chromium.org/p/chromium/issues/detail?id=600120",
        "https://bugzilla.mozilla.org/show_bug.cgi?id=888319",
        "https://chart.example/chart/private?lang=en",
    }
    assert urls <= allowed, urls - allowed
