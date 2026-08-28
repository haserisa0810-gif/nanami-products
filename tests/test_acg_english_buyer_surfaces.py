from __future__ import annotations

from html.parser import HTMLParser
import io
from pathlib import Path
import re
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

import routes
from services.birth_time import resolve_birth_time_accuracy
from services.common_access_package import build_common_access_package
from services.personal_edition_delivery import build_personalized_zip


client = TestClient(routes.app)
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.parts.append(data)


def _visible_text(html: str) -> str:
    parser = _VisibleText()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def test_etsy_acg_start_page_uses_english_product_copy() -> None:
    response = client.get("/start/acg-bundle?lang=en&provider=etsy")
    assert response.status_code == 200
    visible = _visible_text(response.text)
    assert "Astrocartography (ACG) bundle" in visible
    assert "personal astrocartography tools" in visible
    assert not JAPANESE.search(visible)


@pytest.mark.parametrize(
    ("lang", "japan_label", "outside_japan_label"),
    [
        ("ja", "日本国内", "日本国外"),
        ("en", "Japan", "Outside Japan"),
        ("es", "Japón", "Fuera de Japón"),
        ("de", "Japan", "Außerhalb Japans"),
    ],
)
def test_acg_forms_localize_japan_region_and_preserve_internal_prefecture_value(
    lang: str, japan_label: str, outside_japan_label: str,
) -> None:
    for url in (
        f"/redeem/acg-bundle?lang={lang}&provider=etsy",
        f"/personal-edition/activate?lang={lang}",
    ):
        response = client.get(url)
        assert response.status_code == 200
        visible = _visible_text(response.text)
        assert japan_label in visible
        expected_outside_label = (
            "海外" if lang == "ja" and url.startswith("/personal-edition/")
            else outside_japan_label
        )
        assert expected_outside_label in visible
        if lang == "ja":
            assert "東京都" in visible
        else:
            assert "Tokyo" in visible
            assert "Hokkaido" in visible
            assert "東京都" not in visible
            assert not JAPANESE.search(visible)
        # Resolver-facing values intentionally stay Japanese for compatibility.
        assert 'value="東京都"' in response.text


def test_english_birth_time_error_is_localized() -> None:
    try:
        resolve_birth_time_accuracy(selected_accuracy="exact", birth_time="", lang="en")
    except ValueError as exc:
        assert str(exc) == "Enter the birth time when Exact time is selected."
        assert not JAPANESE.search(str(exc))
    else:
        raise AssertionError("Expected an exact-time validation error")


def test_public_acg_errors_have_stable_codes_and_selected_language() -> None:
    english = client.get("/api/acg/mundane?date=not-a-date&lang=en")
    japanese = client.get("/api/acg/mundane?date=not-a-date&lang=ja")
    assert english.status_code == japanese.status_code == 400
    assert english.json()["error_code"] == japanese.json()["error_code"] == "date_format"
    assert english.json()["error"] == "Enter the date in YYYY-MM-DD format."
    assert "日付" in japanese.json()["error"]


def test_english_acg_map_and_globe_use_english_visible_chrome() -> None:
    map_response = client.get("/acg?lang=en")
    assert map_response.status_code == 200
    assert "ogp_acg_en.jpg" in map_response.text
    assert 'content: "Map"' in map_response.text
    assert "GSI Map" in map_response.text
    assert "lang=" in map_response.text and "globe-demo" in map_response.text
    assert not JAPANESE.search(_visible_text(map_response.text))

    globe_response = client.get("/acg/globe-demo?lang=en")
    assert globe_response.status_code == 200
    assert '<html lang="en">' in globe_response.text
    assert "How Astrocartography Works" in _visible_text(globe_response.text)
    assert not JAPANESE.search(_visible_text(globe_response.text))


def test_language_specific_acg_og_images_exist_at_social_share_size() -> None:
    for lang in ("en", "es", "de"):
        path = Path(f"static/ogp_acg_{lang}.jpg")
        assert path.is_file()
        with Image.open(path) as image:
            assert image.size == (1200, 630)


def test_existing_no_lang_acg_route_remains_japanese() -> None:
    response = client.get("/acg")
    assert response.status_code == 200
    assert '<html lang="ja">' in response.text
    assert "ACG 天空線マップ" in response.text


def test_current_english_distribution_packages_have_english_buyer_surfaces() -> None:
    common = build_common_access_package(
        redeem_url="https://chart.nanami-astro.com/redeem/acg-bundle?lang=en&provider=etsy",
        lang="en",
    )
    with zipfile.ZipFile(io.BytesIO(common)) as archive:
        combined = "\n".join(
            archive.read(name).decode("utf-8-sig") for name in archive.namelist()
        )
    assert "Etsy order number" in combined
    assert not JAPANESE.search(combined)

    yaml_text = Path("data/demo/chief_editor_neko.yaml").read_text(encoding="utf-8")
    personal = build_personalized_zip(
        yaml_text=yaml_text,
        lang="en",
        include_acg=True,
        chart_url="https://chart.nanami-astro.com/demo/neko?lang=en",
    )
    with zipfile.ZipFile(io.BytesIO(personal)) as archive:
        readme = archive.read("README-FIRST.txt").decode("utf-8-sig")
        start_html = archive.read("START-ACG.html").decode("utf-8-sig")
    assert "PERSONAL ACG APP" in readme
    assert not JAPANESE.search(readme)
    # Embedded scripts intentionally retain locale dictionaries and approved
    # Japanese place-name search data; only buyer-visible HTML is language-pure.
    assert not JAPANESE.search(_visible_text(start_html))
