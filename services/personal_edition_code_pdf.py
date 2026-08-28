from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


NAVY = HexColor("#17213D")
COPPER = HexColor("#BD6F3A")
PAPER = HexColor("#FAF7F1")
PANEL = HexColor("#F3EEE6")
MUTED = HexColor("#6F7482")
LINE = HexColor("#E4D9CC")
ROOT = Path(__file__).resolve().parent.parent
JAPANESE_FONT_NAME = "NotoSansJP"
JAPANESE_FONT_PATH = ROOT / "static" / "fonts" / "NotoSansJP-VF.ttf"


def _register_fonts() -> None:
    if JAPANESE_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    if not JAPANESE_FONT_PATH.is_file():
        raise RuntimeError(f"Japanese PDF font was not found: {JAPANESE_FONT_PATH}")
    pdfmetrics.registerFont(TTFont(JAPANESE_FONT_NAME, str(JAPANESE_FONT_PATH)))


def _draw_qr(pdf: canvas.Canvas, value: str, x: float, y: float, size: float) -> None:
    widget = qr.QrCodeWidget(value)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, x, y)


def _page_base(
    pdf: canvas.Canvas, title: str, page_number: int, *, font_name: str
) -> tuple[float, float]:
    width, height = A4
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(COPPER)
    pdf.rect(0, height - 4, width, 4, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, height - 36, "nanami-products")
    pdf.setFillColor(NAVY)
    pdf.setFont(font_name if font_name != "Helvetica" else "Helvetica-Bold", 20)
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
    font_name: str,
) -> None:
    width, _ = A4
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(40, y - height, width - 80, height, 8, fill=1, stroke=1)
    pdf.setFillColor(COPPER)
    pdf.setFont(font_name if font_name != "Helvetica" else "Helvetica-Bold", 12)
    pdf.drawString(58, y - 26, title)
    body_style = ParagraphStyle(
        "section-body", fontName=font_name, fontSize=9,
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
    activation_url = activation_url.split("#", 1)[0]
    activation_url += ("&" if "?" in activation_url else "?") + "code=" + code
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    width, height = A4
    pdf.setTitle("Personal Edition Access Code")
    pdf.setAuthor("nanami-products")
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(COPPER)
    pdf.rect(0, height - 4, width, 4, fill=1, stroke=0)

    bundle = product_type == "acg_bundle"
    content_font = JAPANESE_FONT_NAME if lang == "ja" else "Helvetica"
    copy = {
        "ja": {"subtitle": "あなた専用のローカル占星術体験を作成します", "code": "引換コード", "page": "発行ページ", "scan": "カメラで読み取る", "how": "ご利用方法", "steps": ["URLまたはQRコードから発行ページを開く", "引換コードと、確認済みの出生情報を入力する", "ZIPを保存・展開し、start.bat または start.command を実行する"], "bundle_warning": "ACG Bundleは、正確な出生時刻が確認できる方のみご利用いただけます。推定・不明時刻では発行できません。", "warning": "引換コードはZIPの作成成功後に使用済みになります。発行が完了するまで、このPDFを保管してください。"},
        "en": {"subtitle": "Your personalized local astrology experience", "code": "Access code", "page": "Activation page", "scan": "Scan to open", "how": "How to use", "steps": ["Open the activation page using the URL or QR code.", "Enter the access code and your confirmed birth details.", "Download and extract the ZIP, then open the included start file."], "bundle_warning": "An accurate, confirmed birth time is required. Estimated or unknown times cannot be used for the ACG Bundle.", "warning": "The code is marked as used after the ZIP is created successfully. Keep this PDF until activation is complete."},
        "es": {"subtitle": "Tu experiencia astrológica local personalizada", "code": "Código de acceso", "page": "Página de activación", "scan": "Escanea para abrir", "how": "Cómo utilizarlo", "steps": ["Abre la página de activación con la URL o el código QR.", "Introduce el código y tus datos de nacimiento confirmados.", "Descarga y extrae el ZIP y abre el archivo de inicio incluido."], "bundle_warning": "El ACG Bundle requiere una hora de nacimiento exacta y confirmada. No se admiten horas estimadas o desconocidas.", "warning": "El código se marca como usado cuando el ZIP se crea correctamente. Conserva este PDF hasta completar la activación."},
        "de": {"subtitle": "Dein persönliches lokales Astrologie-Erlebnis", "code": "Zugangscode", "page": "Aktivierungsseite", "scan": "Scannen und öffnen", "how": "So funktioniert es", "steps": ["Öffne die Aktivierungsseite über die URL oder den QR-Code.", "Gib den Zugangscode und deine bestätigten Geburtsdaten ein.", "Lade die ZIP-Datei herunter, entpacke sie und öffne die enthaltene Startdatei."], "bundle_warning": "Für das ACG Bundle ist eine genaue, bestätigte Geburtszeit erforderlich. Geschätzte oder unbekannte Zeiten sind nicht zulässig.", "warning": "Der Code wird nach erfolgreicher Erstellung der ZIP-Datei als verwendet markiert. Bewahre dieses PDF bis zum Abschluss auf."},
    }.get(lang, {}) or {}
    if not copy:
        copy = {"subtitle": "Your personalized local astrology experience", "code": "Access code", "page": "Activation page", "scan": "Scan to open", "how": "How to use", "steps": [], "bundle_warning": "An accurate birth time is required.", "warning": "Keep this PDF until activation is complete."}
    def localize(*, ja: str, en: str, es: str, de: str) -> str:
        return {"ja": ja, "en": en, "es": es, "de": de}.get(lang, en)
    title = "ACG Premium Bundle" if bundle else "Personal Edition FULL"
    subtitle = copy["subtitle"] if bundle else localize(
        ja="計算済み占術データと1年Plannerを受け取ります",
        en="Your calculated astrology data and 1-year Planner",
        es="Tus datos astrológicos calculados y Planner de 1 año",
        de="Deine berechneten Astrologiedaten und dein 1-Jahres-Planer",
    )
    if not bundle:
        copy["steps"] = {
            "ja": ["URLまたはQRコードから発行ページを開く", "引換コードと、確認済みの出生情報を入力する", "専用鑑定ページを保存し、データZIPと1年Plannerをダウンロードする"],
            "en": ["Open the activation page using the URL or QR code.", "Enter the access code and your confirmed birth details.", "Save your private chart page, then download the data ZIP and 1-year Planner."],
            "es": ["Abre la página de activación con la URL o el código QR.", "Introduce el código y tus datos de nacimiento confirmados.", "Guarda tu página privada y descarga el ZIP de datos y el Planner de 1 año."],
            "de": ["Öffne die Aktivierungsseite über die URL oder den QR-Code.", "Gib den Zugangscode und deine bestätigten Geburtsdaten ein.", "Speichere deine private Horoskopseite und lade Daten-ZIP und 1-Jahres-Planer herunter."],
        }.get(lang, copy["steps"])

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, height - 36, "nanami-products")
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 23)
    pdf.drawString(40, height - 72, title)
    pdf.setFont(content_font, 10)
    pdf.setFillColor(MUTED)
    pdf.drawString(40, height - 94, subtitle)

    box_y = height - 295
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(38, box_y, width - 76, 155, 8, fill=1, stroke=1)
    pdf.setFillColor(MUTED)
    pdf.setFont(content_font, 10)
    pdf.drawString(55, box_y + 126, copy["code"])
    pdf.setFillColor(COPPER)
    pdf.setFont("Courier-Bold", 17)
    pdf.drawString(55, box_y + 96, code)
    pdf.linkURL(activation_url, (55, box_y + 28, width - 170, box_y + 78), relative=0)
    pdf.setFillColor(MUTED)
    pdf.setFont(content_font, 8.5)
    pdf.drawString(55, box_y + 66, copy["page"])
    pdf.setFillColor(COPPER)
    url_style = ParagraphStyle(
        "url", fontName="Helvetica", fontSize=8.5, leading=11, textColor=COPPER
    )
    url_paragraph = Paragraph(escape(activation_url), url_style)
    url_paragraph.wrapOn(pdf, width - 250, 40)
    url_paragraph.drawOn(pdf, 55, box_y + 36)
    _draw_qr(pdf, activation_url, width - 145, box_y + 32, 88)
    pdf.setFillColor(MUTED)
    pdf.setFont(content_font, 7.5)
    pdf.drawCentredString(width - 101, box_y + 19, copy["scan"])

    section_y = box_y - 45
    pdf.setFillColor(NAVY)
    pdf.setFont(content_font if lang == "ja" else "Helvetica-Bold", 13)
    pdf.drawString(40, section_y, copy["how"])
    pdf.setStrokeColor(COPPER)
    pdf.line(40, section_y - 8, 105, section_y - 8)
    steps = copy["steps"]
    y = section_y - 42
    body_style = ParagraphStyle(
        "body", fontName=content_font, fontSize=10, leading=15, textColor=NAVY
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

    warning = copy["bundle_warning"] if bundle else copy["warning"]
    pdf.setFillColor(PANEL)
    pdf.roundRect(40, 104, width - 80, 58, 7, fill=1, stroke=0)
    note_style = ParagraphStyle(
        "note", fontName=content_font, fontSize=8.5, leading=13,
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
    _page_base(pdf, localize(ja="含まれる内容", en="What is included", es="Contenido incluido", de="Enthaltene Inhalte"), 2, font_name=content_font)
    if bundle:
        _section(pdf, title="ACG Premium Bundle",
                 body=localize(ja="専用鑑定ページ、計算済み占術データ、個人アストロカートグラフィをまとめたセットです。", en="Your private chart page, calculated astrology data, and personal astrocartography app are delivered together.", es="Recibirás tu página privada, los datos astrológicos calculados y tu aplicación personal de astrocartografía.", de="Du erhältst deine private Horoskopseite, berechnete Astrologiedaten und deine persönliche Astrokartografie-App."), y=height - 105, height=142,
                 bullets={"ja": ["出生図FULLデータ", "小惑星・トランジットデータ", "AI用YAML・相談プロンプト", "1年パーソナルPlanner"], "en": ["Full natal chart data", "Asteroids and transit data", "AI-ready YAML and consultation prompt", "1-year personalized Planner"], "es": ["Carta natal completa", "Asteroides y tránsitos", "YAML y consulta para IA", "Planner personal de 1 año"], "de": ["Vollständige Radixdaten", "Asteroiden und Transite", "YAML und Beratungstext für KI", "Persönlicher 1-Jahres-Planer"]}.get(lang), font_name=content_font)
        _section(pdf, title=localize(ja="個人ACGアプリ", en="Personal ACG app", es="Aplicación ACG personal", de="Persönliche ACG-App"),
                 body=localize(ja="確認済み出生時刻から個人の天空線を事前計算し、START-ACG.html内へ保存します。", en="Your planetary angular lines are calculated from your confirmed birth time and stored inside START-ACG.html.", es="Tus líneas angulares se calculan con la hora confirmada y se guardan dentro de START-ACG.html.", de="Deine Achsenlinien werden aus der bestätigten Geburtszeit berechnet und in START-ACG.html gespeichert."), y=height - 270, height=142,
                 bullets={"ja": ["YAML貼り付け不要", "ダウンロード版とオンライン版", "仕事・人の縁などのプリセット"], "en": ["No YAML paste required", "Downloaded and online versions", "Career and relationship presets"], "es": ["No es necesario pegar YAML", "Versión descargada y online", "Temas de profesión y relaciones"], "de": ["Kein Einfügen von YAML nötig", "Download- und Online-Version", "Berufs- und Beziehungsthemen"]}.get(lang), font_name=content_font)
        _section(pdf, title=localize(ja="精度とプライバシー", en="Accuracy and privacy", es="Precisión y privacidad", de="Genauigkeit und Datenschutz"),
                 body=localize(ja="正確な出生時刻が必須です。出生データと計算済みの線はアプリ内に保持され、通信するのは背景地図だけです。", en="An exact birth time is required. Birth data and calculated lines stay inside the app; only background map tiles use the internet.", es="Se requiere una hora exacta. Los datos y las líneas permanecen en la aplicación; solo el mapa de fondo usa internet.", de="Eine genaue Geburtszeit ist erforderlich. Daten und Linien bleiben in der App; nur die Hintergrundkarte nutzt das Internet."), y=height - 435, height=160,
                 bullets={"ja": ["正確な出生時刻が必須", "計算済み個人線", "背景地図のみ通信"], "en": ["Exact birth time required", "Precalculated personal lines", "Only map tiles use the internet"], "es": ["Hora exacta obligatoria", "Líneas personales calculadas", "Solo el mapa de fondo usa internet"], "de": ["Genaue Geburtszeit erforderlich", "Berechnete persönliche Linien", "Nur Kartenkacheln nutzen das Internet"]}.get(lang), font_name=content_font)
    else:
        included_intro = localize(ja="計算済み占術データ、AI相談用ファイル、専用鑑定ページをまとめたPersonal Editionです。", en="Your calculated astrology data, AI consultation files, and private chart page are delivered together.", es="Recibirás tus datos astrológicos calculados, archivos para consulta con IA y tu página privada.", de="Du erhältst berechnete Astrologiedaten, Dateien für die KI-Beratung und deine private Horoskopseite.")
        _section(pdf, title="Personal Edition FULL", body=included_intro, y=height - 105, height=160,
                 bullets={"ja": ["出生図FULLデータ", "小惑星・トランジットデータ", "AI用YAML・相談プロンプト", "専用鑑定ページ"], "en": ["Full natal chart data", "Asteroids and transit data", "AI-ready YAML and consultation prompt", "Private chart page"], "es": ["Carta natal completa", "Asteroides y tránsitos", "YAML y consulta para IA", "Página privada"], "de": ["Vollständige Radixdaten", "Asteroiden und Transite", "YAML und Beratungstext für KI", "Private Horoskopseite"]}.get(lang), font_name=content_font)
        _section(pdf, title=localize(ja="1年パーソナルPlanner", en="1-year personalized Planner", es="Planner personal de 1 año", de="Persönlicher 1-Jahres-Planer"),
                 body=localize(ja="専用鑑定ページから開始月を選び、日別トランジットと月間カレンダーをまとめたPDFを作成・保存できます。", en="Choose a start month on your private chart page, then create and save a PDF with daily transits and monthly calendars.", es="Elige un mes de inicio en tu página privada y crea un PDF con tránsitos diarios y calendarios mensuales.", de="Wähle auf deiner privaten Horoskopseite einen Startmonat und erstelle eine PDF mit täglichen Transiten und Monatskalendern."), y=height - 295, height=160,
                 bullets={"ja": ["12か月分", "開始月を選択", "PDFで保存"], "en": ["12 months", "Choose the start month", "Save as PDF"], "es": ["12 meses", "Elige el mes de inicio", "Guarda como PDF"], "de": ["12 Monate", "Startmonat wählen", "Als PDF speichern"]}.get(lang), font_name=content_font)
    pdf.showPage()

    # Page 3: usage guide
    _page_base(pdf, localize(ja="ACG Bundleの使い方" if bundle else "Personal Editionの使い方", en="Using your ACG Bundle" if bundle else "Using your Personal Edition", es="Cómo usar tu ACG Bundle" if bundle else "Cómo usar tu Edición Personal", de="Dein ACG Bundle verwenden" if bundle else "Deine Personal Edition verwenden"), 3, font_name=content_font)
    if bundle:
        _section(pdf, title=localize(ja="1. 専用鑑定ページを保存", en="1. Save your private chart page", es="1. Guarda tu página privada", de="1. Private Horoskopseite speichern"),
                 body=localize(ja="発行後の専用URLを保存し、占術データZIPとACGアプリをダウンロードします。", en="Save the private URL issued after activation, then download your data archive and ACG app.", es="Guarda la URL privada creada tras la activación y descarga tus datos y la aplicación ACG.", de="Speichere die private URL nach der Aktivierung und lade Datenarchiv und ACG-App herunter."), y=height - 105, height=118, font_name=content_font)
        _section(pdf, title=localize(ja="2. ACGアプリを開く", en="2. Open the ACG app", es="2. Abre la aplicación ACG", de="2. ACG-App öffnen"),
                 body=localize(ja="専用ページからオンライン版を開くか、ZIPを展開してSTART-ACG.htmlを開きます。", en="Open the online app from your private page, or extract the ZIP and open START-ACG.html.", es="Abre la versión online desde tu página privada o extrae el ZIP y abre START-ACG.html.", de="Öffne die Online-App über deine private Seite oder entpacke die ZIP und öffne START-ACG.html."), y=height - 245, height=118, font_name=content_font)
        _section(pdf, title=localize(ja="3. ACGを確認", en="3. Explore ACG", es="3. Explora ACG", de="3. ACG erkunden"),
                 body=localize(ja="テーマを選び、世界地図の天体線を確認します。背景地図だけが通信を使い、出生YAMLは送信されません。", en="Choose a theme and explore your lines. Only map tiles use the internet; your birth YAML is not sent.", es="Elige un tema y explora tus líneas. Solo el mapa de fondo usa internet; tu YAML no se envía.", de="Wähle ein Thema und erkunde deine Linien. Nur die Hintergrundkarte nutzt das Internet; deine YAML wird nicht gesendet."), y=height - 385, height=132, font_name=content_font)
    else:
        _section(pdf, title=localize(ja="1. 専用鑑定ページを保存", en="1. Save your private chart page", es="1. Guarda tu página privada", de="1. Private Horoskopseite speichern"),
                 body=localize(ja="発行後に表示される専用URLを保存します。このページから占術データとPlannerへアクセスできます。", en="Save the private URL shown after activation. It gives you access to your astrology data and Planner.", es="Guarda la URL privada mostrada tras la activación. Desde ella accederás a tus datos y al Planner.", de="Speichere die private URL nach der Aktivierung. Dort findest du deine Astrologiedaten und den Planer."), y=height - 105, height=118, font_name=content_font)
        _section(pdf, title=localize(ja="2. データZIPとPlannerを保存", en="2. Save the data ZIP and Planner", es="2. Guarda el ZIP de datos y el Planner", de="2. Daten-ZIP und Planer speichern"),
                 body=localize(ja="計算済みYAMLとAI相談文を含むZIPを保存し、開始月を選んで1年Planner PDFを作成します。", en="Save the ZIP containing your calculated YAML and AI prompt, then choose a start month to create the 1-year Planner PDF.", es="Guarda el ZIP con el YAML calculado y el prompt para IA; después elige el mes de inicio para crear el Planner de 1 año.", de="Speichere die ZIP mit berechneter YAML und KI-Anleitung. Wähle dann den Startmonat für die 1-Jahres-Planer-PDF."), y=height - 245, height=118, font_name=content_font)
    _section(pdf, title=localize(ja="AIへ相談する", en="Ask an AI", es="Consulta a una IA", de="KI befragen"),
             body=localize(ja="同梱YAMLとプロンプトをAIで利用し、再計算せず記録済みデータを解釈させてください。", en="Use the included YAML and prompt with an AI. Ask it to interpret the calculated values without recalculating.", es="Usa el YAML y el prompt con una IA. Pídele que interprete los valores sin recalcularlos.", de="Nutze YAML und Prompt mit einer KI. Bitte sie, die berechneten Werte ohne Neuberechnung zu deuten."), y=height - 545, height=135,
             bullets=({"ja": ["出生図で強いテーマ", "仕事や人間関係に向くACG線", "トランジットから今後1か月"], "en": ["Strongest natal themes", "ACG lines for career or relationships", "The next month from transits"], "es": ["Temas natales más fuertes", "Líneas ACG para profesión o relaciones", "El próximo mes según los tránsitos"], "de": ["Stärkste Radixthemen", "ACG-Linien für Beruf oder Beziehungen", "Der nächste Monat nach Transiten"]} if bundle else {"ja": ["出生図で強いテーマ", "仕事や人間関係", "トランジットから今後1か月"], "en": ["Strongest natal themes", "Career and relationships", "The next month from transits"], "es": ["Temas natales más fuertes", "Profesión y relaciones", "El próximo mes según los tránsitos"], "de": ["Stärkste Radixthemen", "Beruf und Beziehungen", "Der nächste Monat nach Transiten"]}).get(lang), font_name=content_font)
    pdf.showPage()

    # Page 4: FAQ and important notes
    _page_base(pdf, localize(ja="よくある質問・ご利用上の注意", en="FAQ and important notes", es="Preguntas frecuentes y avisos", de="FAQ und wichtige Hinweise"), 4, font_name=content_font)
    bundle_faq = {
        "en": [
            ("Can I use the code more than once?", "The code is marked as used after the ZIP is created successfully. Keep the downloaded ZIP in a safe place."),
            ("Why does the map need internet access?", "Planetary-line data stays local. Only background map tiles are downloaded from the map provider."),
            ("Can I use an estimated birth time?", "The ACG Bundle requires an accurate confirmed time because the lines can move substantially across the world."),
            ("Is this medical or financial advice?", "No. This product is for personal reflection and entertainment and does not replace professional advice."),
        ],
        "ja": [
            ("引換コードは何度も使えますか？", "ZIPの作成成功後に使用済みになります。ダウンロードしたZIPは安全な場所へ保管してください。"),
            ("地図表示に通信が必要なのはなぜですか？", "天体線と出生情報はローカルに保存されます。通信するのは背景地図タイルの取得だけです。"),
            ("推定出生時刻でもACGを利用できますか？", "利用できません。出生時刻の違いで線が世界規模に移動するため、確認済みの正確な時刻が必要です。"),
            ("診断や投資判断に利用できますか？", "本商品は自己理解とエンターテインメントを目的とし、医療・法律・投資などの専門判断に代わるものではありません。"),
        ],
        "es": [("¿Puedo usar el código varias veces?", "Se marca como usado al crear el ZIP. Guarda el ZIP descargado."), ("¿Por qué necesita internet el mapa?", "Los datos personales permanecen locales; solo se descargan los mosaicos del mapa."), ("¿Puedo usar una hora estimada?", "El ACG Bundle requiere una hora exacta confirmada."), ("¿Es asesoramiento médico o financiero?", "No. Es un producto de reflexión personal y entretenimiento.")],
        "de": [("Kann ich den Code mehrfach verwenden?", "Nach erfolgreicher ZIP-Erstellung gilt er als verwendet. Bewahre die ZIP sicher auf."), ("Warum benötigt die Karte Internet?", "Persönliche Daten bleiben lokal; nur Kartenkacheln werden geladen."), ("Kann ich eine geschätzte Geburtszeit verwenden?", "Das ACG Bundle benötigt eine genaue bestätigte Zeit."), ("Ist dies medizinische oder finanzielle Beratung?", "Nein. Das Produkt dient persönlicher Reflexion und Unterhaltung.")],
    }.get(lang, [])
    full_faq = {
        "en": [("Can I use the code more than once?", "The code is marked as used after the ZIP is created successfully. Keep the ZIP and private URL in a safe place."), ("Where do I create the Planner?", "Open your private chart page, choose the start month, and save the generated 1-year Planner PDF."), ("Can AI recalculate my chart?", "Use the included prompt and YAML and ask the AI to interpret the stored values without recalculating them."), ("Is this medical or financial advice?", "No. This product is for personal reflection and entertainment and does not replace professional advice.")],
        "ja": [("引換コードは何度も使えますか？", "ZIPの作成成功後に使用済みになります。ZIPと専用URLは安全な場所へ保管してください。"), ("Plannerはどこで作成しますか？", "専用鑑定ページを開き、開始月を選んで1年Planner PDFを作成・保存します。"), ("AIに出生図を再計算させますか？", "同梱のプロンプトとYAMLを使い、保存済みの値を再計算せず解釈するよう依頼してください。"), ("診断や投資判断に利用できますか？", "本商品は自己理解とエンターテインメントを目的とし、医療・法律・投資などの専門判断に代わるものではありません。")],
        "es": [("¿Puedo usar el código varias veces?", "Se marca como usado al crear el ZIP. Guarda el ZIP y la URL privada en un lugar seguro."), ("¿Dónde creo el Planner?", "Abre tu página privada, elige el mes de inicio y guarda el Planner de 1 año en PDF."), ("¿Debe la IA recalcular mi carta?", "Usa el prompt y el YAML incluidos y pide a la IA que interprete los valores guardados sin recalcularlos."), ("¿Es asesoramiento médico o financiero?", "No. Es un producto de reflexión personal y entretenimiento y no sustituye el asesoramiento profesional.")],
        "de": [("Kann ich den Code mehrfach verwenden?", "Nach erfolgreicher ZIP-Erstellung gilt er als verwendet. Bewahre ZIP und private URL sicher auf."), ("Wo erstelle ich den Planer?", "Öffne deine private Horoskopseite, wähle den Startmonat und speichere die 1-Jahres-Planer-PDF."), ("Soll die KI mein Horoskop neu berechnen?", "Nutze Anleitung und YAML und bitte die KI, die gespeicherten Werte ohne Neuberechnung zu deuten."), ("Ist dies medizinische oder finanzielle Beratung?", "Nein. Das Produkt dient persönlicher Reflexion und Unterhaltung und ersetzt keine professionelle Beratung.")],
    }.get(lang, [])
    faq = bundle_faq if bundle else full_faq
    y = height - 110
    for question, answer in faq:
        _section(pdf, title=question, body=answer, y=y, height=112, font_name=content_font)
        y -= 132
    pdf.setFillColor(MUTED)
    pdf.setFont(content_font, 8.5)
    final_note = localize(ja="ZIPと専用URLを保管し、お困りの場合はサポートへお問い合わせください。", en="Keep your ZIP and private URL, and contact support if needed.", es="Guarda el ZIP y la URL privada; contacta con soporte si lo necesitas.", de="Bewahre ZIP und private URL auf und kontaktiere bei Bedarf den Support.")
    pdf.drawCentredString(width / 2, 92, final_note)
    pdf.showPage()
    pdf.save()
    return output.getvalue()
