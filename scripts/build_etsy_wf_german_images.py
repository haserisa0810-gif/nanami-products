"""Build German Etsy listing images for the Western FULL edition.

Planner screenshots are taken from the rendered German sample PDF so every
visible product page matches the file buyers will generate.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from scripts.build_etsy_wf_spanish_images import (
        CREAM,
        DEEP_NAVY,
        GOLD,
        LAVENDER,
        MUTED,
        NAVY,
        NAVY_2,
        PALE,
        REPO_ROOT,
        TEAL,
        WHITE,
        add_cropped_page,
        add_page,
        centered,
        fit_font,
        font,
        rounded,
        square_background,
        square_header,
    )
except ModuleNotFoundError:  # direct execution: python scripts/<file>.py
    from build_etsy_wf_spanish_images import (
        CREAM,
        DEEP_NAVY,
        GOLD,
        LAVENDER,
        MUTED,
        NAVY,
        NAVY_2,
        PALE,
        REPO_ROOT,
        TEAL,
        WHITE,
        add_cropped_page,
        add_page,
        centered,
        fit_font,
        font,
        rounded,
        square_background,
        square_header,
    )


DEFAULT_SOURCE = REPO_ROOT / "tmp" / "pdfs" / "planner-marketing-pages-de"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "etsy" / "western-full-de" / "listing-images"
DEFAULT_PLANNER_PDF = (
    REPO_ROOT
    / "output"
    / "etsy"
    / "western-full-de"
    / "planner-sample"
    / "neko-editor-transit-planner-2026-2027-de.pdf"
)


def main_listing_image(output_dir: Path) -> Path:
    width, height = 1600, 1270
    image = Image.new("RGB", (width, height), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 22), fill=GOLD)
    draw.text((82, 58), "NANAMI ASTRO", font=font(27, True), fill=MUTED)

    badge_text = "DEUTSCHE AUSGABE"
    badge_font = font(27, True)
    badge_box = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_width = badge_box[2] - badge_box[0] + 58
    rounded(draw, (1510 - badge_width, 50, 1510, 112), 31, GOLD)
    centered(draw, 1510 - badge_width // 2, 67, badge_text, badge_font, NAVY)

    draw.text((82, 158), "PERSONALISIERTES KOMPLETTPAKET", font=font(36, True), fill=GOLD)
    title_lines = ("GEBURTSHOROSKOP + ASTEROIDEN", "TRANSITE + 12-MONATS-PLANER")
    for index, line in enumerate(title_lines):
        title_font = fit_font(draw, line, 1435, 72, bold=True)
        draw.text((76, 222 + index * 92), line, font=title_font, fill=WHITE)
    draw.text((82, 420), "Das Komplettpaket für westliche Astrologie", font=font(34), fill=PALE)

    rounded(draw, (82, 590, 292, 650), 30, TEAL)
    centered(draw, 187, 604, "NP-WF-DE", font(28, True), NAVY)
    draw.text((322, 603), "Berechnete Astrologiedaten, bereit für KI", font=font(27, True), fill=MUTED)

    cards = (
        ("Geburtshoroskop", "Planeten, Häuser\nund Aspekte"),
        ("Asteroiden", "Chiron, Lilith,\nJuno und mehr"),
        ("Transite", "31 Tage + persönlicher\nJahresplaner"),
    )
    for index, (title, detail) in enumerate(cards):
        left = 90 + index * 510
        rounded(draw, (left, 700, left + 430, 870), 26, NAVY_2, "#31446A", 3)
        draw.ellipse((left + 28, 734, left + 54, 760), fill=GOLD)
        draw.text((left + 76, 727), title, font=fit_font(draw, title, 325, 31, bold=True), fill=WHITE)
        draw.multiline_text((left + 30, 792), detail, font=font(25), fill=PALE, spacing=3)

    steps = (("1", "Etsy-Bestellung"), ("2", "Geburtsdaten"), ("3", "Sofortiger Zugriff"))
    for index, (number, label) in enumerate(steps):
        left = 90 + index * 500
        rounded(draw, (left, 1015, left + 420, 1138), 24, CREAM)
        rounded(draw, (left + 24, 1044, left + 90, 1110), 33, GOLD)
        centered(draw, left + 57, 1054, number, font(31, True), NAVY)
        draw.text((left + 112, 1053), label, font=fit_font(draw, label, 292, 29, bold=True), fill=NAVY)
    for x in (530, 1030):
        draw.line((x, 1077, x + 40, 1077), fill=TEAL, width=8)
        draw.polygon([(x + 40, 1077), (x + 20, 1061), (x + 20, 1093)], fill=TEAL)

    footer = "Anleitung herunterladen und deine persönliche Edition erstellen"
    centered(draw, 800, 1176, footer, fit_font(draw, footer, 1370, 29, bold=True), TEAL)
    draw.text((82, 1230), "Personalisiertes digitales Produkt - kein physischer Versand", font=font(21), fill=MUTED)
    draw.text((1365, 1230), "nanami-astro", font=font(22, True), fill=MUTED)

    output = output_dir / "01-full-bundle-deutsche-ausgabe.jpg"
    image.save(output, "JPEG", quality=95, optimize=True)
    return output


def planner_overview(source_dir: Path, output_dir: Path) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(
        draw,
        "DEIN PERSÖNLICHER ASTROLOGIE-PLANER",
        "Über 400 Seiten auf Deutsch, basierend auf deinem Geburtshoroskop",
    )
    add_page(image, source_dir, "page-004.jpg", (465, 310, 1535, 1630))
    rounded(draw, (230, 1660, 1770, 1910), 42, DEEP_NAVY, GOLD, 3)
    centered(draw, 1000, 1700, "EIN VOLLES JAHR • AUGUST 2026 - JULI 2027", font(43, True), GOLD)
    centered(draw, 1000, 1782, "Persönliche Transite • Mondphasen • Monatsplanung", font(33), CREAM)
    centered(draw, 1000, 1840, "Tagesseiten • Reflexion • PDF-Download", font(33), CREAM)
    output = output_dir / "02-persoenlicher-astrologie-planer.jpg"
    image.convert("RGB").save(output, "JPEG", quality=95, optimize=True)
    return output


def planner_inside(source_dir: Path, output_dir: Path) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(draw, "BLICK IN DEN PLANER", "Echte Seiten aus deinem persönlichen Planer")
    panels = (
        ("page-007.jpg", (80, 330, 980, 1830), "MONDPHASEN"),
        ("page-010.jpg", (1020, 330, 1920, 1830), "RADIX-MOMENTAUFNAHME"),
    )
    for filename, box, label in panels:
        rounded(draw, (box[0], box[1], box[2], box[1] + 80), 24, DEEP_NAVY, GOLD, 2)
        centered(draw, (box[0] + box[2]) // 2, box[1] + 18, label, fit_font(draw, label, 780, 33, bold=True), GOLD)
        add_page(image, source_dir, filename, (box[0] + 20, box[1] + 100, box[2] - 20, box[3]))
    centered(draw, 1000, 1900, "Berechnete Daten und Inhalte auf Deutsch", font(34, True), TEAL)
    output = output_dir / "03-einblick-in-den-planer.jpg"
    image.convert("RGB").save(output, "JPEG", quality=95, optimize=True)
    return output


def planner_transits(source_dir: Path, output_dir: Path) -> Path:
    image = square_background().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    square_header(draw, "DEINE PERSÖNLICHEN TRANSITE - TAG FÜR TAG", "Planen, beobachten und eigene Muster festhalten")
    add_page(image, source_dir, "page-011.jpg", (65, 330, 985, 1630), angle=-2)
    add_page(image, source_dir, "page-014.jpg", (1015, 330, 1935, 1630), angle=2)
    rounded(draw, (120, 1660, 1880, 1910), 42, DEEP_NAVY, LAVENDER, 3)
    labels = ((360, "ASPEKTE"), (780, "MONDPHASE"), (1220, "TRANSITE"), (1650, "NOTIZEN"))
    for x, label in labels:
        draw.ellipse((x - 12, 1714, x + 12, 1738), fill=GOLD)
        centered(draw, x, 1770, label, font(28, True), CREAM)
    centered(draw, 1000, 1842, "Mit Monatskalendern und persönlicher Transitübersicht", font(33), GOLD)
    output = output_dir / "04-persoenliche-transite-tag-fuer-tag.jpg"
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
    rounded(draw, (410, 1842, 1590, 1940), 48, DEEP_NAVY, GOLD, 2)
    centered(draw, 1000, 1868, "ECHTE SEITE AUS DEM PERSÖNLICHEN PDF", font(29, True), GOLD)
    output = output_dir / output_name
    image.convert("RGB").save(output, "JPEG", quality=96, optimize=True)
    return output


def build(source_dir: Path, output_dir: Path) -> list[Path]:
    required = {"page-004.jpg", "page-007.jpg", "page-010.jpg", "page-011.jpg", "page-014.jpg"}
    missing = sorted(name for name in required if not (source_dir / name).exists())
    if missing:
        raise FileNotFoundError(f"Missing rendered German planner pages: {', '.join(missing)}")
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
            title="ECHTE INHALTE AUF DEUTSCH",
            subtitle="Geburtshoroskop, Positionen und persönliche Themen",
            output_name="05-deutsche-inhalte-geburtshoroskop.jpg",
        ),
        planner_closeup(
            source_dir,
            output_dir,
            source_name="page-007.jpg",
            crop=(35, 40, 1155, 1430),
            title="MONDPHASEN AUF DEUTSCH",
            subtitle="Daten, Uhrzeiten und Zeichen des Mondzyklus",
            output_name="06-deutsche-inhalte-mondphasen.jpg",
        ),
        planner_closeup(
            source_dir,
            output_dir,
            source_name="page-014.jpg",
            crop=(35, 40, 1155, 1340),
            title="MONATSKALENDER AUF DEUTSCH",
            subtitle="Astrologische Ereignisse und persönliche Termine",
            output_name="07-deutsche-inhalte-monatskalender.jpg",
        ),
    ]


def render_planner_pages(planner_pdf: Path, output_dir: Path) -> Path:
    if not planner_pdf.exists():
        raise FileNotFoundError(f"German planner PDF is missing: {planner_pdf}")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "pdftoppm",
            "-f",
            "1",
            "-l",
            "14",
            "-jpeg",
            "-r",
            "150",
            str(planner_pdf),
            str(output_dir / "page"),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not render German planner pages: {result.stderr.strip()}")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="optional pre-rendered page directory; otherwise pages are rendered from --planner-pdf",
    )
    parser.add_argument("--planner-pdf", type=Path, default=DEFAULT_PLANNER_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.source_dir:
        outputs = build(args.source_dir, args.output_dir)
    else:
        with tempfile.TemporaryDirectory(prefix="etsy_wf_de_pages_") as temporary:
            outputs = build(
                render_planner_pages(args.planner_pdf, Path(temporary)),
                args.output_dir,
            )
    for path in outputs:
        print(path.resolve())


if __name__ == "__main__":
    main()
