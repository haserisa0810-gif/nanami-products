"""Build buyer guide PDFs for STORES / Payhip / Etsy.

One layout, one product list, and a per-marketplace block that supplies the
provider tag, the wording for finding an order number, and which languages the
guide is printed in. Coconala keeps its own script because it verifies buyers by
username rather than order number.

    python scripts/build_marketplace_product_guides.py            # all markets
    python scripts/build_marketplace_product_guides.py --marketplace etsy
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
# Buyer-facing marketplace PDFs belong under one clearly named distribution
# tree. Keep QA samples and marketplace-specific sales assets elsewhere.
OUTPUT_ROOT = ROOT / "output" / "pdf" / "distribution"
FONT_PATH = ROOT / "static" / "fonts" / "NotoSansJP-VF.ttf"
BASE_URL = "https://chart.nanami-astro.com"

PAGE_W, PAGE_H = A4
INK = colors.HexColor("#342A26")
MUTED = colors.HexColor("#71645E")
ACCENT = colors.HexColor("#B96535")
ACCENT_DARK = colors.HexColor("#8B4528")
GOLD = colors.HexColor("#D3A65C")
PAPER = colors.HexColor("#FBF7F0")
PANEL = colors.HexColor("#F4EDE3")
LINE = colors.HexColor("#DCCDBD")

pdfmetrics.registerFont(TTFont("NotoJP", str(FONT_PATH)))


# --------------------------------------------------------------------- layout

class QRFlowable(Flowable):
    def __init__(self, value: str, size: float = 24 * mm):
        super().__init__()
        self.value = value
        self.width = size
        self.height = size

    def draw(self) -> None:
        widget = QrCodeWidget(self.value)
        x1, y1, x2, y2 = widget.getBounds()
        drawing = Drawing(
            self.width,
            self.height,
            transform=[self.width / (x2 - x1), 0, 0, self.height / (y2 - y1), 0, 0],
        )
        drawing.add(widget)
        renderPDF.draw(drawing, self.canv, 0, 0)


styles = getSampleStyleSheet()
for name, size, leading, colour, extra in [
    ("Brand", 8, 10, MUTED, {"spaceAfter": 3 * mm}),
    ("TitleJP", 22, 28, INK, {"spaceAfter": 2 * mm}),
    ("TitleEN", 21, 27, INK, {"spaceAfter": 2 * mm}),
    ("Subtitle", 11, 16, MUTED, {"spaceAfter": 5 * mm}),
    ("H2", 14, 18, ACCENT_DARK, {"spaceBefore": 2 * mm, "spaceAfter": 2 * mm}),
    ("BodyJP", 10.8, 16.5, INK, {"spaceAfter": 2.4 * mm}),
    ("BodyEN", 10.5, 16, INK, {"spaceAfter": 2.4 * mm}),
    ("Small", 9.4, 13.5, MUTED, {}),
    ("URL", 9.5, 13, ACCENT_DARK, {"wordWrap": "CJK"}),
    ("StepNo", 10, 13, colors.white, {"alignment": TA_CENTER}),
]:
    styles.add(ParagraphStyle(name, fontName="NotoJP", fontSize=size, leading=leading,
                              textColor=colour, **extra))


def p(text: str, style: str = "BodyJP") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str, style: str = "BodyJP") -> Paragraph:
    return Paragraph(text, styles[style], bulletText="•")


def section(title: str, items: list[str], *, style: str = "BodyJP") -> list[Flowable]:
    return [p(title, "H2"), *(bullet(item, style) for item in items)]


def info_box(content: list[Flowable]) -> Table:
    table = Table([[content]], colWidths=[165 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
    ]))
    return table


def route_box(url: str, heading: str, caption: str) -> Table:
    safe_url = url.replace("&", "&amp;")
    copy = [
        p(heading, "H2"),
        p(f'<link href="{safe_url}">{safe_url}</link>', "URL"),
        p(caption, "Small"),
    ]
    table = Table([[copy, QRFlowable(url)]], colWidths=[126 * mm, 39 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.9, GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 5 * mm),
        ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 7 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 7 * mm),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
    ]))
    return table


def steps(items: list[str], *, style: str = "BodyJP") -> Table:
    rows = []
    for index, item in enumerate(items, 1):
        badge = Table(
            [[p(str(index), "StepNo")]], colWidths=[6 * mm], rowHeights=[6 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]),
        )
        rows.append([badge, p(item, style)])
    table = Table(rows, colWidths=[9 * mm, 153 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
    ]))
    return table


# ---------------------------------------------------------------- marketplaces

MARKETPLACES = {
    "stores": {
        "brand": "nanami-products  |  STORES",
        "languages": ("ja", "en"),
        "support": "お問い合わせ: STORESの注文確認メールへご返信ください",
        "id_label_ja": "注文番号",
        "id_label_en": "order number",
        "where_ja": "STORESからの注文確認メール（件名「ご注文ありがとうございます」）を開き、"
                    "下部の「お客様情報」に記載された注文番号をご確認ください。",
        "where_en": "Open the order confirmation email from STORES and find the order number "
                    "listed under Customer Information near the bottom.",
        "verify_ja": "購入直後は反映に数分かかる場合があります。確認できない場合は5分ほど待って再試行してください。",
        "verify_en": "Verification can take a few minutes right after purchase. If it fails, wait five minutes and try again.",
    },
    "payhip": {
        "brand": "nanami-products  |  Payhip",
        "languages": ("en",),
        "support": "Support: reply to your Payhip purchase email",
        "id_label_ja": "Order ID",
        "id_label_en": "Order ID",
        "where_ja": "Payhipの購入完了メールに記載されている Order ID をご確認ください。",
        "where_en": "Open your Payhip purchase email and copy the Order ID shown there. "
                    "The Order ID is the only detail you need.",
        "verify_ja": "Order IDのみで確認します。メールアドレスの入力は任意です。",
        "verify_en": "The Order ID alone verifies your purchase. The email field is optional.",
    },
    "etsy": {
        "brand": "nanami-products  |  Etsy",
        "languages": ("en",),
        "support": "Support: send a message through Etsy",
        "id_label_ja": "Etsyの注文番号",
        "id_label_en": "Etsy order number",
        "where_ja": "Etsyにログインし、Purchases and reviews から注文詳細を開いて注文番号をご確認ください。",
        "where_en": "Sign in to Etsy, open Purchases and reviews, and take the order number from "
                    "the order details or your receipt email.",
        "verify_ja": "購入直後は反映に数分かかる場合があります。",
        "verify_en": "Verification can take a few minutes right after purchase.",
    },
}


# -------------------------------------------------------------------- products

PLANNER_JA = "1年分のトランジット手帳（PDF・430ページ超・書き込み可）"
PLANNER_EN = "One-year Transit Planner (PDF, 430+ pages, annotatable)"

PRODUCTS = [
    {
        "key": "western_basic",
        "slug": "western-basic",
        "title_ja": "ホロスコープ基本版",
        "subtitle_ja": "星の位置・角度・ハウスを事前計算したAI鑑定用データです。",
        "title_en": "Western Astrology Basic",
        "subtitle_en": "Pre-calculated planetary positions, angles, and houses, ready for AI.",
        "included_ja": [
            "主要天体のサイン・度数・ハウス",
            "ASC、MC、ハウスカスプ",
            "主要アスペクト",
            "AI鑑定用プロンプト",
        ],
        "included_en": [
            "Major planets with signs, degrees, and houses",
            "ASC, MC, and house cusps",
            "Major aspects",
            "Prompt for AI interpretation",
        ],
        "description_ja": "生年月日・出生時刻・出生地から西洋占星術データをYAML形式で生成します。"
                          "天体位置は計算済みのため、AIは解釈に集中できます。",
        "description_en": "Generate pre-calculated Western astrology data in YAML format from your "
                          "birth details. The AI can focus on interpretation rather than recalculating positions.",
    },
    {
        "key": "western_transit",
        "slug": "western-transit",
        "title_ja": "ホロスコープ基本版＋トランジット",
        "subtitle_ja": "出生図と31日分のトランジット、1年分のトランジット手帳を含みます。",
        "title_en": "Western Astrology Basic + Transits",
        "subtitle_en": "Core birth chart, 31 days of transits, and a one-year planner.",
        "included_ja": [
            "基本版の全データ（天体・ASC・MC・ハウス・アスペクト）",
            "31日分のトランジット（日別の天体位置・アスペクト・ハウス）",
            PLANNER_JA,
            "小惑星は含みません",
        ],
        "included_en": [
            "Everything in the Basic edition (planets, ASC, MC, houses, aspects)",
            "31 days of transit data (daily positions, aspects, and houses)",
            PLANNER_EN,
            "Asteroids are not included",
        ],
        "description_ja": "基本版にトランジットを加えた構成です。トランジットが含まれるため、"
                          "鑑定ページからトランジット手帳（PDF）を作成できます。"
                          "小惑星（キロン・ジュノー等）もご希望の場合はFULL版をお選びください。",
        "description_en": "The Basic edition plus transits. Because transits are included, you can build "
                          "the Transit Planner (PDF) from your chart page. Choose the FULL edition if you "
                          "also want the asteroids (Chiron, Juno, Vesta, Pallas, Ceres).",
        "transit": True,
        "planner": True,
        # Etsy ships the richer standalone guide from build_etsy_wbt_guide.py
        # (product code, FULL comparison, terms, FAQ), so skip it here.
        "skip_marketplaces": {"etsy"},
    },
    {
        "key": "western_full",
        "slug": "western-full",
        "title_ja": "ホロスコープFULL版",
        "subtitle_ja": "小惑星・31日分のトランジット・1年分のトランジット手帳を含むフルセットです。",
        "title_en": "Western Astrology FULL",
        "subtitle_en": "Complete set with asteroids, 31 days of transits, and a one-year planner.",
        "included_ja": [
            "基本版の全データ",
            "小惑星: キロン、ジュノー、ベスタ、パラス、セレス",
            "31日分のトランジット",
            PLANNER_JA,
        ],
        "included_en": [
            "Everything in the Basic edition",
            "Asteroids: Chiron, Juno, Vesta, Pallas, Ceres",
            "31 days of transit data",
            PLANNER_EN,
        ],
        "description_ja": "基本版に小惑星と31日分のトランジットを加えたフルセットです。"
                          "生成される鑑定ページから、YAMLデータ・ホロスコープ画像・保存用ZIPをダウンロードできます。",
        "description_en": "The Basic edition plus asteroids and 31 days of transit data. From the chart page "
                          "you can download the YAML data, the chart image, and a ZIP archive.",
        "transit": True,
        "planner": True,
    },
    {
        "key": "shichu",
        "slug": "shichu",
        "title_ja": "四柱推命版",
        "subtitle_ja": "年柱・月柱・日柱・時柱と関連情報を計算したデータです。",
        "title_en": "Four Pillars of Destiny",
        "subtitle_en": "Calculated year, month, day, and hour pillars with supporting data.",
        "included_ja": [
            "四柱（年柱・月柱・日柱・時柱）",
            "十神・蔵干などの関連情報",
            "日替わり境界の選択（23時 / 1時）",
            "AI鑑定用プロンプト",
        ],
        "included_en": [
            "The four pillars: year, month, day, and hour",
            "Ten Gods and hidden stems",
            "Selectable day boundary (23:00 or 01:00)",
            "Prompt for AI interpretation",
        ],
        "description_ja": "生年月日・出生時刻から四柱推命データをYAML形式で生成します。"
                          "日替わり境界は購入者が選択できます。",
        "description_en": "Generate Four Pillars data in YAML format from your birth details. "
                          "You choose which day boundary to use.",
    },
]


# ----------------------------------------------------------------- page bodies

def redeem_url(slug: str, lang: str, provider: str) -> str:
    return f"{BASE_URL}/redeem/{slug}?lang={lang}&provider={provider}"


def addon_url(lang: str, provider: str) -> str:
    return f"{BASE_URL}/addon/new?lang={lang}&provider={provider}"


def page_header(market: dict, title: str, subtitle: str, *, english: bool = False) -> list[Flowable]:
    return [
        p(market["brand"], "Brand"),
        p(title, "TitleEN" if english else "TitleJP"),
        p(subtitle, "Subtitle"),
    ]


def notices_ja(market: dict) -> list[Flowable]:
    return [
        *section("ご利用上の注意", [
            "本商品は占術データとAIによる解釈を楽しむためのコンテンツです。医療・法律・投資などの専門判断には使用しないでください。",
            "AIの回答は利用するサービスやモデルにより異なります。重要な判断はご自身の責任で行ってください。",
            "生成データは個人利用向けです。再配布・転載・販売は禁止です。",
        ]),
        *section("購入確認について", [
            f"入力するのは{market['id_label_ja']}です。{market['where_ja']}",
            market["verify_ja"],
        ]),
        *section("共有URLと保存", [
            "生成された鑑定ページは発行から90日間ご利用いただけます。",
            "期限後も使えるよう、発行後に保存用ZIPを端末へダウンロードしてください。",
        ]),
    ]


def notices_en(market: dict) -> list[Flowable]:
    return [
        *section("Notes on use", [
            "This product provides astrology data and AI-assisted reflection. Do not use it for medical, "
            "legal, or financial decisions.",
            "AI answers vary by service and model. Final decisions remain your own.",
            "The generated data is for personal use. Redistribution and resale are not permitted.",
        ], style="BodyEN"),
        *section("Purchase verification", [
            f"You will be asked for your {market['id_label_en']}. {market['where_en']}",
            market["verify_en"],
        ], style="BodyEN"),
        *section("Chart page and storage", [
            "The generated chart page stays available for 90 days.",
            "Download the ZIP archive so you keep the files after that.",
        ], style="BodyEN"),
    ]


def product_pages(market: dict, product: dict) -> list[Flowable]:
    provider = market["provider"]
    story: list[Flowable] = []

    if "ja" in market["languages"]:
        url = redeem_url(product["slug"], "ja", provider)
        story.extend(page_header(market, product["title_ja"], product["subtitle_ja"]))
        story.append(route_box(url, "購入者専用の入力フォーム", "右のQRコード、またはURLをタップして開いてください。"))
        story.append(Spacer(1, 4 * mm))
        story.extend([
            p("ご利用方法", "H2"),
            steps([
                "このPDFの専用URLを開く",
                f"{market['id_label_ja']}と出生情報（生年月日・出生時刻・出生地）を入力する",
                "発行されたデータを保存し、お好みのAIで利用する",
            ]),
            Spacer(1, 2 * mm),
            *section("含まれるデータ", product["included_ja"]),
            Spacer(1, 1 * mm),
            info_box([p(product["description_ja"])]),
        ])
        if product.get("planner"):
            story.append(Spacer(1, 3 * mm))
            story.append(info_box([p(
                "トランジット手帳（PDF）は、鑑定ページの「あなたの1年トランジット手帳（PDF）を作成・保存」"
                "ボタンから作成できます。作成した月から1年分で、何度でも作り直せます。"
            )]))
        story.append(PageBreak())
        story.extend(page_header(market, "ご利用にあたって", "入力前に必ずご確認ください。"))
        story.extend(notices_ja(market))
        story.append(PageBreak())

    url = redeem_url(product["slug"], "en", provider)
    story.extend(page_header(market, product["title_en"], product["subtitle_en"], english=True))
    story.append(route_box(url, "Buyer input form", "Scan the QR code or tap the URL to open the form."))
    story.append(Spacer(1, 4 * mm))
    story.extend([
        p("How to use", "H2"),
        steps([
            "Open the dedicated URL in this PDF.",
            f"Enter your {market['id_label_en']} and your birth date, birth time, and birthplace.",
            "Save the generated files and use them with your preferred AI.",
        ], style="BodyEN"),
        Spacer(1, 2 * mm),
        *section("What's included", product["included_en"], style="BodyEN"),
        info_box([p(product["description_en"], "BodyEN")]),
    ])
    if product.get("planner"):
        story.append(Spacer(1, 3 * mm))
        story.append(info_box([p(
            "Build the planner from your chart page with the "
            "\"Create your 1-Year Transit Planner (PDF)\" button. It covers twelve months from the "
            "month you build it, and you can rebuild it whenever you like.",
            "BodyEN",
        )]))
    if "ja" not in market["languages"]:
        story.append(PageBreak())
        story.extend(page_header(market, "Before you start", "Please read this before entering your details.", english=True))
        story.extend(notices_en(market))
    return story


def addon_pages(market: dict) -> list[Flowable]:
    provider = market["provider"]
    codes_ja = [
        "小惑星データ: キロン、ジュノー、ベスタ、パラス、セレス",
        "31日トランジット: 日別の天体位置、アスペクト、ハウス",
        "長期トランジット（1年）: 出生図への長期トランジット",
        "四柱推命・大運: 10年単位の大運と関連情報",
    ]
    codes_en = [
        "Asteroid data: Chiron, Juno, Vesta, Pallas, Ceres",
        "31-day transits: daily positions, aspects, and houses",
        "Long-term transits (1 year): outer-planet transits to your natal chart",
        "Da-Yun: ten-year luck cycles",
    ]
    story: list[Flowable] = []
    if "ja" in market["languages"]:
        story.extend(page_header(market, "アドオンデータ", "基本版をお持ちの方向けの追加データです。"))
        story.append(route_box(addon_url("ja", provider), "アドオン専用の入力フォーム",
                               "右のQRコード、またはURLをタップして開いてください。"))
        story.append(Spacer(1, 4 * mm))
        story.extend([
            p("ご利用方法", "H2"),
            steps([
                "専用URLを開き、購入したアドオン種別を選ぶ",
                f"{market['id_label_ja']}を入力する",
                "基本版YAMLまたは有効な前回鑑定URLを指定して生成する",
            ]),
            *section("選べるアドオン", codes_ja),
            info_box([p("フォームでは、購入した商品と同じアドオン種別を選択してください。"
                        "異なる種別を選ぶと購入確認に失敗します。")]),
        ])
        story.append(PageBreak())
        story.extend(page_header(market, "ご利用にあたって", "アドオン購入者向けの確認事項です。"))
        story.extend(notices_ja(market))
        story.append(PageBreak())

    story.extend(page_header(market, "Add-on Data",
                             "Additional data for owners of a compatible Basic product.", english=True))
    story.append(route_box(addon_url("en", provider), "Add-on input form",
                           "Scan the QR code or tap the URL to open the form."))
    story.append(Spacer(1, 4 * mm))
    story.extend([
        p("How to use", "H2"),
        steps([
            "Open the dedicated URL and select the add-on you purchased.",
            f"Enter your {market['id_label_en']}.",
            "Provide the compatible base YAML or an active previous chart URL.",
        ], style="BodyEN"),
        *section("Available add-ons", codes_en, style="BodyEN"),
        info_box([p("Choose the same add-on type that you purchased. Selecting a different type "
                    "will fail verification.", "BodyEN")]),
    ])
    if "ja" not in market["languages"]:
        story.append(PageBreak())
        story.extend(page_header(market, "Before you start",
                                 "Please read this before entering your details.", english=True))
        story.extend(notices_en(market))
    return story


# ------------------------------------------------------------------- rendering

def build_pdf(market: dict, story: list[Flowable], path: Path, subject: str) -> None:
    def on_page(canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFillColor(PAPER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 3 * mm, PAGE_W, 3 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, 14 * mm, PAGE_W - 18 * mm, 14 * mm)
        canvas.setFont("NotoJP", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, "nanami-products")
        canvas.drawRightString(PAGE_W - 18 * mm, 9 * mm, market["support"])
        canvas.restoreState()

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=subject, author="nanami-products", subject=subject,
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def build_marketplace(name: str) -> list[Path]:
    market = {**MARKETPLACES[name], "provider": name}
    out_dir = OUTPUT_ROOT / name
    written: list[Path] = []
    for product in PRODUCTS:
        if name in product.get("skip_marketplaces", ()):
            continue
        path = out_dir / f"nanami_{product['key']}_{name}.pdf"
        build_pdf(market, product_pages(market, product), path,
                  f"{product['title_en']} - {name} buyer guide")
        written.append(path)
    path = out_dir / f"nanami_addon_{name}.pdf"
    build_pdf(market, addon_pages(market), path, f"Add-on Data - {name} buyer guide")
    written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace", choices=sorted(MARKETPLACES), action="append",
                        help="repeatable; defaults to every marketplace")
    args = parser.parse_args()
    for name in args.marketplace or sorted(MARKETPLACES):
        for path in build_marketplace(name):
            print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
