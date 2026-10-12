"""Final read-only audit checks; writes fictional evidence only."""
import json
import sys
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.shichusuimei_year_selection import build_year_selection
from services.shichu_chart import build_shichusuimei_svg_from_yaml

OUT = ROOT / "docs/quality_audit_20261010"
results = []
def record(name, ok, **extra):
    results.append(dict(id=name, status="PASS" if ok else "FAIL", **extra))

text = (OUT / "sample_shichu_full.yaml").read_text(encoding="utf-8")
nd = yaml.safe_load(text)["systems"]["shichusuimei"]["normalized_data"]
years = [2032, 2033, 2034]
out = yaml.safe_load(build_year_selection(text, {"mode":"selected", "years":years})["yaml_text"])
expected = [item for item in nd["annual_forecasts"]["items"] if item["effective_year"] in years]
record("selection_across_daiun_switch", out["selected_base_forecasts"] == expected,
       years=years, contexts={str(item["effective_year"]): len(item["daiun_contexts"]) for item in expected})
record("switch_selection_preserves_all_daiun", out["common"]["systems"]["shichusuimei"]["normalized_data"]["daiun"] == nd["daiun"])
svg = build_shichusuimei_svg_from_yaml(text)
record("shichu_svg_xml", bool(svg) and ET.fromstring(svg).tag.endswith("svg"), visual_check="未実施")
if svg:
    (OUT / "sample_shichu.svg").write_text(svg, encoding="utf-8")

before = json.loads((OUT / "application_source_baseline.json").read_text(encoding="utf-8"))
paths = [ROOT / "routes.py", ROOT / "config.py", ROOT / "requirements.txt"]
for folder in ("services", "templates", "static"):
    paths += [p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
record("final_application_source_unchanged", before == after, files=len(after),
       changed_files=sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k)))
for name in ("ai_shichu_full", "ai_shichu_selected", "ai_shichu_selected_followup", "ai_western_full", "ai_western_unknown", "ai_western_unknown_followup"):
    meta = json.loads((OUT / (name + "_metadata.json")).read_text(encoding="utf-8"))
    input_path = OUT / (name + "_input.txt")
    record("real_model_verified:"+name, meta.get("verified") is True and meta.get("reported_models") == ["claude-opus-5-5"], metadata=meta)
    record("model_input_unchanged:"+name, hashlib.sha256(input_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest() == meta.get("input_sha256"), method="送信テキストのLF正規化UTF-8ハッシュ。保存時のWindows CRLF変換を除く")
(OUT / "final_checks.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(results,ensure_ascii=False,indent=2))
