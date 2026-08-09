from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


OUTPUT = Path("output/pdf/nanami_acg_premium_bundle_etsy_en.pdf")
ACCESS_URL = "https://chart.nanami-astro.com/redeem/acg-bundle?lang=en&provider=etsy"

PAGE_W, PAGE_H = A4
NAVY = HexColor("#18213D")
MUTED = HexColor("#72778A")
COPPER = HexColor("#B96732")
CREAM = HexColor("#F8F5EF")
PANEL = HexColor("#F2EEE7")
LINE = HexColor("#DDD6CB")
WHITE = HexColor("#FFFFFF")


def text(pdf, x, y, value, size=11, color=NAVY, font="Helvetica"):
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawString(x, y, value)


def wrapped(pdf, x, y, lines, size=11.5, leading=17, color=NAVY, font="Helvetica"):
    for line in lines:
        text(pdf, x, y, line, size=size, color=color, font=font)
        y -= leading
    return y


def header(pdf, title, subtitle):
    pdf.setFillColor(CREAM)
    pdf.rect(0, PAGE_H - 70 * mm, PAGE_W, 70 * mm, stroke=0, fill=1)
    pdf.setFillColor(COPPER)
    pdf.rect(0, PAGE_H - 1.6 * mm, PAGE_W, 1.6 * mm, stroke=0, fill=1)
    text(pdf, 18 * mm, PAGE_H - 15 * mm, "nanami-astro", 10, MUTED, "Courier")
    text(pdf, 18 * mm, PAGE_H - 32 * mm, title, 25, NAVY, "Helvetica-Bold")
    text(pdf, 18 * mm, PAGE_H - 45 * mm, subtitle, 11.5, MUTED)
    pdf.setStrokeColor(LINE)
    pdf.line(18 * mm, PAGE_H - 60 * mm, PAGE_W - 18 * mm, PAGE_H - 60 * mm)


def footer(pdf, page):
    pdf.setFillColor(PANEL)
    pdf.rect(0, 0, PAGE_W, 14 * mm, stroke=0, fill=1)
    pdf.setFillColor(COPPER)
    pdf.rect(0, 0, PAGE_W, 1.4 * mm, stroke=0, fill=1)
    text(pdf, 18 * mm, 5.5 * mm, "support@nanami-astro.com", 9, MUTED, "Courier")
    text(pdf, PAGE_W - 64 * mm, 5.5 * mm, f"nanami-astro.com   |   {page}", 9, MUTED, "Courier")


def section(pdf, y, title):
    text(pdf, 18 * mm, y, title, 14, NAVY, "Helvetica-Bold")
    pdf.setStrokeColor(COPPER)
    pdf.setLineWidth(1)
    pdf.line(18 * mm, y - 4 * mm, 39 * mm, y - 4 * mm)
    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.6)
    pdf.line(39 * mm, y - 4 * mm, PAGE_W - 18 * mm, y - 4 * mm)
    return y - 13 * mm


def numbered_step(pdf, y, number, title, detail):
    pdf.setFillColor(COPPER)
    pdf.circle(23 * mm, y + 1.5 * mm, 4.8 * mm, stroke=0, fill=1)
    text(pdf, 21.6 * mm, y - 0.5 * mm, str(number), 10, WHITE, "Helvetica-Bold")
    text(pdf, 32 * mm, y + 3 * mm, title, 11, NAVY, "Helvetica-Bold")
    text(pdf, 32 * mm, y - 3.5 * mm, detail, 11.5, MUTED)


def bullet(pdf, y, title, detail):
    pdf.setFillColor(COPPER)
    pdf.circle(21.5 * mm, y + 1.2 * mm, 1.1 * mm, stroke=0, fill=1)
    text(pdf, 26 * mm, y, title, 10.5, NAVY, "Helvetica-Bold")
    text(pdf, 26 * mm, y - 5 * mm, detail, 11.5, MUTED)


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4)
    pdf.setTitle("NANAMI ASTRO - ACG Premium Bundle - Etsy Access Guide")
    pdf.setAuthor("NANAMI ASTRO")
    pdf.setSubject("Automatic access guide for Etsy customers")

    header(
        pdf,
        "ACG PREMIUM BUNDLE",
        "Your permanent Personal Edition app and private astrology workspace",
    )

    box_x, box_y, box_w, box_h = 18 * mm, PAGE_H - 117 * mm, 157 * mm, 39 * mm
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(box_x, box_y, box_w, box_h, 3 * mm, stroke=1, fill=1)
    text(pdf, box_x + 7 * mm, box_y + 28 * mm, "START HERE - AUTOMATIC ACCESS", 10, MUTED)
    text(pdf, box_x + 7 * mm, box_y + 18 * mm, ACCESS_URL, 9.2, COPPER, "Courier")
    text(pdf, box_x + 7 * mm, box_y + 8 * mm, "Tap or click the link, or scan the QR code.", 11.5, MUTED)
    pdf.linkURL(ACCESS_URL, (box_x, box_y, box_x + box_w, box_y + box_h), relative=0)

    qr = QrCodeWidget(ACCESS_URL)
    bounds = qr.getBounds()
    size = 27 * mm
    drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
    qr.barFillColor = COPPER
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, 177 * mm, box_y + 6 * mm)
    pdf.linkURL(ACCESS_URL, (177 * mm, box_y + 6 * mm, 204 * mm, box_y + 33 * mm), relative=0)

    y = section(pdf, PAGE_H - 132 * mm, "HOW TO GET YOUR PERSONAL EDITION")
    numbered_step(pdf, y, 1, "Open the access page", "Use the orange link above or scan the QR code.")
    numbered_step(pdf, y - 18 * mm, 2, "Enter your Etsy order number", "Use the order number shown on your Etsy purchase receipt.")
    numbered_step(pdf, y - 36 * mm, 3, "Enter your birth information", "Provide your birth date, exact birth time, and birthplace.")
    numbered_step(pdf, y - 54 * mm, 4, "Download and keep your ZIP", "Your permanent Personal Edition ZIP downloads automatically.")

    y = section(pdf, PAGE_H - 229 * mm, "IMPORTANT")
    text(pdf, 18 * mm, y, "Access is automatic after Etsy order verification.", 11.5, NAVY)
    text(pdf, 18 * mm, y - 8 * mm, "ACG requires an accurate birth time. Estimated or unknown times cannot be used.", 11.5, NAVY)
    text(pdf, 18 * mm, y - 16 * mm, "If verification is not immediate, wait five minutes and try again.", 11.5, NAVY)
    footer(pdf, 1)
    pdf.showPage()

    header(
        pdf,
        "WHAT IS INCLUDED",
        "A personal astrology package prepared from your confirmed birth data",
    )
    y = section(pdf, PAGE_H - 82 * mm, "YOUR ACG BUNDLE")
    bullet(pdf, y, "Personal astrocartography map", "Explore planetary angular lines on an interactive world map.")
    bullet(pdf, y - 18 * mm, "Birth Chart Museum", "View your natal chart through the visual Personal Edition experience.")
    bullet(pdf, y - 36 * mm, "Precalculated astrology YAML", "Use reliable calculated data with ChatGPT, Claude, Gemini, or another AI.")
    bullet(pdf, y - 54 * mm, "Private chart page", "Return to your private page to download your Personal Edition ZIP again.")
    bullet(pdf, y - 72 * mm, "Personal Planner PDF", "A printable companion planner is included in the downloaded package.")

    y = section(pdf, PAGE_H - 182 * mm, "PLEASE SAVE")
    wrapped(
        pdf,
        18 * mm,
        y,
        [
            "Save your downloaded ZIP and your private chart page URL.",
            "Extract the complete ZIP before opening the Personal Edition app.",
            "The background world map uses an internet connection.",
            "Your personal ACG lines are included with your Personal Edition package.",
        ],
        size=11.5,
        leading=6 * mm,
    )

    y = section(pdf, PAGE_H - 239 * mm, "SUPPORT")
    wrapped(
        pdf,
        18 * mm,
        y,
        [
            "If verification still fails after five minutes, contact us through Etsy Messages.",
            "Include your Etsy order number, but do not post birth information publicly.",
            "Manual support is available when automatic verification needs assistance.",
        ],
        size=11.5,
        leading=6 * mm,
    )
    footer(pdf, 2)
    pdf.save()
    print(OUTPUT.resolve())


if __name__ == "__main__":
    build()
