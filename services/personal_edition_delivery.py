from __future__ import annotations

import html
import io
import json
import re
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from services.acg_api import personal_geojson


ROOT = Path(__file__).resolve().parent.parent
PE_DIR = ROOT / "personal-edition"
VERSION = "1.1.5"
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


def _personal_acg_online_url(chart_url: str | None) -> str | None:
    if not chart_url:
        return None
    parts = urlsplit(chart_url)
    chart_path = parts.path.rstrip("/")
    online_path = f"{chart_path}/acg-app/"
    lang_query = [(key, value) for key, value in parse_qsl(parts.query) if key == "lang"]
    return urlunsplit(
        (parts.scheme, parts.netloc, online_path, urlencode(lang_query), "")
    )


def _acg_licenses() -> str:
    return """NANAMI ASTRO Personal ACG - Third-party licenses
==================================================

Leaflet 1.9.4
https://leafletjs.com/
Copyright (c) 2010-2023, Vladimir Agafonkin
License: BSD 2-Clause

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED.

Natural Earth
https://www.naturalearthdata.com/
Public domain map and place-name data.

OpenStreetMap
https://www.openstreetmap.org/copyright
Background map tiles are provided by OpenStreetMap contributors and are not
bundled in this package.
"""


def _standalone_acg_html(
    *,
    acg_html: str,
    leaflet_css: str,
    leaflet_js: str,
    acg_data: dict,
    city_data: dict,
    world_data: dict,
    chart_url: str | None,
    show_ipad_online_link: bool = False,
) -> str:
    """Build a file://-safe ACG app with personal data and Leaflet embedded."""
    data_json = json.dumps(acg_data, ensure_ascii=False, separators=(",", ":"))
    cities_json = json.dumps(city_data.get("cities", []), ensure_ascii=False, separators=(",", ":"))
    world_json = json.dumps(world_data, ensure_ascii=False, separators=(",", ":"))
    embedded_code = (
        f"data={data_json};render();renderPlaces();"
        "document.getElementById('status').textContent='計算基準: '+"
        "((data.meta&&data.meta.datetime_utc)||'確認済み出生日時');"
    )
    result = acg_html.replace(
        '<link rel="stylesheet" href="/static/vendor/leaflet/leaflet.css">',
        f"<style>\n{leaflet_css}\n</style>",
        1,
    ).replace(
        '<script src="/static/vendor/leaflet/leaflet.js"></script>',
        f"<script>\n{leaflet_js}\n</script>",
        1,
    )
    result, embedded_count = re.subn(
        r"/\* PERSONAL_ACG_DATA_START \*/.*?/\* PERSONAL_ACG_DATA_END \*/",
        embedded_code,
        result,
        count=1,
        flags=re.DOTALL,
    )
    result, city_embedded_count = re.subn(
        r"/\* PERSONAL_CITY_DATA_START \*/.*?/\* PERSONAL_CITY_DATA_END \*/",
        f"cityCatalog={cities_json};",
        result,
        count=1,
        flags=re.DOTALL,
    )
    result, world_embedded_count = re.subn(
        r"/\* PERSONAL_WORLD_DATA_START \*/.*?/\* PERSONAL_WORLD_DATA_END \*/",
        f"worldData={world_json};renderWorld();",
        result,
        count=1,
        flags=re.DOTALL,
    )
    if chart_url:
        result = result.replace('href="/"', f'href="{chart_url}"', 1)
        if show_ipad_online_link:
            online_url = _personal_acg_online_url(chart_url)
            ipad_link = (
                '<style>.ipad-online-acg{display:block;padding:9px 12px;background:#c9a227;'
                'color:#0a1128;text-decoration:none;font-size:.78rem;font-weight:700;'
                'text-align:center}</style>'
                '<a class="ipad-online-acg" href="'
                + html.escape(online_url, quote=True)
                + '">iPad・iPhone：オンラインACG地図を開く / Open online ACG map</a>'
            )
            result = result.replace("</header>", "</header>" + ipad_link, 1)
    else:
        result = result.replace('href="/"', 'href="#" onclick="return false"', 1)
    if (
        embedded_count != 1
        or city_embedded_count != 1
        or world_embedded_count != 1
        or "/acg-personal.geojson" in result
        or "cities.min.json" in result
        or "ne_110m_admin_0_countries.geojson" in result
    ):
        raise RuntimeError("Standalone ACG data embedding failed")
    return result


def build_personal_acg_html(*, yaml_text: str, chart_url: str | None = None) -> str:
    """Build the self-contained Personal ACG app used by web and ZIP delivery."""
    acg_html = (PE_DIR / "acg" / "index.html").read_text(encoding="utf-8")
    city_data = json.loads((PE_DIR / "acg" / "cities.min.json").read_text(encoding="utf-8"))
    leaflet_dir = ROOT / "static" / "vendor" / "leaflet"
    return _standalone_acg_html(
        acg_html=acg_html,
        leaflet_css=(leaflet_dir / "leaflet.css").read_text(encoding="utf-8"),
        leaflet_js=(leaflet_dir / "leaflet.js").read_text(encoding="utf-8"),
        acg_data=personal_geojson(yaml_text),
        city_data=city_data,
        world_data=json.loads((ROOT / "static" / "geo" / "ne_110m_admin_0_countries.geojson").read_text(encoding="utf-8")),
        chart_url=chart_url,
    )


def _acg_direct_start_readme(*, lang: str, chart_url: str | None) -> str:
    online_url = _personal_acg_online_url(chart_url)
    if lang == "en":
        online = (
            "\nYour personal online ACG app:\n"
            f"{online_url}\n"
            if online_url else ""
        )
        chart = f"\nYour private chart page:\n{chart_url}\n" if chart_url else ""
        return (
            "NANAMI ASTRO - PERSONAL ACG APP\n"
            "PLEASE READ THIS FILE FIRST\n\n"
            "WINDOWS / MAC (use the downloaded ZIP)\n"
            "1. Extract the complete ZIP archive.\n"
            "   Do not open START-ACG.html while it is still inside the ZIP.\n"
            "2. Open the extracted folder and double-click START-ACG.html.\n"
            "3. Your default browser opens your personal ACG map.\n"
            "No installation, App Store download, command file, PowerShell, or local server "
            "is required.\n\n"
            "IPAD / IPHONE (recommended: use the online ACG app in Safari)\n"
            "START-ACG.html may not display the map when opened from the Files app preview.\n"
            "1. Open your private chart page below in Safari.\n"
            "2. Expand 'Save your data'.\n"
            "3. Tap 'Open your Personal ACG app'.\n"
            "4. In the ACG app, tap 'Add to Home Screen' for guidance. Then tap Safari's "
            "Share button and select 'Add to Home Screen'.\n"
            "5. Next time, start it from the My ACG icon on your Home Screen.\n"
            "This is a web app, so there is nothing to install from the App Store. An internet "
            "connection is required.\n"
            + online
            + chart
            + "\nHOW TO USE THE MAP\n"
            "1. Select Basic, Work, Relationships, or All.\n"
            "2. Search for a city or click the map to add up to three places.\n"
            "3. Compare the nearest ACG lines shown for each place.\n"
            "4. Use 'Ask AI about the selected places' to copy a consultation prompt.\n"
            "5. Use Print to print the map and comparison or save them as a PDF.\n\n"
            "IF THE MAP DOES NOT APPEAR\n"
            "- iPad/iPhone: do not use the Files preview; open the online ACG app in Safari.\n"
            "- Windows/Mac: make sure the ZIP was fully extracted before opening the HTML.\n"
            "- Check your internet connection. Only the background map tiles are downloaded.\n\n"
            "Your personal birth data and ACG lines are embedded in START-ACG.html. "
            "Place-name search, personal ACG calculation, and comparison all run inside "
            "the file. Only background map tiles require an internet connection.\n"
            "Keep the ZIP and private URLs confidential. Personal use only; do not redistribute.\n"
        )
    online = f"\nあなた専用のオンラインACGアプリ：\n{online_url}\n" if online_url else ""
    chart = f"\n専用鑑定ページ：\n{chart_url}\n" if chart_url else ""
    return (
        "NANAMI ASTRO - 個人用ACGアプリ\n"
        "このファイルを最初にお読みください\n\n"
        "【Windows / Mac：ダウンロードしたZIPを使う】\n"
        "1. ZIPを右クリックし、「すべて展開」します。ZIPの中から直接開かないでください。\n"
        "2. 展開したフォルダー内の START-ACG.html をダブルクリックします。\n"
        "3. いつも使うブラウザで、あなた専用のACG地図が開きます。\n"
        "インストール、App Storeからのダウンロード、バッチファイル、PowerShell、"
        "ローカルサーバーは不要です。\n\n"
        "【iPad / iPhone：SafariのオンラインACGアプリがおすすめ】\n"
        "「ファイル」アプリのプレビューで START-ACG.html を開くと、地図が表示されないことがあります。\n"
        "1. 下記の専用鑑定ページをSafariで開きます。\n"
        "2. ページ内の「データを保存」を開きます。\n"
        "3. 「あなたのACGアプリを開く」を押します。\n"
        "4. ACG画面の「ホーム画面に追加」で案内を確認し、Safariの共有ボタンから"
        "「ホーム画面に追加」を選びます。\n"
        "5. 次回から、ホーム画面の「My ACG」アイコンで起動できます。\n"
        "Webアプリのため、App Storeからインストールするものはありません。利用時はインターネット接続が必要です。\n"
        + online
        + chart
        + "\n【地図の使い方】\n"
        "1. 「基本」「仕事」「人の縁」「すべて」から表示テーマを選びます。\n"
        "2. 都市名検索または地図クリックで、最大3地点を登録します。\n"
        "3. 各地点に近いACGラインとメッセージを比較します。\n"
        "4. 「選んだ場所の星のメッセージをAIに聞く」で、AI相談用の文章をコピーできます。\n"
        "5. 印刷ボタンから、地図と比較結果を印刷またはPDF保存できます。\n\n"
        "【地図が表示されないとき】\n"
        "・iPad / iPhone：「ファイル」アプリではなく、SafariでオンラインACGアプリを開いてください。\n"
        "・Windows / Mac：ZIPをすべて展開してから START-ACG.html を開いてください。\n"
        "・インターネット接続を確認してください。背景地図の表示には通信が必要です。\n\n"
        "出生データとACGラインはSTART-ACG.html内に保存されています。"
        "都市名検索・個人ACGの計算結果・比較処理はファイル内で動作します。"
        "インターネット接続を使用するのは背景地図だけです。\n"
        "ZIPと専用URLは他人に共有しないでください。個人利用専用です。再配布・転売は禁止です。\n"
    )


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


def _free_museum_readme(lang: str) -> str:
    if lang == "en":
        return (
            "BIRTH CHART MUSEUM + DREAM SKY - FREE EDITION\n\n"
            "IMPORTANT: Do not open HTML files inside the app folder directly.\n"
            "1. Extract the complete ZIP archive.\n"
            "2. Windows: double-click START-MUSEUM-WINDOWS.bat.\n"
            "   Mac: Control-click START-MUSEUM-MAC.command, then choose Open.\n"
            "3. Keep the server window open while using the Museum.\n"
            "4. Paste your astrology YAML at the entrance, or use the sample chart.\n\n"
            "This separate free package includes the Symbolic Museum, Architecture Museum, "
            "and Dream Sky. Personal ACG and the Personal Planner are not included.\n"
        )
    return (
        "出生図ミュージアム＋Dream Sky 無料版\n"
        "このファイルを最初にお読みください\n\n"
        "【重要】appフォルダー内のHTMLは直接開かないでください。\n"
        "1. ZIPを右クリックして「すべて展開」します。\n"
        "2. Windows：START-MUSEUM-WINDOWS.bat をダブルクリックします。\n"
        "   Mac：START-MUSEUM-MAC.command をControl＋クリックし、「開く」を選びます。\n"
        "3. 利用中は、起動時に表示されるサーバー画面を閉じないでください。\n"
        "4. 入口で占術データYAMLを貼り付けるか、サンプル出生図を選びます。\n\n"
        "この無料ZIPには、象徴ミュージアム、建築ミュージアム、Dream Skyが入っています。\n"
        "個人用ACGと個人プランナーは含まれません。\n"
    )


def _free_museum_direct_file_guard(lang: str) -> str:
    if lang == "en":
        title = "Please start the Museum from the START file"
        lead = "This page was opened directly from the app folder, so its design and features cannot load."
        steps = (
            "<li>Close this page and extract the complete ZIP archive.</li>"
            "<li>Windows: double-click <strong>START-MUSEUM-WINDOWS.bat</strong>.</li>"
            "<li>Mac: Control-click <strong>START-MUSEUM-MAC.command</strong>, then choose Open.</li>"
        )
        note = "Do not open HTML files inside the app folder directly."
    else:
        title = "STARTファイルからミュージアムを起動してください"
        lead = "appフォルダー内のHTMLを直接開いたため、デザインや機能を読み込めていません。"
        steps = (
            "<li>この画面を閉じ、ZIPを右クリックして「すべて展開」します。</li>"
            "<li>Windows：<strong>START-MUSEUM-WINDOWS.bat</strong> をダブルクリックします。</li>"
            "<li>Mac：<strong>START-MUSEUM-MAC.command</strong> をControl＋クリックし、「開く」を選びます。</li>"
        )
        note = "appフォルダー内のHTMLは直接開かないでください。"
    panel = (
        '<main class="museum-file-warning">'
        '<p class="museum-file-warning__eyebrow">BIRTH CHART MUSEUM + DREAM SKY</p>'
        f"<h1>{title}</h1><p>{lead}</p><ol>{steps}</ol>"
        f'<p class="museum-file-warning__note">{note}</p></main>'
    )
    return f"""
  <style id="museum-direct-file-style">
    html:has(.museum-file-warning), body:has(.museum-file-warning) {{ min-height: 100%; }}
    body:has(.museum-file-warning) {{ margin: 0 !important; padding: 28px !important; box-sizing: border-box;
      display: grid !important; place-items: center !important; background: #081127 !important;
      color: #f6f0df !important; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif !important; }}
    .museum-file-warning {{ width: min(680px, 100%); box-sizing: border-box; padding: clamp(28px, 6vw, 56px);
      border: 1px solid #c9a227; border-radius: 20px; background: #101b38; box-shadow: 0 18px 60px #0008; }}
    .museum-file-warning__eyebrow {{ color: #e2bd39 !important; font-size: 13px !important;
      font-weight: 800 !important; letter-spacing: .12em; }}
    .museum-file-warning h1 {{ margin: 12px 0 18px !important; color: #fff !important;
      font-size: clamp(26px, 5vw, 40px) !important; line-height: 1.35 !important; }}
    .museum-file-warning p, .museum-file-warning li {{ font-size: 17px !important; line-height: 1.8 !important; }}
    .museum-file-warning ol {{ margin: 24px 0; padding-left: 1.5em; }}
    .museum-file-warning li + li {{ margin-top: 10px; }}
    .museum-file-warning strong {{ color: #ffdc5b !important; overflow-wrap: anywhere; }}
    .museum-file-warning__note {{ margin: 24px 0 0 !important; padding: 14px 16px;
      border-radius: 10px; background: #e2bd3918; color: #ffdf70 !important; font-weight: 700 !important; }}
  </style>
  <script>
  if (window.location.protocol === 'file:') {{
    document.addEventListener('DOMContentLoaded', function () {{
      document.title = {json.dumps(title, ensure_ascii=False)};
      document.body.innerHTML = {json.dumps(panel, ensure_ascii=False)};
    }});
  }}
  </script>
"""


def build_free_museum_zip(lang: str = "ja") -> bytes:
    safe_lang = lang if lang in {"ja", "en"} else "ja"
    source_path = ensure_template_zip(safe_lang)
    output = io.BytesIO()
    free_root = "BirthChartMuseum-Free"
    excluded_prefixes = (
        "app/acg/",
        "app/static/vendor/leaflet/",
        "app/static/geo/",
    )
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            if "/" not in item.filename or item.is_dir():
                continue
            relative_name = item.filename.split("/", 1)[1]
            if (
                not relative_name
                or relative_name.startswith(excluded_prefixes)
                or relative_name.startswith("START-ACG-")
                or relative_name in {"README.txt", "YOUR_CHART.txt"}
            ):
                continue
            data = source.read(item.filename)
            if relative_name == "app/index.html":
                page = data.decode("utf-8")
                page = page.replace(
                    "</head>", _free_museum_direct_file_guard(safe_lang) + "</head>", 1
                )
                data = page.encode("utf-8")
            target.writestr(f"{free_root}/{relative_name}", data)
        readme_name = "README-FIRST.txt" if safe_lang == "en" else "00-はじめに_README.txt"
        target.writestr(
            f"{free_root}/{readme_name}",
            _free_museum_readme(safe_lang).encode("utf-8-sig"),
        )
    return output.getvalue()


def build_personalized_zip(
    *, yaml_text: str, lang: str, include_acg: bool = False, chart_url: str | None = None,
) -> bytes:
    source_path = ensure_template_zip(lang)
    output = io.BytesIO()
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as target:
        acg_html = None
        city_data = None
        city_json_data = None
        leaflet_css = None
        leaflet_js = None
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
            if relative_name == "app/acg/index.html":
                acg_html = data.decode("utf-8")
            elif relative_name == "app/acg/cities.min.json":
                city_json_data = data.decode("utf-8")
                city_data = json.loads(city_json_data)
            elif relative_name == "app/static/vendor/leaflet/leaflet.css":
                leaflet_css = data.decode("utf-8")
            elif relative_name == "app/static/vendor/leaflet/leaflet.js":
                leaflet_js = data.decode("utf-8")
            if include_acg:
                continue
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
        if not include_acg:
            target.writestr("app/birth-chart.yaml", yaml_text.encode("utf-8"))
        if include_acg:
            if city_data is None and city_json_data is None:
                fallback_city_path = PE_DIR / "acg" / "cities.min.json"
                if not fallback_city_path.is_file():
                    raise RuntimeError("Personal Edition ACG city data asset was not found")
                city_json_data = fallback_city_path.read_text(encoding="utf-8")
                city_data = json.loads(city_json_data)
            acg_data = personal_geojson(yaml_text)
            standalone_acg_html = acg_html
            if (
                standalone_acg_html is None
                or "/* PERSONAL_ACG_DATA_START */" not in standalone_acg_html
                or "/* PERSONAL_CITY_DATA_START */" not in standalone_acg_html
                or "/* PERSONAL_WORLD_DATA_START */" not in standalone_acg_html
            ):
                standalone_acg_html = (PE_DIR / "acg" / "index.html").read_text(
                    encoding="utf-8"
                )
            if (
                standalone_acg_html is None
                or city_data is None
                or leaflet_css is None
                or leaflet_js is None
                or not city_json_data
            ):
                raise RuntimeError("Personal Edition ACG assets were not found")
            target.writestr(
                "START-ACG.html",
                _standalone_acg_html(
                    acg_html=standalone_acg_html,
                    leaflet_css=leaflet_css,
                    leaflet_js=leaflet_js,
                    acg_data=acg_data,
                    city_data=city_data,
                    world_data=json.loads((ROOT / "static" / "geo" / "ne_110m_admin_0_countries.geojson").read_text(encoding="utf-8")),
                    chart_url=chart_url,
                    show_ipad_online_link=True,
                ).encode("utf-8"),
            )
            target.writestr("LICENSES.txt", _acg_licenses().encode("utf-8-sig"))
        guide = (
            _acg_direct_start_readme(lang=lang, chart_url=chart_url)
            if include_acg
            else _buyer_readme(lang=lang, include_acg=False, chart_url=chart_url)
        )
        guide_name = (
            "README-FIRST.txt"
            if lang == "en"
            else ("00-はじめに_README.txt" if include_acg else "はじめに_README.txt")
        )
        target.writestr(guide_name, guide.encode("utf-8-sig"))
        if chart_url:
            url_name = "PRIVATE-CHART-URL.txt" if lang == "en" else "専用鑑定ページ_URL.txt"
            target.writestr(url_name, (chart_url + "\n").encode("utf-8-sig"))
    return output.getvalue()
