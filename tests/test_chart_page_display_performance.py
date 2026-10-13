"""Offline regressions for parsing and embedding saved chart data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient
import yaml

import routes
from services.shichusuimei_full_prototype import _typed_tree
from tests.test_light_yaml_transit_summary import _asteroid_dense_full_doc
from tests.test_long_term_transit_addon_chart import _samples_long_term_doc

FIXTURES = Path(__file__).parent / "fixtures/shichusuimei"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Display must not initialize, write, calculate, or use the network")

    monkeypatch.setattr(routes.pg_store, "_get_pool", forbidden)
    monkeypatch.setattr(routes.pg_store, "init_db", forbidden)
    monkeypatch.setattr(routes.pg_store, "save_chart", forbidden)
    monkeypatch.setattr(routes.pg_store, "redeem_and_save", forbidden)
    monkeypatch.setattr(routes, "build_product_yaml", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)


def saved_chart(raw, product_type):
    return {
        "token": "fictional", "options": {"product_type": product_type},
        "yaml_text": raw, "prompt_text": "original saved prompt",
        "share_yaml_text": None, "buyer_name": "fictional", "birth_date": "1990-01-01",
        "birth_time": "12:00", "birth_place": "fictional",
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    }


def js_json_constant(html, name):
    return json.loads(re.search(rf"const {name} = (.*);", html).group(1))


@pytest.mark.parametrize("filename", sorted(p.name for p in FIXTURES.glob("*.yaml")))
def test_display_loader_preserves_saved_values_and_aliases(filename, monkeypatch):
    raw = (FIXTURES / filename).read_text(encoding="utf-8")
    expected = yaml.safe_load(raw)
    assert _typed_tree(routes._load_chart_display_yaml(raw)) == _typed_tree(expected)
    monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
    assert _typed_tree(routes._load_chart_display_yaml(raw)) == _typed_tree(expected)


@pytest.mark.parametrize("c_fallback", [False, True])
def test_display_loader_preserves_yaml_alias_identity(c_fallback, monkeypatch):
    if c_fallback:
        monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
    doc = routes._load_chart_display_yaml("original: &saved {value: 1}\ncopies: [*saved, *saved]\n")
    assert doc["original"] is doc["copies"][0] is doc["copies"][1]


@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
@pytest.mark.parametrize("filename", ["spring_exact_base.yaml", "summer_unknown_base.yaml"])
@pytest.mark.parametrize("edition", ["legacy", "basic", "full"])
def test_parsed_prompt_preserves_legacy_and_current_branches(filename, lang, edition, monkeypatch):
    raw = (FIXTURES / filename).read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    shichu = doc["systems"]["shichusuimei"]
    if edition == "legacy":
        shichu.pop("edition", None)
        shichu["engine_version"] = "0.4.1"
    else:
        shichu["edition"] = edition
        shichu["engine_version"] = "0.7.0"
    raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    chart = saved_chart(raw, "shichu_full")
    before = deepcopy(doc)
    expected = routes._chart_prompt_for_yaml_text(chart, raw, fallback_doc=doc, lang=lang)
    monkeypatch.setattr(routes, "_load_chart_display_yaml", lambda *a: pytest.fail("Duplicate parse"))
    assert routes._chart_prompt_for_yaml_text(
        chart, raw, fallback_doc=doc, parsed_doc=doc, lang=lang
    ) == expected
    assert _typed_tree(doc) == _typed_tree(before)


@pytest.mark.parametrize("raw", ["[unterminated", "!!python/name:builtins.len"])
def test_invalid_yaml_keeps_prompt_fallback(raw):
    doc = yaml.safe_load((FIXTURES / "spring_exact_base.yaml").read_text(encoding="utf-8"))
    chart = saved_chart(raw, "shichu_full")
    assert routes._chart_prompt_for_yaml_text(chart, raw, fallback_doc=doc) == (
        routes._chart_prompt_for_yaml_text(chart, raw, fallback_doc=doc, parsed_doc=doc)
    )


@pytest.mark.parametrize("product_type,edition", [("shichu", "basic"), ("shichu_full", "full"), ("shichu_full", None)])
@pytest.mark.parametrize("lang", ["ja", "en", "es", "de"])
def test_four_pillars_page_parses_original_once_and_keeps_full_yaml(product_type, edition, lang, monkeypatch, caplog):
    raw = (FIXTURES / "spring_exact_20years_expanded.yaml").read_text(encoding="utf-8")
    if edition:
        doc = yaml.safe_load(raw)
        doc["systems"]["shichusuimei"].update(edition=edition, engine_version="0.7.0")
        raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    raw = raw.replace("\n", "\r\n") + "\r\n"
    chart = saved_chart(raw, product_type)
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **k: deepcopy(chart))
    loader = routes._load_chart_display_yaml
    inputs = []
    parsed_documents = []

    def counted(text):
        inputs.append(text)
        parsed = loader(text)
        parsed_documents.append((parsed, _typed_tree(deepcopy(parsed))))
        return parsed

    monkeypatch.setattr(routes, "_load_chart_display_yaml", counted)
    client = TestClient(routes.app)  # Do not run DB startup/lifespan.
    response = client.get(f"/chart/fictional?lang={lang}")
    assert response.status_code == 200
    assert inputs == [raw]
    # All page consumers share this doc, including both prompts and notices.
    assert all(_typed_tree(doc) == before for doc, before in parsed_documents)
    assert js_json_constant(response.text, "SHARE_YAML") == raw
    assert "const FULL_YAML_INLINE = SHARE_YAML;" in response.text
    # Exact saved bytes remain available; rendering must not mutate storage.
    assert client.get("/chart/fictional.yaml").content == raw.encode()
    assert chart["prompt_text"] == "original saved prompt"
    assert "prompt_build_ms" in caplog.text


@pytest.mark.parametrize("variant", ["full", "asteroids", "long_term"])
def test_western_lighter_yaml_has_its_own_prompt_and_keeps_lazy_full_download(variant, monkeypatch):
    doc = _samples_long_term_doc() if variant == "long_term" else _asteroid_dense_full_doc()
    if variant == "asteroids":
        doc["systems"]["western"].pop("transit", None)
        doc["product"]["options"]["transit"] = False
    raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    chart = saved_chart(raw, "western_full" if variant == "full" else "western_basic")
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **k: deepcopy(chart))
    expected_share = routes._chart_share_yaml_text(chart, doc=doc)
    expected_prompt = routes._chart_prompt_for_yaml_text(chart, expected_share, fallback_doc=doc)
    loader = routes._load_chart_display_yaml
    inputs = []

    def counted(text):
        inputs.append(text)
        return loader(text)

    monkeypatch.setattr(routes, "_load_chart_display_yaml", counted)
    response = TestClient(routes.app).get("/chart/fictional")
    assert response.status_code == 200
    assert inputs == ([raw] if expected_share == raw else [raw, expected_share])
    assert js_json_constant(response.text, "SHARE_YAML") == expected_share
    assert js_json_constant(response.text, "SHARE_PROMPT") == expected_prompt
    assert 'const FULL_YAML_INLINE = "";' in response.text
    if variant == "full":
        # The lite copy omits asteroids, unlike the complete saved chart.
        assert "小惑星" not in expected_prompt.splitlines()[0]


def test_distinct_share_and_full_strings_are_not_deduplicated(monkeypatch):
    raw = "input: {}\nsystems: {}\n"
    chart = saved_chart(raw, "shichu")
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **k: deepcopy(chart))
    monkeypatch.setattr(routes, "_chart_share_yaml_text", lambda *a, **k: "input: {}\nsystems: {}\nshared: true\n")
    response = TestClient(routes.app).get("/chart/fictional")
    assert response.status_code == 200
    assert js_json_constant(response.text, "FULL_YAML_INLINE") == raw
    assert js_json_constant(response.text, "SHARE_YAML") != raw
