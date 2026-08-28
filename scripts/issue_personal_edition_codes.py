from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import pg_store  # noqa: E402


def _delivery_text(code: str, lang: str) -> str:
    if lang == "es":
        return f"""NANAMI ASTRO — EDICIÓN PERSONAL FULL

Código de acceso: {code}

Abre esta página e introduce el código y tus datos de nacimiento:
https://chart.nanami-astro.com/personal-edition/activate?lang=es

El código puede utilizarse una sola vez. Se marca como usado únicamente después de crear correctamente tu ZIP personalizado.
"""
    if lang == "de":
        return f"""NANAMI ASTRO — PERSONAL EDITION FULL

Zugangscode: {code}

Öffne diese Seite und gib deinen Code und deine Geburtsdaten ein:
https://chart.nanami-astro.com/personal-edition/activate?lang=de

Der Code kann einmal verwendet werden. Er gilt erst nach erfolgreicher Erstellung deiner persönlichen ZIP-Datei als verwendet.
"""
    if lang == "en":
        return f"""NANAMI ASTRO — PERSONAL EDITION FULL

Access code: {code}

Open this page and enter your code and birth details:
https://chart.nanami-astro.com/personal-edition/activate?lang=en

The code can be used once. It is consumed only after your personalized ZIP is created.
"""
    return f"""NANAMI ASTRO — PERSONAL EDITION FULL

引換コード: {code}

次のページを開き、コードと出生情報を入力してください。
https://chart.nanami-astro.com/personal-edition/activate?lang=ja

コードは1回だけ使用できます。本人用ZIPの作成成功後に使用済みになります。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue Personal Edition FULL access codes")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--provider", choices=("etsy", "coconala", "manual"), required=True)
    parser.add_argument("--lang", choices=("ja", "en", "es", "de"), default="ja")
    parser.add_argument("--expiration-days", type=int, default=30)
    parser.add_argument("--delivery-dir", type=Path)
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        parser.error("--count must be between 1 and 100")
    rows = pg_store.issue_personal_edition_codes(
        count=args.count,
        product_type="western_full",
        provider=args.provider,
        locale=args.lang,
        expiration_days=max(1, min(365, args.expiration_days)),
    )
    for index, row in enumerate(rows, 1):
        code = row["code"]
        print(code)
        if args.delivery_dir:
            args.delivery_dir.mkdir(parents=True, exist_ok=True)
            path = args.delivery_dir / f"PersonalEdition-{args.provider}-{index:03d}.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ACCESS-CODE.txt", _delivery_text(code, args.lang).encode("utf-8-sig"))


if __name__ == "__main__":
    main()
