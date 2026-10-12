from copy import deepcopy
from datetime import datetime, timezone

import pytest
import yaml

from services.shichusuimei_annual_prototype import build_period_prototype, dump_period_prototype, expand_shared_year, load_prototype_base
from services.shichusuimei_annual_report import build_annual_fortune_report
from tests.test_shichusuimei_annual_report import synthetic_doc


@pytest.mark.parametrize("years", [5, 10, 20])
def test_period_is_lossless_and_identifies_each_year(years):
    base = synthetic_doc()
    original = deepcopy(base)
    shared = build_period_prototype(base, 2026, years)
    expanded = build_period_prototype(base, 2026, years, layout="expanded")
    text = dump_period_prototype(shared)
    assert yaml.safe_load(text) == shared
    assert "&id" not in text and "*id" not in text
    details = shared["systems"]["shichusuimei"]["annual_details"]
    assert details["period"]["end_effective_year"] == 2026 + years - 1
    assert details["base_reference"]["chart_id"] == base["meta"]["chart_id"]
    assert shared["meta"]["production_ready"] is False
    assert shared["product"]["price"] is None
    assert base == original
    for year in range(2026, 2026 + years):
        annual = build_annual_fortune_report(base, year)["annual_fortune_report"]
        assert expand_shared_year(yaml.safe_load(text), year) == annual
        assert expand_shared_year(expanded, year) == annual
    with pytest.raises(ValueError):
        expand_shared_year(shared, 2025)


@pytest.mark.parametrize("start,years", [(1799, 5), (2395, 10), (2026, 6), (2026, True)])
def test_invalid_experiment_period_is_rejected(start, years):
    with pytest.raises(ValueError):
        build_period_prototype(synthetic_doc(), start, years)


def test_url_and_yaml_share_existing_loader_and_return_identical_results(monkeypatch):
    import routes
    base = synthetic_doc()
    token = "abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *args, **kwargs: {"yaml_text": yaml.safe_dump(base), "options": {}})
    by_url = load_prototype_base(previous_chart_url=f"https://chart.nanami-astro.com/chart/{token}.yaml")
    by_yaml = load_prototype_base(base_yaml="```yaml\n" + yaml.safe_dump(base) + "```")
    assert by_url == by_yaml
    assert build_period_prototype(by_url, 2026, 5) == build_period_prototype(by_yaml, 2026, 5)


@pytest.mark.parametrize("source", ["[broken", "[a,b]", "systems: {western: {}}", "systems: {shichusuimei: {normalized_data: {daiun: {}}}}"])
def test_invalid_yaml_wrong_system_or_addon_without_natal_is_rejected(source):
    with pytest.raises(ValueError):
        load_prototype_base(base_yaml=source)


@pytest.mark.parametrize("url", ["https://evil.example/chart/abcdefghijklmnopqrstuvwxyz", "file:///chart/abcdefghijklmnopqrstuvwxyz",
                                 "https://chart.nanami-astro.com/elsewhere", "https://user:pass@chart.nanami-astro.com/chart/abcdefghijklmnopqrstuvwxyz",
                                 "http://127.0.0.1/chart/abcdefghijklmnopqrstuvwxyz"])
def test_disallowed_urls_never_access_db(monkeypatch, url):
    import routes
    def forbidden(*args, **kwargs):
        raise AssertionError("DB lookup is forbidden for this input")
    monkeypatch.setattr(routes.pg_store, "get_chart", forbidden)
    with pytest.raises(ValueError):
        load_prototype_base(previous_chart_url=url)


def test_url_expiry_and_yaml_fallback_for_existing_buyers(monkeypatch):
    import routes
    base = synthetic_doc()
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *args, **kwargs: {
        "yaml_text": yaml.safe_dump(base), "expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc), "options": {}})
    with pytest.raises(ValueError, match="有効期限"):
        load_prototype_base(previous_chart_url="https://chart.nanami-astro.com/chart/abcdefghijklmnopqrstuvwxyz")
    assert load_prototype_base(base_yaml=yaml.safe_dump(base)) == base


def test_missing_chart_and_missing_input_are_rejected(monkeypatch):
    import routes
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *args, **kwargs: None)
    with pytest.raises(ValueError):
        load_prototype_base(previous_chart_url="https://chart.nanami-astro.com/chart/abcdefghijklmnopqrstuvwxyz")
    with pytest.raises(ValueError):
        load_prototype_base()


def test_legacy_fingerprint_is_stable_and_not_purchase_authentication():
    base = synthetic_doc()
    base.pop("meta")
    base["input"] = {"title": "PRIVATE-NAME", "birth_place": "PRIVATE-ADDRESS"}
    one = build_period_prototype(base, 2026, 5)
    base["input"]["title"] = "OTHER-NAME"
    two = build_period_prototype(base, 2026, 10)
    refs = [p["systems"]["shichusuimei"]["annual_details"]["base_reference"] for p in (one, two)]
    assert refs[0]["structural_fingerprint"] == refs[1]["structural_fingerprint"]
    assert refs[0]["chart_id"] is None
    assert "本人確認・購入証明ではなく" in refs[0]["fingerprint_note"]
    assert "PRIVATE-" not in dump_period_prototype(one)


def test_base_pages_and_routes_are_not_modified_for_phase_one():
    import routes
    from pathlib import Path
    assert not any("annual-fortune" in route.path for route in routes.app.routes)
    assert 'id="annual-form"' not in Path("templates/chart_page.html").read_text(encoding="utf-8")
    assert not any("annual_details" in option["value"] for option in routes.ADDON_FORM_OPTIONS)
