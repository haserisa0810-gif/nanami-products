from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("output/etsy/chart-companion-images")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")

IVORY = "#FFF8E8"
GOLD = "#D6AE5B"
LAVENDER = "#C9B8FF"
NAVY_PANEL = (5, 17, 39, 220)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
             fnt: ImageFont.FreeTypeFont, fill: str) -> None:
    x, y = xy
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - (box[2] - box[0]) / 2, y), text, font=fnt, fill=fill)


def rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                  radius: int = 34) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=NAVY_PANEL, outline=(214, 174, 91, 190), width=3)


def modes() -> None:
    image = Image.open(ROOT / "modes-background.png").convert("RGBA").resize((2000, 2000), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((110, 70, 1890, 285), radius=40, fill=(4, 15, 35, 218))
    centered(draw, (1000, 103), "ONE CHART. TWO WAYS TO USE IT.", font(76, True), IVORY)
    centered(draw, (1000, 205), "Choose a complete reading or continue with a personal consultation.", font(34), GOLD)

    rounded_panel(draw, (120, 1490, 950, 1880))
    rounded_panel(draw, (1050, 1490, 1880, 1880))
    centered(draw, (535, 1555), "READING MODE", font(58, True), GOLD)
    centered(draw, (535, 1655), "Receive a complete", font(38), IVORY)
    centered(draw, (535, 1710), "personalized astrology reading", font(38), IVORY)
    centered(draw, (1465, 1555), "CONSULTATION MODE", font(58, True), LAVENDER)
    centered(draw, (1465, 1655), "Ask follow-up questions", font(38), IVORY)
    centered(draw, (1465, 1710), "with your chart in context", font(38), IVORY)
    image.convert("RGB").save(ROOT / "01-reading-and-consultation-modes.jpg", quality=95)


def saving() -> None:
    image = Image.open(ROOT / "saving-background.png").convert("RGBA").resize((2000, 2000), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((120, 60, 1880, 275), radius=40, fill=(4, 15, 35, 222))
    centered(draw, (1000, 92), "FOR SAVING THE DATA", font(84, True), IVORY)
    centered(draw, (1000, 205), "Download once. Keep your astrology files for later.", font(38), GOLD)

    labels = [
        (340, "1-YEAR PLANNER", "(PDF)"),
        (1000, "SAVE ZIP", "All files together"),
        (1658, "SAVED URL", "Reopen on another device"),
    ]
    for x, title, subtitle in labels:
        draw.rounded_rectangle((x - 275, 1690, x + 275, 1900), radius=32, fill=(4, 15, 35, 225),
                               outline=(214, 174, 91, 185), width=3)
        centered(draw, (x, 1732), title, font(42, True), GOLD)
        centered(draw, (x, 1805), subtitle, font(28), IVORY)
    image.convert("RGB").save(ROOT / "02-for-saving-the-data.jpg", quality=95)


def consultation() -> None:
    image = Image.open(ROOT / "consultation-background.png").convert("RGBA").resize((2000, 2000), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((90, 85, 1090, 500), radius=44, fill=(4, 15, 35, 220),
                           outline=(214, 174, 91, 150), width=3)
    draw.text((150, 140), "ASK YOUR", font=font(72, True), fill=IVORY)
    draw.text((150, 225), "AI ASTROLOGER", font=font(72, True), fill=GOLD)
    draw.text((150, 335), "Work  •  Relationships  •  Timing", font=font(31), fill=IVORY)
    draw.text((150, 385), "Creative projects  •  Future direction", font=font(31), fill=IVORY)

    draw.rounded_rectangle((150, 1730, 1850, 1905), radius=44, fill=(4, 15, 35, 224),
                           outline=(201, 184, 255, 170), width=3)
    centered(draw, (1000, 1772), "A READING THAT CAN BECOME A CONVERSATION", font(45, True), LAVENDER)
    centered(draw, (1000, 1843), "Keep asking questions without starting over.", font(33), IVORY)
    image.convert("RGB").save(ROOT / "03-ai-astrology-consultation.jpg", quality=95)


if __name__ == "__main__":
    modes()
    saving()
    consultation()
    for path in sorted(ROOT.glob("0*.jpg")):
        print(path.resolve())
