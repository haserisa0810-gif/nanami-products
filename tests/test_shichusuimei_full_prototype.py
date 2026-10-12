from copy import deepcopy
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "shichusuimei"

import pytest
import yaml

from services.shichusuimei_full_prototype import (
    _typed_tree, build_ordinary, build_recommended, item_mapping, load_saved_full,
    restore_variant, target_scope, variant_prompt, verify_recommended,
)


def dump(doc):
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120).encode()


@pytest.fixture(scope="module")
def raw_full():
    return (FIXTURES / "spring_exact_base.yaml").read_bytes()


@pytest.fixture(scope="module")
def recommended(raw_full):
    return build_recommended(raw_full)


def identity_fixture():
    identical = {"stem": "甲", "branch": "子", "kanshi": "甲子", "ten_god": "比肩",
                 "note": "値が一致しても、対象の柱・年・大運を統合しないための架空検証。" * 5}
    relation = {"type": "clash", "left": {"name": "luck"}, "right": {"name": "day", "kanshi": "甲子"},
                "detail": "子午冲", "applied": False, "note": "関係の参加者は各年の文脈で区別する。" * 5}
    analysis = {"pillar": "丙午", "relations": [deepcopy(relation)] * 3, "status": "provisional"}
    return {"version": "identity-validation-only", "systems": {"shichusuimei": {
        "normalized_data": {"pillars": {k: deepcopy(identical) for k in ("year", "month", "day", "hour")},
                            "daiun": {"items": [{"index": n, "kanshi": "丙午", "age_from": 10.0 * n,
                                                 "age_to": 10.0 * (n + 1), "analysis": deepcopy(analysis)} for n in (1, 7)]},
                            "annual_forecasts": {"items": [{"effective_year": n, "kanshi": "丙午", "natal_analysis": deepcopy(analysis)} for n in (2026, 2086)]}},
    }}}


def test_recommended_preserves_every_typed_field_and_scope(raw_full, recommended):
    data, manifest = recommended
    assert _typed_tree(restore_variant(data)) == _typed_tree(load_saved_full(raw_full))
    assert manifest["excluded_development_fields"] == []
    assert manifest["table_sections"]
    assert b"__local_trial_table__" in data
    assert verify_recommended(raw_full, data, manifest)["all_typed_values_and_occurrences_equal"]


def test_no_engine_or_annual_recalculation(raw_full, monkeypatch):
    from services import shichusuimei_calc as core
    monkeypatch.setattr(core, "calc_shichusuimei_from_payload", lambda *args, **kwargs: pytest.fail("No recalculation"))
    original = raw_full[:]
    build_recommended(raw_full)
    build_ordinary(raw_full)
    assert raw_full == original


def test_identical_targets_are_distinct_and_all_relation_occurrences_remain():
    doc = identity_fixture()
    raw = dump(doc)
    data, manifest = build_recommended(raw)
    restored = restore_variant(data)
    assert _typed_tree(restored) == _typed_tree(doc)
    nd = restored["systems"]["shichusuimei"]["normalized_data"]
    assert len(nd["pillars"]) == 4
    assert [x["index"] for x in nd["daiun"]["items"]] == [1, 7]
    assert [x["effective_year"] for x in nd["annual_forecasts"]["items"]] == [2026, 2086]
    assert all(len(x["natal_analysis"]["relations"]) == 3 for x in nd["annual_forecasts"]["items"])
    assert target_scope(doc, ("systems", "shichusuimei", "normalized_data", "pillars", "year"), nd["pillars"]["year"]) != target_scope(
        doc, ("systems", "shichusuimei", "normalized_data", "pillars", "day"), nd["pillars"]["day"])
    verify_recommended(raw, data, manifest)


def test_wrong_same_value_target_binding_is_detected():
    doc = identity_fixture()
    raw = dump(doc)
    data, manifest = build_recommended(raw)
    damaged = deepcopy(manifest)
    damaged["references"].append({"source": "/systems/shichusuimei/normalized_data/pillars/year",
                                  "definition": "/systems/shichusuimei/normalized_data/pillars/day", "scope": "natal_year"})
    with pytest.raises(ValueError, match="付け替え"):
        verify_recommended(raw, data, damaged)


def test_reference_byte_change_is_detected_even_when_values_are_equal(recommended, raw_full):
    data, manifest = recommended
    with pytest.raises(ValueError, match="バイト列"):
        verify_recommended(raw_full, data + b"\n", manifest)


def test_missing_anchor_and_wrong_table_column_are_detected(raw_full, recommended):
    data, manifest = recommended
    missing = data.replace(b"*natal", b"*missing_natal", 1)
    with pytest.raises(yaml.YAMLError):
        restore_variant(missing)
    parsed = yaml.safe_load(data)
    from services.shichusuimei_full_prototype import walk, TABLE_MARKER
    table = next(value for _, value in walk(parsed) if isinstance(value, dict) and TABLE_MARKER in value)
    table["columns"][0] = "/WRONG_TARGET"
    with pytest.raises(ValueError, match="差分"):
        verify_recommended(raw_full, dump(parsed), manifest)


def test_types_rounding_and_uncomputed_flags_are_preserved():
    doc = identity_fixture()
    doc["precise"] = {"int": 1, "float": 1.0, "bool": True, "none": None, "small": 0.1234567890123,
                      "conditions": [False, None, "not_assessed", "provisional"]}
    data, _ = build_recommended(dump(doc))
    assert _typed_tree(restore_variant(data)) == _typed_tree(doc)


def test_ordinary_keeps_natal_luck_and_current_annual_but_marks_forecasts_omitted(raw_full):
    data, manifest = build_ordinary(raw_full)
    source = load_saved_full(raw_full)["systems"]["shichusuimei"]["normalized_data"]
    doc = restore_variant(data)
    nd = doc["systems"]["shichusuimei"]["normalized_data"]
    for key in source:
        if key != "annual_forecasts":
            assert _typed_tree(nd[key]) == _typed_tree(source[key])
    assert "annual_forecasts" not in nd
    assert "該当なし" in manifest["coverage"]["omission_meaning"]
    assert len(doc["local_trial_coverage"]["omitted_existing_forecast_years"]) == 10
    assert len(nd["daiun"]["items"]) == 10
    assert nd["kubo"] == source["kubo"]
    assert doc["systems"]["shichusuimei"]["features"]["strength"] == load_saved_full(raw_full)["systems"]["shichusuimei"]["features"]["strength"]


def test_unknown_time_warnings_and_hour_exclusion_are_preserved():
    raw = (FIXTURES / "summer_unknown_base.yaml").read_bytes()
    source = load_saved_full(raw)
    for build in (build_ordinary, build_recommended):
        data, _ = build(raw)
        restored = restore_variant(data)
        nd = restored["systems"]["shichusuimei"]["normalized_data"]
        assert nd["time_sensitive_reference"] == source["systems"]["shichusuimei"]["normalized_data"]["time_sensitive_reference"]
        assert nd["structural_analysis"]["methodology"]["time_basis"] == "three_pillars_hour_excluded"


def test_old_saved_missing_sections_are_not_reported_as_no_hits(raw_full):
    doc = load_saved_full(raw_full)
    doc["systems"]["shichusuimei"]["normalized_data"].pop("annual_forecasts")
    doc["systems"]["shichusuimei"]["normalized_data"].pop("structural_analysis")
    old = dump(doc)
    data, manifest = build_recommended(old)
    verify_recommended(old, data, manifest)
    ordinary, _ = build_ordinary(old)
    coverage = restore_variant(ordinary)["local_trial_coverage"]
    assert "structural_analysis" in coverage["source_missing_sections"]
    assert not coverage["omitted_existing_forecast_years"]


def test_mapping_has_one_row_for_every_original_leaf(raw_full, recommended):
    data, manifest = recommended
    ordinary, normal_manifest = build_ordinary(raw_full)
    rows = item_mapping(raw_full, manifest, normal_manifest)
    assert len({r["source"] for r in rows}) == len(rows)
    assert any(r["ordinary_action"] == "ordinary_only_omitted" for r in rows)
    assert any(r["recommended_action"] == "duplicate_value_reference" for r in rows)
    row = next(r for r in rows if r["source"] == "/systems/shichusuimei/pillars/year")
    assert row["ordinary_destination"].endswith("/pillars/year/kanshi")


@pytest.mark.parametrize("source", [b"[]", b"[broken", b"systems: {western: {}}", b"a: &a {b: *a}\nsystems: {shichusuimei: {}}"])
def test_invalid_inputs_are_rejected(source):
    with pytest.raises(ValueError):
        build_recommended(source)


def test_variant_prompts_do_not_request_missing_normal_forecasts():
    assert "省略された既存10年予測" in variant_prompt("ordinary")
    assert "columns" in variant_prompt("recommended")
    assert "rows" in variant_prompt("recommended")
    assert "この文書内" in variant_prompt("complete")
