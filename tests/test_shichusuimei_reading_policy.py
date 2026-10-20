"""Policy propagation and provenance, not empirical LLM reading scores."""
from copy import deepcopy

import pytest

from services.api_tags import shichu_tags
from services.api_yaml import build_ai_prompt_context
from services.prompt_builder import build_prompt
from services.shichusuimei_calc import Pillars4
from services.shichusuimei_structure import analyze_structure
from services.shichusuimei_full_prompt import build_full_shichu_prompt
from services.shichusuimei_reading_policy import build_reading_context
from services.shichusuimei_legacy_prompts import LEGACY_READING_PROMPTS
from services.yaml_exporter import build_prompt_for_doc


CASES = [
    ("乙丑", "甲申", "甲午", "己巳"),  # audit weak candidate / legacy mismatch
    ("乙丑", "甲申", "丁未", "乙巳"),  # audit boundary
    ("乙卯", "乙卯", "甲子", "乙卯"),  # special review
    ("壬子", "壬子", "丙子", "壬辰"),  # follow-pattern review
    ("丙寅", "丙寅", "甲子", "戊辰"),  # flow materials
    ("丙寅", "辛酉", "丙申", "戊戌"),  # competing combinations/clash
    ("甲子", "己丑", "丙午", "辛卯"),
    ("丙午", "甲午", "庚午", "丙戌"),  # climate/fuyi conflict
]


def doc_for(pillars, reliable=True):
    analysis = analyze_structure(Pillars4(*pillars), time_reliable=reliable)
    return {"birth_time": {"accuracy": "exact" if reliable else "unknown"}, "systems": {
        "shichusuimei": {"edition": "full", "engine_version": "0.7.0",
            "structure_report": {"strength_index": {"score": 53, "label": "LEGACY_LABEL"}},
            "normalized_data": {"structural_analysis": analysis}}}}


@pytest.mark.parametrize("pillars", CASES)
@pytest.mark.parametrize("reliable", [True, False])
def test_reading_context_preserves_raw_materials_and_never_confirms_pattern(pillars, reliable):
    doc = doc_for(pillars, reliable)
    before = deepcopy(doc)
    shichu = doc["systems"]["shichusuimei"]
    context = build_reading_context(shichu)
    prompt = build_full_shichu_prompt(doc)
    assert doc == before
    assert context["strength"]["source"] == "normalized_data.structural_analysis.day_master_support"
    assert context["strength"]["status"] in {"candidate", "ambiguous"}
    assert context["pattern_candidates"]["confirmation"] == "not_assessed"
    assert context["useful_god"]["selection_status"] == "selected"
    if not reliable:
        assert context["useful_god"]["status"] == "ambiguous"
    assert "主要構造を最大2つ" in prompt and "missing_endpoint" in prompt
    assert "喜忌は選択方式の中での役割" in prompt
    assert "強い根拠のある葛藤・弱点・リスク" in prompt
    assert "質問形で問題の存在を埋め込まない" in prompt
    assert "用神は「未確定」「データが不足」と書かない" not in prompt


def test_boundary_and_special_context_do_not_promote_selected_to_confirmed():
    for pillars in CASES[1:4]:
        shichu = doc_for(pillars)["systems"]["shichusuimei"]
        context = build_reading_context(shichu)
        assert context["strength"]["status"] == "ambiguous"
        assert context["useful_god"]["status"] == "ambiguous"


def test_structure_trace_is_opt_in_and_does_not_modify_document():
    doc = doc_for(CASES[0])
    before = deepcopy(doc)
    assert "【検証用構造記録" not in build_full_shichu_prompt(doc)
    trace = build_full_shichu_prompt(doc, include_reading_trace=True)
    assert "【検証用構造記録" in trace
    assert "evidence_paths" in trace and "counter_evidence" in trace
    assert doc == before


def test_new_tag_uses_weighted_candidate_without_old_score():
    shichu = doc_for(CASES[0])["systems"]["shichusuimei"]
    before = deepcopy(shichu)
    tag = next(t for t in shichu_tags(shichu) if t["id"] == "strength_index")
    assert "weak_candidate" in str(tag["basis"])
    assert "LEGACY_LABEL" not in str(tag) and "score=53" not in str(tag)
    assert shichu == before


def test_basic_tag_stays_legacy_reference_without_invented_new_metrics():
    tag = next(t for t in shichu_tags({"structure_report": {"strength_index": {"score": 53, "label": "中庸"}}}) if t["id"] == "strength_index")
    assert "legacy_reference" in str(tag["basis"])
    assert "score=53" in str(tag["basis"])
    assert build_reading_context({})["strength"]["source"] is None


def test_api_exposes_method_state_without_mutating_previous_context():
    doc = doc_for(CASES[1])
    previous = {"caution": ["existing"], "other": {"preserve": True}}
    before = deepcopy(previous)
    context = build_ai_prompt_context(doc, previous)
    assert previous == before
    assert context["shichu_reading_context"]["strength"]["status"] == "ambiguous"
    assert context["shichu_reading_context"]["useful_god"]["selection_status"] == "selected"


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
def test_nonlegacy_common_prompts_use_uncertainty_internally(lang):
    prompt = build_prompt(include_shichusuimei=True, lang=lang)
    for field in ("confidence", "conflicting_rules", "methodology.limitations", "candidate", "ambiguous", "selected", "strength_index"):
        assert field in prompt
    for old in ("Never say the useful element is undetermined", "No digas que el elemento útil está sin determinar", "Sage nie, das nützliche Element sei unbestimmt", "「用神は未確定」「確定していない」「データが不足」とは書かない"):
        assert old not in prompt


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
def test_issued_legacy_prompt_remains_fixed(lang):
    doc = {"birth_time": {"accuracy": "exact"}, "systems": {
        "shichusuimei": {"engine_version": "0.4.0", "normalized_data": {"pillars": {}}}}}
    before = deepcopy(doc)
    assert build_prompt_for_doc(doc, lang=lang) == LEGACY_READING_PROMPTS[f"{lang}:exact"]
    assert doc == before


@pytest.mark.parametrize("lang", ["en", "es", "de"])
def test_localized_deep_reading_retains_explicit_evidence_paths(lang):
    from services.shichusuimei_prompt_rules import localized_shichusuimei_rules
    rules = localized_shichusuimei_rules(lang)
    for path in ("ten_gods.pillars", "ten_gods.hidden_stems", "main_hidden_stems.month", "roots_and_exposure", "ten_god_flow"):
        assert path in rules
    assert "candidate" in rules and "ambiguous" in rules
