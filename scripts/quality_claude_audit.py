"""Fixed-source, tools-disabled Claude audit; never modifies application code."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/quality_audit_20261010"
MODEL = "claude-opus-5-5"
FILES = [
    "services/shichusuimei_calc.py", "services/shichusuimei_structure.py",
    "services/western_calc.py", "services/western_core.py",
    "services/transit_builder.py", "services/asteroid_provider.py",
    "services/transit_yaml.py", "services/long_term_transit_yaml.py",
    "services/yaml_exporter.py", "services/location.py",
    "services/shichusuimei_year_selection.py",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="nanami-quality-claude-"))
    hashes = {}
    if args.probe:
        prompt = "Reply with exactly MODEL_ACCESS_OK. Do not use tools."
        name = "model_probe"
    else:
        name = "independent_review"
        parts = [(OUT / "claude_review_request.md").read_text(encoding="utf-8")]
        for relative in FILES:
            path = ROOT / relative
            if not path.exists():
                continue
            raw = path.read_bytes()
            hashes[relative] = hashlib.sha256(raw).hexdigest()
            lines = "\n".join(f"{i}: {line}" for i, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1))
            parts.append(f"\n## {relative}\n```text\n{lines}\n```\n")
        prompt = "\n".join(parts)
    (OUT / f"{name}_input.md").write_text(prompt, encoding="utf-8")
    (OUT / f"{name}_hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    binary = args.binary or Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    print(f"Requested model={MODEL}; input_bytes={len(prompt.encode('utf-8'))}; tools=disabled", flush=True)
    proc = subprocess.run([
        str(binary), "--print", "--safe-mode", "--no-session-persistence",
        "--model", MODEL, "--tools", "", "--strict-mcp-config", "--mcp-config",
        '{"mcpServers":{}}', "--output-format", "json",
    ], cwd=scratch, input=prompt, capture_output=True, encoding="utf-8", timeout=60 if args.probe else 900)
    (OUT / f"{name}_response.json").write_text(proc.stdout, encoding="utf-8")
    (OUT / f"{name}_stderr.txt").write_text(proc.stderr, encoding="utf-8")
    try:
        response = json.loads(proc.stdout)
    except ValueError:
        response = {}
    usage_models = list((response.get("modelUsage") or {}).keys())
    error = bool(proc.returncode or response.get("is_error"))
    # An unverified or different model must never count as the requested review.
    verified = bool(usage_models) and all(m == MODEL for m in usage_models)
    changed = [n for n, h in hashes.items() if hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != h]
    metadata = dict(timestamp=datetime.now(timezone.utc).isoformat(), requested_model=MODEL,
        reported_models=usage_models, model_verified=verified, returncode=proc.returncode,
        is_error=error, changed_files=changed, tools_enabled=False, source_files=list(hashes))
    (OUT / f"{name}_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report = response.get("result") or proc.stderr or proc.stdout
    (OUT / f"{name}.md").write_text(report, encoding="utf-8")
    print(json.dumps(metadata), flush=True)
    print(str(report)[-1200:] if error else f"Result saved: {OUT / (name + '.md')}", flush=True)
    return 0 if verified and not error and not changed else 1

if __name__ == "__main__":
    raise SystemExit(main())
