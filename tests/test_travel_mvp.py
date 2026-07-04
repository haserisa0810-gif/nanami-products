"""Astro Travel MVP のテスト。

- 生成エンジン（純粋計算・DB非依存）
- 入力バリデーション
- AI解釈プロンプトの再計算禁止ルール
- ルート結線（GET /travel / POST /travel/generate / GET /travel/result/{token}）
  ※ charts テーブルはメモリにモックして DB 非依存で確認する。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import yaml
from fastapi.testclient import TestClient

import routes
from services.travel.travel_generator import build_travel_report

NATAL_YAML = """
version: nanami-products-yaml-v1
systems:
  western:
    natal:
      subject:
        datetime: "1990-04-10T14:30:00+09:00"
        location: {lat: 35.68, lng: 139.69}
"""


def _valid_kwargs(**overrides):
    base = dict(
        natal_yaml_text=NATAL_YAML,
        purpose_key="creativity",
        location_name="Barcelona",
        country="Spain",
        latitude=41.3874,
        longitude=2.1686,
        timezone_name="Europe/Madrid",
        arrival_date="2027-04-10",
        departure_date="2027-04-17",
    )
    base.update(overrides)
    return base


# ─── 生成エンジン ──────────────────────────────────────────

def test_build_travel_report_produces_full_yaml():
    result = build_travel_report(**_valid_kwargs())
    doc = yaml.safe_load(result["yaml_text"])["travel_report"]
    assert doc["schema_version"] == "1.0"
    assert doc["app"] == "astro_travel"
    assert doc["input"]["purpose"]["key"] == "creativity"
    assert doc["input"]["stay"]["days"] == 8
    assert doc["input"]["location"]["latitude"] == 41.3874
    # ACG / Relocation / Transit が含まれる
    assert "nearest_lines" in doc["acg"]
    assert "house_emphasis" in doc["relocation"]
    assert "highlights" in doc["transit"]
    assert 1 <= doc["scoring"]["total_score"] <= 5
    # 解釈用の下地（テーマ・過ごし方・注意点）が入る
    assert doc["interpretation"]["recommended_actions"]
    assert doc["interpretation"]["cautions"]


def test_prompt_contains_no_recalculation_rule():
    result = build_travel_report(**_valid_kwargs())
    assert "再計算" in result["prompt_text"]
    assert "計算済み" in result["prompt_text"]


# ─── バリデーション ────────────────────────────────────────

def test_departure_before_arrival_is_rejected():
    with pytest.raises(ValueError) as exc:
        build_travel_report(**_valid_kwargs(arrival_date="2027-04-17", departure_date="2027-04-10"))
    assert "帰着日" in str(exc.value)


def test_missing_purpose_is_rejected():
    with pytest.raises(ValueError):
        build_travel_report(**_valid_kwargs(purpose_key="not_a_purpose"))


def test_empty_yaml_is_rejected():
    with pytest.raises(ValueError):
        build_travel_report(**_valid_kwargs(natal_yaml_text=""))


def test_invalid_coordinates_are_rejected():
    with pytest.raises(ValueError):
        build_travel_report(**_valid_kwargs(latitude="abc"))
    with pytest.raises(ValueError):
        build_travel_report(**_valid_kwargs(latitude=200))


# ─── ルート結線（DBモック） ────────────────────────────────

@pytest.fixture
def client_with_mem_db(monkeypatch):
    mem: dict[str, dict] = {}

    def fake_save_chart(**kwargs):
        row = dict(kwargs)
        row["created_at"] = datetime.now(timezone.utc)
        mem[kwargs["token"]] = row

    def fake_get_chart(token, include_svgs=True):
        return mem.get(token)

    monkeypatch.setattr(routes.pg_store, "save_chart", fake_save_chart)
    monkeypatch.setattr(routes.pg_store, "get_chart", fake_get_chart)
    return TestClient(routes.app), mem


def test_get_travel_form(client_with_mem_db):
    client, _mem = client_with_mem_db
    response = client.get("/travel")
    assert response.status_code == 200
    assert "次の旅行先" in response.text


def test_post_invalid_dates_returns_form_error(client_with_mem_db):
    client, _mem = client_with_mem_db
    response = client.post(
        "/travel/generate",
        data={
            "natal_yaml": NATAL_YAML,
            "purpose": "creativity",
            "location_name": "Barcelona",
            "latitude": "41.3874",
            "longitude": "2.1686",
            "arrival_date": "2027-04-17",
            "departure_date": "2027-04-10",
        },
    )
    assert response.status_code == 400
    assert "帰着日" in response.text


def test_full_flow_generate_and_result(client_with_mem_db):
    client, _mem = client_with_mem_db
    response = client.post(
        "/travel/generate",
        data={
            "natal_yaml": NATAL_YAML,
            "purpose": "creativity",
            "location_name": "Barcelona",
            "country": "Spain",
            "latitude": "41.3874",
            "longitude": "2.1686",
            "timezone": "Europe/Madrid",
            "arrival_date": "2027-04-10",
            "departure_date": "2027-04-17",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/travel/result/")
    token = location.rsplit("/", 1)[-1]

    result = client.get(location)
    assert result.status_code == 200
    assert "総合評価" in result.text
    assert "AIに渡せるYAML" in result.text
    assert result.headers.get("x-robots-tag") == "noindex, nofollow"

    # 保存された YAML が travel_report であること
    saved = _mem[token]
    assert saved["options"]["product_type"] == "travel"
    assert "travel_report" in saved["yaml_text"]


def test_travel_result_rejects_non_travel_token(client_with_mem_db):
    client, mem = client_with_mem_db
    mem["other"] = {
        "token": "other",
        "yaml_text": "version: x",
        "prompt_text": "",
        "options": {"product_type": "western_basic"},
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    }
    response = client.get("/travel/result/other")
    assert response.status_code == 404
