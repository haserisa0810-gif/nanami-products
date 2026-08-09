from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
HEIGHT = 1270
OUTPUT_DIR = Path("output/etsy/listing-images")

NAVY = "#101A35"
NAVY_2 = "#17274A"
GOLD = "#D5A84D"
CREAM = "#F6F0E3"
PALE = "#DCE6EA"
MUTED = "#AAB7C8"
WHITE = "#FFFFFF"
TEAL = "#6CB7AE"

FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw, box, value, text_font, fill):
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), value, font=text_font)
    tw = bounds[2] - bounds[0]
    th = bounds[3] - bounds[1]
    draw.text(
        ((left + right - tw) / 2, (top + bottom - th) / 2 - bounds[1]),
        value,
        font=text_font,
        fill=fill,
    )


def badge(draw, x, y, text):
    bounds = draw.textbbox((0, 0), text, font=font(30, True))
    width = bounds[2] - bounds[0] + 58
    rounded(draw, (x, y, x + width, y + 62), 31, GOLD)
    center_text(draw, (x, y, x + width, y + 62), text, font(30, True), NAVY)
    return x + width


def feature_card(draw, left, top, title, detail):
    rounded(draw, (left, top, left + 430, top + 170), 26, NAVY_2, "#31446A", 3)
    draw.ellipse((left + 28, top + 34, left + 54, top + 60), fill=GOLD)
    draw.text((left + 76, top + 27), title, font=font(33, True), fill=WHITE)
    draw.text((left + 30, top + 92), detail, font=font(26), fill=PALE)


def flow(draw):
    labels = [
        ("1", "Etsy order number"),
        ("2", "Birth details"),
        ("3", "Automatic access"),
    ]
    lefts = [90, 590, 1090]
    for (number, label), left in zip(labels, lefts):
        rounded(draw, (left, 1015, left + 420, 1138), 24, CREAM)
        rounded(draw, (left + 24, 1044, left + 90, 1110), 33, GOLD)
        center_text(draw, (left + 24, 1044, left + 90, 1110), number, font(31, True), NAVY)
        draw.text((left + 112, 1053), label, font=font(31, True), fill=NAVY)
    for x in (530, 1030):
        draw.line((x, 1077, x + 40, 1077), fill=TEAL, width=8)
        draw.polygon([(x + 40, 1077), (x + 20, 1061), (x + 20, 1093)], fill=TEAL)
    center_text(
        draw,
        (160, 1165, 1440, 1225),
        "Download the guide and create your personalized data right away",
        font(29, True),
        TEAL,
    )


def build(filename, sku, eyebrow, title_lines, subtitle, feature_data):
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, WIDTH, 22), fill=GOLD)
    draw.text((82, 58), "NANAMI ASTRO", font=font(27, True), fill=MUTED)
    badge(draw, 1190, 50, "INSTANT DIGITAL")

    draw.text((82, 158), eyebrow, font=font(38, True), fill=GOLD)
    y = 220
    for line in title_lines:
        draw.text((76, y), line, font=font(80, True), fill=WHITE)
        y += 94
    draw.text((82, y + 18), subtitle, font=font(35), fill=PALE)

    feature_y = 700
    for index, (title, detail) in enumerate(feature_data):
        feature_card(draw, 90 + index * 510, feature_y, title, detail)

    flow(draw)

    rounded(draw, (82, 590, 270, 650), 30, TEAL)
    center_text(draw, (82, 590, 270, 650), sku, font(29, True), NAVY)
    draw.text((300, 603), "AI-ready calculated astrology data", font=font(29, True), fill=MUTED)

    draw.text((82, 1230), "Personalized digital product - no physical item", font=font(22), fill=MUTED)
    draw.text((1365, 1230), "nanami-astro", font=font(22, True), fill=MUTED)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / filename
    image.save(output, "JPEG", quality=94, optimize=True)
    print(output.resolve())


def main():
    build(
        "nanami_wbt_etsy_listing.jpg",
        "NP-WBT",
        "PERSONALIZED ASTROLOGY",
        ["BIRTH CHART + TRANSITS", "1-YEAR PLANNER"],
        "Core natal data and transit timing - without asteroid data",
        [
            ("Birth Chart", "Planets, houses,\nand aspects"),
            ("Transits", "Timing and future-\nfocused readings"),
            ("1-Year Planner", "Personalized digital\nplanner PDF"),
        ],
    )
    build(
        "nanami_wf_etsy_listing.jpg",
        "NP-WF",
        "COMPLETE PERSONALIZED BUNDLE",
        ["BIRTH CHART + ASTEROIDS", "TRANSITS + PLANNER"],
        "The complete Western astrology data package",
        [
            ("Full Birth Chart", "Planets, houses,\nand aspects"),
            ("Asteroids", "Chiron, Lilith,\nJuno and more"),
            ("Transits", "31-day timing +\n1-year planner"),
        ],
    )
    build(
        "nanami_acg_etsy_listing.jpg",
        "NP-ACG",
        "PERSONALIZED ASTROCARTOGRAPHY",
        ["YOUR PLANETARY MAP", "PERSONAL EDITION"],
        "Explore where each planetary influence is strongest",
        [
            ("ACG Map", "Interactive personal\nworld map"),
            ("Birth Chart", "AI-ready calculated\nastrology data"),
            ("Personal Edition", "Permanent ZIP +\n1-year planner"),
        ],
    )


if __name__ == "__main__":
    main()
