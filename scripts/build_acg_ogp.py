"""Build locale-specific Open Graph images for the public ACG map."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static"
WIDTH, HEIGHT = 1200, 630
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")

COPY = {
    "en": ("ASTROCARTOGRAPHY", "See where your stars shine in the world", "Interactive map · Personal lines · AI-ready place guidance"),
    "es": ("ASTROCARTOGRAFÍA", "Descubre dónde brillan tus astros", "Mapa interactivo · Líneas personales · Guía para IA"),
    "de": ("ASTROKARTOGRAFIE", "Entdecke, wo deine Sterne weltweit wirken", "Interaktive Karte · Persönliche Linien · KI-fertige Ortsanalyse"),
}


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > 32:
        candidate = font(size, bold=True)
        box = draw.textbbox((0, 0), text, font=candidate)
        if box[2] - box[0] <= max_width:
            return candidate
        size -= 2
    return font(32, bold=True)


def build(locale: str) -> Path:
    title, subtitle, detail = COPY[locale]
    image = Image.new("RGB", (WIDTH, HEIGHT), "#07162F")
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.ellipse((680, -260, 1350, 420), fill=(65, 55, 145, 150))
    gd.ellipse((-240, 270, 480, 950), fill=(12, 104, 138, 125))
    glow = glow.filter(ImageFilter.GaussianBlur(85))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    draw = ImageDraw.Draw(image, "RGBA")

    # Abstract world/ACG-line motif; no language-bearing map labels.
    draw.ellipse((715, 70, 1165, 520), outline=(213, 178, 78, 95), width=3)
    draw.ellipse((785, 70, 1095, 520), outline=(213, 178, 78, 55), width=2)
    for x, color, width in ((790, (242, 192, 75, 230), 5), (900, (203, 142, 242, 190), 4), (1015, (92, 197, 232, 180), 4)):
        draw.arc((x - 120, 50, x + 120, 540), 84, 276, fill=color, width=width)
    for y in (175, 295, 415):
        draw.arc((715, y - 75, 1165, y + 75), 0, 180, fill=(230, 238, 249, 48), width=2)

    draw.text((70, 66), "NANAMI ASTRO · ACG", font=font(26, bold=True), fill="#DAB64F")
    draw.line((70, 112, 610, 112), fill=(218, 182, 79, 130), width=2)
    title_font = fit(draw, title, 600, 66)
    draw.text((70, 170), title, font=title_font, fill="#FFF8E8")
    draw.text((70, 268), subtitle, font=fit(draw, subtitle, 560, 40), fill="#E3C15A")
    detail_font = font(27)
    words = detail.split(" · ")
    for index, item in enumerate(words):
        y = 365 + index * 48
        draw.ellipse((72, y + 9, 82, y + 19), fill="#C8B2F4")
        draw.text((98, y), item, font=detail_font, fill="#E8EDF7")

    output = OUT / f"ogp_acg_{locale}.jpg"
    image.convert("RGB").save(output, quality=94, optimize=True)
    return output


def main() -> None:
    for locale in COPY:
        print(build(locale))


if __name__ == "__main__":
    main()
