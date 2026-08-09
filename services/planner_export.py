"""App-facing entry point for the vendored Astrology Transit Planner.

The background job that fulfils a personal-planner order calls
``render_personal_planner`` with the already-built nanami-products YAML
(natal + ``transit_long_term`` addon, e.g. from
``long_term_transit_yaml.build_long_term_transits_yaml``). Generation runs in an
isolated subprocess so the planner's per-language reportlab font registration
never races with concurrent requests in the app process.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Reuse the planner's own hint dictionaries so callers can check compatibility.
SUPPORTED_LANGS = ("en", "ja")


class PlannerGenerationError(RuntimeError):
    """Raised when the planner subprocess fails or produces no PDF."""


def render_personal_planner(
    *,
    yaml_text: str,
    lang: str = "ja",
    months: int = 12,
    out_path: Path | None = None,
    chart_url: str | None = None,
    timeout: int = 900,
) -> Path:
    """Render a personal planner PDF from a nanami-products YAML string.

    Returns the path to the written PDF. When ``out_path`` is omitted a
    persistent temp file is created and returned; the caller owns cleanup.
    """
    if lang not in SUPPORTED_LANGS:
        raise ValueError(f"lang must be one of {SUPPORTED_LANGS}, got {lang!r}")
    if not yaml_text.strip():
        raise ValueError("yaml_text is empty")

    work_dir = Path(tempfile.mkdtemp(prefix="planner_"))
    yaml_path = work_dir / "customer.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")
    if out_path is None:
        out_path = work_dir / "personal_planner.pdf"
    out_path = Path(out_path)

    cmd = [
        sys.executable,
        "-m",
        "services.planner.build_personal_planner",
        "--yaml",
        str(yaml_path),
        "--lang",
        lang,
        "--months",
        str(months),
        "--out",
        str(out_path),
    ]
    if chart_url:
        cmd.extend(["--chart-url", chart_url])
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise PlannerGenerationError(f"planner generation timed out after {timeout}s") from exc

    if result.returncode != 0:
        raise PlannerGenerationError(
            f"planner generation failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise PlannerGenerationError("planner generation produced no PDF")
    return out_path
