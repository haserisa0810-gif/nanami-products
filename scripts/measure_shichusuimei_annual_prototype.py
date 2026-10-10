"""Offline fictional-chart measurements. No DB, purchase or deployed UI changes.

python scripts/measure_shichusuimei_annual_prototype.py --tokenizer-path tmp/annual_tokenizer
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.shichusuimei_annual_prototype import build_period_prototype, dump_period_prototype, expand_shared_year
from services.shichusuimei_annual_report import build_annual_fortune_report
from services.yaml_exporter import build_product_yaml

CASES = [
    {"name": "spring_exact", "birth_date": "1990-05-15", "birth_time": "08:30", "gender": "female", "birth_time_accuracy": "exact"},
    {"name": "winter_exact", "birth_date": "1984-01-25", "birth_time": "23:40", "gender": "male", "birth_time_accuracy": "exact"},
    {"name": "summer_unknown", "birth_date": "2000-07-07", "birth_time": None, "gender": "female", "birth_time_accuracy": "unknown"},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenizer-path", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/annual_prototype")
    args = parser.parse_args()
    if args.tokenizer_path:
        sys.path.insert(0, str(args.tokenizer_path.resolve()))
    try:
        import tiktoken
    except ImportError:
        raise SystemExit("Measurement needs isolated tiktoken; pass --tokenizer-path. App dependencies are unchanged.")
    output = args.output.resolve()
    if "onedrive" in str(output).lower():
        raise SystemExit("OneDrive output is prohibited for trial artifacts.")
    output.mkdir(parents=True, exist_ok=True)
    os.environ["TIKTOKEN_CACHE_DIR"] = str(output / "tokenizer_cache")
    encodings = {name: tiktoken.get_encoding(name) for name in ("o200k_base", "cl100k_base")}
    rows, bases = [], []
    for case in CASES:
        name = case["name"]
        birth = {k: v for k, v in case.items() if k != "name"}
        text, _, base = build_product_yaml(title=f"架空検証用 {name}", prefecture="東京都", **birth,
                                          include_shichusuimei=True,
                                          include_asteroids=False, include_transit=False)
        # Base generated_at reflects runtime; all measured files preserve it.
        (output / f"{name}_base.yaml").write_bytes(text.encode("utf-8"))
        base_row = {"case": name, "bytes_utf8": len(text.encode()), "characters": len(text)}
        base_row.update({f"tokens_{encoding}": len(enc.encode(text)) for encoding, enc in encodings.items()})
        bases.append(base_row)
        for years in (5, 10, 20):
            docs = {layout: build_period_prototype(base, 2026, years, layout=layout) for layout in ("shared", "expanded")}
            for year in range(2026, 2026 + years):
                if expand_shared_year(docs["shared"], year) != build_annual_fortune_report(base, year)["annual_fortune_report"]:
                    raise RuntimeError(f"Lossless verification failed: {name} {year}")
            for layout, doc in docs.items():
                yaml_text = dump_period_prototype(doc)
                filename = f"{name}_{years}years_{layout}.yaml"
                # Retain both layouts for inspecting exactly what was measured.
                (output / filename).write_bytes(yaml_text.encode("utf-8"))
                row = {"case": name, "years": years, "layout": layout,
                       "bytes_utf8": len(yaml_text.encode()), "characters": len(yaml_text),
                       "lossless_years_verified": years, "file": filename}
                for encoding, enc in encodings.items():
                    row[f"tokens_{encoding}"] = len(enc.encode(yaml_text))
                    row[f"combined_tokens_{encoding}"] = len(enc.encode(text + "\n\n---\n\n" + yaml_text))
                rows.append(row)
    result = {"measurement": {"tiktoken_version": tiktoken.__version__, "encodings": list(encodings),
                              "counted_text": "UTF-8 YAML only; combined text includes a YAML document separator",
                              "model_independent": True, "chat_message_overhead_included": False,
                              "ai_prompt_overhead_included": False, "fictional_cases": CASES,
                              "generated_at": datetime.now(timezone.utc).isoformat()},
              "base_full_yaml": bases, "annual_addon": rows}
    (output / "measurements.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "measurements.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
