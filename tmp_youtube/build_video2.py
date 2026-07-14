# -*- coding: utf-8 -*-
"""AI占い for AI — 15s vertical (1080x1920) promo.

Fully drawn 2D characters (PIL) with real lip-sync: mouth aperture is driven
by the RMS envelope of each voice clip. 4 scenes:
  S1 鑑定モード (Mio reads her fortune)
  S2 相談モード (Mio asks about her crush)
  S3 Luna (AI fortune-teller) answers
  S4 Mio resolves + end card
"""
from pathlib import Path
import math, wave, subprocess, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
W, H, FPS, DUR = 1080, 1920, 30, 15.0
SS = 2                      # supersampling factor
SW, SH = W * SS, H * SS
NF = int(DUR * FPS)
FFMPEG = Path(r"C:\tmp\youtube-video-deps\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")

# (start, voice file stem, speaker, text)
LINES = [
    (0.40, "voice_mio_0",  "mio",  "鑑定モード、私の恋愛傾向まで分かるんだ。"),
    (3.55, "voice_mio_1",  "mio",  "ルナ、片思いの彼に、どうアプローチすればいい？"),
    (7.00, "voice_luna_0", "luna", "まず短い会話を増やして。彼の好きな話題から、自然に誘ってみて。"),
    (12.15, "voice_mio_2", "mio",  "わかった。今日、話しかけてみる！"),
]
SCENE_CUTS = [3.30, 6.90, 12.00]   # S1|S2|S3|S4 boundaries
XFADE = 0.14

MIO_HAIR   = (178, 138, 224)
MIO_HAIR_D = (150, 108, 200)
MIO_SKIN   = (255, 227, 208)
MIO_TOP    = (255, 246, 234)
LUNA_HAIR   = (72, 84, 168)
LUNA_HAIR_L = (108, 150, 214)
LUNA_SKIN   = (250, 232, 224)
LUNA_ROBE   = (40, 44, 96)

def font(size, bold=True):
    name = "YuGothB.ttc" if bold else "YuGothM.ttc"
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / name), int(size))

# ---------------------------------------------------------------- audio env
def voice_env(stem):
    """Per-video-frame mouth aperture (0..1) for a voice clip."""
    with wave.open(str(ROOT / f"{stem}.wav"), "rb") as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    n = int(math.ceil(len(a) / sr * FPS))
    env = np.zeros(n)
    half = int(sr / FPS * 0.8)
    for i in range(n):
        c = int(i / FPS * sr)
        win = a[max(0, c - half):c + half]
        env[i] = math.sqrt(float(np.mean(win * win))) if len(win) else 0.0
    env = np.clip((env - 0.015) * 10.5, 0, 1)
    out = np.zeros(n)
    prev = 0.0
    for i in range(n):                       # fast attack, soft decay
        prev = max(env[i], prev * 0.68)
        out[i] = prev
    return out, len(a) / sr

ENVS = {stem: voice_env(stem) for _, stem, _, _ in LINES}

def active_line(t):
    for start, stem, who, text in LINES:
        env, dur = ENVS[stem]
        if start <= t < start + dur:
            i = min(len(env) - 1, int((t - start) * FPS))
            return who, text, float(env[i]), (t - start) / dur
    return None, None, 0.0, 0.0

# ------------------------------------------------------------- draw helpers
def vgrad(w, h, top, bottom):
    r = np.linspace(0, 1, h)[:, None]
    arr = np.zeros((h, w, 3), np.uint8)
    for i in range(3):
        arr[:, :, i] = (top[i] * (1 - r) + bottom[i] * r).astype(np.uint8)
    return Image.fromarray(arr, "RGB")

def star4(d, x, y, r, fill):
    d.polygon([(x, y - r), (x + r * .28, y - r * .28), (x + r, y),
               (x + r * .28, y + r * .28), (x, y + r),
               (x - r * .28, y + r * .28), (x - r, y),
               (x - r * .28, y - r * .28)], fill=fill)

def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for c in text:
        if d.textbbox((0, 0), cur + c, font=f)[2] > maxw and cur:
            lines.append(cur); cur = c
        else:
            cur += c
    if cur:
        lines.append(cur)
    return lines

def draw_mouth(d, cx, cy, m, u, happy=False):
    if m < 0.07:
        if happy:
            d.arc((cx - 24 * u, cy - 16 * u, cx + 24 * u, cy + 12 * u), 20, 160,
                  fill=(168, 78, 92), width=max(2, int(4 * u)))
        else:
            d.line((cx - 14 * u, cy + 2 * u, cx + 14 * u, cy), fill=(168, 78, 92),
                   width=max(2, int(3.4 * u)))
    else:
        mw = (16 + 34 * m) * u
        mh = (6 + 40 * m) * u
        d.ellipse((cx - mw / 2, cy - mh * .35, cx + mw / 2, cy + mh * .65), fill=(112, 42, 58))
        if m > 0.32:
            tw = mw * .62
            d.ellipse((cx - tw / 2, cy + mh * .16, cx + tw / 2, cy + mh * .64),
                      fill=(226, 122, 132))

def draw_eye(d, cx, cy, u, iris, blink, look=0.0):
    if blink:
        d.line((cx - 15 * u, cy + 2 * u, cx + 15 * u, cy + 2 * u), fill=(90, 60, 70),
               width=max(2, int(4 * u)))
        return
    d.ellipse((cx - 15 * u, cy - 19 * u, cx + 15 * u, cy + 19 * u), fill="white",
              outline=(90, 60, 70), width=max(1, int(2 * u)))
    ix = cx + look * 6 * u
    d.ellipse((ix - 9.5 * u, cy - 12 * u, ix + 9.5 * u, cy + 14 * u), fill=iris)
    d.ellipse((ix - 5 * u, cy - 3 * u, ix + 5 * u, cy + 9 * u),
              fill=tuple(min(255, c + 55) for c in iris))
    d.ellipse((ix - 6.5 * u, cy - 10 * u, ix + 1 * u, cy - 2 * u), fill="white")
    d.line((cx - 17 * u, cy - 19 * u, cx + 17 * u, cy - 19 * u), fill=(70, 45, 60),
           width=max(2, int(4.6 * u)))

# ------------------------------------------------------------- characters
def make_mio(u, mouth, blink, t, happy=False, look=0.0):
    """Bust of Mio on a transparent canvas. u = px per unit. Head r=100u."""
    cw, ch = int(620 * u), int(660 * u)
    im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    hx, hy = cw / 2, 230 * u
    # back hair
    d.ellipse((hx - 150 * u, hy - 140 * u, hx + 150 * u, hy + 190 * u), fill=MIO_HAIR_D)
    # side locks
    for sx in (-1, 1):
        d.rounded_rectangle((hx + sx * 148 * u - 34 * u, hy - 40 * u,
                             hx + sx * 148 * u + 34 * u, hy + 250 * u), 30 * u, fill=MIO_HAIR_D)
    # neck & body
    d.rectangle((hx - 26 * u, hy + 70 * u, hx + 26 * u, hy + 160 * u), fill=MIO_SKIN)
    d.rounded_rectangle((hx - 185 * u, hy + 140 * u, hx + 185 * u, hy + 430 * u),
                        70 * u, fill=MIO_TOP, outline=(226, 205, 226), width=max(1, int(3 * u)))
    d.arc((hx - 40 * u, hy + 128 * u, hx + 40 * u, hy + 190 * u), 0, 180,
          fill=(226, 205, 226), width=max(2, int(4 * u)))
    # head
    d.ellipse((hx - 100 * u, hy - 108 * u, hx + 100 * u, hy + 108 * u), fill=MIO_SKIN)
    # ears
    for sx in (-1, 1):
        d.ellipse((hx + sx * 100 * u - 14 * u, hy - 12 * u, hx + sx * 100 * u + 14 * u,
                   hy + 26 * u), fill=MIO_SKIN)
    # bangs: hair dome + scallop carve
    d.chord((hx - 106 * u, hy - 122 * u, hx + 106 * u, hy + 60 * u), 180, 360, fill=MIO_HAIR)
    for i, bx in enumerate((-66, -22, 22, 66)):
        r = (30 if i in (1, 2) else 24) * u
        d.ellipse((hx + bx * u - r, hy - 34 * u - r * .2, hx + bx * u + r,
                   hy - 34 * u + r * 1.8), fill=MIO_SKIN)
    d.chord((hx - 106 * u, hy - 122 * u, hx + 106 * u, hy - 10 * u), 180, 360, fill=MIO_HAIR)
    # hairpin stars
    star4(d, hx - 78 * u, hy - 66 * u, 15 * u, (255, 214, 110))
    star4(d, hx - 56 * u, hy - 84 * u, 9 * u, (255, 230, 160))
    # face
    for sx in (-1, 1):
        d.ellipse((hx + sx * 60 * u - 20 * u, hy + 30 * u - 10 * u,
                   hx + sx * 60 * u + 20 * u, hy + 30 * u + 10 * u), fill=(252, 148, 158, 150))
    for sx in (-1, 1):
        ex = hx + sx * 44 * u
        d.arc((ex - 18 * u, hy - 52 * u, ex + 18 * u, hy - 30 * u), 200, 340,
              fill=(140, 96, 150), width=max(2, int(4 * u)))
        draw_eye(d, ex, hy - 6 * u, u, (196, 128, 60), blink, look)
    d.line((hx - 3 * u, hy + 26 * u, hx + 2 * u, hy + 30 * u), fill=(214, 160, 150),
           width=max(1, int(2.4 * u)))
    draw_mouth(d, hx, hy + 58 * u, mouth, u, happy)
    return im, (hx, hy)

def make_luna(u, mouth, blink, t):
    """Bust of Luna, the AI fortune-teller."""
    cw, ch = int(700 * u), int(760 * u)
    im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    hx, hy = cw / 2, 250 * u
    # halo glow
    glow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((hx - 200 * u, hy - 200 * u, hx + 200 * u, hy + 200 * u),
               fill=(140, 190, 255, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(28 * u))
    im = Image.alpha_composite(im, glow)
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse((hx - 150 * u, hy - 150 * u, hx + 150 * u, hy + 150 * u),
              outline=(190, 220, 255, 170), width=max(2, int(4 * u)))
    # flowing hair (back)
    d.polygon([(hx - 130 * u, hy - 90 * u), (hx + 130 * u, hy - 90 * u),
               (hx + 205 * u + 12 * u * math.sin(t * 1.7), hy + 420 * u),
               (hx - 205 * u - 12 * u * math.sin(t * 1.7 + 1), hy + 420 * u)],
              fill=LUNA_HAIR)
    d.ellipse((hx - 138 * u, hy - 138 * u, hx + 138 * u, hy + 110 * u), fill=LUNA_HAIR)
    for k, sx in enumerate((-150, -90, 95, 150)):
        px = hx + sx * u + 9 * u * math.sin(t * 1.9 + k)
        d.polygon([(px - 22 * u, hy + 40 * u), (px + 22 * u, hy + 40 * u),
                   (px + 6 * u, hy + (400 + 18 * math.sin(t * 1.5 + k)) * u),
                   (px - 14 * u, hy + 380 * u)], fill=LUNA_HAIR_L)
    # body robe
    d.rectangle((hx - 24 * u, hy + 74 * u, hx + 24 * u, hy + 150 * u), fill=LUNA_SKIN)
    d.polygon([(hx - 120 * u, hy + 140 * u), (hx + 120 * u, hy + 140 * u),
               (hx + 210 * u, hy + 500 * u), (hx - 210 * u, hy + 500 * u)], fill=LUNA_ROBE)
    d.polygon([(hx - 34 * u, hy + 140 * u), (hx + 34 * u, hy + 140 * u),
               (hx, hy + 230 * u)], fill=(226, 234, 255))
    rng = random.Random(7)
    for _ in range(14):
        sx_, sy_ = rng.uniform(-190, 190), rng.uniform(170, 470)
        if abs(sx_) > 40 or sy_ > 250:
            star4(d, hx + sx_ * u, hy + sy_ * u, rng.uniform(4, 9) * u, (168, 196, 255))
    # head
    d.ellipse((hx - 96 * u, hy - 104 * u, hx + 96 * u, hy + 104 * u), fill=LUNA_SKIN)
    # bangs (center-parted)
    d.chord((hx - 102 * u, hy - 120 * u, hx + 102 * u, hy + 44 * u), 180, 360, fill=LUNA_HAIR)
    d.polygon([(hx - 2 * u, hy - 92 * u), (hx - 78 * u, hy - 4 * u), (hx - 100 * u, hy - 60 * u)],
              fill=LUNA_HAIR)
    d.polygon([(hx + 2 * u, hy - 92 * u), (hx + 78 * u, hy - 4 * u), (hx + 100 * u, hy - 60 * u)],
              fill=LUNA_HAIR)
    d.ellipse((hx - 60 * u, hy - 60 * u, hx + 60 * u, hy - 20 * u), fill=LUNA_SKIN)  # forehead
    d.chord((hx - 102 * u, hy - 124 * u, hx + 102 * u, hy - 30 * u), 180, 360, fill=LUNA_HAIR)
    # crescent ornament
    d.ellipse((hx + 52 * u, hy - 112 * u, hx + 110 * u, hy - 54 * u), fill=(255, 222, 120))
    d.ellipse((hx + 44 * u, hy - 116 * u, hx + 98 * u, hy - 62 * u), fill=LUNA_HAIR)
    star4(d, hx - 74 * u, hy - 82 * u, 11 * u, (210, 230, 255))
    # face
    for sx in (-1, 1):
        ex = hx + sx * 42 * u
        d.arc((ex - 18 * u, hy - 50 * u, ex + 18 * u, hy - 30 * u), 200, 340,
              fill=(70, 84, 150), width=max(2, int(4 * u)))
        draw_eye(d, ex, hy - 4 * u, u, (52, 150, 168), blink)
    draw_mouth(d, hx, hy + 56 * u, mouth, u, happy=True)
    return im, (hx, hy)

def paste_char(canvas, char_im, anchor, dst, angle):
    rot = char_im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True,
                         center=anchor)
    dx = (rot.width - char_im.width) / 2
    dy = (rot.height - char_im.height) / 2
    x = int(dst[0] - anchor[0] - dx)
    y = int(dst[1] - anchor[1] - dy)
    canvas.alpha_composite(rot, (max(-rot.width, x), max(-rot.height, y)))

def blinking(t, phase, period=3.2):
    return ((t + phase) % period) < 0.13

# ---------------------------------------------------------------- UI chrome
F_TITLE = font(62 * SS)
F_CHIP  = font(34 * SS)
F_CARD  = font(44 * SS)
F_CARD_S = font(36 * SS)
F_SUB   = font(46 * SS)
F_TAG   = font(31 * SS)
F_END   = font(58 * SS)

def chip(d, x, y, text, fill, f=None):
    f = f or F_CHIP
    tw = d.textbbox((0, 0), text, font=f)[2]
    d.rounded_rectangle((x, y, x + tw + 52 * SS, y + 64 * SS), 24 * SS, fill=fill)
    d.text((x + 26 * SS, y + 8 * SS), text, font=f, fill="white")
    return x + tw + 52 * SS

def header(im, t, mode, mode_color):
    d = ImageDraw.Draw(im, "RGBA")
    d.text((54 * SS, 46 * SS), "AI占い for AI", font=F_TITLE, fill="white",
           stroke_width=3 * SS, stroke_fill=(40, 18, 80, 190))
    chip(d, 56 * SS, 136 * SS, mode, mode_color)

def subtitle(im, who, text):
    d = ImageDraw.Draw(im, "RGBA")
    name = "ミオ" if who == "mio" else "AI占い師 ルナ"
    color = (176, 104, 226, 245) if who == "mio" else (24, 158, 186, 245)
    chip(d, 58 * SS, 1462 * SS, name, color, F_TAG)
    lines = wrap(d, text, F_SUB, 930 * SS)
    top = 1545 * SS
    d.rounded_rectangle((40 * SS, top - 20 * SS, 1040 * SS,
                         top + len(lines) * 68 * SS + 20 * SS), 30 * SS,
                        fill=(12, 8, 32, 215), outline=(255, 255, 255, 60), width=2 * SS)
    for i, s in enumerate(lines):
        bb = d.textbbox((0, 0), s, font=F_SUB)
        d.text(((SW - bb[2]) / 2, top + i * 68 * SS), s, font=F_SUB, fill="white",
               stroke_width=3 * SS, stroke_fill=(20, 8, 35, 230))

# ------------------------------------------------------------- backgrounds
def starfield(base, n, seed, bright=200):
    d = ImageDraw.Draw(base, "RGBA")
    rng = random.Random(seed)
    for _ in range(n):
        x, y = rng.uniform(0, SW), rng.uniform(0, SH)
        r = rng.uniform(1.2, 4.2) * SS
        a = rng.randint(60, bright)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
    return base

BG1 = starfield(vgrad(SW, SH, (46, 26, 92), (110, 60, 160)).convert("RGBA"), 90, 3)
BG2 = starfield(vgrad(SW, SH, (22, 30, 74), (52, 96, 150)).convert("RGBA"), 70, 5)
BG3 = starfield(vgrad(SW, SH, (10, 14, 44), (36, 44, 110)).convert("RGBA"), 170, 9, 235)
BG4 = starfield(vgrad(SW, SH, (66, 34, 118), (168, 96, 170)).convert("RGBA"), 110, 11)

def twinkle(im, t, seed, n=8):
    d = ImageDraw.Draw(im, "RGBA")
    rng = random.Random(seed)
    for k in range(n):
        x, y = rng.uniform(60, SW - 60), rng.uniform(120 * SS, 1300 * SS)
        a = int(120 + 110 * math.sin(t * 2.4 + k * 1.7))
        if a > 90:
            star4(d, x, y, (7 + 4 * math.sin(t * 3 + k)) * SS, (255, 255, 255, a))

def typing(text, prog, lead=0.06, tail=0.72):
    p = min(1.0, max(0.0, (prog - lead) / (tail - lead)))
    return text[:max(0, int(len(text) * p + 0.999))]

# ------------------------------------------------------------------ scenes
def scene1(t):
    im = BG1.copy()
    twinkle(im, t, 21)
    d = ImageDraw.Draw(im, "RGBA")
    # fortune card
    cx0, cy0, cx1 = 90 * SS, 300 * SS, 990 * SS
    d.rounded_rectangle((cx0, cy0, cx1, cy0 + 560 * SS), 42 * SS,
                        fill=(255, 252, 248, 242), outline=(255, 214, 120), width=4 * SS)
    d.rounded_rectangle((cx0, cy0, cx1, cy0 + 108 * SS), 42 * SS, fill=(116, 70, 210, 255))
    d.rectangle((cx0, cy0 + 60 * SS, cx1, cy0 + 108 * SS), fill=(116, 70, 210, 255))
    d.text((cx0 + 44 * SS, cy0 + 22 * SS), "今日の鑑定結果", font=F_CARD, fill="white")
    star4(d, cx1 - 80 * SS, cy0 + 54 * SS, 22 * SS, (255, 224, 130))
    d.text((cx0 + 44 * SS, cy0 + 150 * SS), "恋愛運", font=F_CARD, fill=(80, 48, 120))
    stars = "★★★★" + ("☆" if t < 1.2 else "★")
    d.text((cx0 + 250 * SS, cy0 + 150 * SS), stars, font=F_CARD, fill=(255, 168, 40))
    reveal = [("片思いは、進展の兆しあり。", 0.7), ("鍵は「自分から話しかける勇気」。", 1.6)]
    yy = cy0 + 270 * SS
    for txt, at in reveal:
        if t > at:
            a = min(1.0, (t - at) / 0.4)
            shown = txt[:int(len(txt) * min(1.0, (t - at) / 0.9) + 0.999)]
            d.text((cx0 + 44 * SS, yy), shown, font=F_CARD_S,
                   fill=(60, 44, 90, int(255 * a)))
        yy += 90 * SS
    d.rounded_rectangle((cx0 + 44 * SS, cy0 + 452 * SS, cx1 - 44 * SS, cy0 + 520 * SS),
                        26 * SS, fill=(244, 236, 255))
    d.text((cx0 + 70 * SS, cy0 + 462 * SS), "▶ 相談モードで深掘りする", font=F_CARD_S,
           fill=(116, 70, 210))
    # Mio reading (mouth synced)
    who, _, level, _ = active_line(t)
    m = level if who == "mio" else 0.0
    char, anchor = make_mio(1.55 * SS, m, blinking(t, 0.4), t, look=-0.3)
    bob = 6 * SS * math.sin(t * 2.1)
    paste_char(im, char, anchor, (540 * SS, 1190 * SS + bob), 1.8 * math.sin(t * 1.2))
    header(im, t, "占い鑑定モード", (116, 70, 210, 230))
    return im

def scene2(t):
    im = BG2.copy()
    twinkle(im, t, 33)
    d = ImageDraw.Draw(im, "RGBA")
    # chat panel
    d.rounded_rectangle((60 * SS, 300 * SS, 1020 * SS, 1020 * SS), 44 * SS,
                        fill=(16, 22, 52, 200), outline=(120, 160, 230, 120), width=3 * SS)
    # Luna mini avatar + name
    ax, ay = 150 * SS, 396 * SS
    d.ellipse((ax - 52 * SS, ay - 52 * SS, ax + 52 * SS, ay + 52 * SS), fill=LUNA_HAIR)
    d.ellipse((ax - 34 * SS, ay - 30 * SS, ax + 34 * SS, ay + 44 * SS), fill=LUNA_SKIN)
    d.chord((ax - 38 * SS, ay - 40 * SS, ax + 38 * SS, ay + 14 * SS), 180, 360, fill=LUNA_HAIR)
    d.ellipse((ax + 18 * SS, ay - 44 * SS, ax + 42 * SS, ay - 20 * SS), fill=(255, 222, 120))
    d.ellipse((ax + 13 * SS, ay - 46 * SS, ax + 37 * SS, ay - 22 * SS), fill=LUNA_HAIR)
    d.text((ax + 76 * SS, ay - 42 * SS), "AI占い師 ルナ", font=F_CARD_S, fill="white")
    d.text((ax + 76 * SS, ay + 6 * SS), "オンライン", font=F_TAG, fill=(120, 230, 190))
    # Mio's message bubble (typed)
    _, _, _, prog = active_line(t)
    who = active_line(t)[0]
    text = LINES[1][3]
    shown = typing(text, prog if who == "mio" else (1.0 if t > 6.6 else 0.0))
    if t > 3.7 and shown:
        lines = wrap(d, shown, F_CARD_S, 560 * SS)
        bw = max(d.textbbox((0, 0), s, font=F_CARD_S)[2] for s in lines) + 76 * SS
        bh = len(lines) * 62 * SS + 48 * SS
        bx1, by0 = 950 * SS, 520 * SS
        d.rounded_rectangle((bx1 - bw, by0, bx1, by0 + bh), 34 * SS, fill=(176, 104, 226, 250))
        for i, s in enumerate(lines):
            d.text((bx1 - bw + 38 * SS, by0 + 24 * SS + i * 62 * SS), s,
                   font=F_CARD_S, fill="white")
    # typing dots from Luna
    if t > 5.9:
        dy0 = 860 * SS
        d.rounded_rectangle((130 * SS, dy0, 330 * SS, dy0 + 92 * SS), 34 * SS,
                            fill=(236, 242, 255, 240))
        for k in range(3):
            a = 0.4 + 0.6 * max(0, math.sin(t * 5 - k * 0.9))
            r = 11 * SS
            d.ellipse((170 * SS + k * 60 * SS - r, dy0 + 46 * SS - r,
                       170 * SS + k * 60 * SS + r, dy0 + 46 * SS + r),
                      fill=(90, 110, 180, int(255 * a)))
    # Mio speaking
    who, _, level, _ = active_line(t)
    m = level if who == "mio" else 0.0
    char, anchor = make_mio(1.5 * SS, m, blinking(t, 1.1), t, look=0.35)
    bob = 6 * SS * math.sin(t * 2.3)
    paste_char(im, char, anchor, (760 * SS, 1230 * SS + bob), -2.0 + 1.6 * math.sin(t * 1.4))
    header(im, t, "相談モード", (24, 158, 186, 235))
    return im

def scene3(t):
    im = BG3.copy()
    twinkle(im, t, 55, n=12)
    d = ImageDraw.Draw(im, "RGBA")
    who, _, level, prog = active_line(t)
    m = level if who == "luna" else 0.0
    char, anchor = make_luna(2.05 * SS, m, blinking(t, 2.0), t)
    bob = 7 * SS * math.sin(t * 1.6)
    paste_char(im, char, anchor, (540 * SS, 560 * SS + bob), 1.4 * math.sin(t * 0.9))
    # advice bubble
    text = LINES[2][3]
    shown = typing(text, prog if who == "luna" else (1.0 if t > 11.5 else 0.0), tail=0.8)
    if shown:
        d = ImageDraw.Draw(im, "RGBA")
        lines = wrap(d, shown, F_CARD_S, 780 * SS)
        bh = len(lines) * 62 * SS + 52 * SS
        by0 = 1080 * SS
        d.rounded_rectangle((90 * SS, by0, 990 * SS, by0 + bh), 36 * SS,
                            fill=(240, 248, 255, 246), outline=(120, 200, 220), width=3 * SS)
        d.polygon([(500 * SS, by0 + 2 * SS), (560 * SS, by0 + 2 * SS),
                   (530 * SS, by0 - 30 * SS)], fill=(240, 248, 255, 246))
        for i, s in enumerate(lines):
            d.text((132 * SS, by0 + 26 * SS + i * 62 * SS), s, font=F_CARD_S,
                   fill=(36, 60, 96))
    header(im, t, "相談モード", (24, 158, 186, 235))
    return im

def scene4(t):
    im = BG4.copy()
    twinkle(im, t, 77, n=14)
    who, _, level, _ = active_line(t)
    m = level if who == "mio" else 0.0
    char, anchor = make_mio(2.0 * SS, m, blinking(t, 0.2), t, happy=True)
    bob = 7 * SS * math.sin(t * 2.5)
    paste_char(im, char, anchor, (540 * SS, 700 * SS + bob), 2.0 * math.sin(t * 1.8))
    d = ImageDraw.Draw(im, "RGBA")
    rng = random.Random(int(t * 6))
    for _ in range(6):
        star4(d, rng.uniform(100, SW - 100), rng.uniform(200 * SS, 1200 * SS),
              rng.uniform(6, 16) * SS, (255, 240, 170, 200))
    if t > 13.9:
        a = min(1.0, (t - 13.9) / 0.5)
        d.rounded_rectangle((120 * SS, 1160 * SS, 960 * SS, 1382 * SS), 44 * SS,
                            fill=(70, 34, 140, int(240 * a)),
                            outline=(255, 255, 255, int(160 * a)), width=3 * SS)
        msg = "占いを、次の一歩に。"
        bb = d.textbbox((0, 0), msg, font=F_END)
        d.text(((SW - bb[2]) / 2, 1192 * SS), msg, font=F_END,
               fill=(255, 255, 255, int(255 * a)))
        sub = "AI占い for AI"
        bb2 = d.textbbox((0, 0), sub, font=F_CARD_S)
        d.text(((SW - bb2[2]) / 2, 1300 * SS), sub, font=F_CARD_S,
               fill=(214, 196, 255, int(255 * a)))
    header(im, t, "相談モード", (24, 158, 186, 235))
    return im

SCENES = [scene1, scene2, scene3, scene4]

def scene_index(t):
    for i, b in enumerate(SCENE_CUTS):
        if t < b:
            return i
    return 3

def render_frame(t):
    si = scene_index(t)
    im = SCENES[si](t)
    for b in SCENE_CUTS:            # crossfade
        if 0 < b - t <= XFADE:
            nxt = SCENES[scene_index(b + 0.01)](t)
            im = Image.blend(im, nxt, 1 - (b - t) / XFADE)
        elif 0 <= t - b < XFADE:
            prv = SCENES[scene_index(b - 0.01)](t)
            im = Image.blend(prv, im, 0.5 + 0.5 * (t - b) / XFADE)
    who, text, _, _ = active_line(t)
    if who:
        subtitle(im, who, text)
    return im.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)

def make_frames(only=None):
    out = ROOT / "frames2"
    out.mkdir(exist_ok=True)
    frames = only if only is not None else range(NF)
    for fi in frames:
        render_frame(fi / FPS).save(out / f"f{fi:04d}.jpg", quality=91, subsampling=0)
        if fi % 60 == 0:
            print("frame", fi, flush=True)

def mux():
    inputs = ["-framerate", str(FPS), "-i", str(ROOT / "frames2/f%04d.jpg"),
              "-i", str(ROOT / "music.wav")]
    filters = ["[1:a]volume=0.26[m]"]
    tags = []
    for idx, (start, stem, _, _) in enumerate(LINES):
        inputs += ["-i", str(ROOT / f"{stem}.wav")]
        dly = round(start * 1000)
        filters.append(f"[{idx + 2}:a]adelay={dly}|{dly},volume=1.3[v{idx}]")
        tags.append(f"[v{idx}]")
    filters.append("[m]" + "".join(tags) +
                   f"amix=inputs={len(LINES) + 1}:duration=first:normalize=0,"
                   "alimiter=limit=0.95[a]")
    cmd = [str(FFMPEG), "-y"] + inputs + [
        "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]",
        "-t", str(DUR), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(ROOT / "AI占いforAI_15秒縦動画_口パク版.mp4")]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        for fi in [15, 60, 140, 260, 300, 420, 440]:
            render_frame(fi / FPS).save(ROOT / f"test_{fi}.png")
        print("test frames done")
    else:
        make_frames()
        mux()
        print("done")
