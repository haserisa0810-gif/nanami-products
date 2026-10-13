"""Product-level saved-year selection; all fixtures are fictional and offline."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib

import pytest
import yaml
from fastapi.testclient import TestClient

import routes
from services.shichusuimei_year_selection import YearSelectionError, build_year_selection, selection_info
from services.shichusuimei_full_prototype import _typed_tree


@pytest.fixture
def chart():
    # Separate, self-contained saved fixture; no engine and no ignored artifacts.
    basis = "three_pillars_hour_excluded"
    cycles = [{"index": i, "kanshi": "丙午", "age_from": 10.0 * i, "age_to": 10.0 * (i + 1),
               "boundary_provisional": True, "analysis": {"note": "概算起運・全大運を保持"}} for i in (1, 2, 3)]
    forecasts = []
    for year in (2027, 2030, 2033):
        relation = {"type": "clash", "left": {"name": "luck"}, "right": {"name": "day", "kanshi": "甲子"},
                    "detail": "子午冲", "status": "candidate"}
        forecasts.append({"effective_year": year, "kanshi": "丙午",
                          "period_start": f"{year}-02-04T03:00:00+09:00",
                          "period_end": f"{year + 1}-02-04T03:00:00+09:00",
                          "natal_analysis": {"pillar": "丙午", "time_basis": basis,
                                             "relations": [deepcopy(relation) for _ in range(3)],
                                             "combination_screening": {"status": "undetermined", "reasons": ["条件未確定"]}},
                          "daiun_contexts": [{**deepcopy(cycles[i]), "analysis": {"concurrent_daiun": "丙午"}}
                                             for i in ((0, 1) if year == 2030 else (0,))],
                          "warnings": ["年内交運の境界は概算"]})
    nd = {"pillars": {k: {"kanshi": "甲子"} for k in ("year", "month", "day")},
          "daiun": {"items": cycles},
          "structural_analysis": {"methodology": {"time_basis": basis}, "useful_god": {"confidence": "low"}},
          "time_sensitive_reference": {"hour_excluded": True},
          "annual_fortune": {"effective_year": 2026, "kanshi": "丙午"},
          "annual_forecasts": {"years": 10, "items": forecasts},
          "kubo": {"empty_branches": ["戌", "亥"]}}
    doc = {"version": "fictional-saved-full", "meta": {"chart_id": "fictional-base"},
           "input": {"birth_time_accuracy": "unknown"},
           "systems": {"shichusuimei": {"normalized_data": nd, "features": deepcopy(nd),
                                        "raw": {"note": "架空保存データ"}}}}
    text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    # 年選択は四柱推命FULL版（shichu_full）の機能。
    return {"token": "fictional", "options": {"product_type": "shichu_full", "shichusuimei": True},
            "yaml_text": text, "prompt_text": "original saved prompt",
            "buyer_name": "架空例", "birth_date": "1990-01-01", "birth_place": "東京都",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1)}


@pytest.fixture
def client(chart, monkeypatch):
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda token, **kw: deepcopy(chart) if token == "fictional" else None)
    # Any production initialization, calculation, or writes must fail this suite.
    monkeypatch.setattr(routes.pg_store, "init_db", lambda *a, **kw: pytest.fail("No DB initialization"))
    monkeypatch.setattr(routes.pg_store, "redeem_and_save", lambda *a, **kw: pytest.fail("No DB writes"))
    monkeypatch.setattr(routes, "build_product_yaml", lambda *a, **kw: pytest.fail("No recalculation"))
    from services import shichusuimei_calc
    monkeypatch.setattr(shichusuimei_calc, "calc_shichusuimei_from_payload", lambda *a, **kw: pytest.fail("No engine"))
    # Not a context manager: do not run app lifespan/startup against any database.
    return TestClient(routes.app)


def test_selection_keeps_full_selected_records_and_all_cycles(chart):
    original = deepcopy(chart)
    source = yaml.safe_load(chart["yaml_text"])["systems"]["shichusuimei"]["normalized_data"]
    result = build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2030, 2027]})
    doc = yaml.safe_load(result["yaml_text"])
    assert doc["year_selection"]["schema_version"] == "1.0"
    assert doc["year_selection"]["included_years"] == [2030, 2027]
    assert "local_year_extraction" not in doc
    assert [i["effective_year"] for i in doc["selected_base_forecasts"]] == [2030, 2027]
    assert _typed_tree(doc["selected_base_forecasts"]) == _typed_tree([source["annual_forecasts"]["items"][i] for i in (1, 0)])
    common = doc["common"]["systems"]["shichusuimei"]["normalized_data"]
    assert _typed_tree(common["daiun"]) == _typed_tree(source["daiun"])
    assert common["time_sensitive_reference"] == source["time_sensitive_reference"]
    assert "annual_fortune" not in common and "annual_forecasts" not in common
    assert "annual_forecasts" not in doc["common"]["systems"]["shichusuimei"]["features"]
    assert len(doc["selected_base_forecasts"][0]["daiun_contexts"]) == 2
    assert result["source_sha256"] == hashlib.sha256(chart["yaml_text"].encode()).hexdigest()
    assert result["bytes"] == len(result["yaml_text"].encode())
    assert result["characters"] == len(result["yaml_text"])
    assert result["yaml_text"].rstrip() in result["ai_text"]
    assert "year_selection" in result["prompt_text"]
    assert chart == original


def test_basic_keeps_saved_current_annual(chart):
    result = build_year_selection(chart["yaml_text"], {"mode": "basic"})
    doc = yaml.safe_load(result["yaml_text"])
    nd = doc["common"]["systems"]["shichusuimei"]["normalized_data"]
    assert nd["annual_fortune"]["effective_year"] == 2026
    assert "annual_forecasts" not in nd and "selected_base_forecasts" not in doc


def test_complete_preserves_original_bytes_even_crlf(chart):
    original = chart["yaml_text"].replace("\n", "\r\n") + "\r\n"
    result = build_year_selection(original, {"mode": "complete", "years": []})
    assert result["yaml_text"].encode() == original.encode()


def test_old_internal_metadata_survives_only_complete_original_with_new_prompt(chart):
    doc = yaml.safe_load(chart["yaml_text"])
    system = doc["systems"]["shichusuimei"]
    system["ephemeris"] = {"ephe_dir": "C:/private/ephe", "ephe_files": ["private.se1"], "has_se1": True}
    original = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).replace("\n", "\r\n")
    source_hash = hashlib.sha256(original.encode()).hexdigest()
    for mode, years in (("complete", []), ("basic", []), ("selected", [2027, 2033])):
        result = build_year_selection(original, {"mode": mode, "years": years})
        prompt = result["prompt_text"]
        assert "conflicting_rules" in prompt and "原本作成時" in prompt
        assert not any(term in prompt for term in ("ASC", "ハウス", "トランジット", "ACG"))
        assert result["source_sha256"] == source_hash
        if mode == "complete":
            assert result["yaml_text"].encode() == original.encode()
            assert "C:/private/ephe" in result["yaml_text"]
        else:
            assert "C:/private/ephe" not in result["yaml_text"] and "private.se1" not in result["yaml_text"]
            common = yaml.safe_load(result["yaml_text"])["common"]["systems"]["shichusuimei"]
            assert common["ephemeris"] == {"has_se1": True}
    assert hashlib.sha256(original.encode()).hexdigest() == source_hash


def test_old_saved_prompt_is_replaced_for_display_without_changing_original(client, chart, monkeypatch):
    old = deepcopy(chart)
    old["prompt_text"] = "古い指示: ハウス・ASC/MC・今年の流年・ACG"
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **kw: deepcopy(old))
    prompt = client.get("/chart/fictional/prompt.txt").text
    assert "conflicting_rules" in prompt and "原本作成時" in prompt
    assert not any(term in prompt for term in ("ASC", "ハウス", "トランジット", "ACG"))
    assert client.get("/chart/fictional.yaml").text == old["yaml_text"]
    import io, zipfile
    archive = client.get("/chart/fictional/download.zip")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        assert z.read("full.yaml").decode() == old["yaml_text"]
        assert z.read("prompt.txt").decode() == prompt
        assert "conflicting_rules" in z.read("ai_paste.txt").decode()
    assert old["prompt_text"].startswith("古い指示")


@pytest.mark.parametrize("payload", [
    {}, {"mode": "unsupported"}, {"mode": True}, {"mode": ["basic"]},
    {"mode": "selected"}, {"mode": "selected", "years": []},
    {"mode": "selected", "years": [True]}, {"mode": "selected", "years": [2027.0]},
    {"mode": "selected", "years": ["2027"]}, {"mode": "selected", "years": [2027, 2027]},
    {"mode": "selected", "years": [2027, 2036]}, {"mode": "basic", "years": [2027]},
    {"mode": "complete", "years": [2027]}, {"mode": "basic", "addon_yaml": "unapproved"},
])
def test_invalid_requests_stop_without_partial_output(chart, payload):
    with pytest.raises(YearSelectionError):
        build_year_selection(chart["yaml_text"], payload)


def test_old_missing_forecasts_basic_and_complete_only(chart):
    doc = yaml.safe_load(chart["yaml_text"])
    for key in ("normalized_data", "features"):
        doc["systems"]["shichusuimei"][key].pop("annual_forecasts")
    old = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    assert selection_info(old)["available_years"] == []
    build_year_selection(old, {"mode": "basic"})
    assert build_year_selection(old, {"mode": "complete"})["yaml_text"] == old
    with pytest.raises(YearSelectionError, match="収録されていません"):
        build_year_selection(old, {"mode": "selected", "years": [2027]})


def test_duplicate_saved_ids_disable_years_but_preserve_original(chart):
    doc = yaml.safe_load(chart["yaml_text"])
    forecasts = doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]["items"]
    forecasts.append(deepcopy(forecasts[0]))
    raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    assert selection_info(raw)["year_selection_available"] is False
    assert build_year_selection(raw, {"mode": "complete"})["yaml_text"] == raw


@pytest.mark.parametrize("raw", ["[1,2]", "systems: [1]", "systems: {shichusuimei: []}", "a: [", "a: &a {again: *a}"])
def test_invalid_or_wrong_chart_fails_with_safe_message(raw):
    with pytest.raises(YearSelectionError) as caught:
        selection_info(raw)
    assert caught.value.code == "invalid_base"


def test_page_and_api_use_existing_token_access_no_store_and_matching_prompt(client, chart):
    page = client.get("/chart/fictional/year-selection")
    assert page.status_code == 200
    assert 'value="2027"' in page.text and 'value="2033"' in page.text
    assert chart["yaml_text"] not in page.text  # Data fetched only on explicit creation.
    assert 'id="selection-result"' in page.text
    assert "no-store" in page.headers["cache-control"]
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    response = client.post("/chart/fictional/year-selection", json={"mode": "selected", "years": [2030]})
    assert response.status_code == 200
    result = response.json()
    assert result["included_years"] == [2030]
    assert result["yaml_text"].rstrip() in result["ai_text"]
    assert "no-store" in response.headers["cache-control"]
    assert client.get("/chart/fictional.yaml").text == chart["yaml_text"]
    assert client.get("/chart/fictional/prompt.txt").status_code == 200


def test_http_unselected_or_invalid_requests_return_safe_error(client):
    for payload in ({"mode": "selected", "years": [2027, 2045]}, {"mode": "selected", "years": [True]}):
        response = client.post("/chart/fictional/year-selection", json=payload)
        assert response.status_code == 422
        assert "yaml_text" not in response.json()
        assert "no-store" in response.headers["cache-control"]
        assert "fictional-base" not in response.text


@pytest.mark.parametrize("method", ["get", "post"])
def test_missing_and_expired_token_are_rejected(client, chart, monkeypatch, method):
    call = getattr(client, method)
    kwargs = {"json": {"mode": "basic"}} if method == "post" else {}
    assert call("/chart/missing/year-selection", **kwargs).status_code == 404
    expired = {**chart, "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **kw: expired)
    assert call("/chart/fictional/year-selection", **kwargs).status_code == 410


def test_other_product_does_not_get_four_pillars_selection(client, chart, monkeypatch):
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **kw: {**chart, "options": {"product_type": "western_full"}})
    assert client.get("/chart/fictional/year-selection").status_code == 404
    assert client.post("/chart/fictional/year-selection", json={"mode": "basic"}).status_code == 404
    assert "year-selection?lang=" not in client.get("/chart/fictional").text


def test_link_only_on_shichu_chart_and_english_page(client, chart, monkeypatch):
    page = client.get("/chart/fictional")
    assert page.status_code == 200
    assert "/chart/fictional/year-selection?lang=ja" in page.text
    english = client.get("/chart/fictional/year-selection?lang=en")
    assert "Choose reading years" in english.text
    assert "Basic chart + chosen years" in english.text


def test_saved_conflict_returns_generic_error_without_paths(client, chart, monkeypatch):
    doc = yaml.safe_load(chart["yaml_text"])
    for key in ("normalized_data", "features"):
        doc["systems"]["shichusuimei"][key]["annual_forecasts"]["items"][0]["natal_analysis"]["pillar"] = "甲子"
    damaged = {**chart, "yaml_text": yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)}
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **kw: damaged)
    response = client.post("/chart/fictional/year-selection", json={"mode": "selected", "years": [2027]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_saved_data"
    assert "natal_analysis" not in response.text and "fictional-base" not in response.text


def test_content_summary_heads_every_ai_text(chart):
    selected = build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2033, 2027]})
    assert selected["ai_text"].startswith("【このデータの中身】命式と、大運3期をすべて含みます。")
    assert "年ごとの年運：2027・2033年" in selected["content_summary"]
    assert "chart_id: fictional-base" in selected["content_summary"]
    basic = build_year_selection(chart["yaml_text"], {"mode": "basic"})
    assert "年ごとの年運：含みません（原本作成時の単年流年のみ）" in basic["content_summary"]
    complete = build_year_selection(chart["yaml_text"], {"mode": "complete"})
    assert "2027・2030・2033年（収録年すべて）" in complete["content_summary"]


def test_selected_prompt_allows_same_chart_years_sent_earlier(chart):
    result = build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2027]})
    doc = yaml.safe_load(result["yaml_text"])
    assert doc["year_selection"]["unselected_years"] == [2030, 2033]
    assert "このファイルに入っていない年" in doc["year_selection"]["omission_meaning"]
    assert "同じ chart_id" in doc["year_selection"]["omission_meaning"]
    assert "選択されていない年を推測" not in result["prompt_text"]
    assert "同じ会話で先に渡した同じ原本（chart_id: fictional-base）の年データは使えます" in result["prompt_text"]


def test_years_only_drops_common_block_and_keeps_reference(chart):
    full = build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2030]})
    result = build_year_selection(chart["yaml_text"], {"mode": "years_only", "years": [2030]})
    doc = yaml.safe_load(result["yaml_text"])
    assert "common" not in doc
    assert doc["year_selection"]["purpose"] == "continuation_years_only"
    assert doc["reference"]["chart_id"] == "fictional-base"
    assert doc["reference"]["pillars"] == {"year": "甲子", "month": "甲子", "day": "甲子"}
    assert [c["kanshi"] for c in doc["reference"]["daiun_summary"]] == ["丙午"] * 3
    assert [i["effective_year"] for i in doc["selected_base_forecasts"]] == [2030]
    assert _typed_tree(doc["selected_base_forecasts"]) == _typed_tree(yaml.safe_load(full["yaml_text"])["selected_base_forecasts"])
    assert result["characters"] < full["characters"]
    assert result["ai_text"].startswith("【このデータの中身】同じ会話で先に渡した四柱推命データ（chart_id: fictional-base）の続きです。")
    # The continuation prompt does not repeat the full reading instructions.
    assert "conflicting_rules" not in result["prompt_text"]
    assert "命式つきのデータ" in result["prompt_text"]
    assert result["filename"] == "nanami-shichusuimei-more-years-2030"


@pytest.mark.parametrize("payload", [
    {"mode": "years_only"}, {"mode": "years_only", "years": []}, {"mode": "years_only", "years": [2045]},
])
def test_years_only_requires_saved_years(chart, payload):
    with pytest.raises(YearSelectionError):
        build_year_selection(chart["yaml_text"], payload)


def test_http_years_only_and_chart_page_handoff_toggle(client):
    response = client.post("/chart/fictional/year-selection", json={"mode": "years_only", "years": [2033]})
    assert response.status_code == 200
    assert "common" not in yaml.safe_load(response.json()["yaml_text"])
    page = client.get("/chart/fictional").text
    assert 'name="shichu-year-handoff" value="years_only"' in page
    assert "mode: continuation ? 'years_only' : 'selected'" in page
    selection_page = client.get("/chart/fictional/year-selection").text
    assert 'name="mode" value="years_only"' in selection_page


def test_reading_guidance_covers_personality_layers_in_all_languages():
    from services.prompt_builder import SHICHUSUIMEI_STRUCTURE_GUIDANCE as ja
    from services.shichusuimei_prompt_rules import localized_shichusuimei_rules
    for term in ("表と裏", "main_hidden_stems.month", "roots_and_exposure", "ten_god_flow", "宮位",
                 "【計算】", "【伝統的解釈】", "【推論】", "同じ chart_id"):
        assert term in ja, term
    for lang in ("en", "es", "de"):
        rules = localized_shichusuimei_rules(lang)
        for term in ("main_hidden_stems.month", "roots_and_exposure", "ten_god_flow", "chart_id", "unselected_years"):
            assert term in rules, (lang, term)


def test_repeated_selection_is_cached_and_callers_cannot_mutate_cache(chart, monkeypatch):
    import services.shichusuimei_year_selection as selection
    selection._cache.clear()
    calls = []
    original = selection._build_year_selection
    monkeypatch.setattr(selection, "_build_year_selection", lambda *a: calls.append(1) or original(*a))
    first = build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2027]})
    first["included_years"].append(9999)
    second = build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2027]})
    assert len(calls) == 1 and second["included_years"] == [2027]
    assert second["yaml_text"] == first["yaml_text"]
    build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2030]})
    assert len(calls) == 2
    with pytest.raises(YearSelectionError):
        build_year_selection(chart["yaml_text"], {"mode": "selected", "years": [2045]})
    selection._cache.clear()


def test_chart_page_shows_preparing_label_on_ai_button(client):
    page = client.get("/chart/fictional").text
    assert "'準備中…'" in page and "readyLabel" in page
