"""Build static/geo/ne_50m_admin_0_countries.geojson for the Personal ACG built-in map.

Source: Natural Earth 5.1.2 Admin 0 Countries 1:50m (public domain)
https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson

Usage:
    python scripts/build_ne50m_countries.py <downloaded ne_50m_admin_0_countries.geojson>

Keeps only the Japanese country name (same shape as ne_110m_admin_0_countries.geojson),
rounds coordinates to 3 decimals (about 100 m), and drops points that collapse onto
their neighbour after rounding.
"""

import json
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "static" / "geo" / "ne_50m_admin_0_countries.geojson"


def _ring(points):
    out = []
    for lon, lat in points:
        point = [round(lon, 3), round(lat, 3)]
        if not out or out[-1] != point:
            out.append(point)
    if out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) >= 4 else None


def build(source: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    features = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        slim = []
        for polygon in polygons:
            rings = [ring for ring in (_ring(points) for points in polygon) if ring]
            if rings:
                slim.append(rings)
        if not slim:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"name": feature["properties"]["NAME_JA"]},
                "geometry": {"type": "MultiPolygon", "coordinates": slim},
            }
        )
    output = {
        "type": "FeatureCollection",
        "name": "ne_50m_admin_0_countries",
        "source": "Natural Earth 5.1.2 Admin 0 Countries 1:50m (public domain), names from NAME_JA",
        "features": features,
    }
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(output, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"{OUTPUT} ({len(features)} features)")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
