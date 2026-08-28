"""Regenerate the buyer-facing English ACG access-code sample PDF."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.personal_edition_code_pdf import build_personal_edition_code_pdf


OUTPUT = ROOT / "output" / "pdf" / "personal-edition-acg-access-code-sample-en.pdf"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(
        build_personal_edition_code_pdf(
            code="PE-ACG-SAMPLE-ENGLISH",
            activation_url="https://chart.nanami-astro.com/personal-edition/activate?lang=en",
            product_type="acg_bundle",
            lang="en",
        )
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
