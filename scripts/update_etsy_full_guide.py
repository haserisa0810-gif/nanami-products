from __future__ import annotations

from pathlib import Path

from shutil import copyfile

from pypdf import PdfReader


SOURCE = Path("output/guides/etsy/nanami_western_full_etsy.pdf")
OUTPUT = Path("output/etsy/western-full/nanami_western_full_ETSY_EN.pdf")

def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"{SOURCE} is missing. Run build_marketplace_product_guides.py first."
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    copyfile(SOURCE, OUTPUT)

    check = PdfReader(OUTPUT)
    text = "\n".join(page.extract_text() or "" for page in check.pages)
    if "STORES" in text:
        raise RuntimeError("STORES remains in the edited PDF")
    for expected in (
        "Enter your Etsy order number",
        "provider=etsy",
    ):
        if expected not in text:
            raise RuntimeError(f"Missing expected replacement: {expected}")

    print(OUTPUT.resolve())


if __name__ == "__main__":
    main()
