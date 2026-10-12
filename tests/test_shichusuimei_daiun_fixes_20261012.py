"""2026-10-12 大運・流年レビュー指摘の修正（I1-I3, Q06, Q07。D-1 は test_shichu_time_window.py）。旧原本の扱いは test_shichusuimei_editions.py。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from services import shichusuimei_calc as core
from services.yaml_exporter import SHICHU_FORTUNE_CYCLES_ADDON_PROMPT

JST = ZoneInfo("Asia/Tokyo")
AS_OF = datetime(2026, 10, 12, 12, 0, tzinfo=JST)


def _calc(y, m, d, hour, minute, gender="male", **kw):
    payload = {"year": y, "month": m, "day": d, "hour": hour, "minute": minute, "gender": gender}
    return core.calc_shichusuimei_from_payload(payload, as_of=kw.pop("as_of", AS_OF), **kw)


# --- I1 / I2: 現在の大運 -------------------------------------------------------------

def test_current_daiun_carries_structural_analysis_of_its_item():
    nd = _calc(1990, 5, 10, 10, 0)["normalized_data"]
    current = nd["annual_fortune"]["current_daiun"]
    assert nd["annual_fortune"]["current_daiun_status"] == "selected"
    item = next(i for i in nd["daiun"]["items"] if i["index"] == current["index"])
    assert current["structural_analysis"] == item["structural_analysis"]


def test_before_first_daiun_is_explained():
    nd = _calc(1990, 5, 10, 10, 0, as_of=datetime(1991, 1, 1, 12, tzinfo=JST))["normalized_data"]
    annual = nd["annual_fortune"]
    assert annual["current_daiun"] is None
    assert annual["current_daiun_status"] == "before_first_daiun"
    assert "起運前" in annual["current_daiun_note"]


def test_unknown_gender_current_daiun_status():
    annual = _calc(1990, 5, 10, 10, 0, "unknown")["normalized_data"]["annual_fortune"]
    assert annual["current_daiun"] is None
    assert annual["current_daiun_status"] == "undetermined_gender"


# --- I3: 追加商品の指示 ----------------------------------------------------------------

def test_addon_prompt_names_annual_forecasts():
    assert "annual_forecasts" in SHICHU_FORTUNE_CYCLES_ADDON_PROMPT.split("【四柱推命構造分析の優先規則】")[0] \
        or "daiun・annual_fortune・annual_forecasts" in SHICHU_FORTUNE_CYCLES_ADDON_PROMPT


# --- Q06 / Q07 ------------------------------------------------------------------------

def test_jd_conversion_handles_dates_before_1970():
    # JD 2433282.5 = 1950-01-01 00:00 UTC。Windows の fromtimestamp では負値で OSError になっていた。
    assert core._jdut_to_datetime_utc(2433282.5) == datetime(1950, 1, 1, tzinfo=timezone.utc)
    result = _calc(1950, 7, 15, 13, 30, "female")
    assert result["normalized_data"]["daiun"]["items"]


def test_legacy_strength_describes_leakage_without_changing_score():
    strength = core._calc_strength_score(core.Pillars4("庚午", "壬午", "甲子", "甲子"))
    seasonal = strength["breakdown"][0]
    assert seasonal["name"] == "得令(洩気)"
    assert seasonal["delta"] == 0
    assert "中立" not in seasonal["detail"]
