# -*- coding: utf-8 -*-
"""One-shot personal-planner build: a nanami-products YAML in, a PDF out.

This is the single seam a background job (or CLI) invokes as an isolated
subprocess: it runs the calculation and layout stages in one process, so the
per-language font registration never races with anything else. Period and time
zone default to the YAML's long-term-transit start month and input timezone.

    python build_personal_planner.py --yaml customer.yaml --lang ja --out out.pdf
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import yaml as yaml_lib

from . import compute_ephemeris as ce
from . import generate_planner as gp


def build(yaml_path: Path, lang: str, out_path: Path, *, months: int = 12,
          chart_url: str | None = None) -> Path:
    source = yaml_lib.safe_load(yaml_path.read_text(encoding="utf-8"))
    western = (source.get("systems") or {}).get("western") or {}
    long_term = western.get("transit_long_term") or {}
    period_meta = long_term.get("period") or {}

    start_month = str(period_meta.get("start_date", ""))[:7]
    if not start_month:
        # Fall back to the current month when the addon lacks a period.
        today = date.today()
        start_month = f"{today.year:04d}-{today.month:02d}"
    tz_name = source.get("input", {}).get("timezone") or period_meta.get("timezone") or "UTC"

    year, month = int(start_month[:4]), int(start_month[5:7])
    ce.PERIOD = ce.Period(year, month, months, tz_name)
    snapshot = ce.build_snapshot(yaml_path)

    gp.register_fonts(lang)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    planner = gp.Planner(snapshot, out_path, "personal", lang, chart_url=chart_url)
    planner.render()
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yaml", type=Path, required=True, help="nanami-products YAML (natal + transit_long_term)")
    parser.add_argument("--lang", choices=["en", "ja"], default="en")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--chart-url", default=None)
    args = parser.parse_args()
    if not args.yaml.exists():
        raise SystemExit(f"YAML not found: {args.yaml}")
    out = build(args.yaml, args.lang, args.out, months=args.months, chart_url=args.chart_url)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
