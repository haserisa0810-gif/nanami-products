from __future__ import annotations

import io
import zipfile


ETSY_PACKAGE_FILENAME = "nanamiastro-ACG-Premium-Bundle-Access-Package.zip"


def build_common_access_package(*, activation_url: str, lang: str = "en") -> bytes:
    """Build a buyer-neutral package suitable for uploading once to Etsy."""
    if lang not in {"en", "ja"}:
        raise ValueError("lang must be en or ja")
    clean_url = activation_url.strip()
    if not clean_url.startswith(("https://", "http://")):
        raise ValueError("activation_url must be an absolute HTTP(S) URL")

    english = (
        "NANAMI ASTRO - ACCESS PACKAGE\n\n"
        "Thank you for your purchase.\n\n"
        "This Access Package does not contain your personal activation code.\n\n"
        "Your personal activation code will be sent separately through Etsy Messages after your purchase.\n\n"
        "How to begin:\n\n"
        "1. Check your Etsy Messages for your personal activation code.\n"
        "2. Open the activation page using the link in this package.\n"
        "3. Enter your activation code and birth details.\n"
        "4. Generate your personalized astrology page and download package.\n\n"
        "Astrocartography requires an accurate birth time.\n"
    )
    japanese = (
        "NANAMI ASTRO - 共通アクセスパッケージ\n\n"
        "ご購入ありがとうございます。\n\n"
        "このパッケージには個別のアクティベーションコードは含まれていません。\n"
        "ご注文確認後、Etsyメッセージで個別コードをお送りします。\n\n"
        "Etsyメッセージを確認し、このパッケージ内のリンクからアクティベーションページを開いて、"
        "コードと出生情報を入力してください。\n"
        "アストロカートグラフィには正確な出生時刻が必要です。\n"
    )
    readme = english if lang == "en" else japanese + "\n\n" + english

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README-FIRST.txt", readme.encode("utf-8-sig"))
        archive.writestr("ACTIVATION-URL.txt", (clean_url + "\n").encode("utf-8-sig"))
        archive.writestr(
            "OPEN-ACTIVATION-PAGE.url",
            ("[InternetShortcut]\r\nURL=" + clean_url + "\r\n").encode("utf-8"),
        )
    return output.getvalue()
