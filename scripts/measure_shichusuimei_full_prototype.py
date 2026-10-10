"""Phase A/B only: saved fictional Full variants, section and combination sizes.

No product routes/storage/ZIP/annual builders are edited or called for issuance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.shichusuimei_full_prototype import (
    build_ordinary, build_recommended, item_mapping, load_saved_full, restore_variant,
    variant_prompt, verify_recommended, walk, pointer, _typed_tree,
    _get, _pointer_parts,
)


def dump(data):
    import yaml
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120).encode("utf-8")


def fixture_sources(annual_dir: Path, output: Path) -> dict[str, bytes]:
    sources = {name: (annual_dir / f"{name}_base.yaml").read_bytes()
               for name in ("spring_exact", "winter_exact", "summer_unknown")}
    spring = load_saved_full(sources["spring_exact"])
    # Fixture generation is separate from preservation checks; each is saved
    # before any variant is built. Variant transforms never call the engine.
    from services import shichusuimei_calc as core
    start = datetime.fromisoformat(spring["systems"]["shichusuimei"]["normalized_data"]["daiun"]["items"][3]["approx_start_at"])
    lichun = core._lichun_utc_for_year(2026, "Asia/Tokyo")
    for name, as_of in (("daiun_boundary", start), ("lichun_before", lichun - timedelta(seconds=1)),
                        ("lichun_after", lichun + timedelta(seconds=1))):
        case = deepcopy(spring)
        case["systems"]["shichusuimei"] = core.calc_shichusuimei_from_payload(
            dict(year=1990, month=5, day=15, hour=8, minute=30, gender="female"), as_of=as_of)
        case["generated_at"] = case["meta"]["generated_at"] = as_of.isoformat()
        case["input"]["title"] = f"架空保存 fixture {name}"
        sources[name] = dump(case)
    old = deepcopy(spring)
    shichu = old["systems"]["shichusuimei"]
    shichu["engine_version"] = "0.3-old-format-fixture"
    nd = shichu["normalized_data"]
    nd.pop("structural_analysis", None)
    nd.pop("annual_forecasts", None)
    for item in nd["daiun"]["items"]:
        for key in ("approx_start_at", "approx_end_at", "structural_analysis"):
            item.pop(key, None)
    nd["annual_fortune"].pop("structural_analysis", None)
    sources["old_saved_format"] = dump(old)
    saved = output / "saved_sources"
    saved.mkdir(parents=True, exist_ok=True)
    for name, raw in sources.items():
        (saved / f"{name}.yaml").write_bytes(raw)
    return sources


def annual_compatibility(base: dict, annual: dict) -> dict:
    details = annual["systems"]["shichusuimei"]["annual_details"]
    reference = details["base_reference"]
    shichu = base["systems"]["shichusuimei"]
    nd = shichu.get("normalized_data") or {}
    problems = []
    if (base.get("meta") or {}).get("chart_id") != reference["chart_id"]:
        problems.append("chart_id mismatch")
    for name, kanshi in reference["pillars"].items():
        value = (nd.get("pillars") or {}).get(name)
        if isinstance(value, dict):
            value = value.get("kanshi")
        if value != kanshi:
            problems.append(f"natal pillar mismatch: {name}")
    for field in ("structural_analysis", "daiun", "kubo", "five_elements"):
        if not nd.get(field):
            problems.append(f"required base material absent: {field}")
    # Current annual prototype's references must resolve within its own file.
    from services.shichusuimei_annual_prototype import expand_shared_year
    for item in details["years"]:
        expand_shared_year(annual, item["selected_year"])
    return {"valid": not problems, "problems": problems}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenizer-path", type=Path, default=ROOT / "tmp/annual_tokenizer")
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/shichu_full_ab")
    args = parser.parse_args()
    sys.path.insert(0, str(args.tokenizer_path.resolve()))
    import tiktoken
    import yaml
    # Reuse already-downloaded definitions read-only; no model/API calls.
    os.environ["TIKTOKEN_CACHE_DIR"] = str(ROOT / "tmp/annual_prototype/tokenizer_cache")
    from unittest.mock import patch
    with patch("requests.get", side_effect=RuntimeError("Offline trial: no network downloads allowed")):
        encoding = tiktoken.get_encoding("o200k_base")
    output = args.output.resolve()
    if "onedrive" in str(output).lower():
        raise SystemExit("OneDrive output is prohibited")
    output.mkdir(parents=True, exist_ok=True)
    annual_dir = ROOT / "tmp/annual_prototype"
    sources = fixture_sources(annual_dir, output)
    variants, sections, repeats, combinations, checks, questions = [], [], [], [], [], []

    def measure(raw):
        text = raw.decode("utf-8")
        return {"bytes_utf8": len(raw), "characters": len(text), "tokens_o200k_base": len(encoding.encode(text))}

    for name, raw in sources.items():
        doc = load_saved_full(raw)
        recommended, rec_manifest = build_recommended(raw)
        ordinary, normal_manifest = build_ordinary(raw)
        plain_refs, _ = build_recommended(raw, tables=False)
        folder = output / name
        folder.mkdir(exist_ok=True)
        values = {"complete": raw, "ordinary": ordinary, "recommended": recommended}
        decoded = {"complete": doc, "ordinary": restore_variant(ordinary), "recommended": restore_variant(recommended)}
        baseline = measure(raw)
        for variant, data in values.items():
            (folder / f"{variant}_local_trial.yaml").write_bytes(data)
            prompt = variant_prompt(variant)
            (folder / f"{variant}_local_prompt.txt").write_bytes(prompt.encode("utf-8"))
            row = {"case": name, "variant": variant, **measure(data),
                   "tokens_with_local_usage_instructions": len(encoding.encode(prompt + "\n---\n" + data.decode())),
                   "byte_reduction_percent": round(100 * (1 - len(data) / len(raw)), 2),
                   "token_reduction_percent": round(100 * (1 - measure(data)["tokens_o200k_base"] / baseline["tokens_o200k_base"]), 2)}
            variants.append(row)
        verified = verify_recommended(raw, recommended, rec_manifest)
        complete_hash = hashlib.sha256((folder / "complete_local_trial.yaml").read_bytes()).hexdigest()
        assert complete_hash == hashlib.sha256(raw).hexdigest()
        normal_nd = decoded["ordinary"]["systems"]["shichusuimei"]["normalized_data"]
        source_nd = doc["systems"]["shichusuimei"]["normalized_data"]
        for field, material in source_nd.items():
            if field != "annual_forecasts":
                assert _typed_tree(normal_nd[field]) == _typed_tree(material)
        assert "annual_forecasts" not in normal_nd
        checks.append({"case": name, "complete_sha256": complete_hash, "complete_bytes_identical": True,
                       **verified, "ordinary_retained_calculation_fields_equal": True,
                       "ordinary_omissions": normal_manifest["coverage"],
                       "reference_only_candidate_tokens": measure(plain_refs)["tokens_o200k_base"],
                       "recommended_table_sections": len(rec_manifest["table_sections"])})
        mapping = item_mapping(raw, rec_manifest, normal_manifest)
        for row in mapping:
            original_value = _get(doc, tuple(_pointer_parts(row["source"], doc)))
            restored_value = _get(decoded["recommended"], tuple(_pointer_parts(row["recommended_destination"], decoded["recommended"])))
            assert _typed_tree(original_value) == _typed_tree(restored_value)
            if row["ordinary_action"] in {"retained", "duplicate_consolidated"}:
                normal_value = _get(decoded["ordinary"], tuple(_pointer_parts(row["ordinary_destination"], decoded["ordinary"])))
                assert _typed_tree(original_value) == _typed_tree(normal_value)
            row["recommended_representation"] = "named_column_table" if any(row["source"].startswith(t["source"] + "/") for t in rec_manifest["table_sections"]) else "mapping_or_named_reference"
        checks[-1]["mapped_source_leaves_verified"] = len(mapping)
        (folder / "item_mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "recommended_reference_manifest.json").write_text(json.dumps(rec_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "ordinary_coverage.json").write_text(json.dumps(normal_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        roots = [((), doc)] + [( (k,), v) for k, v in doc.items()]
        shichu = doc["systems"]["shichusuimei"]
        roots += [( ("systems", "shichusuimei", k), v) for k, v in shichu.items()]
        nd = shichu["normalized_data"]
        roots += [( ("systems", "shichusuimei", "normalized_data", k), v) for k, v in nd.items()]
        for path, material in roots:
            serialized = dump(material if not path else {path[-1]: material})
            sections.append({"case": name, "source": pointer(path), "measurement_kind": "whole_reserialized" if not path else "isolated_subtree_non_additive", **measure(serialized)})
        for path, material in walk(doc):
            if isinstance(material, list) and path and path[-1] in {"items", "placements", "branch_relations", "stem_relations", "roots", "limitations", "stem_actions", "daiun_contexts"}:
                repeats.append({"case": name, "source": pointer(path), "item_count": len(material), **measure(dump({path[-1]: material}))})
        questions.append({"case": name, "external_ai_not_run": True, "questions_and_expected_facts": [
            {"question": "出生時刻の確実性と、時柱を根拠に使える範囲は？", "source": "/systems/shichusuimei/input/assumptions", "expected": shichu["input"]["assumptions"]},
            {"question": "日柱の地支と、各年の流年地支を別の対象として答えてください。", "source": "/systems/shichusuimei/normalized_data", "expected": {"day_pillar": nd["pillars"]["day"], "current_annual": nd["annual_fortune"], "forecast_year_pillars": [{"effective_year": x["effective_year"], "kanshi": x["kanshi"]} for x in (nd.get("annual_forecasts") or {}).get("items", [])]}},
            {"question": "大運の切り替わりと適用期間を概算として説明してください。", "source": "/systems/shichusuimei/normalized_data/daiun/items", "expected": [{k: v for k, v in item.items() if k != "structural_analysis"} for item in nd["daiun"]["items"]]},
            {"question": "合がある場合、どの柱・運が参加し、合化を確定しているかを答えてください。", "source": "/systems/shichusuimei/normalized_data/interactions", "expected": nd["interactions"]},
            {"question": "通常版にない既存流年予測を、該当なしと解釈してよいですか？", "expected": "不可。収録範囲からの省略。完全版・推奨版に残る。"},
        ]})
        if name in {"spring_exact", "winter_exact", "summer_unknown"}:
            for years in (5, 10, 20):
                annual_path = annual_dir / f"{name}_{years}years_shared.yaml"
                annual_raw = annual_path.read_bytes()
                annual = yaml.safe_load(annual_raw)
                for variant, data in values.items():
                    compatible = annual_compatibility(decoded[variant], annual)
                    combinations.append({"case": name, "variant": variant, "years": years,
                                         "annual_file_sha256": hashlib.sha256(annual_raw).hexdigest(), **compatible,
                                         "combined_yaml_tokens": len(encoding.encode(data.decode() + "\n---\n" + annual_raw.decode())) if compatible["valid"] else None,
                                         "combined_tokens_with_local_instructions": len(encoding.encode(variant_prompt(variant) + "\n---\n" + data.decode() + "\n---\n" + annual_raw.decode())) if compatible["valid"] else None})
    result = {"conditions": {"tiktoken_version": tiktoken.__version__, "encoding": "o200k_base", "character_encoding": "UTF-8, no BOM, LF",
               "section_serializer": "yaml.safe_dump allow_unicode=True sort_keys=False width=120; isolated subtree contributions are non-additive",
               "complete": "saved original bytes, not reserialized", "recommended": "readable leaf mappings + scoped named anchors + named-column tables",
               "ordinary": "source subset with explicit coverage; no new calculations", "external_ai_calls": False,
               "chat_and_answer_overhead_included": False, "existing_annual_trials_unchanged": True},
              "variants": variants, "sections": sections, "repeated_structures": repeats, "combinations": combinations, "verification": checks}
    (output / "measurements.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "ai_reading_questions_expected_facts.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    for filename, rows in (("variants.csv", variants), ("sections.csv", sections), ("repeated_structures.csv", repeats), ("combinations.csv", combinations)):
        with (output / filename).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"variants": variants, "combinations": combinations, "verification": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
