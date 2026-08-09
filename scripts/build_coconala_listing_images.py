from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1200
HEIGHT = 1320
OUTPUT_DIR = Path("output/coconala/listing-images")

BG = "#F7F3EA"
INK = "#173C35"
MUTED = "#526B65"
GREEN = "#2F6657"
PALE = "#E4EEE8"
GOLD = "#B68B45"
WHITE = "#FFFFFF"
LINE = "#CBD9D2"

FONT_REGULAR = Path(r"C:\Windows\Fonts\YuGothM.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\YuGothB.ttc")


def font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size)


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


def down_arrow(draw, x, y1, y2):
    draw.line((x, y1, x, y2), fill=GOLD, width=8)
    draw.polygon([(x, y2), (x - 15, y2 - 22), (x + 15, y2 - 22)], fill=GOLD)


def icon_person(draw, cx, cy):
    draw.ellipse((cx - 16, cy - 38, cx + 16, cy - 6), fill=GREEN)
    draw.rounded_rectangle((cx - 29, cy + 3, cx + 29, cy + 45), radius=16, fill=GREEN)


def icon_document(draw, cx, cy):
    draw.rounded_rectangle((cx - 31, cy - 42, cx + 31, cy + 45), radius=7, fill=GREEN)
    draw.polygon([(cx + 5, cy - 42), (cx + 31, cy - 16), (cx + 5, cy - 16)], fill=PALE)
    for offset in (0, 18, 36):
        draw.line((cx - 17, cy - 5 + offset, cx + 17, cy - 5 + offset), fill=WHITE, width=5)


def icon_chat(draw, cx, cy):
    draw.rounded_rectangle((cx - 42, cy - 34, cx + 42, cy + 30), radius=18, fill=GREEN)
    draw.polygon([(cx - 20, cy + 25), (cx - 34, cy + 48), (cx + 1, cy + 28)], fill=GREEN)
    for x in (-19, 0, 19):
        draw.ellipse((cx + x - 5, cy - 6, cx + x + 5, cy + 4), fill=WHITE)


def draw_flow(draw):
    y_positions = [(750, 875), (915, 1040), (1080, 1205)]
    cards = [
        ("1", "ユーザー名と出生情報を入力", icon_person),
        ("2", "専用データを自動生成", icon_document),
        ("3", "お好みのAIへ貼り付け", icon_chat),
    ]
    for index, ((top, bottom), (number, label, icon)) in enumerate(zip(y_positions, cards)):
        rounded(draw, (100, top, 1100, bottom), 24, WHITE, LINE, 3)
        rounded(draw, (126, top + 31, 190, top + 95), 32, GOLD)
        center_text(draw, (126, top + 31, 190, top + 95), number, font(30, True), WHITE)
        icon(draw, 263, top + 64)
        draw.text((345, top + 37), label, font=font(39, True), fill=INK)
        if index < 2:
            down_arrow(draw, 600, bottom + 8, bottom + 35)
    center_text(draw, (120, 1230, 1080, 1288), "購入後すぐに、ご自身で利用を開始できます", font(30, True), GREEN)


def build(filename, eyebrow, title_lines, badge, features):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, WIDTH, 24), fill=GOLD)
    draw.text((70, 62), "NANAMI ASTRO", font=font(25, True), fill=GREEN)

    rounded(draw, (760, 52, 1130, 118), 33, PALE)
    center_text(draw, (760, 52, 1130, 118), "購入後すぐ自動生成", font(27, True), GREEN)

    draw.text((70, 158), eyebrow, font=font(31, True), fill=GOLD)
    title_y = 218
    for line in title_lines:
        draw.text((66, title_y), line, font=font(70, True), fill=INK)
        title_y += 92

    rounded(draw, (70, 432, 1130, 690), 28, PALE)
    rounded(draw, (100, 464, 420, 550), 20, GREEN)
    center_text(draw, (100, 464, 420, 550), badge, font(34, True), WHITE)

    feature_x = 122
    for index, feature in enumerate(features):
        x = feature_x + index * 345
        draw.ellipse((x, 607, x + 22, 629), fill=GOLD)
        draw.text((x + 36, 592), feature, font=font(28, True), fill=INK)

    draw_flow(draw)
    draw.text((70, 1290), "計算済みデータ + AI鑑定用プロンプト", font=font(19), fill=MUTED)
    draw.text((1010, 1290), "[ココナラ版]", font=font(19, True), fill=MUTED)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / filename
    image.save(output, "PNG", optimize=True)
    print(output.resolve())


def main():
    build(
        "nanami_shichu_coconala_listing.png",
        "AIと相談しやすい、計算済みデータ",
        ["四柱推命データ", "AI鑑定セット"],
        "四柱推命",
        ["命式・十神", "大運・年運", "空亡・神殺"],
    )
    build(
        "nanami_western_full_coconala_listing.png",
        "AIが出生図を理解した状態で相談できる",
        ["西洋占星術 FULL", "AI鑑定データ"],
        "FULL版",
        ["小惑星付き", "アスペクト", "トランジット31日"],
    )


if __name__ == "__main__":
    main()
