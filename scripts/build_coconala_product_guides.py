from __future__ import annotations

from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "pdf"
FONT_PATH = Path(r"C:\Windows\Fonts\NotoSansJP-VF.ttf")

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


class QRFlowable(Flowable):
    def __init__(self, value: str, size: float = 29 * mm):
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
            transform=[
                self.width / (x2 - x1),
                0,
                0,
                self.height / (y2 - y1),
                0,
                0,
            ],
        )
        drawing.add(widget)
        renderPDF.draw(drawing, self.canv, 0, 0)


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "Brand",
        fontName="NotoJP",
        fontSize=8,
        leading=10,
        textColor=MUTED,
        spaceAfter=3 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "TitleJP",
        fontName="NotoJP",
        fontSize=22,
        leading=28,
        textColor=INK,
        spaceAfter=2 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "TitleEN",
        fontName="NotoJP",
        fontSize=21,
        leading=27,
        textColor=INK,
        spaceAfter=2 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "Subtitle",
        fontName="NotoJP",
        fontSize=11,
        leading=16,
        textColor=MUTED,
        spaceAfter=5 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "H2",
        fontName="NotoJP",
        fontSize=14,
        leading=18,
        textColor=ACCENT_DARK,
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "BodyJP",
        fontName="NotoJP",
        fontSize=10.8,
        leading=16.5,
        textColor=INK,
        spaceAfter=2 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "BodyEN",
        fontName="NotoJP",
        fontSize=10.5,
        leading=16,
        textColor=INK,
        spaceAfter=2 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "Small",
        fontName="NotoJP",
        fontSize=9.4,
        leading=13.5,
        textColor=MUTED,
    )
)
styles.add(
    ParagraphStyle(
        "URL",
        fontName="NotoJP",
        fontSize=9.5,
        leading=13,
        textColor=ACCENT_DARK,
        wordWrap="CJK",
    )
)
styles.add(
    ParagraphStyle(
        "StepNo",
        fontName="NotoJP",
        fontSize=10,
        leading=13,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        "CenterSmall",
        fontName="NotoJP",
        fontSize=9,
        leading=12.5,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
)


def p(text: str, style: str = "BodyJP") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str, style: str = "BodyJP") -> Paragraph:
    return Paragraph(text, styles[style], bulletText="•")


def section(title: str, items: list[str], *, style: str = "BodyJP") -> list[Flowable]:
    result: list[Flowable] = [p(title, "H2")]
    result.extend(bullet(item, style) for item in items)
    return result


def info_box(content: list[Flowable], *, border: colors.Color = LINE) -> Table:
    table = Table([[content]], colWidths=[165 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    return table


def route_box(url: str, language: str) -> Table:
    safe_url = url.replace("&", "&amp;")
    is_western_basic = "/redeem/western-basic" in url
    qr_size = 22 * mm if is_western_basic else 24 * mm
    vertical_padding = 7 * mm if is_western_basic else 5 * mm
    qr_left_padding = 0 if is_western_basic else 7 * mm
    qr_right_padding = 20 if is_western_basic else 7 * mm
    copy = (
        [
            p("ココナラ購入者専用入力フォーム", "H2"),
            p(f'<link href="{safe_url}">{safe_url}</link>', "URL"),
            p("右のQRコード、またはURLをタップして開いてください。", "Small"),
        ]
        if language == "ja"
        else [
            p("Coconala buyer input form", "H2"),
            p(f'<link href="{safe_url}">{safe_url}</link>', "URL"),
            p("Scan the QR code or tap the URL to open the form.", "Small"),
        ]
    )
    table = Table([[copy, QRFlowable(url, size=qr_size)]], colWidths=[126 * mm, 39 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.9, GOLD),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 5 * mm),
                ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
                ("LEFTPADDING", (1, 0), (1, 0), qr_left_padding),
                ("RIGHTPADDING", (1, 0), (1, 0), qr_right_padding),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), vertical_padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), vertical_padding),
            ]
        )
    )
    return table


def steps(items: list[str], *, style: str = "BodyJP") -> Table:
    rows = []
    for idx, item in enumerate(items, 1):
        badge = Table(
            [[p(str(idx), "StepNo")]],
            colWidths=[6 * mm],
            rowHeights=[6 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            ),
        )
        rows.append([badge, p(item, style)])
    table = Table(rows, colWidths=[9 * mm, 153 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
            ]
        )
    )
    return table


def page_header(title: str, subtitle: str, *, english: bool = False) -> list[Flowable]:
    return [
        p("nanami-products  |  Coconala Content Market", "Brand"),
        p(title, "TitleEN" if english else "TitleJP"),
        p(subtitle, "Subtitle"),
    ]


def on_page(canvas, doc) -> None:
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
    canvas.drawRightString(
        PAGE_W - 18 * mm,
        9 * mm,
        "Support: use the inquiry option on the Coconala product page",
    )
    canvas.restoreState()


def common_notice_jp() -> list[Flowable]:
    return [
        *section(
            "ご利用上の注意",
            [
                "本商品は占術データとAIによる解釈を楽しむためのコンテンツです。医療・法律・投資などの専門判断には使用しないでください。",
                "AIの回答は利用するサービスやモデルにより異なります。重要な判断はご自身の責任で行ってください。",
                "生成データは個人利用向けです。再配布・転載・販売は禁止です。",
            ],
        ),
        *section(
            "購入確認について",
            [
                "入力するのは注文番号ではなく、購入時のココナラユーザー名です。",
                "購入通知がシステムへ反映されるまで数分かかる場合があります。確認できない場合は5分ほど待って再試行してください。",
                "ユーザー名を購入後に変更した場合は、購入時に使っていた旧ユーザー名を入力してください。",
            ],
        ),
        *section(
            "共有URLと保存",
            [
                "生成された共有URLは発行から90日間利用できます。",
                "期限後も利用できるよう、発行後に保存用ZIPを端末へダウンロードしてください。",
            ],
        ),
    ]


def faq_jp(*, base_required: bool = False, include_title: bool = True) -> list[Flowable]:
    result: list[Flowable] = []
    if include_title:
        result.append(p("よくあるご質問", "TitleJP"))
    result.extend(
        [
        p("Q. ココナラのユーザー名はどこで確認できますか？", "H2"),
        p("ココナラへログインし、マイページ上部に表示される名前を確認してください。購入時と同じ表記で入力します。"),
        p("Q. 購入したのに確認できません", "H2"),
        p("購入通知の反映に数分かかる場合があります。5分ほど待って再試行してください。商品タイトルに正しい商品コードが付いている購入だけが対象です。"),
        ]
    )
    if base_required:
        result.extend(
            [
                p("Q. 基本版を持っていなくても利用できますか？", "H2"),
                p("アドオンは既存の基本データと組み合わせて使用します。対象となる基本版を先にご用意ください。"),
            ]
        )
    result.extend(
        [
            p("Q. どのAIで利用できますか？", "H2"),
            p("ChatGPT、Claude、Geminiなどで利用できます。生成ページの案内に従い、YAMLまたはプロンプトを貼り付けてください。"),
            p("Q. 入力を間違えました", "H2"),
            p("購入1件につき発行は1回です。入力確定前に生年月日・出生時刻・出生地を必ず確認してください。例外対応はココナラの商品ページからお問い合わせください。"),
            p("Q. エラーが続きます", "H2"),
            p("通信環境を確認し、時間を置いて再試行してください。解決しない場合はココナラの商品ページにある問い合わせ機能をご利用ください。"),
        ]
    )
    return result


def guide_pages(product: dict) -> list[Flowable]:
    url_ja = product["url_ja"]
    url_en = product["url_en"]
    story: list[Flowable] = []
    story.extend(page_header(product["title_ja"], product["subtitle_ja"]))
    story.append(route_box(url_ja, "ja"))
    story.append(Spacer(1, 4 * mm))
    story.extend(
        [
            p("ご利用方法", "H2"),
            steps(
                [
                    "このPDFの専用URLを開く",
                    "購入時のココナラユーザー名と出生情報を入力する",
                    "発行されたデータを保存し、お好みのAIで利用する",
                ]
            ),
            Spacer(1, 2 * mm),
            *section("含まれるデータ", product["included_ja"]),
            Spacer(1, 1 * mm),
            info_box([p(product["description_ja"])]),
            Spacer(1, 3 * mm),
            p(
                f"商品タイトルには <b>{product['code']}</b> が必要です。購入確認には商品コードを使用します。",
                "Small",
            ),
        ]
    )
    story.append(PageBreak())
    story.extend(page_header("ご利用にあたって", "購入前・入力前に必ずご確認ください。"))
    story.extend(common_notice_jp())
    if product.get("transit"):
        story.extend(
            section(
                "トランジットデータについて",
                [
                    "31日分のトランジットは生成日を基準にした期間データです。",
                    "保存用ZIPをダウンロードすると、共有URLの期限後も過去分析や参考用途に利用できます。",
                ],
            )
        )
    story.append(PageBreak())
    story.extend(page_header("よくあるご質問", "ココナラ購入者向けの確認事項です。"))
    story.extend(faq_jp(include_title=False))
    story.append(PageBreak())
    story.extend(page_header(product["title_en"], product["subtitle_en"], english=True))
    story.append(route_box(url_en, "en"))
    story.append(Spacer(1, 4 * mm))
    story.extend(
        [
            p("How to use", "H2"),
            steps(
                [
                    "Open the dedicated URL in this PDF.",
                    "Enter the exact Coconala username used for purchase and your birth details.",
                    "Save the generated files and use them with your preferred AI.",
                ],
                style="BodyEN",
            ),
            Spacer(1, 2 * mm),
            *section("What's included", product["included_en"], style="BodyEN"),
            info_box([p(product["description_en"], "BodyEN")]),
            Spacer(1, 3 * mm),
            p(
                f"The listing title must include <b>{product['code']}</b>. "
                "Purchase verification may take a few minutes. If verification fails, wait five minutes and try again.",
                "Small",
            ),
            Spacer(1, 2 * mm),
            p(
                "The chart page is available for 90 days. Download the ZIP archive for permanent local storage. "
                "For support, use the inquiry option on the Coconala product page.",
                "Small",
            ),
        ]
    )
    return story


def addon_pages() -> list[Flowable]:
    url_ja = "https://chart.nanami-astro.com/addon/new?lang=ja&provider=coconala"
    url_en = "https://chart.nanami-astro.com/addon/new?lang=en&provider=coconala"
    story: list[Flowable] = []
    story.extend(page_header("アドオンデータ", "基本版をお持ちの方向けの追加データです。"))
    story.append(route_box(url_ja, "ja"))
    story.append(Spacer(1, 4 * mm))
    story.extend(
        [
            p("ご利用方法", "H2"),
            steps(
                [
                    "専用URLを開き、購入したアドオン種別を選ぶ",
                    "購入時のココナラユーザー名を入力する",
                    "基本版YAMLまたは有効な前回鑑定URLを指定して生成する",
                ]
            ),
            *section(
                "購入商品と商品コード",
                [
                    "[NP-WA] 小惑星データ: キロン、ジュノー、ベスタ、パラス、セレス",
                    "[NP-WT] 31日トランジット: 日別の天体位置、アスペクト、ハウス",
                    "[NP-SF] 四柱推命・大運: 10年単位の大運と関連情報",
                ],
            ),
            info_box(
                [
                    p(
                        "フォームでは、ココナラで購入した商品と同じアドオン種別を選択してください。"
                        "異なる商品を選ぶと購入確認に失敗します。"
                    )
                ]
            ),
        ]
    )
    story.append(PageBreak())
    story.extend(page_header("ご利用にあたって", "アドオン購入者向けの確認事項です。"))
    story.extend(common_notice_jp())
    story.extend(faq_jp(base_required=True))
    story.append(PageBreak())
    story.extend(page_header("Add-on Data", "Additional data for owners of a compatible Basic product.", english=True))
    story.append(route_box(url_en, "en"))
    story.append(Spacer(1, 4 * mm))
    story.extend(
        [
            p("How to use", "H2"),
            steps(
                [
                    "Open the dedicated URL and select the add-on you purchased.",
                    "Enter the exact Coconala username used for purchase.",
                    "Provide the compatible base YAML or an active previous chart URL.",
                ],
                style="BodyEN",
            ),
            *section(
                "Product codes",
                [
                    "[NP-WA] Asteroid Data",
                    "[NP-WT] 31-day Transit Data",
                    "[NP-SF] Da-Yun / 10-Year Luck Cycle",
                ],
                style="BodyEN",
            ),
            info_box(
                [
                    p(
                        "Choose the same add-on type that you purchased on Coconala. "
                        "The username and product code must both match the purchase notification.",
                        "BodyEN",
                    )
                ]
            ),
            Spacer(1, 3 * mm),
            p(
                "Purchase verification may take a few minutes. For support, use the inquiry option on the Coconala product page.",
                "Small",
            ),
        ]
    )
    return story


PRODUCTS = [
    {
        "filename": "nanami_western_basic_coconala.pdf",
        "code": "[NP-WB]",
        "title_ja": "ホロスコープ基本版",
        "subtitle_ja": "星の位置・角度・ハウスを事前計算したAI鑑定用データです。",
        "title_en": "Western Astrology Basic",
        "subtitle_en": "Pre-calculated planetary positions, angles, and houses, ready for AI.",
        "url_ja": "https://chart.nanami-astro.com/redeem/western-basic?lang=ja&provider=coconala",
        "url_en": "https://chart.nanami-astro.com/redeem/western-basic?lang=en&provider=coconala",
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
        "description_ja": "生年月日・出生時刻・出生地から西洋占星術データをYAML形式で生成します。天体位置は計算済みのため、AIは解釈に集中できます。",
        "description_en": "Generate pre-calculated Western astrology data in YAML format from your birth details. The AI can focus on interpretation without recalculating planetary positions.",
    },
    {
        "filename": "nanami_western_full_coconala.pdf",
        "code": "[NP-WF]",
        "title_ja": "ホロスコープFULL版",
        "subtitle_ja": "小惑星と31日分のトランジットを含むフルセットです。",
        "title_en": "Western Astrology FULL",
        "subtitle_en": "Complete set with asteroids and 31 days of transit data.",
        "url_ja": "https://chart.nanami-astro.com/redeem/western-full?lang=ja&provider=coconala",
        "url_en": "https://chart.nanami-astro.com/redeem/western-full?lang=en&provider=coconala",
        "included_ja": [
            "基本版の全データ",
            "小惑星: キロン、ジュノー、ベスタ、パラス、セレス",
            "31日分のトランジット",
            "AI鑑定用プロンプト",
        ],
        "included_en": [
            "All data from the Basic version",
            "Chiron, Juno, Vesta, Pallas, and Ceres",
            "31 days of transit data",
            "Prompt for AI interpretation",
        ],
        "description_ja": "出生図に小惑星と日別トランジットを加え、現在の流れ・転機・注意日をAIで読み解けるデータセットです。",
        "description_en": "A complete dataset combining the natal chart, asteroids, and daily transits for exploring current themes, turning points, and important dates.",
        "transit": True,
    },
    {
        "filename": "nanami_shichu_coconala.pdf",
        "code": "[NP-SC]",
        "title_ja": "四柱推命",
        "subtitle_ja": "命式・十神・大運を事前計算したAI鑑定用データです。",
        "title_en": "Four Pillars of Destiny",
        "subtitle_en": "Pre-calculated pillars, Ten Gods, and Da-Yun cycles, ready for AI.",
        "url_ja": "https://chart.nanami-astro.com/redeem/shichu?lang=ja&provider=coconala",
        "url_en": "https://chart.nanami-astro.com/redeem/shichu?lang=en&provider=coconala",
        "included_ja": [
            "四柱: 年柱・月柱・日柱・時柱",
            "十神・蔵干",
            "大運・年運",
            "空亡・神殺・AI鑑定用プロンプト",
        ],
        "included_en": [
            "Year, Month, Day, and Hour Pillars",
            "Ten Gods and Hidden Stems",
            "Da-Yun and annual fortune",
            "Empty Branches, Shen-Sha, and AI prompt",
        ],
        "description_ja": "生年月日・出生時刻から四柱推命の命式をYAML形式で生成します。1時切替と23時切替の両方に対応しています。",
        "description_en": "Generate a pre-calculated Four Pillars chart in YAML format. Both the 1:00 AM and 23:00 day-boundary rules are supported.",
    },
]


def build_pdf(path: Path, story: list[Flowable], title: str) -> None:
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="nanami-products",
        subject="Coconala buyer guide",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for product in PRODUCTS:
        build_pdf(OUTPUT_DIR / product["filename"], guide_pages(product), product["title_en"])
    build_pdf(
        OUTPUT_DIR / "nanami_addon_coconala.pdf",
        addon_pages(),
        "Add-on Data - Coconala",
    )


if __name__ == "__main__":
    main()
