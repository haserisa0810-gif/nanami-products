"""Build the four language-specific Etsy access PDFs for Western FULL.

These are the small files attached to Etsy digital listings.  They direct the
buyer to the order-number redemption form; they are not the generated reading
or the 12-month planner itself.

    python scripts/build_etsy_full_access_guides.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from shutil import copyfile

from reportlab.platypus import PageBreak, Spacer

try:
    from scripts.build_marketplace_product_guides import (
        ROOT,
        build_pdf,
        info_box,
        p,
        page_header,
        route_box,
        section,
        steps,
    )
except ModuleNotFoundError:  # direct execution: python scripts/<file>.py
    from build_marketplace_product_guides import (
        ROOT,
        build_pdf,
        info_box,
        p,
        page_header,
        route_box,
        section,
        steps,
    )


OUTPUT_DIR = ROOT / "output" / "pdf" / "etsy-western-full"
DISTRIBUTION_DIR = ROOT / "output" / "etsy" / "western-full"
BASE_URL = "https://chart.nanami-astro.com"

LOCALES: dict[str, dict[str, object]] = {
    "ja": {
        "title": "西洋占星術 FULL版",
        "subtitle": "出生図・小惑星・31日分のトランジット・12か月プランナーを含む完全版です。",
        "form_heading": "購入者専用入力フォーム",
        "form_caption": "QRコードを読み取るか、URLをタップして開いてください。",
        "how": "ご利用方法",
        "steps": [
            "このPDFの専用URLを開きます。",
            "Etsyの注文番号と出生情報（生年月日・出生時刻・出生地）を入力します。",
            "発行された鑑定ページのURLとファイルを保存し、お好みのAIで利用します。",
        ],
        "included_heading": "含まれるもの",
        "included": [
            "出生図の主要天体・ハウス・感受点・アスペクト",
            "小惑星：キロン、ジュノー、ベスタ、パラス、セレス",
            "31日分のトランジットデータ",
            "あなた専用の12か月トランジットプランナー（PDF）",
        ],
        "description": "鑑定ページからYAMLデータ、ホロスコープ画像、保存用ZIPをダウンロードできます。アストロカートグラフィー（ACG）は別商品です。",
        "planner": "プランナーは鑑定ページの「あなたの1年トランジット手帳（PDF）を作成・保存」から作成します。作成した月から12か月分で、必要に応じて作り直せます。",
        "before_title": "入力前にご確認ください",
        "before_subtitle": "注文番号を使用する前に、出生情報を確認してください。",
        "notes_heading": "ご利用上の注意",
        "notes": [
            "本商品は占星術データとAIによる解釈を楽しむためのデジタル商品です。医療・法律・投資などの専門判断には使用しないでください。",
            "AIの回答は利用するサービスやモデルにより異なります。重要な判断はご自身の責任で行ってください。",
            "生成データは個人利用向けです。再配布・転載・販売は禁止です。",
        ],
        "verification_heading": "購入確認",
        "verification": [
            "Etsyの「購入履歴とレビュー」または注文確認メールで注文番号を確認し、入力してください。",
            "購入直後は確認に数分かかる場合があります。確認できない場合は、少し待ってから再試行してください。",
        ],
        "storage_heading": "鑑定ページと保存",
        "storage": [
            "発行された鑑定ページは90日間利用できます。",
            "期限後も使えるよう、鑑定ページのURLと保存用ZIPを端末へ保存してください。",
        ],
        "support": "お問い合わせ：Etsyメッセージ",
    },
    "en": {
        "title": "Western Astrology FULL",
        "subtitle": "The complete edition with a birth chart, asteroids, 31 days of transits, and a 12-month planner.",
        "form_heading": "Buyer input form",
        "form_caption": "Scan the QR code or tap the URL to open the form.",
        "how": "How to use",
        "steps": [
            "Open the dedicated URL in this PDF.",
            "Enter your Etsy order number and your birth date, birth time, and birthplace.",
            "Save the private chart page and generated files, then use them with your preferred AI.",
        ],
        "included_heading": "What's included",
        "included": [
            "Natal planets, houses, angles, and major aspects",
            "Asteroids: Chiron, Juno, Vesta, Pallas, and Ceres",
            "31 days of transit data",
            "Your personalized 12-month Transit Planner (PDF)",
        ],
        "description": "Download your YAML data, horoscope image, and archive ZIP from the private chart page. Astrocartography (ACG) is a separate product.",
        "planner": "Create the planner from your chart page with the “Create your 1-Year Transit Planner (PDF)” button. It covers 12 months from the month you create it and can be rebuilt when needed.",
        "before_title": "Before you start",
        "before_subtitle": "Check your birth details before using the order number.",
        "notes_heading": "Notes on use",
        "notes": [
            "This is a digital product for astrology data and AI-assisted reflection. Do not use it for medical, legal, or financial decisions.",
            "AI answers vary by service and model. Final decisions remain your own.",
            "The generated data is for personal use. Redistribution and resale are not permitted.",
        ],
        "verification_heading": "Purchase verification",
        "verification": [
            "Find your order number in Etsy Purchases and reviews or in your receipt email, then enter it in the form.",
            "Verification can take a few minutes immediately after purchase. If it fails, wait briefly and try again.",
        ],
        "storage_heading": "Chart page and storage",
        "storage": [
            "The generated chart page stays available for 90 days.",
            "Save the private URL and download the archive ZIP so you can keep the files after that.",
        ],
        "support": "Support: send a message through Etsy",
    },
    "es": {
        "title": "Astrología Occidental · Edición FULL",
        "subtitle": "La edición completa con carta natal, asteroides, 31 días de tránsitos y un planificador de 12 meses.",
        "form_heading": "Formulario para compradores",
        "form_caption": "Escanea el código QR o pulsa la URL para abrir el formulario.",
        "how": "Cómo utilizarlo",
        "steps": [
            "Abre la URL exclusiva que aparece en este PDF.",
            "Introduce tu número de pedido de Etsy y tus datos de nacimiento: fecha, hora y lugar.",
            "Guarda la página privada y los archivos generados; después, utilízalos con la IA que prefieras.",
        ],
        "included_heading": "Qué incluye",
        "included": [
            "Planetas natales, casas, ángulos y aspectos principales",
            "Asteroides: Quirón, Juno, Vesta, Palas y Ceres",
            "31 días de datos de tránsitos",
            "Tu Planificador de Tránsitos personalizado de 12 meses (PDF)",
        ],
        "description": "Desde la página privada puedes descargar los datos YAML, la imagen de la carta y un archivo ZIP. La astrocartografía (ACG) es un producto independiente.",
        "planner": "Crea el planificador desde tu página con el botón «Crear tu Planificador de Tránsitos de 12 meses (PDF)». Abarca 12 meses desde el mes de creación y puedes volver a generarlo cuando lo necesites.",
        "before_title": "Antes de empezar",
        "before_subtitle": "Comprueba tus datos de nacimiento antes de utilizar el número de pedido.",
        "notes_heading": "Avisos de uso",
        "notes": [
            "Este producto digital ofrece datos astrológicos y reflexión asistida por IA. No lo utilices para tomar decisiones médicas, legales o financieras.",
            "Las respuestas varían según el servicio y el modelo de IA. Las decisiones finales son responsabilidad tuya.",
            "Los datos generados son para uso personal. No se permite redistribuirlos ni revenderlos.",
        ],
        "verification_heading": "Verificación de la compra",
        "verification": [
            "Busca el número de pedido en Compras y reseñas de Etsy o en el correo del recibo e introdúcelo en el formulario.",
            "La verificación puede tardar unos minutos justo después de la compra. Si falla, espera un momento y vuelve a intentarlo.",
        ],
        "storage_heading": "Página privada y archivos",
        "storage": [
            "La página privada estará disponible durante 90 días.",
            "Guarda la URL privada y descarga el ZIP para conservar los archivos después de ese plazo.",
        ],
        "support": "Ayuda: envía un mensaje por Etsy",
    },
    "de": {
        "title": "Westliche Astrologie · FULL Edition",
        "subtitle": "Die vollständige Edition mit Geburtshoroskop, Asteroiden, 31 Tagen Transiten und einem 12-Monats-Planer.",
        "form_heading": "Eingabeformular für Käufer",
        "form_caption": "Scanne den QR-Code oder tippe auf die URL, um das Formular zu öffnen.",
        "how": "So funktioniert es",
        "steps": [
            "Öffne die persönliche URL in diesem PDF.",
            "Gib deine Etsy-Bestellnummer sowie Geburtsdatum, Geburtszeit und Geburtsort ein.",
            "Speichere die private Horoskopseite und die erstellten Dateien und nutze sie anschließend mit dem KI-Dienst deiner Wahl.",
        ],
        "included_heading": "Enthalten",
        "included": [
            "Radixplaneten, Häuser, Achsen und Hauptaspekte",
            "Asteroiden: Chiron, Juno, Vesta, Pallas und Ceres",
            "Transitdaten für 31 Tage",
            "Dein persönlicher 12-Monats-Transitplaner (PDF)",
        ],
        "description": "Auf der privaten Horoskopseite kannst du YAML-Daten, Horoskopgrafik und Archiv-ZIP herunterladen. Astrokartografie (ACG) ist ein separates Produkt.",
        "planner": "Erstelle den Planer auf deiner Horoskopseite über „Deinen 12-Monats-Transitplaner erstellen (PDF)“. Er umfasst 12 Monate ab dem Erstellungsmonat und kann bei Bedarf neu erstellt werden.",
        "before_title": "Vor dem Start",
        "before_subtitle": "Prüfe deine Geburtsdaten, bevor du die Bestellnummer verwendest.",
        "notes_heading": "Nutzungshinweise",
        "notes": [
            "Dieses digitale Produkt bietet astrologische Daten und KI-gestützte Reflexion. Verwende es nicht für medizinische, rechtliche oder finanzielle Entscheidungen.",
            "Antworten unterscheiden sich je nach KI-Dienst und Modell. Die endgültigen Entscheidungen triffst du selbst.",
            "Die erstellten Daten sind nur für den persönlichen Gebrauch bestimmt. Weitergabe und Weiterverkauf sind nicht gestattet.",
        ],
        "verification_heading": "Kaufbestätigung",
        "verification": [
            "Du findest die Bestellnummer unter Einkäufe und Bewertungen bei Etsy oder in der Beleg-E-Mail. Gib sie anschließend im Formular ein.",
            "Direkt nach dem Kauf kann die Bestätigung einige Minuten dauern. Warte bei einem Fehler kurz und versuche es erneut.",
        ],
        "storage_heading": "Horoskopseite und Speicherung",
        "storage": [
            "Die private Horoskopseite bleibt 90 Tage verfügbar.",
            "Speichere die private URL und lade das Archiv-ZIP herunter, damit du die Dateien danach behältst.",
        ],
        "support": "Hilfe: Nachricht über Etsy senden",
    },
}


def access_url(lang: str) -> str:
    return f"{BASE_URL}/redeem/western-full?lang={lang}&provider=etsy"


def output_path(lang: str) -> Path:
    return OUTPUT_DIR / f"nanami_western_full_ETSY_{lang.upper()}.pdf"


def build_story(lang: str) -> list[object]:
    copy = LOCALES[lang]
    market = {
        "brand": "nanami-products  |  Etsy",
        "support": copy["support"],
    }
    body_style = "BodyJP" if lang == "ja" else "BodyEN"
    story: list[object] = [
        *page_header(market, str(copy["title"]), str(copy["subtitle"]), english=lang != "ja"),
        route_box(access_url(lang), str(copy["form_heading"]), str(copy["form_caption"])),
        Spacer(1, 4),
        p(str(copy["how"]), "H2"),
        steps(list(copy["steps"]), style=body_style),
        Spacer(1, 2),
        *section(str(copy["included_heading"]), list(copy["included"]), style=body_style),
        info_box([p(str(copy["description"]), body_style)]),
        Spacer(1, 3),
        info_box([p(str(copy["planner"]), body_style)]),
        PageBreak(),
        *page_header(
            market,
            str(copy["before_title"]),
            str(copy["before_subtitle"]),
            english=lang != "ja",
        ),
        *section(str(copy["notes_heading"]), list(copy["notes"]), style=body_style),
        *section(
            str(copy["verification_heading"]),
            list(copy["verification"]),
            style=body_style,
        ),
        *section(str(copy["storage_heading"]), list(copy["storage"]), style=body_style),
    ]
    return story


def build_one(lang: str) -> Path:
    copy = LOCALES[lang]
    path = output_path(lang)
    market = {"support": copy["support"]}
    build_pdf(
        market,
        build_story(lang),
        path,
        f"Western Astrology FULL - Etsy buyer guide ({lang})",
    )
    DISTRIBUTION_DIR.mkdir(parents=True, exist_ok=True)
    copyfile(path, DISTRIBUTION_DIR / path.name)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=tuple(LOCALES), action="append")
    args = parser.parse_args()
    for lang in args.lang or tuple(LOCALES):
        print(build_one(lang).relative_to(ROOT))


if __name__ == "__main__":
    main()
