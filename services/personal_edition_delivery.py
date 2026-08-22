from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

from services.acg_api import personal_geojson


ROOT = Path(__file__).resolve().parent.parent
PE_DIR = ROOT / "personal-edition"
VERSION = "1.1.4"
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


def _standalone_acg_html(
    *,
    acg_html: str,
    leaflet_css: str,
    leaflet_js: str,
    acg_data: dict,
    city_data: dict,
    world_data: dict,
    chart_url: str | None,
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
    if lang == "en":
        fallback = f"\nPrivate online backup page:\n{chart_url}\n" if chart_url else ""
        return (
            "NANAMI ASTRO - PERSONAL ACG APP\n\n"
            "QUICK START\n"
            "1. Extract the complete ZIP archive.\n"
            "2. Double-click START-ACG.html.\n"
            "3. Your browser opens your personal ACG map. No installation, command file, "
            "PowerShell, or local server is required.\n\n"
            "Search for or click up to three places to compare their nearest personal ACG "
            "lines. Use the Print button to print the comparison or save it as a PDF.\n"
            "Your personal birth data and ACG lines are embedded in START-ACG.html. "
            "Place-name search, personal ACG calculation, and comparison all run inside "
            "the file. Only background map tiles require an internet connection.\n"
            + fallback
            + "\nKeep this package private. Personal use only; do not redistribute.\n"
        )
    fallback = f"\nオンライン予備ページ：\n{chart_url}\n" if chart_url else ""
    return (
        "NANAMI ASTRO - 個人用ACGアプリ\n\n"
        "【起動方法】\n"
        "1. ZIPを右クリックし、「すべて展開」します。\n"
        "2. START-ACG.html をダブルクリックします。\n"
        "3. ブラウザであなた専用のACG地図が開きます。インストール、バッチファイル、"
        "PowerShell、ローカルサーバーは不要です。\n\n"
        "都市名検索または地図クリックで最大3地点を登録し、近いACGラインを比較できます。"
        "印刷ボタンから、比較結果の印刷またはPDF保存ができます。\n"
        "出生データとACGラインはSTART-ACG.html内に保存されています。"
        "都市名検索・個人ACGの計算結果・比較処理はファイル内で動作します。"
        "インターネット接続を使用するのは背景地図だけです。\n"
        + fallback
        + "\n個人利用専用です。このパッケージを再配布・転売しないでください。\n"
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
            if relative_name == "start.bat":
                relative_name = "START-MUSEUM-WINDOWS.bat"
            elif relative_name == "start.command":
                relative_name = "START-MUSEUM-MAC.command"
            elif relative_name in {"README.txt", "YOUR_CHART.txt"}:
                continue
            if include_acg and relative_name in {
                "START-ACG-WINDOWS.bat",
                "START-ACG-MAC.command",
            }:
                continue
            if relative_name == "app/index.html":
                html = data.decode("utf-8")
                html = html.replace("</head>", _autoload_script(include_acg=include_acg, lang=lang) + "</head>", 1)
                data = html.encode("utf-8")
            elif relative_name == "app/acg/index.html":
                acg_html = data.decode("utf-8")
            elif relative_name == "app/acg/cities.min.json":
                city_json_data = data.decode("utf-8")
                city_data = json.loads(city_json_data)
            elif relative_name == "app/static/vendor/leaflet/leaflet.css":
                leaflet_css = data.decode("utf-8")
            elif relative_name == "app/static/vendor/leaflet/leaflet.js":
                leaflet_js = data.decode("utf-8")
            target.writestr(relative_name, data)
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
            target.writestr(
                "app/acg-personal.geojson",
                json.dumps(acg_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            )
            if (
                standalone_acg_html is None
                or city_data is None
                or leaflet_css is None
                or leaflet_js is None
                or not city_json_data
            ):
                raise RuntimeError("Personal Edition ACG assets were not found")
            target.writestr("app/acg/cities.min.json", city_json_data.encode("utf-8"))
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
                ).encode("utf-8"),
            )
        guide = (
            _acg_direct_start_readme(lang=lang, chart_url=chart_url)
            if include_acg
            else _buyer_readme(lang=lang, include_acg=False, chart_url=chart_url)
        )
        guide_name = "README-FIRST.txt" if lang == "en" else "はじめに_README.txt"
        target.writestr(guide_name, guide.encode("utf-8-sig"))
        if chart_url:
            url_name = "PRIVATE-CHART-URL.txt" if lang == "en" else "専用鑑定ページ_URL.txt"
            target.writestr(url_name, (chart_url + "\n").encode("utf-8-sig"))
    return output.getvalue()
