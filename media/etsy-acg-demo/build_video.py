from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
ENGLISH_FRAMES = ROOT / "frames-en"
OUTPUT = ROOT / "etsy_acg_demo_15s.mp4"
WIDTH, HEIGHT, FPS, DURATION = 1080, 2160, 30, 15


SCENES = [
    (0.0, 1.2, "01_yaml_panel.png", "Open your ACG map", (0.76, 0.92)),
    (1.2, 3.0, "02_yaml_loaded.png", "Your personal\nastrocartography data", (0.50, 0.49)),
    (3.0, 5.0, "03_lines_map.png", "See your planetary lines\nacross the world", (0.82, 0.94)),
    (5.0, 6.5, "04_london_typed.png", "Search any destination", (0.55, 0.51)),
    (6.5, 8.5, "05_london_results.png", "Explore London", (0.47, 0.56)),
    (8.5, 10.5, "07_london_map.png", "Work  •  Creativity  •  Travel\nRelocation", (0.52, 0.55)),
    (10.5, 12.5, "06_london_explanation.png", "Use it with AI for personalized\nlocation guidance", (0.50, 0.65)),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size)


def cover(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def english_ui(image: Image.Image, filename: str) -> Image.Image:
    """Replace localized map/search strings in captured frames for the English listing."""
    image = image.copy()
    draw = ImageDraw.Draw(image, "RGBA")
    navy = (5, 14, 43, 255)
    border = (45, 57, 89, 255)
    white = (239, 242, 249, 255)

    # Keep the sales video language-pure while the live product retains its
    # locale switcher.  The original captures remain untouched.
    draw.rounded_rectangle((816, 18, 1058, 84), radius=18, fill=navy, outline=border, width=2)
    draw.text((937, 51), "ENGLISH", font=font(25, bold=True), fill=(224, 181, 45, 255), anchor="mm")

    if filename in {"03_lines_map.png", "07_london_map.png"}:
        draw.rounded_rectangle((992, 104, 1068, 178), radius=16, fill=navy, outline=border, width=2)
        draw.text((1030, 141), "Map", font=font(25, bold=True), fill=(224, 181, 45, 255), anchor="mm")

    if filename == "05_london_results.png":
        labels = [
            "Greater London, England, United Kingdom",
            "London, Southwestern Ontario, Canada",
            "London, Laurel County, Kentucky, 40741, USA",
            "London, Madison County, Ohio, 43140, USA",
            "London, Pope County, Arkansas, USA",
        ]
        # Cover the complete original results stack, including the final
        # Japanese geocoder row at the bottom of the capture.
        draw.rectangle((20, 1058, 1060, 1605), fill=(11, 24, 66, 255))
        draw.text((26, 1080), "Results (click to select a point)", font=font(25), fill=(180, 189, 211, 255), anchor="lm")
        rows = [(1100, 1180), (1190, 1270), (1280, 1360), (1370, 1450), (1460, 1540)]
        row_font = font(27)
        for label, (top, bottom) in zip(labels, rows):
            draw.rounded_rectangle((24, top, 1056, bottom), radius=10, fill=navy, outline=border, width=2)
            draw.text((48, (top + bottom) // 2), label, font=row_font, fill=white, anchor="lm")

    if filename == "06_london_explanation.png":
        # The source has both a Latin and Japanese place-name row. Replace the
        # full two-row block so no lower row remains visible in English media.
        draw.rounded_rectangle((24, 860, 1056, 1046), radius=10, fill=navy, outline=border, width=2)
        draw.text((48, 953), "Greater London, England, United Kingdom", font=font(29), fill=white, anchor="lm")

    return image


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > 30:
        candidate = font(size, bold=True)
        boxes = [draw.textbbox((0, 0), line, font=candidate) for line in text.splitlines()]
        if max((box[2] - box[0] for box in boxes), default=0) <= max_width:
            return candidate
        size -= 2
    return font(30, bold=True)


def draw_caption(image: Image.Image, text: str) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    lines = text.splitlines()
    caption_font = fit_text(draw, text, WIDTH - 120, 62)
    line_height = int(caption_font.size * 1.25)
    box_height = 82 + line_height * len(lines)
    y0 = 120
    draw.rounded_rectangle((42, y0, WIDTH - 42, y0 + box_height), radius=28, fill=(5, 14, 43, 225), outline=(214, 170, 34, 245), width=3)
    y = y0 + 38
    for line in lines:
        box = draw.textbbox((0, 0), line, font=caption_font)
        x = (WIDTH - (box[2] - box[0])) // 2
        draw.text((x + 2, y + 3), line, font=caption_font, fill=(0, 0, 0, 150))
        draw.text((x, y), line, font=caption_font, fill=(255, 255, 255, 255))
        y += line_height


def draw_cursor(image: Image.Image, xy: tuple[float, float], pulse: float) -> None:
    x, y = int(xy[0] * WIDTH), int(xy[1] * HEIGHT)
    draw = ImageDraw.Draw(image, "RGBA")
    if pulse > 0:
        radius = int(24 + 30 * pulse)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=(255, 204, 48, int(210 * (1 - pulse))), width=8)
    points = [(x, y), (x + 8, y + 62), (x + 25, y + 47), (x + 43, y + 85), (x + 59, y + 77), (x + 41, y + 40), (x + 67, y + 38)]
    draw.polygon(points, fill=(255, 255, 255, 255), outline=(6, 12, 30, 255))


def final_card(background: Image.Image, progress: float) -> Image.Image:
    image = background.copy()
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(4, 12, 38, 220))
    gold = (222, 178, 42, 255)
    title = font(82, bold=True)
    body = font(56, bold=True)
    small = font(38)
    draw.text((WIDTH // 2, 710), "YOUR PERSONAL", font=small, fill=(230, 235, 245, 255), anchor="mm")
    draw.text((WIDTH // 2, 815), "ASTROCARTOGRAPHY", font=title, fill=gold, anchor="mm")
    draw.text((WIDTH // 2, 920), "MAP + AI-READY DATA", font=body, fill=(255, 255, 255, 255), anchor="mm")
    draw.rounded_rectangle((135, 1070, WIDTH - 135, 1250), radius=42, fill=gold)
    draw.text((WIDTH // 2, 1160), "INSTANT DIGITAL DOWNLOAD", font=font(46, bold=True), fill=(7, 16, 45, 255), anchor="mm")
    draw.text((WIDTH // 2, 1380), "Explore • compare • ask AI", font=small, fill=(230, 235, 245, 255), anchor="mm")
    return image


def render(ffmpeg: Path, output: Path) -> None:
    sources = {name: english_ui(cover(FRAMES / name), name) for _, _, name, _, _ in SCENES}
    ENGLISH_FRAMES.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        source.save(ENGLISH_FRAMES / name, optimize=True)
    final_bg = sources["03_lines_map.png"]
    command = [
        str(ffmpeg), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    previous_cursor = SCENES[0][4]
    for frame_no in range(FPS * DURATION):
        t = frame_no / FPS
        if t >= 12.5:
            image = final_card(final_bg, (t - 12.5) / 2.5)
        else:
            scene_index = next(i for i, scene in enumerate(SCENES) if scene[0] <= t < scene[1])
            start, end, filename, caption, target = SCENES[scene_index]
            image = sources[filename].copy()
            draw_caption(image, caption)
            local = min(1.0, max(0.0, (t - start) / max(0.35, end - start)))
            ease = local * local * (3 - 2 * local)
            cursor = (previous_cursor[0] + (target[0] - previous_cursor[0]) * ease, previous_cursor[1] + (target[1] - previous_cursor[1]) * ease)
            pulse = ((t - start) / 0.45) if 0 <= t - start <= 0.45 else 0
            draw_cursor(image, cursor, pulse)
            previous_cursor = target if local > 0.98 else previous_cursor
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise SystemExit("ffmpeg failed")


def verify(ffmpeg: Path, output: Path) -> None:
    subprocess.run([str(ffmpeg), "-v", "error", "-i", str(output), "-f", "null", "-"], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the silent 15-second Etsy ACG demo video.")
    parser.add_argument("--ffmpeg", type=Path, required=True, help="Path to ffmpeg executable")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    render(args.ffmpeg, args.output)
    verify(args.ffmpeg, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
