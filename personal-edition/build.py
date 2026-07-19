#!/usr/bin/env python3
"""Birth Chart Museum — Personal Edition builder.

Web 公開版（templates/ + static/、FastAPI 配信）はそのまま維持し、
このスクリプトが「販売用ローカル版」を dist/ に生成する。

やること:
  1. Jinja テンプレート 3 枚（入口 / 抽象版 / 建築版）と dream-sky を
     プレーン HTML に変換（asset_url 展開・CDN → 同梱 vendor 差し替え・
     Google Fonts → ローカル fonts.css・サイト内リンク調整）
  2. static/house-tour, static/house-tour-architecture, favicon をコピー
  3. vendor（three.js / js-yaml / OrbitControls / Cinzel）と
     runtime（start.bat / start.command / server / README / LICENSES）を配置
  4. ZIP を作成（start.command に実行権限を付与して格納）

使い方:
  python personal-edition/build.py

出力:
  personal-edition/dist/BirthChartMuseum-PersonalEdition/   (フォルダ)
  personal-edition/dist/BirthChartMuseum-PersonalEdition-v<VERSION>.zip

テンプレート側の文言・構造が変わって置換が空振りした場合は
AssertionError で止まる（黙って壊れた ZIP を作らない）。
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

VERSION = "1.1.2"
PRODUCT = "BirthChartMuseum-PersonalEdition"

# 配布バリアント: Etsy=英語デフォルト / STORES=日本語デフォルト。
# 各HTMLに window.HT_DEFAULT_LANG を注入する（画面内の日英切替は両方に残る）。
VARIANTS = {"EN": "en", "JA": "ja"}

PE_DIR = Path(__file__).resolve().parent
REPO = PE_DIR.parent
TEMPLATES = REPO / "templates"
STATIC = REPO / "static"
DIST = PE_DIR / "dist"

# ビルド中に差し替わるグローバル（バリアントごとに main() 内で設定）
OUT = DIST / PRODUCT
APP = OUT / "app"

HEAD_ICONS = (
    '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">\n'
    '  <link rel="shortcut icon" href="/static/favicon.svg" type="image/svg+xml">\n'
    '  <link rel="apple-touch-icon" href="/static/favicon.svg">\n'
    '  <meta name="theme-color" content="#0A1128">'
)

GOOGLE_FONTS_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500'
    "&family=Noto+Sans+JP:wght@300;400;500&family=Noto+Serif+JP:wght@300;400;500"
    '&display=swap" rel="stylesheet">'
)

CDN_THREE = (
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'
)
CDN_JSYAML = (
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js"></script>'
)
CDN_ORBIT = (
    '<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>'
)


def must_sub(text: str, old: str, new: str, count: int, label: str) -> str:
    found = text.count(old)
    assert found == count, (
        f"[{label}] expected {count} occurrence(s) of:\n  {old!r}\nfound {found}. "
        "テンプレートが変わっています。build.py の置換を更新してください。"
    )
    return text.replace(old, new)


def strip_jinja(html: str, label: str) -> str:
    # Web Demo 専用ブロック（{% if demo %}…{% endif %}）は販売版に含めない
    html = re.sub(r"[ \t]*\{% if demo %\}.*?\{% endif %\}\n?", "", html, flags=re.S)
    html = re.sub(r"\{\{\s*asset_url\('([^']+)'\)\s*\}\}", r"/static/\1", html)
    html = re.sub(r"[ \t]*<!-- asset_version: \{\{ asset_version \}\} -->\n", "", html)
    html = must_sub(
        html, '{% include "_head_icons.html" %}', HEAD_ICONS, 1, label
    )
    return html


def localize_head(html: str, label: str, three: bool) -> str:
    html = must_sub(
        html, '  <link rel="preconnect" href="https://fonts.googleapis.com">\n', "", 1, label
    )
    html = must_sub(
        html,
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n',
        "",
        1,
        label,
    )
    html = must_sub(
        html,
        GOOGLE_FONTS_LINK,
        '<link rel="stylesheet" href="/vendor/fonts/fonts.css">',
        1,
        label,
    )
    if three:
        html = must_sub(
            html, CDN_THREE, '<script src="/vendor/three.min.js"></script>', 1, label
        )
        html = must_sub(
            html, CDN_JSYAML, '<script src="/vendor/js-yaml.min.js"></script>', 1, label
        )
    return html


def drop_site_links(html: str, label: str) -> str:
    """サイト内リンクの調整。ホームへ戻るリンクは Web 版から撤去済みなので、
    ここでは再混入していないことの検証と、入口URLのルート置き換えのみ行う。"""
    assert '<p class="ht-back">' not in html and '<p class="me-back">' not in html, (
        f"[{label}] ホームへ戻るリンクが再導入されています"
    )
    assert 'data-i18n="menu_home"' not in html, f"[{label}] menu_home が再導入されています"
    # 版切替リンクの「/birth-chart-museum」は入口 = ルートに置き換え
    html = html.replace('href="/birth-chart-museum"', 'href="/"')
    return html


def assert_offline(html: str, label: str) -> None:
    for marker in ("{{", "{%", "cdnjs.cloudflare.com", "fonts.googleapis.com",
                   "fonts.gstatic.com", "cdn.jsdelivr.net"):
        assert marker not in html, f"[{label}] 未処理の依存が残っています: {marker}"


def build_entrance() -> str:
    label = "entrance"
    html = (TEMPLATES / "birth_chart_museum.html").read_text(encoding="utf-8")
    html = strip_jinja(html, label)
    html = localize_head(html, label, three=False)
    html = drop_site_links(html, label)
    # 入口ロゴは自分自身（PEではルート）を指す。ラベルは製品名に。
    html = must_sub(
        html,
        '<a class="me-logo" href="/">NANAMI ASTRO</a>',
        '<a class="me-logo" href="/">BIRTH CHART MUSEUM · PERSONAL</a>',
        1,
        label,
    )
    assert_offline(html, label)
    return html


def build_house_tour() -> str:
    label = "house-tour"
    html = (TEMPLATES / "house_tour.html").read_text(encoding="utf-8")
    html = strip_jinja(html, label)
    html = localize_head(html, label, three=True)
    html = drop_site_links(html, label)
    assert_offline(html, label)
    return html


def build_architecture() -> str:
    label = "architecture"
    html = (TEMPLATES / "house_tour_architecture.html").read_text(encoding="utf-8")
    html = strip_jinja(html, label)
    html = localize_head(html, label, three=True)
    html = drop_site_links(html, label)
    assert_offline(html, label)
    return html


def build_dream_sky() -> str:
    label = "dream-sky"
    html = (STATIC / "dream-sky" / "index.html").read_text(encoding="utf-8")
    html = must_sub(html, CDN_THREE, '<script src="/vendor/three.min.js"></script>', 1, label)
    html = must_sub(html, CDN_ORBIT, '<script src="/vendor/OrbitControls.js"></script>', 1, label)
    html = must_sub(html, CDN_JSYAML, '<script src="/vendor/js-yaml.min.js"></script>', 1, label)
    # Web の /static/dream-sky/*.mp4 → PE では同ディレクトリ相対参照
    html = html.replace("/static/dream-sky/dream-backdrop.mp4", "./dream-backdrop.mp4")
    html = html.replace(
        "/static/dream-sky/grok-video-916142da-bf80-4377-8944-451fc843041f.mp4",
        "./dream-backdrop.mp4",
    )
    assert_offline(html, label)
    return html


def copy_static() -> None:
    ignore_docs = shutil.ignore_patterns("*.md")
    shutil.copytree(STATIC / "house-tour", APP / "static" / "house-tour", ignore=ignore_docs)
    shutil.copytree(
        STATIC / "house-tour-architecture",
        APP / "static" / "house-tour-architecture",
        ignore=ignore_docs,
    )
    shutil.copy2(STATIC / "favicon.svg", APP / "static" / "favicon.svg")


def copy_vendor() -> None:
    shutil.copytree(PE_DIR / "vendor", APP / "vendor")


def copy_runtime() -> None:
    rt = PE_DIR / "runtime"
    # start.bat は CRLF、start.command は LF で確実に出力する
    bat = (rt / "start.bat").read_text(encoding="utf-8").replace("\r\n", "\n")
    (OUT / "START-MUSEUM-WINDOWS.bat").write_bytes(
        bat.replace("\n", "\r\n").encode("utf-8")
    )
    acg_bat = (rt / "start-acg.bat").read_text(encoding="utf-8").replace("\r\n", "\n")
    (OUT / "START-ACG-WINDOWS.bat").write_bytes(
        acg_bat.replace("\n", "\r\n").encode("utf-8")
    )
    cmd = (rt / "start.command").read_text(encoding="utf-8").replace("\r\n", "\n")
    (OUT / "START-MUSEUM-MAC.command").write_bytes(cmd.encode("utf-8"))
    acg_cmd = (rt / "start-acg.command").read_text(encoding="utf-8").replace("\r\n", "\n")
    (OUT / "START-ACG-MAC.command").write_bytes(acg_cmd.encode("utf-8"))
    # README は古いメモ帳対策で BOM 付き UTF-8
    readme = (rt / "README.txt").read_text(encoding="utf-8")
    (OUT / "README.txt").write_bytes(readme.replace("\r\n", "\n").encode("utf-8-sig"))
    shutil.copy2(rt / "LICENSES.txt", OUT / "LICENSES.txt")
    (OUT / "tools").mkdir(parents=True, exist_ok=True)
    # PowerShell 5.1 は BOM なし UTF-8 を ANSI 扱いして日本語で壊れるため BOM 必須
    ps1 = (rt / "tools" / "server.ps1").read_text(encoding="utf-8-sig")
    (OUT / "tools" / "server.ps1").write_bytes(
        ps1.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")
    )
    py = (rt / "tools" / "server.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    (OUT / "tools" / "server.py").write_bytes(py.encode("utf-8"))


def inject_default_lang(html: str, lang: str, label: str) -> str:
    """配布設定としての初期言語を注入（URL ?lang → localStorage → これ → ブラウザ言語 → en）。"""
    marker = '<meta charset="utf-8">'
    return must_sub(
        html,
        marker,
        marker + f'\n  <script>window.HT_DEFAULT_LANG = "{lang}";</script>',
        1,
        label,
    )


def make_zip(variant: str) -> Path:
    zip_path = DIST / f"{PRODUCT}-{variant}-v{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(OUT.rglob("*")):
            if path.is_dir():
                continue
            arcname = f"{PRODUCT}/{path.relative_to(OUT).as_posix()}"
            info = zipfile.ZipInfo(arcname)
            data = path.read_bytes()
            # Mac でダブルクリック起動できるよう .command / .py に実行権限
            mode = 0o755 if path.suffix in (".command", ".py") else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return zip_path


def _clean_dir(path: Path) -> None:
    """rmtree。Windows で他プロセスが CWD として掴んでいて空ディレクトリ自体を
    消せない場合は、中身が空になっていれば続行してよい（再利用する）。"""
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except PermissionError:
        remaining = list(path.rglob("*"))
        assert not remaining, f"dist を削除できません（使用中）: {path}"


def build_variant(variant: str, lang: str) -> None:
    global OUT, APP
    OUT = DIST / f"{PRODUCT}-{variant}"
    APP = OUT / "app"

    _clean_dir(OUT)
    (APP / "house-tour").mkdir(parents=True)
    (APP / "house-tour-architecture").mkdir(parents=True)
    (APP / "dream-sky").mkdir(parents=True)
    (APP / "acg").mkdir(parents=True)
    (APP / "static").mkdir(parents=True, exist_ok=True)

    (APP / "index.html").write_text(
        inject_default_lang(build_entrance(), lang, "entrance-lang"),
        encoding="utf-8",
        newline="\n",
    )
    (APP / "house-tour" / "index.html").write_text(
        inject_default_lang(build_house_tour(), lang, "house-tour-lang"),
        encoding="utf-8",
        newline="\n",
    )
    (APP / "house-tour-architecture" / "index.html").write_text(
        inject_default_lang(build_architecture(), lang, "architecture-lang"),
        encoding="utf-8",
        newline="\n",
    )
    # dream-sky は i18n 非対応（日本語固定）なので注入しない
    (APP / "dream-sky" / "index.html").write_text(
        build_dream_sky(), encoding="utf-8", newline="\n"
    )
    shutil.copy2(PE_DIR / "acg" / "index.html", APP / "acg" / "index.html")
    # Dream Sky videos: overview sky + 12 house portal films
    ds_src = STATIC / "dream-sky"
    ds_dst = APP / "dream-sky"
    for name in ("dream-backdrop.mp4", "grok-video-916142da-bf80-4377-8944-451fc843041f.mp4"):
        src = ds_src / name
        if src.is_file():
            shutil.copy2(src, ds_dst / "dream-backdrop.mp4")
            break
    for n in range(1, 13):
        src = ds_src / f"grok-video-{n}house.mp4"
        if src.is_file():
            shutil.copy2(src, ds_dst / f"grok-video-{n}house.mp4")

    copy_static()
    shutil.copytree(STATIC / "vendor" / "leaflet", APP / "static" / "vendor" / "leaflet")
    copy_vendor()
    copy_runtime()
    zip_path = make_zip(variant)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"OK: {OUT}")
    print(f"OK: {zip_path}  ({size_mb:.1f} MB)")


def main() -> None:
    for required in (
        PE_DIR / "vendor" / "three.min.js",
        PE_DIR / "vendor" / "js-yaml.min.js",
        PE_DIR / "vendor" / "OrbitControls.js",
        PE_DIR / "vendor" / "fonts" / "fonts.css",
        PE_DIR / "vendor" / "fonts" / "cinzel-latin.woff2",
        PE_DIR / "vendor" / "fonts" / "cinzel-latin-ext.woff2",
    ):
        assert required.is_file(), f"vendor ファイルがありません: {required}"

    for variant, lang in VARIANTS.items():
        build_variant(variant, lang)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
