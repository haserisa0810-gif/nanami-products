"""Build permanent Chief Editor Neko demo planners in selected locales."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from services.planner_delivery import build_planner_yaml_from_natal_yaml
from services.planner_export import render_personal_planner


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_YAML = REPO_ROOT / "data" / "demo" / "chief_editor_neko.yaml"
PLANNER_START = datetime(2026, 8, 1, tzinfo=timezone.utc)
AI_URL = "https://chart.nanami-astro.com/demo/neko/planner-ai"


SUPPORTED_LANGS = ("en", "es", "de", "ja")


def build(output_dir: Path, languages: tuple[str, ...] = ("en", "ja")) -> list[Path]:
    chart_yaml = SOURCE_YAML.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for lang in languages:
        planner_yaml = build_planner_yaml_from_natal_yaml(
            chart_yaml=chart_yaml,
            lang=lang,
            months=12,
            transit_start_date=PLANNER_START,
        )
        out_path = output_dir / f"neko-editor-transit-planner-2026-2027-{lang}.pdf"
        render_personal_planner(
            yaml_text=planner_yaml,
            lang=lang,
            months=12,
            out_path=out_path,
            chart_url=f"{AI_URL}?lang={lang}",
        )
        outputs.append(out_path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--langs",
        nargs="+",
        choices=SUPPORTED_LANGS,
        default=["en", "ja"],
        help="Planner locales to generate (default: en ja)",
    )
    args = parser.parse_args()
    for path in build(args.output_dir, tuple(args.langs)):
        print(path)


if __name__ == "__main__":
    main()
