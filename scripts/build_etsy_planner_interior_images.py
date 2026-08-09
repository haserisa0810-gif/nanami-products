from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


SOURCE = Path("tmp/pdfs/planner-marketing-pages")
OUTPUT = Path("output/etsy/digital-planner/interior-images")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")

NAVY = "#071A34"
DEEP_NAVY = "#041226"
GOLD = "#D8AE5A"
IVORY = "#FFF9EB"
LAVENDER = "#C9B8FF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def centered(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
             fnt: ImageFont.FreeTypeFont, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - (box[2] - box[0]) / 2, y), text, font=fnt, fill=fill)


def background() -> Image.Image:
    im = Image.new("RGB", (2000, 2000), NAVY)
    draw = ImageDraw.Draw(im)
    for y in range(2000):
        t = y / 1999
        color = (
            int(7 * (1 - t) + 4 * t),
            int(26 * (1 - t) + 18 * t),
            int(52 * (1 - t) + 38 * t),
        )
        draw.line((0, y, 2000, y), fill=color)
    for x, y, r in [(130, 320, 4), (1840, 430, 5), (1770, 1240, 3),
                    (230, 1510, 4), (1010, 390, 3), (1450, 1650, 4)]:
        draw.ellipse((x-r, y-r, x+r, y+r), fill=GOLD)
    return im


def add_page(canvas: Image.Image, filename: str, box: tuple[int, int, int, int],
             angle: float = 0) -> None:
    page = Image.open(SOURCE / filename).convert("RGB")
    max_w, max_h = box[2] - box[0], box[3] - box[1]
    page.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", (page.width + 70, page.height + 70), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (30, 30, page.width + 30, page.height + 30), radius=8, fill=(0, 0, 0, 165)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    card = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    card.alpha_composite(shadow)
    card.paste(page, (20, 20))
    if angle:
        card = card.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    x = box[0] + (max_w - card.width) // 2
    y = box[1] + (max_h - card.height) // 2
    canvas.paste(card, (x, y), card)


def header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    centered(draw, 1000, 82, title, font(72, True), IVORY)
    centered(draw, 1000, 182, subtitle, font(34), GOLD)
    draw.line((350, 250, 1650, 250), fill=GOLD, width=3)


def image_one() -> None:
    im = background().convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    header(draw, "YOUR PERSONAL ASTROLOGY PLANNER",
           "A 430-page PDF generated from your birth chart")
    add_page(im, "page-001.jpg", (490, 310, 1510, 1600))
    draw.rounded_rectangle((245, 1640, 1755, 1900), radius=42,
                           fill=(4, 18, 38, 235), outline=GOLD, width=3)
    centered(draw, 1000, 1690, "ONE FULL YEAR • JULY 2026 – JUNE 2027",
             font(46, True), GOLD)
    centered(draw, 1000, 1772, "Personal transits • Moon phases • Monthly planning",
             font(35), IVORY)
    centered(draw, 1000, 1830, "Daily reflection pages • Downloadable PDF",
             font(35), IVORY)
    im.convert("RGB").save(OUTPUT / "01-personal-astrology-planner.jpg", quality=95)


def image_two() -> None:
    im = background().convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    header(draw, "SEE WHAT'S INSIDE", "Real pages from your personalized planner")
    cards = [
        ("page-004.jpg", (80, 330, 980, 1080), "YEAR AT A GLANCE"),
        ("page-007.jpg", (1020, 330, 1920, 1080), "MOON PHASES"),
        ("page-010.jpg", (80, 1110, 980, 1860), "NATAL SNAPSHOT"),
        ("page-012.jpg", (1020, 1110, 1920, 1860), "MONTHLY CALENDAR"),
    ]
    for filename, box, label in cards:
        add_page(im, filename, (box[0] + 15, box[1] + 65, box[2] - 15, box[3]))
        draw.rounded_rectangle((box[0], box[1], box[2], box[1] + 78),
                               radius=24, fill=(4, 18, 38, 240),
                               outline=GOLD, width=2)
        centered(draw, (box[0] + box[2]) // 2, box[1] + 18, label,
                 font(34, True), GOLD)
    im.convert("RGB").save(OUTPUT / "02-whats-inside-the-planner.jpg", quality=95)


def image_three() -> None:
    im = background().convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    header(draw, "PERSONAL TRANSITS, DAY BY DAY",
           "Plan, observe and record your own patterns")
    add_page(im, "page-011.jpg", (60, 340, 980, 1630), angle=-2)
    add_page(im, "page-014.jpg", (1000, 320, 1940, 1630), angle=2)
    draw.rounded_rectangle((120, 1660, 1880, 1910), radius=42,
                           fill=(4, 18, 38, 238), outline=LAVENDER, width=3)
    labels = [
        (410, "MAJOR ASPECTS"),
        (800, "MOON PHASE"),
        (1200, "ACTIVE TRANSITS"),
        (1590, "SPACE FOR NOTES"),
    ]
    for x, label in labels:
        draw.ellipse((x - 12, 1717, x + 12, 1741), fill=GOLD)
        centered(draw, x, 1772, label, font(28, True), IVORY)
    centered(draw, 1000, 1842, "Includes monthly dashboards and daily transit records",
             font(34), GOLD)
    im.convert("RGB").save(OUTPUT / "03-personal-transits-day-by-day.jpg", quality=95)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image_one()
    image_two()
    image_three()
    for path in sorted(OUTPUT.glob("*.jpg")):
        print(path.resolve())
