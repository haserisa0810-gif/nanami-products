"""四柱推命の基本版（NP-SC）／FULL版（NP-SCF）の出し分けと、既存購入者の旧原本の固定。

旧原本の固定指示文（services/shichusuimei_legacy_prompts.py）は、本番 8c25fc0 の
services/prompt_builder.py を実行して生成した。再生成するときは 8c25fc0 の services/ と
config.py を一時ディレクトリへ展開し、build_prompt(include_shichusuimei=True,
birth_time_accuracy=..., interpretation_flags=_interpretation_flags(...), lang=...) と
build_chart_companion_prompt(lang=..., include_shichusuimei=True) の出力を書き出す。
"""
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
import yaml
from fastapi.testclient import TestClient

import routes
from services import product_catalog
from services.shichusuimei_editions import is_legacy_shichu_doc, legacy_companion_prompt
from services.shichusuimei_legacy_prompts import LEGACY_COMPANION_PROMPTS, LEGACY_READING_PROMPTS
from services.yaml_exporter import build_product_yaml, build_prompt_for_doc

ARGS = dict(title=None, birth_date="1990-05-10", birth_time="10:00", prefecture="東京都", gender="male")

# 本番 8c25fc0（エンジン0.3.0）の normalized_data の項目。基本版はこの項目を維持する。
LEGACY_NORMALIZED_KEYS = {
    "pillars", "hidden_stems", "main_hidden_stems", "ten_gods", "five_elements", "twelve_fortune",
    "kubo", "daiun", "interactions", "annual_fortune", "shinsatsu",
}
# 基本版で追加を許す項目は、計算の不確実性を示すものだけ。
BASIC_BUGFIX_KEYS = {"time_sensitive_reference"}
FULL_ONLY_KEYS = {"structural_analysis", "annual_forecasts"}
FULL_ONLY_ITEM_KEYS = {"structural_analysis", "special_relations_natal"}


# --- 出力範囲 ---------------------------------------------------------------------

def test_basic_edition_keeps_legacy_items_without_full_analysis():
    _text, _prompt, doc = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    shichu = doc["systems"]["shichusuimei"]
    nd = shichu["normalized_data"]
    assert shichu["edition"] == "basic"
    assert doc["product"]["options"]["shichusuimei_edition"] == "basic"
    assert LEGACY_NORMALIZED_KEYS <= set(nd) <= LEGACY_NORMALIZED_KEYS | BASIC_BUGFIX_KEYS
    assert len(nd["daiun"]["items"]) == 10
    assert all("structural_analysis" not in item for item in nd["daiun"]["items"])
    assert "structural_analysis" not in nd["annual_fortune"]
    assert "structural_analysis" not in (nd["annual_fortune"]["current_daiun"] or {})
    assert "structural_time_basis" not in shichu["input"]["assumptions"]


def test_basic_edition_withholds_daiun_on_solar_term_day_without_full_wording():
    # 2024-03-05 は啓蟄の当日。時刻不明では月柱が確定しないため大運を保留する（D-1）。
    args = {**ARGS, "birth_date": "2024-03-05", "birth_time": None}
    _text, _prompt, doc = build_product_yaml(**args, include_shichusuimei=True, shichusuimei_edition="basic")
    shichu = doc["systems"]["shichusuimei"]
    nd = shichu["normalized_data"]
    assert nd["daiun"]["status"] == "undetermined_month_pillar"
    assert nd["daiun"]["items"] == [] and nd["daiun"]["candidates"]
    joined = " ".join(shichu["unknowns"]) + nd["time_sensitive_reference"]["note"]
    assert "年別予測" not in joined and "構造分析" not in joined


def test_basic_edition_has_no_special_relations():
    _text, _prompt, doc = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    shichu = doc["systems"]["shichusuimei"]
    nd = shichu["normalized_data"]
    assert all(not FULL_ONLY_ITEM_KEYS & set(item) for item in nd["daiun"]["items"])
    assert not {"special_relations_natal", "special_relations_daiun", "structural_analysis"} & set(nd["annual_fortune"])
    assert "special_relations_rules" not in shichu["input"]["assumptions"]


def test_full_edition_has_ten_cycles_ten_year_forecast_and_structure():
    _text, _prompt, doc = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    nd = doc["systems"]["shichusuimei"]["normalized_data"]
    assert doc["systems"]["shichusuimei"]["edition"] == "full"
    assert FULL_ONLY_KEYS <= set(nd)
    assert len(nd["daiun"]["items"]) == 10
    assert len(nd["annual_forecasts"]["items"]) == 10
    assert all(FULL_ONLY_ITEM_KEYS <= set(item) for item in nd["daiun"]["items"])
    current = nd["annual_fortune"]["current_daiun"]
    assert FULL_ONLY_ITEM_KEYS <= set(current)
    assert "special_relations_natal" in nd["annual_forecasts"]["items"][0]


def test_basic_and_full_share_the_same_calculation():
    _t1, _p1, basic = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    _t2, _p2, full = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    b = basic["systems"]["shichusuimei"]["normalized_data"]
    f = full["systems"]["shichusuimei"]["normalized_data"]
    assert b["pillars"] == f["pillars"]
    assert [(i["kanshi"], i["age_from"]) for i in b["daiun"]["items"]] == \
        [(i["kanshi"], i["age_from"]) for i in f["daiun"]["items"]]
    assert basic["meta"]["chart_id"] != full["meta"]["chart_id"]


def test_unknown_edition_is_rejected():
    with pytest.raises(ValueError):
        build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="premium")


# --- 商品コード -----------------------------------------------------------------------

def test_full_product_code_is_registered_without_touching_existing_codes():
    assert product_catalog.product_for_sku("NP-SCF").product_type == "shichu_full"
    assert product_catalog.product_for_sku("NP-SC").product_type == "shichu"
    assert product_catalog.resolve_text("[NP-SCF] 四柱推命FULL版") == "shichu_full"
    assert product_catalog.resolve_text("[NP-SC] 四柱推命 命式データ") == "shichu"
    assert product_catalog.product_for_sku("NP-SFULL") is None  # 予約のまま
    assert not product_catalog.verified_identity("shichu", "NP-SCF")
    assert not product_catalog.verified_identity("shichu_full", "NP-SC")


# --- 旧原本（既存購入者） -----------------------------------------------------------

def _legacy_doc(accuracy="exact", version="0.3.0", options=True, **shichu_extra):
    return {
        "birth_time": {"accuracy": accuracy},
        "interpretation_flags": {"use_houses_as_reference_only": accuracy != "exact"},
        **({"product": {"options": {"western_natal": False, "shichusuimei": True}}} if options else {}),
        "systems": {"western": None, "shichusuimei": {
            "engine_version": version, "normalized_data": {"pillars": {}}, **shichu_extra}},
    }


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
@pytest.mark.parametrize("accuracy,key", [("exact", "exact"), ("unknown", "time_sensitive"),
                                          ("approximate", "time_sensitive")])
def test_legacy_original_gets_production_prompt(lang, accuracy, key):
    doc = _legacy_doc(accuracy)
    assert is_legacy_shichu_doc(doc)
    assert build_prompt_for_doc(doc, include_shichusuimei=True, lang=lang) == LEGACY_READING_PROMPTS[f"{lang}:{key}"]


@pytest.mark.parametrize("doc", [
    _legacy_doc(version="0.5.1"),
    _legacy_doc(edition="basic"),
    _legacy_doc(version=None),
])
def test_new_or_unversioned_documents_are_not_legacy(doc):
    assert not is_legacy_shichu_doc(doc)
    assert build_prompt_for_doc(doc, include_shichusuimei=True) not in LEGACY_READING_PROMPTS.values()


def test_legacy_prompts_have_no_new_rules():
    for text in [*LEGACY_READING_PROMPTS.values(), *LEGACY_COMPANION_PROMPTS.values()]:
        for term in ("structural_analysis", "annual_forecasts", "undetermined_month_pillar", "year_selection",
                     "special_relations"):
            assert term not in text
    assert legacy_companion_prompt("xx") == LEGACY_COMPANION_PROMPTS["ja"]


def test_legacy_prompt_does_not_modify_document():
    doc = _legacy_doc()
    before = deepcopy(doc)
    build_prompt_for_doc(doc, include_shichusuimei=True)
    assert doc == before


# --- 画面（既存購入者は変わらない／FULLは別画面） ---------------------------------

def _chart(doc, product_type="shichu", prompt_text="保存済みの指示文"):
    return {"token": "fictional", "options": {"product_type": product_type, "shichusuimei": True},
            "yaml_text": yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
            "prompt_text": prompt_text, "buyer_name": "架空例", "birth_date": "1990-05-10",
            "birth_place": "東京都", "expires_at": datetime.now(timezone.utc) + timedelta(days=1)}


@pytest.fixture
def client_for(monkeypatch):
    def make(chart):
        monkeypatch.setattr(routes.pg_store, "get_chart", lambda token, **kw: deepcopy(chart) if token == "fictional" else None)
        monkeypatch.setattr(routes.pg_store, "init_db", lambda *a, **kw: None)
        monkeypatch.setattr(routes.pg_store, "redeem_and_save", lambda *a, **kw: pytest.fail("No DB writes"))
        return TestClient(routes.app)
    return make


def test_legacy_chart_prompt_matches_production(client_for):
    doc = _legacy_doc("unknown")
    chart = _chart(doc)
    assert routes._chart_prompt_for_yaml_text(chart, chart["yaml_text"], lang="ja") == LEGACY_READING_PROMPTS["ja:time_sensitive"]
    # product.options のない古い原本は、本番と同じく保存済みの指示文を返す。
    bare = _chart(_legacy_doc(options=False))
    assert routes._chart_prompt_for_yaml_text(bare, bare["yaml_text"], lang="ja") == "保存済みの指示文"


def test_legacy_basic_chart_page_has_no_year_selection_and_production_companion(client_for):
    client = client_for(_chart(_legacy_doc()))
    page = client.get("/chart/fictional")
    assert page.status_code == 200
    assert "/year-selection" not in page.text
    assert client.get("/chart/fictional/year-selection").status_code == 404


def test_full_chart_offers_year_selection(client_for):
    _text, _prompt, doc = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    client = client_for(_chart(doc, product_type="shichu_full"))
    assert "/chart/fictional/year-selection" in client.get("/chart/fictional").text
    assert client.get("/chart/fictional/year-selection").status_code == 200


def test_new_basic_chart_has_no_year_selection(client_for):
    _text, _prompt, doc = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    client = client_for(_chart(doc))
    assert "/year-selection" not in client.get("/chart/fictional").text
    assert client.get("/chart/fictional/year-selection").status_code == 404


def test_full_and_basic_have_separate_redeem_pages():
    client = TestClient(routes.app)
    full = client.get("/redeem/shichu-full")
    basic = client.get("/redeem/shichu")
    assert full.status_code == basic.status_code == 200
    assert 'name="product_type" value="shichu_full"' in full.text and "四柱推命FULL版" in full.text
    assert 'name="product_type" value="shichu"' in basic.text and "四柱推命FULL版" not in basic.text
    assert routes._buyer_template("redeem", "shichu_full") == "redeem_shichu_full.html"
    assert routes._buyer_template("start", "shichu_full") == "start_shichu_full.html"
    assert client.get("/start/shichu-full").status_code == 200


def test_basic_redeem_template_preserves_production_except_wait_notice():
    import hashlib
    text = (Path(__file__).parents[1] / "templates/redeem_shichu.html").read_bytes().replace(b"\r\n", b"\n")
    # 2026-10-15: explicitly approved waiting notice is the only allowed change.
    notice = '        <p class="hint" id="generation-wait-notice">{{ t.submit_loading_desc }}</p>\n'.encode("utf-8")
    modal_desc = b"desc: {{ t.submit_loading_desc | tojson }},"
    assert text.count(notice) == 1
    assert text.count(modal_desc) == 1
    text = text.replace(notice, b"").replace(modal_desc, "desc: '完了までしばらくお待ちください。',".encode("utf-8"))
    # Keep the original production hash after removing only the approved copy changes.
    assert hashlib.sha256(text).hexdigest() == "c183fb79353156242fac0f34c37be31713bd7573408fefb8231c6dafe6030b77"


@pytest.mark.parametrize("product_type,edition", [("shichu", "basic"), ("shichu_full", "full")])
def test_each_product_maps_to_its_edition(product_type, edition):
    assert routes.PRODUCT_CONFIG[product_type]["include_shichusuimei"] is True
    assert routes.edition_for_product_type(product_type) == edition
    source = Path(routes.__file__).read_text(encoding="utf-8")
    assert '"shichusuimei_edition": edition_for_product_type(product_type)' in source


@pytest.mark.parametrize("slug,product_type,edition", [("shichu-full", "shichu_full", "full"), ("shichu", "shichu", "basic")])
def test_redeem_saves_each_product_with_its_edition(monkeypatch, slug, product_type, edition):
    saved = {}
    monkeypatch.setattr(routes, "_check_order_for_redeem",
                        lambda **kw: ("ok", {"product_type": kw["product_type"], "payment_status": "paid"}, None, 200))
    monkeypatch.setattr(routes.pg_store, "redeem_and_save", lambda **kw: saved.update(kw) or True)
    monkeypatch.setattr(routes.pg_store, "init_db", lambda *a, **kw: None)
    response = TestClient(routes.app).post(f"/redeem/{slug}?lang=ja", data={
        "order_code": "1234567890", "order_provider": "stores", "birth_date": "1990-05-10",
        "birth_time": "10:00", "prefecture": "東京都", "gender": "male",
        "day_change_at_23": "false", "agree_final": "1"}, follow_redirects=False)
    assert response.status_code == 303
    assert saved["options"]["product_type"] == product_type
    doc = yaml.safe_load(saved["yaml_text"])
    assert doc["systems"]["shichusuimei"]["edition"] == edition
    assert ("annual_forecasts" in doc["systems"]["shichusuimei"]["normalized_data"]) is (edition == "full")
    assert saved["shichusuimei_svg"]


@pytest.mark.parametrize("channel", ["stores", "etsy"])
def test_full_order_cannot_issue_another_product(channel):
    from unittest.mock import patch
    from services import stores_mail_sync as sync
    row = {"provider": channel, "product_type": "shichu_full", "payment_status": "paid", "sku": "NP-SCF"}
    with patch.object(sync, "verify_order_entitlement", return_value=("ok", row)),          patch.object(routes, "_verify_strict_stores_order", return_value=("ok", row)):
        for requested in ("western_full", "shichu"):
            result = routes._check_order_for_redeem(order_id="9123456789", provider=channel, product_type=requested)
            assert result[0] != "ok" and result[3] == 409


@pytest.mark.parametrize("provider,order_code", [("coconala", "nanami_user"), ("etsy", "1234567890")])
def test_full_is_stores_only(monkeypatch, provider, order_code):
    monkeypatch.setattr(routes.pg_store, "redeem_and_save", lambda **kw: pytest.fail("No issue for non-STORES"))
    monkeypatch.setattr(routes, "build_product_yaml", lambda **kw: pytest.fail("No calculation"))
    monkeypatch.setattr(routes, "_resolve_coconala_order_from_buyer",
                        lambda **kw: ("C-1", {"product_type": "shichu_full"}, None, 200))
    response = TestClient(routes.app).post(f"/redeem/shichu-full?lang=ja&provider={provider}", data={
        "order_code": order_code, "order_provider": provider, "birth_date": "1990-05-10",
        "birth_time": "10:00", "prefecture": "東京都", "gender": "male", "agree_final": "1"})
    assert "STORES でご購入いただいた注文番号でのみ" in response.text


def test_full_form_fixes_stores_and_explains_withholding():
    page = TestClient(routes.app).get("/redeem/shichu-full?provider=coconala").text
    assert '<input type="hidden" name="order_provider" id="order-provider" value="stores">' in page
    assert "ココナラのユーザー名" not in page.split('id="order-code-label">')[1][:40]
    assert "大運と10年分の年運予測は確定できず保留" in page


def test_year_selection_card_and_accuracy_warning_only_on_full_pages(client_for):
    _t, _p, full = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    page = client_for(_chart(full, product_type="shichu_full")).get("/chart/fictional").text
    assert 'id="shichu-year-picker"' in page and "精度が下がります" in page
    _t, _p, basic = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    for chart in (_chart(basic), _chart(_legacy_doc())):
        assert 'id="shichu-year-picker"' not in client_for(chart).get("/chart/fictional").text


def test_year_selection_page_has_accuracy_notice(client_for):
    _t, _p, full = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    page = client_for(_chart(full, product_type="shichu_full")).get("/chart/fictional/year-selection").text
    assert 'id="selection-accuracy-notice"' in page and "1回の相談では1〜3年" in page
    assert 'id="selection-warning"' in page



def test_full_page_inline_year_picker_lists_saved_years_and_hides_duplicate_block(client_for):
    _t, _p, full = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    years = [i["effective_year"] for i in full["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]]
    page = client_for(_chart(full, product_type="shichu_full")).get("/chart/fictional").text
    for year in years:
        assert f'name="shichu-year" value="{year}"' in page
    assert "年を選ばない場合は、命式と大運をもとにした基本鑑定" in page
    assert 'id="shichu-all-data"' in page and "全データをコピー" in page
    assert 'id="mode-paste-card"' not in page  # 重複する「データ種別」欄は出さない
    # 基本版は従来の画面（データ種別欄あり、年選択・全データ欄なし）
    _t, _p, basic = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    basic_page = client_for(_chart(basic)).get("/chart/fictional").text
    assert 'id="mode-paste-card"' in basic_page
    assert '<section class="shichu-all-data"' not in basic_page
    assert 'type="checkbox" name="shichu-year"' not in basic_page


def test_picker_quick_years_are_this_next_and_year_after_next():
    from zoneinfo import ZoneInfo
    years = list(range(2026, 2036))
    after_lichun = datetime(2027, 3, 1, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
    quick, other = routes._split_shichu_picker_years(years, now=after_lichun)
    assert [(q["year"], q["label"]) for q in quick] == [(2027, "this_year"), (2028, "next_year"), (2029, "year_after_next")]
    assert other == [2026, 2030, 2031, 2032, 2033, 2034, 2035]
    # 立春前（1月）は前年が「今年」
    before_lichun = datetime(2027, 1, 20, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert routes._split_shichu_picker_years(years, now=before_lichun)[0][0] == {"year": 2026, "label": "this_year"}


def test_picker_falls_back_when_this_year_is_not_saved():
    from zoneinfo import ZoneInfo
    now = datetime(2026, 6, 1, tzinfo=ZoneInfo("Asia/Tokyo"))
    quick, other = routes._split_shichu_picker_years([2040, 2041, 2042, 2043], now=now)
    assert [q["year"] for q in quick] == [2040, 2041, 2042] and all(q["label"] == "" for q in quick)
    assert other == [2043]
    quick, other = routes._split_shichu_picker_years([2000, 2001, 2002, 2003], now=now)
    assert [q["year"] for q in quick] == [2001, 2002, 2003] and other == [2000]
    assert routes._split_shichu_picker_years([]) == ([], [])


def test_picker_layout_quick_chips_and_folded_others(client_for):
    _t, _p, full = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    page = client_for(_chart(full, product_type="shichu_full")).get("/chart/fictional").text
    assert page.count('class="shichu-year-chip"') == 3
    assert '<details class="shichu-year-more" id="shichu-year-more">' in page
    assert "ほかの年を選ぶ（" in page
    assert "選択中：なし（命式と大運の基本鑑定）" in page


def test_full_redeem_start_year_parser():
    import routes
    assert routes._parse_full_annual_start_year("", "1976-08-10", "ja") == (None, None)
    assert routes._parse_full_annual_start_year("2007", "1976-08-10", "ja") == (2007, None)
    assert routes._parse_full_annual_start_year("1975", "1976-08-10", "ja")[1].startswith("年運の開始年は 1976年〜2076年")
    assert routes._parse_full_annual_start_year("20xx", "1976-08-10", "ja")[1].startswith("年運の開始年は西暦4桁")
    assert routes._parse_full_annual_start_year("2077", "1976-08-10", "en")[1] == "Choose a first forecast year between 1976 and 2076."


def test_full_redeem_uses_chosen_start_year_and_rejects_bad_one_before_issue(monkeypatch):
    saved = {}
    monkeypatch.setattr(routes, "_check_order_for_redeem",
                        lambda **kw: ("ok", {"product_type": kw["product_type"], "payment_status": "paid"}, None, 200))
    monkeypatch.setattr(routes.pg_store, "redeem_and_save", lambda **kw: saved.update(kw) or True)
    monkeypatch.setattr(routes.pg_store, "init_db", lambda *a, **kw: None)
    data = {"order_code": "1234567890", "order_provider": "stores", "birth_date": "1990-05-10",
            "birth_time": "10:00", "prefecture": "東京都", "gender": "male",
            "day_change_at_23": "false", "agree_final": "1"}
    client = TestClient(routes.app)
    response = client.post("/redeem/shichu-full?lang=ja", data={**data, "annual_start_year": "2012"},
                           follow_redirects=False)
    assert response.status_code == 303
    forecasts = yaml.safe_load(saved["yaml_text"])["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]
    assert [i["effective_year"] for i in forecasts["items"]] == list(range(2012, 2022))
    saved.clear()
    bad = client.post("/redeem/shichu-full?lang=ja", data={**data, "annual_start_year": "1980"})
    assert "年運の開始年は 1990年〜2090年" in bad.text and 'value="1980"' in bad.text
    assert not saved
    page = client.get("/redeem/shichu-full").text
    assert 'name="annual_start_year"' in page and "confirm-annual-start-year" in page
    assert 'name="annual_start_year"' not in client.get("/redeem/shichu").text
