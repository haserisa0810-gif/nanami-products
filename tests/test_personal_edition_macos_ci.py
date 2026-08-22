from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "personal-edition-macos.yml"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_personal_edition_macos.sh"


def test_macos_workflow_builds_and_launches_personal_edition() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "runs-on: macos-15" in workflow
    assert "uses: actions/checkout@v7" in workflow
    assert "uses: actions/setup-python@v7" in workflow
    assert "python -m pip install -r requirements.txt pytest" in workflow
    assert "python personal-edition/build.py" in workflow
    assert "bash scripts/verify_personal_edition_macos.sh" in workflow
    assert "test_acg_bundle_zip_contains_precomputed_lines_and_local_map" in workflow
    assert "permissions:\n  contents: read" in workflow


def test_macos_verifier_checks_buyer_critical_behaviors() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")

    assert "/usr/bin/ditto -x -k" in script
    assert "START-MUSEUM-MAC.command" in script
    assert "START-ACG-MAC.command" in script
    assert "[[ -x" in script
    assert "grep -q $'\\r'" in script
    assert "http://127.0.0.1:8787/acg/" in script
    assert "選んだ場所の星のメッセージをAIに聞く" in script
    assert "占術データへ戻る" in script
