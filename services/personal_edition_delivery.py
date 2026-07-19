from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

from services.acg_api import personal_geojson


ROOT = Path(__file__).resolve().parent.parent
PE_DIR = ROOT / "personal-edition"
VERSION = "1.1.0"
_build_lock = threading.Lock()


def _template_zip(lang: str) -> Path:
    variant = "JA" if lang == "ja" else "EN"
    return PE_DIR / "dist" / f"BirthChartMuseum-PersonalEdition-{variant}-v{VERSION}.zip"


def ensure_template_zip(lang: str) -> Path:
    target = _template_zip(lang)
    if target.is_file():
        return target
    with _build_lock:
        if not target.is_file():
            subprocess.run(
                [sys.executable, str(PE_DIR / "build.py")],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
    if not target.is_file():
        raise RuntimeError("Personal Edition template ZIP was not created")
    return target


def _autoload_script(*, include_acg: bool) -> str:
    acg_link = """
      var acg = document.createElement('a');
      acg.href = '/acg/';
      acg.textContent = 'ACG · あなたの天空線';
      acg.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;padding:11px 16px;border-radius:999px;background:#c9a227;color:#0a1128;text-decoration:none;font-weight:700;box-shadow:0 5px 18px rgba(0,0,0,.35)';
      document.body.appendChild(acg);
""" if include_acg else ""
    return """
  <script>
  document.addEventListener('DOMContentLoaded', function () {
    fetch('/birth-chart.yaml', {cache: 'no-store'}).then(function (r) {
      if (!r.ok) throw new Error('chart not found');
      return r.text();
    }).then(function (yaml) {
      sessionStorage.setItem('ht-last-yaml', yaml);
      sessionStorage.setItem('ht-chart-pref', 'yaml');
      sessionStorage.setItem('ds-last-yaml', yaml);
      sessionStorage.setItem('ds-chart-pref', 'yaml');
      var input = document.getElementById('me-yaml-input');
      if (input) input.value = yaml;
    }).catch(function () {});
%s
  });
  </script>
""" % acg_link


def build_personalized_zip(*, yaml_text: str, lang: str, include_acg: bool = False) -> bytes:
    source_path = ensure_template_zip(lang)
    output = io.BytesIO()
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as target:
        root_name = None
        for item in source.infolist():
            data = source.read(item.filename)
            if root_name is None and "/" in item.filename:
                root_name = item.filename.split("/", 1)[0]
            if item.filename.endswith("/app/index.html"):
                html = data.decode("utf-8")
                html = html.replace("</head>", _autoload_script(include_acg=include_acg) + "</head>", 1)
                data = html.encode("utf-8")
            target.writestr(item, data)
        if not root_name:
            raise RuntimeError("Personal Edition ZIP root was not found")
        target.writestr(f"{root_name}/app/birth-chart.yaml", yaml_text.encode("utf-8"))
        if include_acg:
            acg_data = personal_geojson(yaml_text)
            target.writestr(
                f"{root_name}/app/acg-personal.geojson",
                json.dumps(acg_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            )
        target.writestr(
            f"{root_name}/YOUR_CHART.txt",
            ("Your personal birth chart is already installed.\n"
             if lang == "en" else "あなた専用の出生図データはインストール済みです。\n").encode("utf-8-sig"),
        )
    return output.getvalue()
