"""Build Spanish Etsy listing images for the Western FULL edition.

The planner screenshots must come from the rendered Spanish sample PDF.  This
keeps the sales images tied to the product buyers will actually receive instead
of using an invented UI mockup.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "tmp" / "pdfs" / "planner-marketing-pages-es"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "etsy" / "western-full-es" / "listing-images"

NAVY = "#101A35"
NAVY_2 = "#17274A"
DEEP_NAVY = "#041226"
GOLD = "#D5A84D"
CREAM = "#F6F0E3"
PALE = "#DCE6EA"
MUTED = "#AAB7C8"
WHITE = "#FFFFFF"
TEAL = "#6CB7AE"
LAVENDER = "#C9B8FF"

FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def centered(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    text_font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    box = draw.textbbox((0, 0), text, font=text_font)
    draw.text((x - (box[2] - box[0]) / 2, y - box[1]), text, font=text_font, fill=fill)


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, *, bold: bool = False):
    while size > 22:
        candidate = font(size, bold)
        box = draw.textbbox((0, 0), text, font=candidate)
        if box[2] - box[0] <= max_width:
            return candidate
        size -= 2
    return font(size, bold)


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill: str, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def main_listing_image(output_dir: Path) -> Path:
    width, height = 1600, 1270
    image = Image.new("RGB", (width, height), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 22), fill=GOLD)
    draw.text((82, 58), "NANAMI ASTRO", font=font(27, True), fill=MUTED)

    badge_text = "EDICIÓN EN ESPAÑOL"
    badge_font = font(27, True)
    badge_box = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_width = badge_box[2] - badge_box[0] + 58
    rounded(draw, (1510 - badge_width, 50, 1510, 112), 31, GOLD)
    centered(draw, 1510 - badge_width // 2, 67, badge_text, badge_font, NAVY)

    draw.text((82, 158), "PAQUETE PERSONALIZADO COMPLETO", font=font(36, True), fill=GOLD)
    title_lines = ("CARTA NATAL + ASTEROIDES", "TRÁNSITOS + PLANIFICADOR")
    for index, line in enumerate(title_lines):
        title_font = fit_font(draw, line, 1435, 72, bold=True)
        draw.text((76, 222 + index * 92), line, font=title_font, fill=WHITE)
    draw.text((82, 420), "El paquete completo de astrología occidental", font=font(34), fill=PALE)

    rounded(draw, (82, 590, 292, 650), 30, TEAL)
    centered(draw, 187, 604, "NP-WF-ES", font(28, True), NAVY)
    draw.text((322, 603), "Datos astrológicos calculados y listos para IA", font=font(27, True), fill=MUTED)

    cards = (
        ("Carta natal", "Planetas, casas\ny aspectos"),
        ("Asteroides", "Quirón, Lilith,\nJuno y más"),
        ("Tránsitos", "31 días + planificador\nde 1 año"),
    )
    for index, (title, detail) in enumerate(cards):
        left = 90 + index * 510
        rounded(draw, (left, 700, left + 430, 870), 26, NAVY_2, "#31446A", 3)
        draw.ellipse((left + 28, 734, left + 54, 760), fill=GOLD)
        draw.text((left + 76, 727), title, font=font(31, True), fill=WHITE)
        draw.multiline_text((left + 30, 792), detail, font=font(25), fill=PALE, spacing=3)

    steps = (("1", "Pedido Etsy"), ("2", "Datos de nacimiento"), ("3", "Acceso automático"))
    for index, (number, label) in enumerate(steps):
        left = 90 + index * 500
        rounded(draw, (left, 1015, left + 420, 1138), 24, CREAM)
        rounded(draw, (left + 24, 1044, left + 90, 1110), 33, GOLD)
        centered(draw, left + 57, 1054, number, font(31, True), NAVY)
        label_font = fit_font(draw, label, 292, 29, bold=True)
        draw.text((left + 112, 1053), label, font=label_font, fill=NAVY)
    for x in (530, 1030):
        draw.line((x, 1077, x + 40, 1077), fill=TEAL, width=8)
        draw.polygon([(x + 40, 1077), (x + 20, 1061), (x + 20, 1093)], fill=TEAL)

    centered(
        draw,
        800,
        1176,
        "Descarga la guía y crea tus datos personalizados al instante",
        fit_font(draw, "Descarga la guía y crea tus datos personalizados al instante", 1370, 29, bold=True),
        TEAL,
    )
    draw.text((82, 1230), "Producto digital personalizado - sin envío físico", font=font(21), fill=MUTED)
    draw.text((1365, 1230), "nanami-astro", font=font(22, True), fill=MUTED)

    output = output_dir / "01-full-bundle-edicion-espanol.jpg"
    image.save(output, "JPEG", quality=95, optimize=True)
    return output


def square_background() -> Image.Image:
    image = Image.new("RGB", (2000, 2000), NAVY)
    draw = ImageDraw.Draw(image)
    for y in range(2000):
        t = y / 1999
        color = (
            int(16 * (1 - t) + 4 * t),
            int(26 * (1 - t) + 18 * t),
            int(53 * (1 - t) + 38 * t),
        )
        draw.line((0, y, 2000, y), fill=color)
    for x, y, radius in ((130, 320, 4), (1840, 430, 5), (1770, 1240, 3), (230, 1510, 4)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=GOLD)
    return image


def add_page(
    canvas: Image.Image,
    source_dir: Path,
    filename: str,
    box: tuple[int, int, int, int],
    *,
    angle: float = 0,
) -> None:
    page = Image.open(source_dir / filename).convert("RGB")
    max_width, max_height = box[2] - box[0], box[3] - box[1]
    page.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
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
    x = box[0] + (max_width - card.width) // 2
    y = box[1] + (max_height - card.height) // 2
    canvas.paste(card, (x, y), card)


def add_cropped_page(
    canvas: Image.Image,
    source_dir: Path,
    filename: str,
    crop: tuple[int, int, int, int],
    box: tuple[int, int, int, int],
) -> None:
    page = Image.open(source_dir / filename).convert("RGB").crop(crop)
    max_width, max_height = box[2] - box[0], box[3] - box[1]
    page.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", (page.width + 80, page.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (34, 34, page.width + 34, page.height + 34), radius=12, fill=(0, 0, 0, 175)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    card = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    card.alpha_composite(shadow)
    card.paste(page, (20, 20))
    x = box[0] + (max_width - card.width) // 2
    y = box[1] + (max_height - card.height) // 2
    canvas.paste(card, (x, y), card)


def square_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    title_font = fit_font(draw, title, 1780, 70, bold=True)
    centered(draw, 1000, 72, title, title_font, CREAM)
    centered(draw, 1000, 176, subtitle, fit_font(draw, subtitle, 1700, 34), GOLD)
    draw.line((350, 252, 1650, 252), fill=GOLD, width=3)


def planner_overview(source_dir: Path, output_dir: Path) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(draw, "TU PLANIFICADOR ASTROLÓGICO PERSONAL", "Más de 400 páginas en español basadas en tu carta natal")
    add_page(image, source_dir, "page-004.jpg", (465, 310, 1535, 1630))
    rounded(draw, (230, 1660, 1770, 1910), 42, DEEP_NAVY, GOLD, 3)
    centered(draw, 1000, 1700, "UN AÑO COMPLETO • AGOSTO 2026 - JULIO 2027", font(43, True), GOLD)
    centered(draw, 1000, 1782, "Tránsitos personales • Fases lunares • Planificación mensual", font(33), CREAM)
    centered(draw, 1000, 1840, "Páginas diarias • Reflexión • PDF descargable", font(33), CREAM)
    output = output_dir / "02-planificador-personal-espanol.jpg"
    image.convert("RGB").save(output, "JPEG", quality=95, optimize=True)
    return output


def planner_inside(source_dir: Path, output_dir: Path) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(draw, "DESCUBRE EL INTERIOR", "Páginas reales de tu planificador personalizado")
    panels = (
        ("page-007.jpg", (80, 330, 980, 1830), "FASES LUNARES"),
        ("page-010.jpg", (1020, 330, 1920, 1830), "INSTANTÁNEA NATAL"),
    )
    for filename, box, label in panels:
        rounded(draw, (box[0], box[1], box[2], box[1] + 80), 24, DEEP_NAVY, GOLD, 2)
        centered(draw, (box[0] + box[2]) // 2, box[1] + 18, label, font(33, True), GOLD)
        add_page(image, source_dir, filename, (box[0] + 20, box[1] + 100, box[2] - 20, box[3]))
    centered(draw, 1000, 1900, "Datos calculados y contenido en español", font(34, True), TEAL)
    output = output_dir / "03-interior-planificador-espanol.jpg"
    image.convert("RGB").save(output, "JPEG", quality=95, optimize=True)
    return output


def planner_transits(source_dir: Path, output_dir: Path) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(draw, "TUS TRÁNSITOS PERSONALES, DÍA A DÍA", "Planifica, observa y registra tus propios patrones")
    add_page(image, source_dir, "page-011.jpg", (65, 330, 985, 1630), angle=-2)
    add_page(image, source_dir, "page-014.jpg", (1015, 330, 1935, 1630), angle=2)
    rounded(draw, (120, 1660, 1880, 1910), 42, DEEP_NAVY, LAVENDER, 3)
    labels = ((360, "ASPECTOS"), (780, "FASE LUNAR"), (1220, "TRÁNSITOS"), (1650, "NOTAS"))
    for x, label in labels:
        draw.ellipse((x - 12, 1714, x + 12, 1738), fill=GOLD)
        centered(draw, x, 1770, label, font(28, True), CREAM)
    centered(draw, 1000, 1842, "Incluye calendarios mensuales y seguimiento de tránsitos", font(33), GOLD)
    output = output_dir / "04-transitos-personales-espanol.jpg"
    image.convert("RGB").save(output, "JPEG", quality=95, optimize=True)
    return output


def planner_closeup(
    source_dir: Path,
    output_dir: Path,
    *,
    source_name: str,
    crop: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    output_name: str,
) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(draw, title, subtitle)
    add_cropped_page(image, source_dir, source_name, crop, (110, 300, 1890, 1835))
    rounded(draw, (430, 1842, 1570, 1940), 48, DEEP_NAVY, GOLD, 2)
    centered(draw, 1000, 1868, "PÁGINA REAL DEL PDF PERSONALIZADO", font(29, True), GOLD)
    output = output_dir / output_name
    image.convert("RGB").save(output, "JPEG", quality=96, optimize=True)
    return output


def build(source_dir: Path, output_dir: Path) -> list[Path]:
    required = {"page-004.jpg", "page-007.jpg", "page-010.jpg", "page-011.jpg", "page-014.jpg"}
    missing = sorted(name for name in required if not (source_dir / name).exists())
    if missing:
        raise FileNotFoundError(f"Missing rendered Spanish planner pages: {', '.join(missing)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        main_listing_image(output_dir),
        planner_overview(source_dir, output_dir),
        planner_inside(source_dir, output_dir),
        planner_transits(source_dir, output_dir),
        planner_closeup(
            source_dir,
            output_dir,
            source_name="page-010.jpg",
            crop=(35, 60, 1155, 1190),
            title="CONTENIDO REAL EN ESPAÑOL",
            subtitle="Carta natal, posiciones y temas personales",
            output_name="05-contenido-espanol-carta-natal.jpg",
        ),
        planner_closeup(
            source_dir,
            output_dir,
            source_name="page-007.jpg",
            crop=(35, 40, 1155, 1430),
            title="FASES LUNARES EN ESPAÑOL",
            subtitle="Fechas, horas y signos del ciclo lunar",
            output_name="06-contenido-espanol-fases-lunares.jpg",
        ),
        planner_closeup(
            source_dir,
            output_dir,
            source_name="page-014.jpg",
            crop=(35, 40, 1155, 1340),
            title="CALENDARIO MENSUAL EN ESPAÑOL",
            subtitle="Eventos astrológicos y fechas personales",
            output_name="07-contenido-espanol-calendario-mensual.jpg",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for path in build(args.source_dir, args.output_dir):
        print(path.resolve())


if __name__ == "__main__":
    main()
