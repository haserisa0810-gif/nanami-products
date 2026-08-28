from __future__ import annotations

import io
import zipfile


ETSY_PACKAGE_FILENAME = "nanamiastro-ACG-Premium-Bundle-Access-Package.zip"


def build_common_access_package(*, redeem_url: str, lang: str = "en") -> bytes:
    """Build the buyer-neutral, automatic-redemption package for Etsy."""
    if lang not in {"en", "ja", "es", "de"}:
        raise ValueError("unsupported language")
    clean_url = redeem_url.strip()
    if not clean_url.startswith(("https://", "http://")):
        raise ValueError("redeem_url must be an absolute HTTP(S) URL")

    english = (
        "NANAMI ASTRO - ACG PREMIUM BUNDLE\n"
        "AUTOMATIC ACCESS PACKAGE\n\n"
        "Thank you for your purchase.\n\n"
        "No activation code is required. You do not need to wait for a separate Etsy Message.\n\n"
        "How to begin:\n\n"
        "1. Open the automatic access page using the link in this package.\n"
        "2. Enter the Etsy order number shown on your purchase receipt.\n"
        "3. Enter your birth date, exact birth time, and birthplace.\n"
        "4. After purchase verification, your private chart page is created and your "
        "permanent Personal Edition ZIP downloads automatically.\n"
        "5. Save both the ZIP and the private chart page URL. You can download the ZIP "
        "again from that page.\n\n"
        "If your purchase cannot be verified immediately, wait five minutes and try again.\n"
        "Manual support remains available through Etsy Messages if needed.\n\n"
        "IMPORTANT: Astrocartography requires an accurate birth time.\n"
    )
    japanese = (
        "NANAMI ASTRO - ACG PREMIUM BUNDLE\n"
        "自動アクセスパッケージ\n\n"
        "ご購入ありがとうございます。\n\n"
        "アクセスコードは不要です。個別メッセージを待たずに利用できます。\n\n"
        "ご利用方法:\n\n"
        "1. このパッケージ内のリンクから自動受付ページを開きます。\n"
        "2. Etsyの購入明細に記載された注文番号を入力します。\n"
        "3. 生年月日、正確な出生時刻、出生地を入力します。\n"
        "4. 購入確認後、専用鑑定ページが作成され、無期限のPersonal Edition ZIPが自動ダウンロードされます。\n"
        "5. ZIPと専用鑑定ページURLの両方を保存してください。ページからZIPを再ダウンロードできます。\n\n"
        "購入直後に確認できない場合は、5分ほど待ってから再度お試しください。\n"
        "必要な場合はEtsyメッセージで手動サポートいたします。\n\n"
        "重要: アストロカートグラフィには正確な出生時刻が必要です。\n"
    )
    localized = {
        "es": "NANAMI ASTRO - ACG PREMIUM BUNDLE\nPAQUETE DE ACCESO AUTOMÁTICO\n\nGracias por tu compra. No necesitas un código de activación. Abre el enlace, introduce tu número de pedido de Etsy y tus datos de nacimiento exactos. Tras verificar la compra se crearán tu página privada y el ZIP permanente. La astrocartografía requiere una hora de nacimiento exacta.\n",
        "de": "NANAMI ASTRO – ACG PREMIUM BUNDLE\nAUTOMATISCHES ZUGANGSPAKET\n\nVielen Dank für deinen Kauf. Du benötigst keinen Aktivierungscode. Öffne den Link und gib deine Etsy-Bestellnummer sowie deine genauen Geburtsdaten ein. Nach der Kaufprüfung werden deine private Seite und die dauerhafte ZIP-Datei erstellt. Astrokartografie erfordert eine genaue Geburtszeit.\n",
    }
    readme = english if lang == "en" else (japanese + "\n\n" + english if lang == "ja" else localized[lang])
    start_copy = {
        "ja": ("このURLをブラウザで開いてください:", "リンクを押せない場合は、アドレス欄へコピーしてください。"),
        "en": ("Open this URL in your web browser:", "If the URL is not clickable, copy and paste it into the address bar."),
        "es": ("Abre esta URL en tu navegador:", "Si no puedes pulsar el enlace, cópialo en la barra de direcciones."),
        "de": ("Öffne diese URL im Browser:", "Falls der Link nicht anklickbar ist, kopiere ihn in die Adresszeile."),
    }[lang]

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README-FIRST.txt", readme.encode("utf-8-sig"))
        archive.writestr(
            "START-HERE-AUTOMATIC-ACCESS.txt",
            (
                "NANAMI ASTRO - ACG PREMIUM BUNDLE\n\n"
                f"{start_copy[0]}\n"
                f"{clean_url}\n\n"
                f"{start_copy[1]}\n"
            ).encode("utf-8-sig"),
        )
    return output.getvalue()
