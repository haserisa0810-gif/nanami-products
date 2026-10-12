"""Archive local verification and record only this fix's source deltas."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/shichusuimei_engine_fix_20261011"
baseline = json.loads((ROOT / "docs/quality_audit_20261010/application_source_baseline.json").read_text(encoding="utf-8"))
before = json.loads((OUT / "before_hashes.json").read_text(encoding="utf-8"))
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

changed = []
patches = []
for name, digest in baseline.items():
    name = name.replace("\\", "/")
    current = (ROOT / name).read_bytes()
    if sha(current) == digest:
        continue
    saved = OUT / "before" / name
    if saved.exists():
        original = saved.read_bytes()
    else:
        original = subprocess.run(["git", "show", "HEAD:" + name], cwd=ROOT, capture_output=True, check=True).stdout
        # Git may normalize CRLF. Do not invent a baseline when its content differs.
        if sha(original) != digest and sha(original.replace(b"\n", b"\r\n")) != digest:
            raise RuntimeError("Missing protected pre-fix content: " + name)
    changed.append({"file": name, "before_sha256": digest, "after_sha256": sha(current)})
    a = original.decode("utf-8-sig").replace("\r\n", "\n")
    b = current.decode("utf-8-sig").replace("\r\n", "\n")
    patches.append("".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), fromfile="before/" + name, tofile="after/" + name)))
new_source = ROOT / "services/birth_datetime.py"
changed.append({"file": "services/birth_datetime.py", "before_sha256": None, "after_sha256": sha(new_source.read_bytes())})
patches.append("".join(difflib.unified_diff([], new_source.read_text(encoding="utf-8").splitlines(True), fromfile="/dev/null", tofile="after/services/birth_datetime.py")))
(OUT / "fix_only_application.patch").write_text("\n".join(patches), encoding="utf-8")
root_check = []
for row in json.loads((ROOT / "docs/quality_audit_20261010/root_vs_audited_worktree.json").read_text(encoding="utf-8"))[:4]:
    raw = (ROOT.parents[1] / row["file"]).read_bytes().replace(b"\r\n", b"\n")
    root_check.append({"file": row["file"], "root_unchanged_since_audit": sha(raw) == row["root_sha256"]})
manifest = {"protected_before_snapshots_match": all(sha((OUT / "before" / n).read_bytes()) == h for n, h in before.items()),
            "application_baseline_files": len(baseline), "baseline_files_changed": len(changed) - 1,
            "new_application_files": 1, "changed_application_files": changed,
            "root_engine_checks": root_check,
            "western_and_structure_sources_unchanged": all(n not in {r["file"] for r in changed} for n in ["services/western_calc.py", "services/western_core.py", "services/shichusuimei_structure.py"])}
(OUT / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
log = (ROOT.parents[1] / "tmp/shichu-fix-complete-20261011.log").read_text(encoding="utf-8")
(OUT / "pytest_final.log").write_text(log, encoding="utf-8")
match = re.search(r"(\d+) passed, (\d+) warnings, (\d+) subtests passed in ([\d.]+)s", log)
if not match or "FAILED " in log:
    raise RuntimeError("Final pytest has not passed")
results = {"status": "PASS", "pytest_total": int(match[1]), "existing_tests": 891,
           "new_tests": int(match[1]) - 891, "warnings": int(match[2]), "subtests": int(match[3]),
           "seconds": float(match[4]), "javascript_tests": 6,
           "command": "python -m pytest tests -q -p no:cacheprovider --basetemp=<local temporary directory>",
           "fixture_reference": "lunar_python 1.4.8 plus independent offsets/hour arithmetic and NAOJ 2026 Lichun",
           "database": "mocks only; no production or buyer database validation", "push": False, "deploy": False}
(OUT / "test_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
assert manifest["protected_before_snapshots_match"] and manifest["western_and_structure_sources_unchanged"]
print(json.dumps({"manifest": manifest, "tests": results}, ensure_ascii=False, indent=2))
