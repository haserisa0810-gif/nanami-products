"""Render the existing nanami-products SVG logo as a Pinterest-ready PNG."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "nanami-products-logo.png"
SCALE = 4
SIZE = 512


def scaled(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def rotate(
    points: list[tuple[float, float]], degrees: float, center: tuple[float, float]
) -> list[tuple[float, float]]:
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    cx, cy = center
    return [
        (
            cx + (x - cx) * cosine - (y - cy) * sine,
            cy + (x - cx) * sine + (y - cy) * cosine,
        )
        for x, y in points
    ]


def main() -> None:
    canvas = Image.new("RGB", (SIZE * SCALE, SIZE * SCALE), "#0E1426")
    draw = ImageDraw.Draw(canvas)
    gold = "#C9A15A"

    draw.rounded_rectangle(
        (0, 0, SIZE * SCALE - 1, SIZE * SCALE - 1),
        radius=72 * SCALE,
        fill="#0E1426",
    )
    draw.ellipse(
        scaled([(70, 70), (442, 442)]),
        outline=gold,
        width=8 * SCALE,
    )
    draw.ellipse(
        scaled([(122, 122), (390, 390)]),
        outline="#6F5B37",
        width=3 * SCALE,
    )

    outer_star = [
        (256, 45.8),
        (258.2, 51.8),
        (264.2, 54),
        (258.2, 56.2),
        (256, 62.2),
        (253.8, 56.2),
        (247.8, 54),
        (253.8, 51.8),
    ]
    for degrees in range(0, 360, 30):
        draw.polygon(scaled(rotate(outer_star, degrees, (256, 256))), fill=gold)

    main_star = [
        (256, 104),
        (283, 216),
        (360, 152),
        (296, 229),
        (408, 256),
        (296, 283),
        (360, 360),
        (283, 296),
        (256, 408),
        (229, 296),
        (152, 360),
        (216, 283),
        (104, 256),
        (216, 229),
        (152, 152),
        (229, 216),
    ]
    draw.polygon(scaled(main_star), fill=gold)

    inner_star = [
        (256, 151),
        (276, 230),
        (361, 256),
        (276, 282),
        (256, 361),
        (236, 282),
        (151, 256),
        (236, 230),
    ]
    draw.polygon(scaled(inner_star), fill="#10172A")
    draw.ellipse(scaled([(231, 231), (281, 281)]), fill=gold)
    draw.ellipse(scaled([(247, 247), (265, 265)]), fill="#0E1426")

    canvas.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(
        OUTPUT, format="PNG", optimize=True
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
