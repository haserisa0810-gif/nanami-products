from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path("tmp/etsy-acg-neko-video")
OUTPUT = Path("output/video/etsy-acg/neko-chart-companion-demo-15s.mp4")
ENGLISH_SOURCES = Path("output/video/etsy-acg/source-en")
FFMPEG = Path(r"C:\tmp\youtube-video-deps\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")

W, H = 720, 1280
FPS = 30
DURATION = 15
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")

SCENES = [
    (ROOT / "01-reading.png", "A COMPLETE PERSONAL READING", "Reading mode", 0.0, 5.0),
    (ROOT / "02-consultation.png", "KEEP ASKING QUESTIONS", "Consultation mode", 5.0, 10.0),
    (ROOT / "03-saving-raw.png", "SAVE IT FOR LATER", "1-Year Planner  •  ZIP  •  Saved URL", 10.0, 15.0),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def centered(draw: ImageDraw.ImageDraw, y: int, text: str,
             fnt: ImageFont.FreeTypeFont, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=fnt, fill=fill)


def english_source(image: Image.Image, filename: str) -> Image.Image:
    """Remove locale-switch and Japanese sample metadata from sales captures."""
    image = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    paper, ink, gold = (255, 251, 243, 255), (68, 56, 44, 255), (173, 119, 54, 255)
    if filename == "01-reading.png":
        draw.rectangle((28, 0, W - 28, 106), fill=paper)
        draw.text((56, 24), "Chief Editor Neko · Yokohama, Japan", font=font(21, True), fill=ink)
        draw.text((56, 62), "Fixed fictional sample · English interface", font=font(18), fill=gold)
    elif filename == "02-consultation.png":
        draw.rounded_rectangle((28, 38, W - 28, 430), radius=26, fill=paper)
        draw.text((56, 70), "AI-READABLE ASTROLOGY DATA", font=font(18, True), fill=gold)
        draw.rounded_rectangle((550, 60, 664, 100), radius=18, fill=(173, 119, 54, 255))
        draw.text((607, 80), "ENGLISH", font=font(15, True), fill="#FFFFFF", anchor="mm")
        draw.text((56, 146), "Chief Editor Neko's", font=font(39), fill=ink)
        draw.text((56, 198), "sample astrology data", font=font(39), fill=ink)
        draw.text((56, 286), "February 22, 2022 · 10:22 PM", font=font(19), fill=ink)
        draw.text((56, 328), "Yokohama, Japan · Fictional sample", font=font(19), fill=ink)
        draw.text((56, 380), "Read-only permanent demo", font=font(18), fill=gold)
    return image.convert("RGB")


def scene_frame(source: Image.Image, headline: str, subtitle: str,
                local_progress: float, global_time: float) -> Image.Image:
    # A very subtle push-in keeps the screen recording lively without making
    # the UI hard to read.
    scale = 1.0 + 0.018 * local_progress
    enlarged = source.resize((round(W * scale), round(H * scale)), Image.Resampling.LANCZOS)
    left = (enlarged.width - W) // 2
    top = round((enlarged.height - H) * (0.25 + 0.45 * local_progress))
    frame = enlarged.crop((left, top, left + W, top + H)).convert("RGBA")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay, "RGBA")
    od.rounded_rectangle((24, 24, W - 24, 196), radius=28,
                         fill=(5, 17, 39, 235), outline=(205, 164, 80, 220), width=3)
    centered(od, 63, headline, font(38, True), "#FFF8E8")
    centered(od, 128, subtitle, font(27), "#D8B363")

    # Small progress indicator makes the three-part structure obvious.
    for idx in range(3):
        x1 = 236 + idx * 88
        active = int(global_time // 5) == idx
        od.rounded_rectangle((x1, 174, x1 + 64, 181), radius=4,
                             fill=(216, 179, 99, 255) if active else (255, 248, 232, 90))

    # Fade at each scene boundary.
    edge = min(local_progress / 0.12, (1.0 - local_progress) / 0.12, 1.0)
    composed = Image.alpha_composite(frame, overlay).convert("RGB")
    if edge < 1:
        composed = ImageEnhance.Brightness(composed).enhance(max(0.08, edge))
    return composed


def main() -> None:
    sources = [english_source(Image.open(path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS), path.name)
               for path, *_ in SCENES]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ENGLISH_SOURCES.mkdir(parents=True, exist_ok=True)
    for source, (path, *_rest) in zip(sources, SCENES):
        source.save(ENGLISH_SOURCES / path.name, optimize=True)

    command = [
        str(FFMPEG), "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUTPUT),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(FPS * DURATION):
        now = frame_index / FPS
        scene_index = min(int(now // 5), 2)
        _, headline, subtitle, start, end = SCENES[scene_index]
        local = (now - start) / (end - start)
        frame = scene_frame(sources[scene_index], headline, subtitle, local, now)
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed")

    subprocess.run([
        str(FFMPEG), "-v", "error", "-i", str(OUTPUT), "-f", "null", "-"
    ], check=True)
    print(OUTPUT.resolve())


if __name__ == "__main__":
    main()
