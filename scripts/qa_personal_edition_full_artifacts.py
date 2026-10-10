"""Validate the current four-language Personal Edition FULL sample PDFs."""

from __future__ import annotations

from pathlib import Path
import sys

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "pdf" / "personal-edition-full-current"
EXPECTED_PLANNER_LABEL = {
    "ja": "1年パーソナルPlanner",
    "en": "1-year personalized Planner",
    "es": "Planner personal de 1 año",
    "de": "Persönlicher 1-Jahres-Planer",
}


def _has_embedded_font(reader: PdfReader) -> bool:
    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources:
            continue
        fonts = resources.get_object().get("/Font")
        if not fonts:
            continue
        for font_ref in fonts.get_object().values():
            font = font_ref.get_object()
            descriptor = font.get("/FontDescriptor")
            descendants = font.get("/DescendantFonts") or []
            if not descriptor and descendants:
                descriptor = descendants[0].get_object().get("/FontDescriptor")
            if not descriptor:
                continue
            descriptor = descriptor.get_object()
            if any(descriptor.get(key) for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                return True
    return False


def main() -> None:
    failed = False
    for lang, planner_label in EXPECTED_PLANNER_LABEL.items():
        path = OUTPUT_DIR / f"personal-edition-full-access-code-sample-{lang}.pdf"
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        urls = []
        for page in reader.pages:
            for annotation in page.get("/Annots") or []:
                action = annotation.get_object().get("/A")
                if action and action.get("/URI"):
                    urls.append(str(action.get("/URI")))
        checks = {
            "pages=4": len(reader.pages) == 4,
            "museum=0": "museum" not in text.lower() and "ミュージアム" not in text,
            "planner": planner_label in text,
            "activation-link=1": urls == [
                "https://chart.nanami-astro.com/personal-edition/activate"
                f"?lang={lang}&code=PE-FULL-SAMPLE-{lang.upper()}"
            ],
        }
        if lang == "ja":
            checks["japanese-font-embedded"] = _has_embedded_font(reader)
        failed = failed or not all(checks.values())
        print(f"{path.name}: {checks}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
