from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Paragraph


OUTPUT = Path("output/etsy/western-transit/nanami_western_transit_ETSY_EN.pdf")
# provider=etsy tags the buyer's route so the form locks the order field to Etsy
# instead of asking which marketplace they bought from.
START_URL = "https://chart.nanami-astro.com/start/western-transit?lang=en&provider=etsy"

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

BG = HexColor("#FAF7F0")
INK = HexColor("#332A26")
BODY = HexColor("#796B61")
GOLD = HexColor("#A5732B")
LINE = HexColor("#C8A84B")
ORANGE = HexColor("#DF6038")


def footer(c: canvas.Canvas) -> None:
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN_X, 17 * mm, PAGE_W - MARGIN_X, 17 * mm)
    c.setFillColor(BODY)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN_X, 11.5 * mm, "Contact: support@nanami-astro.com")
    c.drawRightString(PAGE_W - MARGIN_X, 11.5 * mm, "nanami-astro.com")


def page_header(c: canvas.Canvas) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(BODY)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN_X, PAGE_H - 19 * mm, "nanami-products")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN_X, PAGE_H - 24 * mm, PAGE_W - MARGIN_X, PAGE_H - 24 * mm)
    footer(c)


def heading(c: canvas.Canvas, text: str, y: float, size: float = 25) -> float:
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", size)
    c.drawString(MARGIN_X, y, text)
    return y - size - 5


def section_line(c: canvas.Canvas, title: str, y: float) -> float:
    c.setStrokeColor(LINE)
    c.setLineWidth(0.55)
    c.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN_X, y - 17, title)
    return y - 30


def body_lines(c: canvas.Canvas, lines: list[str], y: float, *, x: float | None = None,
               size: float = 8.8, leading: float = 14) -> float:
    x = MARGIN_X if x is None else x
    c.setFillColor(BODY)
    c.setFont("Helvetica", size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def bullet_lines(c: canvas.Canvas, lines: list[str], y: float) -> float:
    c.setFont("Helvetica", 8.8)
    for line in lines:
        c.setFillColor(GOLD)
        c.circle(MARGIN_X + 3, y + 2, 3, stroke=0, fill=1)
        c.setFillColor(INK)
        c.drawString(MARGIN_X + 12, y, line)
        y -= 16
    return y


def numbered_step(c: canvas.Canvas, number: int, text: str, y: float) -> float:
    c.setFillColor(GOLD)
    c.circle(MARGIN_X + 6, y + 3, 8, stroke=0, fill=1)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 8)
    num = str(number)
    c.drawString(MARGIN_X + 6 - stringWidth(num, "Helvetica-Bold", 8) / 2, y, num)
    c.setFillColor(INK)
    c.setFont("Helvetica", 9.2)
    c.drawString(MARGIN_X + 23, y, text)
    return y - 19


def faq(c: canvas.Canvas, question: str, answers: list[str], y: float) -> float:
    c.setFillColor(GOLD)
    c.roundRect(MARGIN_X, y - 4, CONTENT_W, 20, 5, stroke=0, fill=1)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(MARGIN_X + 9, y + 3, f"Q.  {question}")
    y -= 22
    return body_lines(c, answers, y, x=MARGIN_X + 11, size=8.3, leading=13) - 7


def draw_qr(c: canvas.Canvas, value: str, x: float, y: float, size: float) -> None:
    widget = QrCodeWidget(value)
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(OUTPUT), pagesize=A4, pageCompression=1)
    c.setTitle("Nanami Astro Basic + Transits Etsy Access Guide")
    c.setAuthor("Nanami Astro")

    # Page 1
    page_header(c)
    y = PAGE_H - 43 * mm
    y = heading(c, "Basic + Transits", y)
    c.setFillColor(BODY)
    c.setFont("Helvetica", 11)
    c.drawString(
        MARGIN_X, y,
        "Core birth chart data, transit timing, and a personalized 1-year digital planner."
    )
    y -= 16
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.roundRect(MARGIN_X, y - 51, CONTENT_W - 28 * mm, 51, 9, stroke=1, fill=0)
    c.setFillColor(BODY)
    c.setFont("Helvetica", 7.7)
    c.drawString(MARGIN_X + 9, y - 14, ">> Input form")
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 8.4)
    c.drawString(MARGIN_X + 9, y - 32, START_URL)
    # the page invites a tap, so the URL has to be a real link, not just text
    url_width = stringWidth(START_URL, "Helvetica-Bold", 8.4)
    c.linkURL(START_URL, (MARGIN_X + 9, y - 36, MARGIN_X + 9 + url_width, y - 24), relative=0, thickness=0)
    c.setFillColor(BODY)
    c.setFont("Helvetica", 7.4)
    c.drawString(MARGIN_X + 9, y - 45, "Tap or click to open")
    draw_qr(c, START_URL, PAGE_W - MARGIN_X - 25 * mm, y - 53, 25 * mm)
    y -= 75

    y = section_line(c, "How to Use", y)
    y = numbered_step(c, 1, "Open the URL above (or scan the QR code)", y)
    y = numbered_step(c, 2, "Enter your Etsy order number and birth details", y)
    y = numbered_step(c, 3, "Generate your personal chart page", y)
    y = numbered_step(c, 4, "Download your AI-ready data and 1-year planner", y)

    y -= 4
    y = section_line(c, "What's Included", y)
    y = bullet_lines(c, [
        "Major planets (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto)",
        "ASC, MC, House cusps, and major aspects",
        "Transit data with daily positions, aspects, house placements, and orbs",
        "Personalized 1-year digital astrology planner PDF",
        "AI-ready YAML data for ChatGPT, Claude, Gemini, or another text-based AI",
    ], y)

    y -= 4
    y = section_line(c, "Basic + Transits or Full?", y)
    y = body_lines(c, [
        "This [NP-WBT] version includes core natal data, transits, and the 1-year planner.",
        "It does not include asteroid data.",
        "Choose [NP-WF] Full if you also want Chiron, Juno, Vesta, Pallas, Ceres, Lilith, and Vertex.",
    ], y, size=8.5, leading=14)
    y -= 4
    c.setFillColor(BODY)
    style = ParagraphStyle(
        "note", fontName="Helvetica", fontSize=7.5, leading=10,
        textColor=BODY, maxLeading=10,
    )
    note = Paragraph(
        "* After purchase, please allow up to 5 minutes for the system to confirm your order.",
        style,
    )
    note.wrapOn(c, CONTENT_W, 24)
    note.drawOn(c, MARGIN_X, y - 12)
    c.showPage()

    # Page 2
    page_header(c)
    y = PAGE_H - 43 * mm
    y = heading(c, "Terms of Use", y)
    y -= 10
    sections = [
        ("Transit Data and Planner", [
            "Transit data is calculated from the date of generation.",
            "Download the ZIP archive and planner PDF to retain your files for future reference.",
        ]),
        ("Important Notice", [
            "This service is for entertainment and personal reflection related to astrology data and AI interpretation.",
            "It is not intended for medical, legal, financial, or other professional advisory use.",
            "AI-generated interpretations may vary depending on the AI service and model used.",
        ]),
        ("System & Data", [
            "Service specifications may change without prior notice.",
            "Temporary unavailability may occur due to server or network issues.",
            "Please save your generated files and shared URL as needed.",
        ]),
        ("Shared URL", [
            "The shared URL is valid for 90 days from the date of issue.",
            "To continue using the data after expiry, download the ZIP archive to your device.",
        ]),
        ("AI Usage", [
            "This product provides pre-calculated data intended to be passed to an AI.",
            "AI subscriptions or usage fees are not included.",
        ]),
        ("Birth Time", [
            "If birth time is unknown, house cusps, ASC, and MC will be approximate reference values.",
        ]),
        ("Usage Scope", [
            "This data and planner are for personal use only.",
            "Redistribution, republication, resale, and commercial use are not permitted.",
        ]),
    ]
    for title, lines in sections:
        y = section_line(c, title, y)
        y = body_lines(c, lines, y, x=MARGIN_X + 11, size=8.2, leading=13)
        y -= 9
    c.showPage()

    # Page 3
    page_header(c)
    y = PAGE_H - 43 * mm
    y = heading(c, "Frequently Asked Questions", y)
    y -= 7
    y = faq(c, "Where can I find my order number?", [
        "Open your Etsy account and go to Purchases and reviews.",
        "Your order number is shown in the Etsy order details and receipt email.",
    ], y)
    y = faq(c, "What is the difference from the Full version?", [
        "Both versions include transits and the personalized 1-year digital planner.",
        "The Full version also includes asteroid data; Basic + Transits does not.",
    ], y)
    y = faq(c, "Which AI should I use?", [
        "You can use ChatGPT, Claude, Gemini, or another text-based AI.",
        'After pasting the data, ask: "Please give me a reading based on this data."',
    ], y)
    y = faq(c, "It is taking a long time or I am getting an error.", [
        "Order confirmation may take up to 5 minutes. Please wait and try again.",
        "If the issue continues, contact support through Etsy Messages.",
    ], y)
    y = faq(c, "Can I use this data more than once?", [
        "Yes. The shared URL is valid for 90 days.",
        "Download the ZIP archive and planner early for long-term access.",
    ], y)
    y = faq(c, "Does this product include asteroid data?", [
        "No. Choose the Full version [NP-WF], or purchase the asteroid add-on [NP-WA].",
    ], y)
    c.save()
    print(OUTPUT.resolve())


if __name__ == "__main__":
    build()
