"""四柱推命の申込フォーム（基本版・FULL版）の文言と性別欄の初期値（2026-10-21）。"""
import re
from html import unescape

import pytest
from fastapi.testclient import TestClient

import routes

JAPANESE = re.compile(r"[぀-ヿ一-鿿！-｠]")


def _visible_text(html: str) -> str:
    body = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    return unescape(re.sub(r"<[^>]+>", "\n", body))


def _gender_select(html: str) -> str:
    return re.search(r'<select name="gender" required>(.*?)</select>', html, flags=re.S).group(1)


def _selected_gender(html: str) -> str | None:
    options = re.findall(r'<option value="([^"]*)"\s*(selected)?', _gender_select(html))
    chosen = [value for value, selected in options if selected]
    assert len(chosen) <= 1
    return chosen[0] if chosen else None


@pytest.mark.parametrize("slug", ["shichu-full", "shichu"])
def test_gender_starts_unselected_so_buyers_must_choose(slug):
    html = TestClient(routes.app).get(f"/redeem/{slug}?lang=ja&provider=stores").text
    options = re.findall(r'<option value="([^"]*)"', _gender_select(html))
    assert options == ["", "female", "male", "unknown"]
    assert _selected_gender(html) == ""
    assert "選択してください" in _gender_select(html)


@pytest.mark.parametrize("gender", ["female", "male", "unknown"])
def test_gender_choice_survives_form_error(gender):
    response = TestClient(routes.app).post("/redeem/shichu-full?lang=ja&provider=stores", data={
        "order_code": "1234567890", "order_provider": "stores", "birth_date": "1990-05-10",
        "birth_time": "10:00", "prefecture": "東京都", "gender": gender, "day_change_at_23": "false",
    })
    assert response.status_code == 400
    assert _selected_gender(response.text) == gender


def test_full_form_is_english_with_lang_en():
    html = TestClient(routes.app).get("/redeem/shichu-full?lang=en&provider=stores").text
    leftover = sorted({line.strip() for line in _visible_text(html).splitlines() if JAPANESE.search(line)})
    assert leftover == []
    assert "Four Pillars FULL" in html and "Sex at birth" in html and "First year of the annual forecast" in html
    assert '"annualFrom": "10 years from {year}"' in html


def test_full_form_keeps_japanese_copy_with_lang_ja():
    html = TestClient(routes.app).get("/redeem/shichu-full?lang=ja&provider=stores").text
    for copy in ("四柱推命FULL版", "STORES購入完了メールの件名にある10桁の番号です。", "年運の開始年",
                 "入力内容を確認しました。送信後に変更できないことに同意します。"):
        assert copy in html
    assert "Sex at birth" not in html


def test_basic_form_time_note_is_four_pillars_copy():
    html = TestClient(routes.app).get("/redeem/shichu?lang=ja&provider=stores").text
    assert "ASC" not in html and "ハウス" not in html
    assert "時刻が不明・推定の場合、時柱は参考値になります。" in html
