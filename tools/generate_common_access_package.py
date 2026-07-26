from __future__ import annotations

import argparse
import os
from pathlib import Path

from services.common_access_package import ETSY_PACKAGE_FILENAME, build_common_access_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a buyer-neutral Access Package.")
    parser.add_argument("--channel", choices=["etsy"], default="etsy")
    parser.add_argument("--lang", choices=["en", "ja"], default="en")
    parser.add_argument("--base-url", default=os.getenv("PUBLIC_BASE_URL", "https://chart.nanami-astro.com"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    redeem_url = args.base_url.rstrip("/") + f"/redeem/acg-bundle?lang={args.lang}&provider=etsy"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / ETSY_PACKAGE_FILENAME
    destination.write_bytes(build_common_access_package(redeem_url=redeem_url, lang=args.lang))
    print(destination.resolve())


if __name__ == "__main__":
    main()
