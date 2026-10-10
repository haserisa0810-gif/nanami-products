"""Build clearly named, current English ACG distribution artifacts."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.common_access_package import build_common_access_package
from services.personal_edition_delivery import build_personalized_zip


OUTPUT = ROOT / "output" / "acg" / "current-en"
REDEEM_URL = "https://chart.nanami-astro.com/redeem/acg-bundle?lang=en&provider=etsy"
DEMO_URL = "https://chart.nanami-astro.com/demo/neko?lang=en"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "nanamiastro-ACG-Premium-Bundle-Automatic-Access-EN-CURRENT.zip").write_bytes(
        build_common_access_package(redeem_url=REDEEM_URL, lang="en")
    )
    yaml_text = (ROOT / "data" / "demo" / "chief_editor_neko.yaml").read_text(encoding="utf-8")
    (OUTPUT / "Chief-Editor-Neko-Personal-Edition-ACG-Sample-EN-CURRENT.zip").write_bytes(
        build_personalized_zip(
            yaml_text=yaml_text,
            lang="en",
            include_acg=True,
            chart_url=DEMO_URL,
        )
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
