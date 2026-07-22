from pathlib import Path

from services.chart_svg import build_horoscope_svg_from_yaml


def test_zodiac_symbols_mask_wheel_lines() -> None:
    yaml_text = Path("data/demo/chief_editor_neko.yaml").read_text(encoding="utf-8")

    svg = build_horoscope_svg_from_yaml(yaml_text, compact=False)

    assert svg is not None
    assert ".sign{font-size:34px;paint-order:stroke fill" in svg
    assert "stroke:#fffaf2;stroke-width:10px" in svg
    assert 'dominant-baseline="central"' in svg
    assert svg.count('class="sign"') == 12
