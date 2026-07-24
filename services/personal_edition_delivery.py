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
VERSION = "1.1.2"
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


def _autoload_script(*, include_acg: bool, lang: str) -> str:
    acg_link = ""
    if include_acg:
        acg_label = "View your ACG map" if lang == "en" else "あなたのACG地図を開く"
        acg_link = f"""
      var acg = document.createElement('a');
      acg.href = '/acg/';
      acg.textContent = {json.dumps(acg_label, ensure_ascii=False)};
      acg.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;padding:11px 16px;border-radius:999px;background:#c9a227;color:#0a1128;text-decoration:none;font-weight:700;box-shadow:0 5px 18px rgba(0,0,0,.35)';
      document.body.appendChild(acg);
"""
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

def _buyer_readme(*, lang: str, include_acg: bool, chart_url: str | None) -> str:
    if lang == "en":
        acg = (
            "\nACG (included with your bundle)\n"
            "- Windows: double-click START-ACG-WINDOWS.bat.\n"
            "- Mac: double-click START-ACG-MAC.command.\n"
            "- Online: open your private chart URL and select 'View your ACG map'.\n"
            "- You can also start the Museum, then select the gold ACG button.\n"
            "- Your personal ACG data is already installed; no YAML paste is required.\n"
            if include_acg else ""
        )
        url = f"\nPrivate chart page\n{chart_url}\n" if chart_url else ""
        return (
            "BIRTH CHART MUSEUM - PERSONAL EDITION\n\n"
            "QUICK START\n"
            + ("ACG on Windows: double-click START-ACG-WINDOWS.bat\nACG on Mac: double-click START-ACG-MAC.command\n" if include_acg else "") +
            "Windows: unzip everything, then double-click START-MUSEUM-WINDOWS.bat\n"
            "Mac: unzip everything, then double-click START-MUSEUM-MAC.command\n"
            "Keep the black server window open while using the Museum. Close it when finished.\n\n"
            "WHAT EACH ITEM DOES\n"
            + ("- START-ACG-WINDOWS.bat: opens your personal ACG map on Windows.\n- START-ACG-MAC.command: opens your personal ACG map on Mac.\n" if include_acg else "") +
            "- START-MUSEUM-WINDOWS.bat: starts the Museum on Windows.\n"
            "- START-MUSEUM-MAC.command: starts the Museum on Mac.\n"
            "- app: application files. Do not move or delete this folder.\n"
            "- OPEN-ONLINE-CHART.url / PRIVATE-CHART-URL.txt: opens your private online chart.\n\n"
            "MUSEUM\n"
            "The START file opens the Birth Chart Museum in your browser. Your birth chart is already installed.\n"
            + acg + url +
            "\nPrivacy: the local edition runs only on your computer. Personal use only; do not redistribute.\n"
        )
    acg = (
        "\n【ACG（ACG Bundleに含まれます）】\n"
        "・Windows：START-ACG-WINDOWS.bat をダブルクリックします。\n"
        "・Mac：START-ACG-MAC.command をダブルクリックします。\n"
        "・オンライン：専用鑑定ページの「あなたのACG地図を見る」を押します。\n"
        "・ミュージアム画面の金色のACGボタンから開くこともできます。\n"
        "・あなた専用のACGデータは設定済みです。YAMLの貼り付けは不要です。\n"
        if include_acg else ""
    )
    url = f"\n【専用鑑定ページ】\n{chart_url}\n" if chart_url else ""
    museum_step = 3 if include_acg else 2
    browser_step = museum_step + 1
    close_step = museum_step + 2
    return (
        "BIRTH CHART MUSEUM - PERSONAL EDITION\n"
        "購入者さま向け はじめにお読みください\n\n"
        "【最初にすること】\n"
        "1. ZIPを右クリックして「すべて展開」します。ZIPの中から直接起動しないでください。\n"
        + ("2. ACGを開く：WindowsはSTART-ACG-WINDOWS.bat、MacはSTART-ACG-MAC.commandをダブルクリックします。\n" if include_acg else "") +
        f"{museum_step}. ミュージアムを開く：WindowsはSTART-MUSEUM-WINDOWS.bat をダブルクリックします。\n"
        "   Mac：START-MUSEUM-MAC.command をダブルクリックします。\n"
        f"{browser_step}. ブラウザで画面が自動的に開きます。出生データは設定済みです。\n"
        f"{close_step}. 使用中は黒いサーバー画面を閉じないでください。終了時に閉じます。\n\n"
        "【ファイルの役割】\n"
        + ("・START-ACG-WINDOWS.bat：Windowsであなた専用のACG地図を開きます。\n・START-ACG-MAC.command：Macであなた専用のACG地図を開きます。\n" if include_acg else "") +
        "・START-MUSEUM-WINDOWS.bat：Windowsでミュージアムを起動します。\n"
        "・START-MUSEUM-MAC.command：Macでミュージアムを起動します。\n"
        "・appフォルダー：アプリ本体です。移動・削除しないでください。\n"
        "・OPEN-ONLINE-CHART.url：Windowsで専用鑑定ページを開きます。\n"
        "・専用鑑定ページ_URL.txt：専用鑑定ページURLの控えです。\n\n"
        "【ミュージアム】\n"
        "STARTファイルを押すとミュージアムが起動します。YAMLを貼り付ける必要はありません。\n"
        + acg + url +
        "\n【ご注意】\n"
        "ローカル版はお使いのパソコン内だけで動作します。個人利用専用です。再配布・転売はしないでください。\n"
    )


def build_personalized_zip(
    *, yaml_text: str, lang: str, include_acg: bool = False, chart_url: str | None = None,
    planner_pdf: bytes | None = None,
) -> bytes:
    source_path = ensure_template_zip(lang)
    output = io.BytesIO()
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as target:
        source_names = source.namelist()
        root_name = next((name.split("/", 1)[0] for name in source_names if "/" in name), None)
        if not root_name:
            raise RuntimeError("Personal Edition ZIP root was not found")
        for item in source.infolist():
            if "/" not in item.filename:
                continue
            relative_name = item.filename.split("/", 1)[1]
            if not relative_name or item.is_dir():
                continue
            data = source.read(item.filename)
            if relative_name == "start.bat":
                relative_name = "START-MUSEUM-WINDOWS.bat"
            elif relative_name == "start.command":
                relative_name = "START-MUSEUM-MAC.command"
            elif relative_name in {"README.txt", "YOUR_CHART.txt"}:
                continue
            if relative_name == "app/index.html":
                html = data.decode("utf-8")
                html = html.replace("</head>", _autoload_script(include_acg=include_acg, lang=lang) + "</head>", 1)
                data = html.encode("utf-8")
            target.writestr(relative_name, data)
        target.writestr("app/birth-chart.yaml", yaml_text.encode("utf-8"))
        if planner_pdf:
            planner_name = "Personal-Planner.pdf" if lang == "en" else "パーソナル・プランナー.pdf"
            target.writestr(planner_name, planner_pdf)
        if include_acg:
            acg_data = personal_geojson(yaml_text)
            target.writestr(
                "app/acg-personal.geojson",
                json.dumps(acg_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            )
        guide = _buyer_readme(lang=lang, include_acg=include_acg, chart_url=chart_url)
        guide_name = "README-FIRST.txt" if lang == "en" else "はじめに_README.txt"
        target.writestr(guide_name, guide.encode("utf-8-sig"))
        if chart_url:
            url_name = "PRIVATE-CHART-URL.txt" if lang == "en" else "専用鑑定ページ_URL.txt"
            target.writestr(url_name, (chart_url + "\n").encode("utf-8-sig"))
            target.writestr(
                "OPEN-ONLINE-CHART.url",
                ("[InternetShortcut]\r\nURL=" + chart_url + "\r\n").encode("utf-8"),
            )
    return output.getvalue()
