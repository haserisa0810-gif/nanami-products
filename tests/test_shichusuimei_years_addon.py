"""四柱推命 年運アドオン（NP-SY05）。FULL版原本から指定年のN年分を作り、照合後にだけ発行する。"""
from copy import deepcopy

import pytest
import yaml
from fastapi.testclient import TestClient

import routes
from services import product_catalog
from services.addon_prompt_locales import build_addon_prompt
from services.shichusuimei_years_addon import (
    YEARS_ADDON_PROMPT, YearsAddonError, build_years_addon, full_base_info, merge_years_into_full,
)
from services.shichusuimei_year_selection import build_year_selection, selection_info
from services.yaml_exporter import build_product_yaml

ARGS = dict(title=None, birth_date="1990-05-10", birth_time="10:00", prefecture="東京都", gender="male")


@pytest.fixture(scope="module")
def full_doc():
    _text, _prompt, doc = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="full")
    return doc


def _engine_args(doc):
    return routes._shichu_engine_args_from_base(doc, routes._addon_args_from_base_doc(doc))


def test_five_years_from_chosen_start_year_match_the_full_original(full_doc):
    info = full_base_info(full_doc)
    assert len(info["included_years"]) == 10
    start = info["default_start_year"]
    text, prompt, doc = build_years_addon(full_doc, "shichu_annual_5y_addon", start, engine_args=_engine_args(full_doc))
    shichu = doc["systems"]["shichusuimei"]
    years = [i["effective_year"] for i in shichu["normalized_data"]["annual_forecasts"]["items"]]
    assert years == list(range(start, start + 5))
    assert shichu["reference"]["included_years"] == years
    base_pillars = {k: v["kanshi"] for k, v in full_doc["systems"]["shichusuimei"]["normalized_data"]["pillars"].items()}
    assert shichu["reference"]["pillars"] == base_pillars
    assert [d["kanshi"] for d in shichu["reference"]["daiun_summary"]] == \
        [d["kanshi"] for d in full_doc["systems"]["shichusuimei"]["normalized_data"]["daiun"]["items"]]
    assert doc["meta"]["product_type"] == "shichu_annual_5y_addon" and doc["meta"]["data_role"] == "addon"
    assert "&id" not in text and "*id" not in text
    assert yaml.safe_load(text) == doc
    assert prompt == YEARS_ADDON_PROMPT.strip() + "\n"


def test_past_start_year_is_allowed(full_doc):
    _t, _p, doc = build_years_addon(full_doc, "shichu_annual_5y_addon", 2000, engine_args=_engine_args(full_doc))
    years = [i["effective_year"] for i in doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]]
    assert years == [2000, 2001, 2002, 2003, 2004]


def test_years_already_in_full_are_rejected(full_doc):
    first = full_base_info(full_doc)["included_years"][0]
    with pytest.raises(YearsAddonError, match="すでにお手元のデータに入っています"):
        build_years_addon(full_doc, "shichu_annual_5y_addon", first + 8, engine_args=_engine_args(full_doc))


def test_merge_keeps_full_and_adds_years_without_touching_original(full_doc):
    before = deepcopy(full_doc)
    _t, _p, addon = build_years_addon(full_doc, "shichu_annual_5y_addon", 2040, engine_args=_engine_args(full_doc))
    merged = merge_years_into_full(full_doc, addon, "shichu_annual_5y_addon")
    assert full_doc == before
    years = [i["effective_year"] for i in merged["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]]
    assert years == full_base_info(full_doc)["included_years"] + [2040, 2041, 2042, 2043, 2044]
    assert merged["meta"]["addons"][0]["years"] == [2040, 2041, 2042, 2043, 2044]
    assert merged["systems"]["shichusuimei"]["edition"] == "full"
    # 追加した年も年選択の対象になる（保存値から抽出、再計算なし）。
    text = yaml.safe_dump(merged, allow_unicode=True, sort_keys=False)
    assert 2042 in selection_info(text)["available_years"]
    picked = build_year_selection(text, {"mode": "selected", "years": [2042]})
    assert picked["included_years"] == [2042]


def test_addon_can_be_stacked_on_a_previous_addon(full_doc):
    _t, _p, first = build_years_addon(full_doc, "shichu_annual_5y_addon", 2040, engine_args=_engine_args(full_doc))
    merged = merge_years_into_full(full_doc, first, "shichu_annual_5y_addon")
    info = full_base_info(merged)
    _t, _p, second = build_years_addon(merged, "shichu_annual_5y_addon", 2045, engine_args=_engine_args(merged))
    merged2 = merge_years_into_full(merged, second, "shichu_annual_5y_addon")
    assert full_base_info(merged2)["included_years"][-5:] == [2045, 2046, 2047, 2048, 2049]
    assert info["default_start_year"] == 2045


@pytest.mark.parametrize("start", [1989, 2091, "2030"])
def test_out_of_range_or_non_integer_start_year_is_rejected(full_doc, start):
    with pytest.raises(YearsAddonError):
        build_years_addon(full_doc, "shichu_annual_5y_addon", start, engine_args=_engine_args(full_doc))


def test_basic_edition_original_is_rejected():
    _text, _prompt, basic = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    with pytest.raises(YearsAddonError, match="FULL版"):
        full_base_info(basic)


def test_withheld_daiun_original_is_rejected():
    # 2024-03-05 は啓蟄の当日。時刻不明では大運が保留されるため、年運アドオンも作れない。
    _text, _prompt, doc = build_product_yaml(**{**ARGS, "birth_date": "2024-03-05", "birth_time": None},
                                             include_shichusuimei=True, shichusuimei_edition="full")
    with pytest.raises(YearsAddonError, match="節入り"):
        full_base_info(doc)


def test_mismatched_original_is_rejected_before_issue(full_doc):
    tampered = deepcopy(full_doc)
    tampered["systems"]["shichusuimei"]["normalized_data"]["pillars"]["day"]["kanshi"] = "甲子"
    with pytest.raises(YearsAddonError, match="一致しない"):
        build_years_addon(tampered, "shichu_annual_5y_addon", 2040, engine_args=_engine_args(full_doc))


def test_only_five_years_is_on_sale():
    assert product_catalog.product_for_sku("NP-SY05").product_type == "shichu_annual_5y_addon"
    assert product_catalog.product_for_sku("NP-SY10") is None
    assert product_catalog.product_for_sku("NP-SY20") is None
    options = [o["value"] for o in routes.ADDON_FORM_OPTIONS]
    assert "shichu_annual_5y_addon" in options
    assert "shichu_annual_10y_addon" not in options and "shichu_annual_20y_addon" not in options


def test_addon_prompts_by_language():
    assert build_addon_prompt("shichu_annual_5y_addon", "ja") == YEARS_ADDON_PROMPT.strip() + "\n"
    assert "Four Pillars" in build_addon_prompt("shichu_annual_5y_addon", "en")


# --- 発行の流れ（注文確認と保存はモック。本番DBに接続しない） -------------------------

@pytest.fixture
def issue_env(monkeypatch, full_doc):
    calls = {"redeem": 0}

    def fake_redeem(**kw):
        calls["redeem"] += 1
        calls.update(kw)
        return "ok", {"product_type": kw["addon_type"], "payment_status": "paid", "sku": "NP-SY05"}

    monkeypatch.setenv("DATABASE_URL", "postgresql://fictional.invalid:5432/never")
    monkeypatch.setattr(routes.pg_store, "redeem_addon_order_and_save_chart", fake_redeem)
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda token, **kw: {
        "token": token, "yaml_text": yaml.safe_dump(full_doc, allow_unicode=True, sort_keys=False),
        "options": {"product_type": "shichu_full"}, "expires_at": None})
    return calls


def _post(data):
    base = {"addon_type": "shichu_annual_5y_addon", "order_code": "1234567890", "order_provider": "stores",
            "previous_chart_url": "https://chart.nanami-astro.com/chart/" + "a" * 24}
    return TestClient(routes.app).post("/addon/generate?lang=ja", data={**base, **data}, follow_redirects=False)


def test_issue_flow_saves_full_plus_added_years_like_horoscope_addons(issue_env, full_doc):
    response = _post({"annual_start_year": "2040"})
    assert response.status_code == 303 and response.headers["location"].startswith("/chart/")
    assert issue_env["redeem"] == 1 and issue_env["addon_type"] == "shichu_annual_5y_addon"
    payload = issue_env["chart_payload"]
    assert payload["options"]["product_type"] == "shichu_annual_5y_addon"
    doc = yaml.safe_load(payload["yaml_text"])
    years = [i["effective_year"] for i in doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]]
    assert years == full_base_info(full_doc)["included_years"] + [2040, 2041, 2042, 2043, 2044]
    assert doc["systems"]["shichusuimei"]["normalized_data"]["structural_analysis"]  # FULL の内容を保持
    assert payload["shichusuimei_svg"]
    assert "四柱推命" in payload["prompt_text"] and "このYAML単体を命式全体として扱わない" not in payload["prompt_text"]


def test_issued_addon_page_offers_year_selection(issue_env, monkeypatch):
    assert _post({"annual_start_year": "2040"}).status_code == 303
    saved = {**issue_env["chart_payload"], "token": "fictionalissued", "expires_at": None}
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda token, **kw: dict(saved))
    client = TestClient(routes.app)
    page = client.get("/chart/fictionalissued").text
    assert 'id="shichu-year-picker"' in page and "精度が下がります" in page
    selection = client.get("/chart/fictionalissued/year-selection")
    assert selection.status_code == 200 and 'value="2042"' in selection.text


def test_issue_flow_defaults_to_year_after_full(issue_env, full_doc):
    assert _post({"annual_start_year": ""}).status_code == 303
    doc = yaml.safe_load(issue_env["chart_payload"]["yaml_text"])
    added = doc["meta"]["addons"][0]["years"]
    start = full_base_info(full_doc)["default_start_year"]
    assert added == list(range(start, start + 5))


@pytest.mark.parametrize("data,message", [
    ({"annual_start_year": "1800"}, "開始年は"),
    ({"annual_start_year": "20X0"}, "西暦4桁"),
    ({"annual_start_year": "2030"}, "すでにお手元のデータに入っています"),
    ({"order_provider": "coconala", "order_code": "nanami_user"}, "STORES でご購入"),
])
def test_issue_flow_rejects_without_consuming_order(issue_env, monkeypatch, data, message):
    monkeypatch.setattr(routes, "_resolve_coconala_order_from_buyer",
                        lambda **kw: ("C-1", {"product_type": "shichu_annual_5y_addon"}, None, 200))
    response = _post(data)
    assert message in response.text
    assert issue_env["redeem"] == 0


def test_issue_flow_rejects_basic_chart_url_without_consuming(issue_env, monkeypatch):
    _text, _prompt, basic = build_product_yaml(**ARGS, include_shichusuimei=True, shichusuimei_edition="basic")
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda token, **kw: {
        "token": token, "yaml_text": yaml.safe_dump(basic, allow_unicode=True, sort_keys=False),
        "options": {"product_type": "shichu"}, "expires_at": None})
    response = _post({"annual_start_year": "2040"})
    assert "FULL版" in response.text
    assert issue_env["redeem"] == 0


def test_addon_form_shows_start_year_field():
    page = TestClient(routes.app).get("/addon/new?addon_type=shichu_annual_5y_addon").text
    assert 'name="annual_start_year"' in page
    assert "四柱推命：年運追加（5年）" in page
