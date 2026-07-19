from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


NAVY = HexColor("#17213D")
COPPER = HexColor("#BD6F3A")
PAPER = HexColor("#FAF7F1")
PANEL = HexColor("#F3EEE6")
MUTED = HexColor("#6F7482")
LINE = HexColor("#E4D9CC")


def _register_fonts() -> None:
    for name in ("HeiseiKakuGo-W5", "HeiseiMin-W3"):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(name))


def _draw_qr(pdf: canvas.Canvas, value: str, x: float, y: float, size: float) -> None:
    widget = qr.QrCodeWidget(value)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, x, y)


def _page_base(pdf: canvas.Canvas, title: str, page_number: int) -> tuple[float, float]:
    width, height = A4
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(COPPER)
    pdf.rect(0, height - 4, width, 4, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, height - 36, "nanami-products")
    pdf.setFillColor(NAVY)
    pdf.setFont("HeiseiKakuGo-W5", 20)
    pdf.drawString(40, height - 70, title)
    pdf.setStrokeColor(LINE)
    pdf.line(40, 52, width - 40, 52)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 34, "support@nanami-astro.com")
    pdf.drawCentredString(width / 2, 34, str(page_number))
    pdf.drawRightString(width - 40, 34, "nanami-astro.com")
    pdf.setFillColor(COPPER)
    pdf.rect(0, 0, width, 3, fill=1, stroke=0)
    return width, height


def _section(
    pdf: canvas.Canvas,
    *,
    title: str,
    body: str,
    y: float,
    height: float,
    bullets: list[str] | None = None,
) -> None:
    width, _ = A4
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(40, y - height, width - 80, height, 8, fill=1, stroke=1)
    pdf.setFillColor(COPPER)
    pdf.setFont("HeiseiKakuGo-W5", 12)
    pdf.drawString(58, y - 26, title)
    body_style = ParagraphStyle(
        "section-body", fontName="HeiseiKakuGo-W5", fontSize=9,
        leading=14, textColor=NAVY,
    )
    paragraph = Paragraph(escape(body), body_style)
    _, body_h = paragraph.wrap(width - 116, height - 52)
    paragraph.drawOn(pdf, 58, y - 45 - body_h)
    bullet_y = y - 58 - body_h
    for item in bullets or []:
        pdf.setFillColor(COPPER)
        pdf.circle(63, bullet_y + 4, 2.2, fill=1, stroke=0)
        bullet = Paragraph(escape(item), body_style)
        _, bullet_h = bullet.wrap(width - 137, 36)
        bullet.drawOn(pdf, 74, bullet_y - 3)
        bullet_y -= max(20, bullet_h + 6)


def build_personal_edition_code_pdf(
    *, code: str, activation_url: str, product_type: str, lang: str = "ja"
) -> bytes:
    """購入者へ納品する、選択・コピー可能な引換コードPDFを生成する。"""
    _register_fonts()
    activation_url = activation_url.split("#", 1)[0] + "#code=" + code
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    width, height = A4
    pdf.setTitle("Personal Edition Access Code")
    pdf.setAuthor("nanami-products")
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(COPPER)
    pdf.rect(0, height - 4, width, 4, fill=1, stroke=0)

    is_en = lang == "en"
    bundle = product_type == "acg_bundle"
    title = "ACG Premium Bundle" if bundle else "Personal Edition FULL"
    subtitle = (
        "Your personalized local astrology experience"
        if is_en
        else "あなた専用のローカル占星術体験を作成します"
    )

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, height - 36, "nanami-products")
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 23)
    pdf.drawString(40, height - 72, title)
    pdf.setFont("HeiseiKakuGo-W5", 10)
    pdf.setFillColor(MUTED)
    pdf.drawString(40, height - 94, subtitle)

    box_y = height - 295
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(38, box_y, width - 76, 155, 8, fill=1, stroke=1)
    pdf.setFillColor(MUTED)
    pdf.setFont("HeiseiKakuGo-W5", 10)
    pdf.drawString(55, box_y + 126, "Access code" if is_en else "引換コード")
    pdf.setFillColor(COPPER)
    pdf.setFont("Courier-Bold", 17)
    pdf.drawString(55, box_y + 96, code)
    pdf.linkURL(activation_url, (55, box_y + 28, width - 170, box_y + 78), relative=0)
    pdf.setFillColor(MUTED)
    pdf.setFont("HeiseiKakuGo-W5", 8.5)
    pdf.drawString(55, box_y + 66, "Activation page" if is_en else "発行ページ")
    pdf.setFillColor(COPPER)
    url_style = ParagraphStyle(
        "url", fontName="Helvetica", fontSize=8.5, leading=11, textColor=COPPER
    )
    url_paragraph = Paragraph(escape(activation_url), url_style)
    url_paragraph.wrapOn(pdf, width - 250, 40)
    url_paragraph.drawOn(pdf, 55, box_y + 36)
    _draw_qr(pdf, activation_url, width - 145, box_y + 32, 88)
    pdf.setFillColor(MUTED)
    pdf.setFont("HeiseiKakuGo-W5", 7.5)
    pdf.drawCentredString(width - 101, box_y + 19, "Scan to open" if is_en else "カメラで読み取る")

    section_y = box_y - 45
    pdf.setFillColor(NAVY)
    pdf.setFont("HeiseiKakuGo-W5", 13)
    pdf.drawString(40, section_y, "How to use" if is_en else "ご利用方法")
    pdf.setStrokeColor(COPPER)
    pdf.line(40, section_y - 8, 105, section_y - 8)
    steps = (
        [
            "Open the activation page using the URL or QR code.",
            "Enter the access code and your confirmed birth details.",
            "Download the ZIP, extract it, and run start.bat or start.command.",
        ]
        if is_en
        else [
            "URLまたはQRコードから発行ページを開く",
            "引換コードと、確認済みの出生情報を入力する",
            "ZIPを保存・展開し、start.bat または start.command を実行する",
        ]
    )
    y = section_y - 42
    body_style = ParagraphStyle(
        "body", fontName="HeiseiKakuGo-W5", fontSize=10, leading=15, textColor=NAVY
    )
    for number, step in enumerate(steps, 1):
        pdf.setFillColor(COPPER)
        pdf.circle(53, y + 4, 10, fill=1, stroke=0)
        pdf.setFillColor(PAPER)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(53, y + 1, str(number))
        step_paragraph = Paragraph(escape(step), body_style)
        step_paragraph.wrapOn(pdf, width - 105, 40)
        step_paragraph.drawOn(pdf, 75, y - 4)
        y -= 43

    warning = (
        "An accurate, confirmed birth time is required. Estimated or unknown times cannot be used for the ACG Bundle."
        if is_en and bundle
        else "ACG Bundleは、正確な出生時刻が確認できる方のみご利用いただけます。推定・不明時刻では発行できません。"
        if bundle
        else "引換コードはZIPの作成成功後に使用済みになります。発行が完了するまで、このPDFを保管してください。"
    )
    pdf.setFillColor(PANEL)
    pdf.roundRect(40, 104, width - 80, 58, 7, fill=1, stroke=0)
    note_style = ParagraphStyle(
        "note", fontName="HeiseiKakuGo-W5", fontSize=8.5, leading=13,
        textColor=MUTED, alignment=TA_CENTER,
    )
    note = Paragraph(escape(warning), note_style)
    _, note_h = note.wrap(width - 120, 45)
    note.drawOn(pdf, 60, 124 - note_h / 2)

    pdf.setStrokeColor(LINE)
    pdf.line(40, 70, width - 40, 70)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 50, "support@nanami-astro.com")
    pdf.drawRightString(width - 40, 50, "nanami-astro.com")
    pdf.setFillColor(COPPER)
    pdf.rect(0, 0, width, 3, fill=1, stroke=0)
    pdf.showPage()

    # Page 2: included products
    _page_base(pdf, "What is included" if is_en else "含まれる内容", 2)
    if bundle:
        included_intro = (
            "This bundle combines calculated astrology data, a personal astrocartography map, and the Birth Chart Museum beta experience."
            if is_en else
            "計算済み占術データ、個人アストロカートグラフィ、Birth Chart Museumベータ版を1つにまとめたセットです。"
        )
    else:
        included_intro = (
            "Your calculated astrology data and the Birth Chart Museum beta experience are packaged together."
            if is_en else
            "計算済み占術データとBirth Chart Museumベータ版をまとめたPersonal Editionです。"
        )
    _section(pdf, title="Personal Edition FULL", body=included_intro, y=height - 105, height=142,
             bullets=(
                 ["Full natal chart data", "Asteroids and transit data", "AI-ready YAML and consultation prompt", "Personal local ZIP package"]
                 if is_en else
                 ["出生図FULLデータ", "小惑星・トランジットデータ", "AI用YAML・相談プロンプト", "あなた専用のローカルZIP"]
             ))
    _section(pdf, title="Birth Chart Museum (Beta)",
             body=(
                 "Explore your calculated birth chart as a visual museum. The abstract and architectural editions load your installed YAML automatically."
                 if is_en else
                 "計算済みの出生図を、視覚的なミュージアムとして巡るベータ機能です。抽象版・建築版ともに、組み込み済みYAMLを自動で読み込みます。"
             ), y=height - 270, height=142,
             bullets=(
                 ["No YAML paste required", "Runs from your downloaded ZIP", "Japanese and English display"]
                 if is_en else
                 ["YAML貼り付け不要", "ダウンロードしたZIPから起動", "日本語・英語表示に対応"]
             ))
    if bundle:
        _section(pdf, title="Astrocartography (ACG)",
                 body=(
                     "Your planetary angular lines are calculated in advance from your confirmed birth time and stored in the ZIP. Open the ACG button in the museum to view them."
                     if is_en else
                     "確認済み出生時刻から個人の天空線を事前計算し、ZIP内へ保存します。ミュージアムのACGボタンから、世界地図上の線を確認できます。"
                 ), y=height - 435, height=160,
                 bullets=(
                     ["Precalculated personal lines", "Career and relationship presets", "Exact birth time required"]
                     if is_en else
                     ["計算済み個人線を自動表示", "仕事・人の縁などのプリセット", "正確な出生時刻が必須"]
                 ))
    pdf.showPage()

    # Page 3: usage guide
    _page_base(pdf, "Using your Personal Edition" if is_en else "Personal Editionの使い方", 3)
    _section(pdf, title="1. Start the local app" if is_en else "1. ローカルアプリを起動",
             body=(
                 "Extract the downloaded ZIP. Run start.bat on Windows or start.command on macOS. Your browser opens a local-only address."
                 if is_en else
                 "ダウンロードしたZIPを展開します。Windowsはstart.bat、Macはstart.commandを実行すると、ローカル専用URLがブラウザで開きます。"
             ), y=height - 105, height=118)
    _section(pdf, title="2. Open the museum" if is_en else "2. ミュージアムを見る",
             body=(
                 "Choose the abstract or architectural museum. Your birth-chart YAML is already installed and loads automatically."
                 if is_en else
                 "抽象版または建築版を選びます。出生図YAMLはあらかじめ組み込まれているため、コピーや貼り付けは必要ありません。"
             ), y=height - 245, height=118)
    if bundle:
        _section(pdf, title="3. Explore ACG" if is_en else "3. ACGを確認",
                 body=(
                     "Select the ACG button, choose a theme, and tap planetary lines on the world map. Map background tiles require an internet connection; your birth YAML is not sent to the map provider."
                     if is_en else
                     "ACGボタンを開き、テーマを選んで世界地図の天体線をタップします。背景地図の表示には通信が必要ですが、出生YAMLを地図サービスへ送信することはありません。"
                 ), y=height - 385, height=132)
    _section(pdf, title="Ask an AI" if is_en else "AIへ相談する",
             body=(
                 "Use the included YAML and prompt with ChatGPT, Claude, or Gemini. Ask the AI to interpret the calculated values without recalculating them."
                 if is_en else
                 "同梱YAMLとプロンプトは、ChatGPT・Claude・Geminiなどで利用できます。AIには再計算させず、記録された計算結果を根拠に解釈させてください。"
             ), y=height - 545, height=135,
             bullets=(
                 ["What themes are strongest in my natal chart?", "Which ACG lines support career or relationships?", "Explain the next month using my transit data."]
                 if is_en else
                 ["出生図で特に強いテーマを教えてください", "仕事や人間関係に向くACG線を説明してください", "トランジットから今後1か月を解釈してください"]
             ))
    pdf.showPage()

    # Page 4: FAQ and important notes
    _page_base(pdf, "FAQ and important notes" if is_en else "よくある質問・ご利用上の注意", 4)
    faq = (
        [
            ("Can I use the code more than once?", "The code is marked as used after the ZIP is created successfully. Keep the downloaded ZIP in a safe place."),
            ("Why does the map need internet access?", "Planetary-line data stays local. Only background map tiles are downloaded from the map provider."),
            ("Can I use an estimated birth time?", "The ACG Bundle requires an accurate confirmed time because the lines can move substantially across the world."),
            ("Is this medical or financial advice?", "No. This product is for personal reflection and entertainment and does not replace professional advice."),
        ]
        if is_en else
        [
            ("引換コードは何度も使えますか？", "ZIPの作成成功後に使用済みになります。ダウンロードしたZIPは安全な場所へ保管してください。"),
            ("地図表示に通信が必要なのはなぜですか？", "天体線と出生情報はローカルに保存されます。通信するのは背景地図タイルの取得だけです。"),
            ("推定出生時刻でもACGを利用できますか？", "利用できません。出生時刻の違いで線が世界規模に移動するため、確認済みの正確な時刻が必要です。"),
            ("診断や投資判断に利用できますか？", "本商品は自己理解とエンターテインメントを目的とし、医療・法律・投資などの専門判断に代わるものではありません。"),
        ]
    )
    y = height - 110
    for question, answer in faq:
        _section(pdf, title=question, body=answer, y=y, height=112)
        y -= 132
    pdf.setFillColor(MUTED)
    pdf.setFont("HeiseiKakuGo-W5", 8.5)
    final_note = (
        "Specifications and supported features may change during the beta period. Please keep your ZIP and contact support if you need help."
        if is_en else
        "ベータ期間中は仕様や対応機能が変更される場合があります。ZIPを保管し、お困りの場合はサポートへお問い合わせください。"
    )
    pdf.drawCentredString(width / 2, 92, final_note)
    pdf.showPage()
    pdf.save()
    return output.getvalue()
