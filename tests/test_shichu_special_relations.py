"""伏吟・反吟・天干冲（services/shichu_special_relations.py）のテスト。

表は nanami-astro フェーズ2から移植した固定値。lunar_python 1.4.8 との照合は
docs/claude_shichu_calc_verification_20261012.md G節。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from services import shichusuimei_calc as core
from services.shichu_special_relations import (
    BRANCH_CLASHES,
    STEM_CLASHES,
    detect_special_kanshi_relations,
)

AS_OF = datetime(2026, 10, 12, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def _calc(**kw):
    payload = {"year": 1990, "month": 5, "day": 15, "hour": 12, "minute": 30, "gender": "female"}
    payload.update(kw)
    return core.calc_shichusuimei_from_payload(payload, as_of=AS_OF)


def test_tables_are_fixed_and_match_engine():
    # 六冲表は循環import回避のための再掲。エンジン側の正本と同一であること。
    assert BRANCH_CLASHES == core.BRANCH_CLASHES
    # 天干冲は4組のみ（戊・己なし）。追加・変更禁止の固定表。
    assert STEM_CLASHES == {
        frozenset(("甲", "庚")), frozenset(("乙", "辛")),
        frozenset(("丙", "壬")), frozenset(("丁", "癸")),
    }


def test_fukugin_detected_on_identical_kanshi():
    items = detect_special_kanshi_relations([("year", "庚午")], "庚午", "daiun", scope="daiun_natal")
    assert [i["rule_id"] for i in items] == ["fukugin_v1"]
    assert items[0]["type"] == "伏吟"
    assert items[0]["pillars"] == ["year", "daiun"]
    assert items[0]["members"] == ["庚午", "庚午"]
    assert items[0]["scope"] == "daiun_natal"
    assert items[0]["tags"] == ["repetition", "stagnation_or_emphasis"]


def test_hangin_requires_both_stem_and_branch_clash():
    # 甲庚＝天干冲、子午＝地支冲 → 反吟
    both = detect_special_kanshi_relations([("year", "甲子")], "庚午", "ryunen", scope="ryunen_natal")
    assert [i["rule_id"] for i in both] == ["hangin_v1"]
    assert both[0]["type"] == "反吟"
    # 反吟成立柱には天干冲を重複記録しない
    assert "stem_clash_v1" not in [i["rule_id"] for i in both]
    # 戊・己に天干冲は無い: 地支冲だけでは反吟にならず、何も出ない
    assert detect_special_kanshi_relations([("year", "戊子")], "己午", "ryunen", scope="ryunen_natal") == []
    # 天干冲のみ（地支冲なし）→ stem_clash_v1
    only_stem = detect_special_kanshi_relations([("year", "甲子")], "庚子", "ryunen", scope="ryunen_natal")
    assert [i["rule_id"] for i in only_stem] == ["stem_clash_v1"]
    assert only_stem[0]["type"] == "天干冲"
    # 無関係の組は何も出ない
    assert detect_special_kanshi_relations([("year", "甲子")], "乙丑", "ryunen", scope="ryunen_natal") == []


def test_engine_outputs_contain_special_relation_keys():
    nd = _calc()["normalized_data"]
    assert nd["daiun"]["items"]
    for item in nd["daiun"]["items"]:
        assert "special_relations_natal" in item
        assert all(r["scope"] == "daiun_natal" for r in item["special_relations_natal"])
    annual = nd["annual_fortune"]
    assert "special_relations_natal" in annual
    assert "special_relations_daiun" in annual
    assert all(r["scope"] == "ryunen_natal" for r in annual["special_relations_natal"])
    assert all(r["scope"] == "ryunen_daiun" for r in annual["special_relations_daiun"])
    for year_item in nd["annual_forecasts"]["items"]:
        assert "special_relations_natal" in year_item
        for context in year_item["daiun_contexts"]:
            assert "special_relations_daiun" in context
            assert all(r["scope"] == "ryunen_daiun" for r in context["special_relations_daiun"])


def test_annual_fukugin_on_month_pillar():
    # 1972-06-10生まれ: 年柱壬子・月柱丙午（午月×年干壬→丙午）。
    # 流年丙午(2026)に対し、月柱は伏吟、年柱は反吟（壬丙天干冲＋子午冲）。
    # 1966年の干支一巡例はQ06（Windowsで1970年以前が計算不能）のため使わない。
    nd = core.calc_shichusuimei_from_payload(
        {"year": 1972, "month": 6, "day": 10, "hour": 10, "minute": 0, "gender": "male"}, as_of=AS_OF,
    )["normalized_data"]
    assert nd["pillars"]["month"]["kanshi"] == "丙午"
    annual = nd["annual_fortune"]
    assert annual["kanshi"] == "丙午"
    month_hits = [r for r in annual["special_relations_natal"] if r["pillars"][0] == "month"]
    assert [r["rule_id"] for r in month_hits] == ["fukugin_v1"]
    assert month_hits[0]["members"] == ["丙午", "丙午"]
    year_hits = [r for r in annual["special_relations_natal"] if r["pillars"][0] == "year"]
    assert [r["rule_id"] for r in year_hits] == ["hangin_v1"]


def test_annual_hangin_against_natal_year():
    # 1972年＝壬子生まれ、流年丙午: 壬丙＝天干冲かつ子午＝冲 → 反吟
    nd = core.calc_shichusuimei_from_payload(
        {"year": 1972, "month": 3, "day": 1, "hour": 10, "minute": 0, "gender": "male"}, as_of=AS_OF,
    )["normalized_data"]
    annual = nd["annual_fortune"]
    assert annual["kanshi"] == "丙午"
    year_hits = [r for r in annual["special_relations_natal"] if r["pillars"][0] == "year"]
    assert [r["rule_id"] for r in year_hits] == ["hangin_v1"]
    # 月柱は壬寅: 壬丙の天干冲のみ（寅午は冲でない）→ stem_clash_v1
    month_hits = [r for r in annual["special_relations_natal"] if r["pillars"][0] == "month"]
    assert [r["rule_id"] for r in month_hits] == ["stem_clash_v1"]


def test_unknown_time_excludes_hour_pillar():
    nd = _calc(hour=None, minute=None)["normalized_data"]
    collected = list(nd["annual_fortune"]["special_relations_natal"])
    for item in nd["daiun"]["items"]:
        collected += item["special_relations_natal"]
    for year_item in nd["annual_forecasts"]["items"]:
        collected += year_item["special_relations_natal"]
    assert all("hour" not in r["pillars"] for r in collected)


def test_engine_version_and_rules_disclosed():
    result = _calc()
    assert result["engine_version"] == core.ENGINE_VERSION
    assert "special_relations_rules" in result["input"]["assumptions"]


def test_existing_daiun_item_keys_preserved():
    item = _calc()["normalized_data"]["daiun"]["items"][0]
    for key in ("index", "kanshi", "age_from", "age_to", "approx_start_year",
                "approx_start_at", "approx_end_at", "structural_analysis"):
        assert key in item


def test_undetermined_gender_keeps_daiun_empty_without_error():
    nd = _calc(gender="unknown")["normalized_data"]
    assert nd["daiun"]["status"] == "undetermined_gender"
    assert nd["daiun"]["items"] == []
    # 大運が無い場合、流年×現大運の特殊関係は空
    assert nd["annual_fortune"]["special_relations_daiun"] == []
    assert "special_relations_natal" in nd["annual_fortune"]


def test_addon_includes_special_relations():
    from services.yaml_exporter import build_shichu_fortune_cycles_addon_yaml
    _, _, addon = build_shichu_fortune_cycles_addon_yaml(
        title=None, birth_date="1972-03-01", birth_time="10:00", prefecture="東京都", gender="male",
    )
    nd = addon["systems"]["shichusuimei"]["normalized_data"]
    assert nd["daiun"]["items"]
    assert all("special_relations_natal" in item for item in nd["daiun"]["items"])
    assert "special_relations_natal" in nd["annual_fortune"]
    assert all("special_relations_natal" in item for item in nd["annual_forecasts"]["items"])
