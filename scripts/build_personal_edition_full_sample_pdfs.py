"""Regenerate Museum-free Personal Edition FULL access-code sample PDFs."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.personal_edition_code_pdf import build_personal_edition_code_pdf


OUTPUT_DIR = ROOT / "output" / "pdf" / "personal-edition-full-current"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for lang in ("ja", "en", "es", "de"):
        output = OUTPUT_DIR / f"personal-edition-full-access-code-sample-{lang}.pdf"
        output.write_bytes(
            build_personal_edition_code_pdf(
                code=f"PE-FULL-SAMPLE-{lang.upper()}",
                activation_url=(
                    "https://chart.nanami-astro.com/personal-edition/activate"
                    f"?lang={lang}"
                ),
                product_type="western_full",
                lang=lang,
            )
        )
        print(output)


if __name__ == "__main__":
    main()
