"""Index already collected audit evidence; never rerun app/model/DB here."""
import collections
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/quality_audit_20261010"
lines = ["# 各プローブの結果一覧", "", "既存pytestとは別に実行した監査プローブです。同じ不具合の反例や重複した項目を含み、商品合格率・不具合件数とはしません。実行条件・actual／expected／methodの詳細は各JSONにあります。", ""]
summary = {}
for name in ("new_verification_results.json", "followup_probe_results.json", "final_checks.json"):
    doc = json.loads((OUT / name).read_text(encoding="utf-8"))
    rows = doc["results"] if isinstance(doc, dict) else doc
    counts = dict(collections.Counter(row["status"] for row in rows))
    summary[name] = counts
    lines += [f"## [{name}]({name})", "", "集計：" + json.dumps(counts, ensure_ascii=False), "", "| ID | 状態 |", "|---|---|"]
    lines += ["| `" + row["id"].replace("|", "\\|") + "` | " + row["status"] + " |" for row in rows]
    lines += [""]
(OUT / "evidence_matrix.md").write_text("\n".join(lines), encoding="utf-8")
state = {}
for label, folder in [("audited_worktree", ROOT), ("main_checkout", Path("C:/Users/haser/nanami-products"))]:
    values = {}
    for key, args in [("branch", ["branch", "--show-current"]), ("head", ["rev-parse", "HEAD"]), ("status", ["status", "--short"])]:
        proc = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8")
        values[key] = proc.stdout.strip() if proc.returncode == 0 else {"unavailable": proc.stderr.strip()}
    state[label] = values
(OUT / "audit_summary.json").write_text(json.dumps({"counts":summary, "git_final":state},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
