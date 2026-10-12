"""System-specific prompts, unchanged saved data and export provenance."""
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from services.prompt_builder import build_prompt, build_chart_companion_prompt
from services.yaml_exporter import build_product_yaml, build_prompt_for_doc
from services.output_metadata import customer_output_doc, EPHEMERIS_DIAGNOSTIC_KEYS
from services.shichusuimei_full_prototype import _typed_tree
from services.api_yaml import build_ai_prompt_context
from services.addon_prompt_locales import build_addon_prompt

WESTERN_TERMS = ("ASC", "MC", "ハウス", "トランジット", "アスペクト", "ACG", "/acg", "planetary", "houses", "transits", "casas", "tránsitos", "Häuser", "Transite")


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
@pytest.mark.parametrize("accuracy", ["exact", "unknown", "approximate"])
def test_four_pillars_reading_and_consultation_exclude_western_instructions(lang, accuracy):
    prompts = [
        build_prompt(include_shichusuimei=True, birth_time_accuracy=accuracy, lang=lang),
        build_chart_companion_prompt(include_shichusuimei=True, lang=lang),
        build_addon_prompt("shichu_fortune_cycles_addon", lang),
    ]
    for prompt in prompts:
        assert all(term not in prompt for term in WESTERN_TERMS)
        for rule in ("time_basis", "conflicting_rules", "useful_god_analysis", "daiun_boundary_in_window"):
            assert rule in prompt
        assert "今年の" not in prompt
        assert "原本作成時" in prompt if lang == "ja" else "annual_fortune" in prompt


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
def test_western_retains_acg_and_uncertain_time_rules_without_four_pillars(lang):
    for prompt in (
        build_prompt(include_transit=True, birth_time_accuracy="unknown", lang=lang),
        build_chart_companion_prompt(lang=lang),
    ):
        assert "/acg?lang=" in prompt
        assert "time_sensitive_provisional" in prompt
        assert not any(term in prompt for term in ("structural_analysis", "useful_god_analysis", "annual_forecasts", "daiun", "四柱推命"))


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
def test_combined_document_uses_both_systems_even_without_product_options(lang):
    doc = {"birth_time": {"accuracy": "unknown"}, "systems": {
        "western": {"natal": {"bodies": {"Sun": {"degree": 10}}}},
        "shichusuimei": {"normalized_data": {"pillars": {"day": {"kanshi": "甲子"}}}},
    }}
    before = deepcopy(doc)
    prompts = [build_prompt_for_doc(doc, lang=lang),
               build_chart_companion_prompt(lang=lang, include_shichusuimei=True, include_western=True)]
    for prompt in prompts:
        assert "useful_god_analysis" in prompt
        assert "/acg?lang=" in prompt
        assert "time_sensitive_provisional" in prompt
    assert doc == before


def test_actual_systems_override_stale_product_flags():
    doc = {"product": {"options": {"western_natal": True, "transit": True, "shichusuimei": False}},
           "systems": {"western": None, "shichusuimei": {"normalized_data": {"pillars": {}}}}}
    prompt = build_prompt_for_doc(doc, include_transit=True, include_asteroids=True)
    assert "四柱推命" in prompt and all(term not in prompt for term in WESTERN_TERMS)


def test_diagnostic_filter_keeps_all_calculated_fields_and_source_occurrences():
    doc = yaml.safe_load((Path(__file__).parent / "fixtures/shichusuimei/spring_exact_base.yaml").read_bytes())
    before = deepcopy(doc)
    cleaned = customer_output_doc(doc)
    assert _typed_tree(doc) == _typed_tree(before)
    old = doc["systems"]["shichusuimei"]
    new = cleaned["systems"]["shichusuimei"]
    for key in old.keys() - {"ephemeris"}:
        assert _typed_tree(new[key]) == _typed_tree(old[key]), key
    assert new["ephemeris"]["has_se1"] == old["ephemeris"]["has_se1"]
    assert not EPHEMERIS_DIAGNOSTIC_KEYS.intersection(new["ephemeris"])
    assert cleaned["calculation"] == before["calculation"]
    assert new["engine_version"] == old["engine_version"]
    # Unknown provenance is not discarded by an overbroad metadata whitelist.
    assert customer_output_doc({"ephemeris": {"provider": "fixture", "version": "1", "flags": 4}})["ephemeris"] == {"provider": "fixture", "version": "1", "flags": 4}


def test_new_product_export_removes_paths_without_modifying_engine_return(monkeypatch):
    from services import shichusuimei_calc
    from services import yaml_exporter
    fixture = yaml.safe_load((Path(__file__).parent / "fixtures/shichusuimei/spring_exact_base.yaml").read_bytes())
    raw = fixture["systems"]["shichusuimei"]
    raw["ephemeris"].update(ephe_dir="C:/private/ephe", ephe_files=["private.se1"], searched_ephe_dirs=["/app/ephe"])
    before = deepcopy(raw)
    calls = []
    monkeypatch.setattr(shichusuimei_calc, "calc_shichusuimei_from_payload", lambda *a, **kw: calls.append(1) or raw)
    monkeypatch.setattr(yaml_exporter, "calc_western_from_payload", lambda *a, **kw: pytest.fail("No Western calculation"))
    text, prompt, doc = build_product_yaml(title="fictional export", birth_date="1990-05-15",
        birth_time="08:30", prefecture="東京都", include_shichusuimei=True)
    assert calls == [1]  # No extra engine call for instruction generation.
    assert raw == before
    assert "C:/private" not in text and "/app/ephe" not in text and "private.se1" not in text
    assert "ASC" not in doc["birth_time"]["note"]
    assert "トランジット" not in doc["usage_note"]["continuous_use"]
    assert doc == yaml.safe_load(text)
    for key in ("normalized_data", "features", "raw", "engine_version"):
        assert _typed_tree(doc["systems"]["shichusuimei"][key]) == _typed_tree(before[key])
    assert all(term not in prompt for term in WESTERN_TERMS)


def test_trial_api_instructions_prioritize_structure_without_changing_tags_or_data():
    from services.api_calc import _success
    from services.api_demo import build_demo_response
    doc = {"systems": {"shichusuimei": {"normalized_data": {"pillars": {"day": {"kanshi": "甲子"}}}}}}
    before = deepcopy(doc)
    response, status = _success("shichu", {}, doc)
    assert status == 200
    assert response["raw_data"]["shichu"] == before["systems"]["shichusuimei"]
    assert doc == before
    for data in (response, build_demo_response("shichu", {}, base_url="https://example.invalid")):
        context = data["ai_prompt_context"]
        assert all(term not in context["reading_instructions"] for term in WESTERN_TERMS)
        assert "補助" in context["instruction"]
        assert context["source_mapping"] == {"systems.shichusuimei": "raw_data.shichu"}
        assert yaml.safe_load(data["handoff_yaml"])["ai_prompt_context"] == context


def test_mcp_four_pillars_has_matching_recommended_section():
    from services.mcp_chart_service import get_astrology_prompt
    response = get_astrology_prompt(product_type="shichu")
    assert response["recommended_sections"] == ["shichu"]
    assert all(term not in response["prompt"] for term in WESTERN_TERMS)
