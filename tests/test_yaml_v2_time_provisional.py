from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml
import pytest
from fastapi.testclient import TestClient

import routes
from services.acg_api import ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR, AcgYamlFormatError, personal_geojson
from services.chart_svg import build_horoscope_svg_from_yaml
from services.light_yaml import build_base_astrology_yaml
from services.mcp_chart_service import build_section_yaml
from services.prompt_builder import build_prompt
from services.yaml_exporter import (
    build_product_yaml,
    read_body_house,
    read_natal_angles,
    read_natal_houses,
)


FIXTURES = Path(__file__).parent / "fixtures"
V1_DOC = yaml.safe_load((FIXTURES / "yaml_v1_base.yaml").read_text(encoding="utf-8"))


def _build(*, birth_time: str | None, accuracy: str):
    return build_product_yaml(
        title="YAML v2 test",
        birth_date="1990-05-15",
        birth_time=birth_time,
        prefecture="東京都",
        birth_place_label="東京都",
        birth_lat=35.6895,
        birth_lng=139.6917,
        birth_time_accuracy=accuracy,
        include_asteroids=False,
        include_transit=False,
    )


def _natal(doc):
    return doc["systems"]["western"]["natal"]


def test_unknown_time_moves_time_sensitive_values_to_provisional():
    yaml_text, _prompt, doc = _build(birth_time=None, accuracy="unknown")
    natal = _natal(doc)
    provisional = natal["time_sensitive_provisional"]

    assert doc["meta"]["schema_version"] == "2.0"
    assert "time_sensitive_provisional:" in yaml_text
    assert provisional["status"] == "assumed_birth_time"
    assert provisional["assumed_time"] == "12:00"
    assert provisional["valid_for_assertive_interpretation"] is False
    assert provisional["recalculation_required_when_time_known"] is True
    assert provisional["reason"] == "birth_time_unknown"
    assert "houses" not in natal
    assert "angles" not in natal
    assert "ASC" not in natal["bodies"]
    assert "MC" not in natal["bodies"]
    assert all("house" not in body for body in natal["bodies"].values())
    assert all(
        aspect["body1"] not in {"ASC", "MC", "Vertex"}
        and aspect["body2"] not in {"ASC", "MC", "Vertex"}
        for aspect in natal["aspects"]
    )
    assert provisional["houses"]
    assert provisional["angles"]["asc"]
    assert provisional["body_house_placements"]


def test_exact_time_keeps_v1_natal_shape_except_schema_version():
    _yaml_text, _prompt, doc = _build(birth_time="08:30", accuracy="exact")
    natal = _natal(doc)

    assert doc["meta"]["schema_version"] == "2.0"
    assert "time_sensitive_provisional" not in natal
    assert natal["houses"]
    assert natal["bodies"]["ASC"]["house"] == 1
    assert all("house" in body for body in natal["bodies"].values())


def test_approximate_time_uses_approximate_metadata():
    _yaml_text, _prompt, doc = _build(birth_time="09:00", accuracy="approximate")
    provisional = _natal(doc)["time_sensitive_provisional"]

    assert provisional["status"] == "approximate_birth_time"
    assert provisional["reason"] == "birth_time_approximate"
    assert provisional["assumed_time"] == "09:00"


def test_natal_readers_support_v1_and_v2():
    v1_natal = _natal(V1_DOC)
    _yaml_text, _prompt, v2_doc = _build(birth_time=None, accuracy="unknown")
    v2_natal = _natal(v2_doc)

    assert read_natal_houses(v1_natal) == v1_natal["houses"]
    assert read_natal_angles(v1_natal)["asc"] == v1_natal["bodies"]["ASC"]
    assert read_body_house(v1_natal, "Sun") == 10
    assert read_natal_houses(v2_natal) == v2_natal["time_sensitive_provisional"]["houses"]
    assert read_natal_angles(v2_natal) == v2_natal["time_sensitive_provisional"]["angles"]
    assert read_body_house(v2_natal, "Sun") == v2_natal["time_sensitive_provisional"]["body_house_placements"]["Sun"]


def test_addon_args_accept_v1_and_v2_base_docs():
    v1_args = routes._addon_args_from_base_doc(V1_DOC)
    _yaml_text, _prompt, v2_doc = _build(birth_time=None, accuracy="unknown")
    v2_args = routes._addon_args_from_base_doc(v2_doc)

    routes._validate_addon_base_doc(V1_DOC, "western_asteroids_addon")
    routes._validate_addon_base_doc(v2_doc, "western_asteroids_addon")
    assert v1_args["birth_date"] == "1990-05-15"
    assert v1_args["birth_time"] == "08:30"
    assert v2_args["birth_date"] == "1990-05-15"
    assert v2_args["birth_time"] == "12:00"
    assert v2_args["birth_time_accuracy"] == "unknown"


def test_svg_draws_houses_from_provisional_section():
    yaml_text, _prompt, doc = _build(birth_time=None, accuracy="unknown")

    svg = build_horoscope_svg_from_yaml(yaml_text, doc=doc)

    assert svg is not None
    assert 'class="house-line"' in svg
    assert 'data-body="ASC"' in svg


def test_light_yaml_preserves_provisional_isolation():
    yaml_text, _prompt, _doc = _build(birth_time=None, accuracy="unknown")

    light_doc = yaml.safe_load(build_base_astrology_yaml(yaml_text))
    natal = _natal(light_doc)

    assert "time_sensitive_provisional" in natal
    assert "houses" not in natal
    assert all("house" not in body for body in natal["bodies"].values())


def test_mcp_natal_section_preserves_provisional_isolation():
    _yaml_text, _prompt, doc = _build(birth_time=None, accuracy="unknown")

    mcp_doc = yaml.safe_load(build_section_yaml(doc, ["natal"]))

    assert "time_sensitive_provisional" in _natal(mcp_doc)
    assert "houses" not in _natal(mcp_doc)


def test_prompt_contains_time_sensitive_priority_rules():
    prompt = build_prompt(birth_time_accuracy="unknown")

    assert "time_sensitive_provisional" in prompt
    assert "出生時刻が判明した場合は再計算が必要" in prompt
    assert "データに存在しないセクションを推測で補完しない" in prompt


def test_acg_v2_unknown_is_rejected_before_calculation():
    yaml_text, _prompt, _doc = _build(birth_time=None, accuracy="unknown")

    with patch("services.acg_api.lines_to_geojson") as calculate:
        with pytest.raises(AcgYamlFormatError, match=ACG_BIRTH_TIME_NOT_CONFIRMED_ERROR):
            personal_geojson(yaml_text)
    calculate.assert_not_called()


def _chart(doc, yaml_text):
    return {
        "yaml_text": yaml_text,
        "prompt_text": "",
        "options": {"product_type": "western_basic"},
        "buyer_name": "テスト",
        "birth_date": "1990-05-15",
        "birth_time": (doc.get("input") or {}).get("calculation_time"),
        "birth_place": "東京都",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
    }


def test_chart_page_shows_reissue_guidance_only_for_uncertain_time():
    unknown_yaml, _prompt, unknown_doc = _build(birth_time=None, accuracy="unknown")
    exact_yaml, _prompt, exact_doc = _build(birth_time="08:30", accuracy="exact")
    client = TestClient(routes.app)

    line_url = "https://example.invalid/official-line"
    with patch.dict("os.environ", {"LINE_ADD_FRIEND_URL": line_url}):
        with patch.object(routes, "_load_chart_or_404", return_value=_chart(unknown_doc, unknown_yaml)):
            unknown_response = client.get("/chart/unknown-token")
        with patch.object(routes, "_load_chart_or_404", return_value=_chart(exact_doc, exact_yaml)):
            exact_response = client.get("/chart/exact-token")

    assert unknown_response.status_code == 200
    assert "出生時刻が後から判明した場合" in unknown_response.text
    assert "時刻の修正・再発行" in unknown_response.text
    assert "時刻のみ変更可" in unknown_response.text
    assert "購入したショップからお問い合わせください" in unknown_response.text
    assert line_url not in unknown_response.text
    assert "あなたのデータでACGを開く" not in unknown_response.text
    assert exact_response.status_code == 200
    assert "出生時刻が後から判明した場合" not in exact_response.text
    assert "あなたのデータでACGを開く" in exact_response.text
