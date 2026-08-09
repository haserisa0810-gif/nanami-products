from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC = Path("tmp/etsy-acg-current-main.jpg")
OUT = Path("output/etsy/acg-conversion")
OUT.mkdir(parents=True, exist_ok=True)

im = Image.new("RGB", (2000, 2000), "#07172f")
screen = Image.open(SRC).convert("RGB")
screen.thumbnail((1780, 1050), Image.Resampling.LANCZOS)

shadow = Image.new("RGBA", (screen.width + 80, screen.height + 80), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle(
    (30, 30, screen.width + 30, screen.height + 30), 24, fill=(0, 0, 0, 170)
)
shadow = shadow.filter(ImageFilter.GaussianBlur(22))
im.paste(shadow, ((2000-shadow.width)//2, 500), shadow)
im.paste(screen, ((2000-screen.width)//2, 520))

d = ImageDraw.Draw(im)
bold = lambda n: ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", n)
reg = lambda n: ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", n)
gold, ivory, lavender = "#D8AE5A", "#FFF9EB", "#C9B8FF"

def center(y, text, f, color):
    b = d.textbbox((0, 0), text, font=f)
    d.text(((2000-(b[2]-b[0]))/2, y), text, font=f, fill=color)

center(78, "PERSONALIZED ASTROCARTOGRAPHY MAP", bold(76), ivory)
center(182, "See where your planetary influences are strongest", reg(38), gold)
center(250, "Birth chart • Transits • Relocation & travel astrology", reg(32), ivory)
d.line((270, 330, 1730, 330), fill=gold, width=4)

d.rounded_rectangle((120, 1630, 1880, 1905), 46, fill="#081a37", outline=gold, width=4)
center(1675, "PREMIUM PERSONAL BUNDLE", bold(48), gold)
items = [
    (430, "AI-READY", "READING + CONSULTATION"),
    (1000, "INTERACTIVE", "PERSONAL ACG MAP"),
    (1570, "430-PAGE", "1-YEAR PLANNER"),
]
for x, top, bottom in items:
    d.ellipse((x-12, 1760, x+12, 1784), fill=lavender)
    b = d.textbbox((0, 0), top, font=bold(31))
    d.text((x-(b[2]-b[0])/2, 1800), top, font=bold(31), fill=ivory)
    b = d.textbbox((0, 0), bottom, font=reg(25))
    d.text((x-(b[2]-b[0])/2, 1842), bottom, font=reg(25), fill=lavender)

im.save(OUT / "01-personalized-acg-premium-bundle.jpg", quality=95)
