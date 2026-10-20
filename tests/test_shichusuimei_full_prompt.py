"""FULL版専用の鑑定指示文（章立て・該当する注意だけ）。架空データのみ。"""
from services.shichusuimei_full_prompt import build_full_shichu_prompt, is_full_shichu_doc
from services.shichusuimei_year_selection import build_year_selection
from services.yaml_exporter import build_product_yaml, build_prompt_for_doc

ARGS = dict(title=None, birth_date="1976-08-10", birth_time="20:41", prefecture="東京都", gender="female",
            include_shichusuimei=True)
CHAPTERS = ("1. 命式の全体像", "2. 性格と動機", "3. 才能の組み合わせ", "4. 宮位から見る暮らし",
            "5. 用神と喜忌の活かし方", "6. 大運の流れ", "7. ", "8. これからの活かし方")


def test_full_prompt_has_deep_dive_chapters_in_order_and_is_short():
    text, prompt, doc = build_product_yaml(**ARGS, shichusuimei_edition="full")
    assert is_full_shichu_doc(doc)
    positions = [prompt.index(c) for c in CHAPTERS]
    assert positions == sorted(positions)
    for key in ("main_hidden_stems.month", "roots_and_exposure", "ten_god_flow", "useful_god_selection"):
        assert key in prompt
    assert "【計算】" in prompt and "【推論】" in prompt
    assert "出力してほしい内容" not in prompt  # 基本版の章立てを使わない
    assert len(prompt) < 5500  # 方式・候補・反証を運ぶ読解規約を含む。
    assert build_prompt_for_doc(doc, include_shichusuimei=True) == prompt  # 鑑定ページの表示と一致


def test_full_prompt_only_includes_cautions_that_apply():
    _, exact, doc = build_product_yaml(**ARGS, shichusuimei_edition="full")
    assert "【この命式の注意】" not in exact  # 正確な時刻・性別あり・神殺の該当なし
    assert "女性へ補完せず" not in exact and "時柱は参考値" not in exact
    _, unknown, _ = build_product_yaml(**{**ARGS, "birth_time": None, "birth_time_accuracy": "unknown"},
                                       shichusuimei_edition="full")
    assert "時柱は参考値" in unknown and "時柱の宮位は使わない" in unknown
    _, no_gender, _ = build_product_yaml(**{**ARGS, "gender": "unknown"}, shichusuimei_edition="full")
    assert "女性へ補完せず" in no_gender


def test_shinsatsu_mentioned_only_when_present():
    _, _, doc = build_product_yaml(**ARGS, shichusuimei_edition="full")
    stars = doc["systems"]["shichusuimei"]["normalized_data"]["shinsatsu"]["stars"]
    assert "神殺（" not in build_full_shichu_prompt(doc)
    stars[0]["hit"] = True
    assert f"神殺（{stars[0]['name_ja']}）" in build_full_shichu_prompt(doc)


def test_basic_edition_keeps_shared_prompt():
    _, prompt, doc = build_product_yaml(**ARGS, shichusuimei_edition="basic")
    assert not is_full_shichu_doc(doc)
    assert "出力してほしい内容" in prompt and "【鑑定の章立て】" not in prompt


def test_year_selection_uses_full_prompt_with_year_chapter():
    text, _, _ = build_product_yaml(**ARGS, shichusuimei_edition="full")
    selected = build_year_selection(text, {"mode": "selected", "years": [2027]})["prompt_text"]
    assert "7. 2027年の運勢" in selected and "common の中" in selected
    assert "出力してほしい内容" not in selected
    basic = build_year_selection(text, {"mode": "basic"})["prompt_text"]
    assert "7. 原本作成時の年のテーマ" in basic
    complete = build_year_selection(text, {"mode": "complete"})["prompt_text"]
    assert "7. 年ごとの運勢" in complete and "common の中" not in complete


def test_full_annual_start_year_shifts_only_forecasts():
    _, _, now_doc = build_product_yaml(**ARGS, shichusuimei_edition="full")
    _, _, past = build_product_yaml(**ARGS, shichusuimei_edition="full", shichusuimei_annual_start_year=2007)
    nd_now = now_doc["systems"]["shichusuimei"]["normalized_data"]
    nd = past["systems"]["shichusuimei"]["normalized_data"]
    years = [i["effective_year"] for i in nd["annual_forecasts"]["items"]]
    assert years == list(range(2007, 2017)) and nd["annual_forecasts"]["start_effective_year"] == 2007
    # 原本作成時の流年・現在の大運・命式は発行日のまま
    assert nd["annual_fortune"]["effective_year"] == nd_now["annual_fortune"]["effective_year"]
    assert nd["annual_fortune"]["current_daiun"] == nd_now["annual_fortune"]["current_daiun"]
    assert nd["pillars"] == nd_now["pillars"] and nd["daiun"] == nd_now["daiun"]
    # 2007年は壬辰大運が始まる年：大運の切り替わりを含む
    assert nd["annual_forecasts"]["items"][0]["daiun_boundary_in_window"] in (True, False)
    assert "振り返り" in build_full_shichu_prompt(past)


def test_full_annual_start_year_rejects_invalid_values():
    import pytest
    from services.shichusuimei_calc import calc_shichusuimei_from_payload
    with pytest.raises(ValueError):
        calc_shichusuimei_from_payload({"year": 1990, "month": 5, "day": 10, "hour": 10, "minute": 0,
                                        "gender": "female"}, annual_start_year=1700)
