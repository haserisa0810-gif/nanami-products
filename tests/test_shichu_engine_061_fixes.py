"""エンジン0.6.1系の修正テスト（Q06: 1970年以前のOS依存、Q07: 得令説明）。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services import shichusuimei_calc as core

AS_OF = datetime(2026, 10, 12, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_pre_1970_birth_computes_on_any_os():
    # Q06: Windows の fromtimestamp 負値制限で 1970-01-05 ごろより前の出生が
    # OSError になっていた。epoch+timedelta 化後は全OSで計算できる。
    result = core.calc_shichusuimei_from_payload(
        {"year": 1950, "month": 7, "day": 15, "hour": 13, "minute": 30, "gender": "female"}, as_of=AS_OF,
    )
    daiun = result["normalized_data"]["daiun"]
    assert daiun["direction"] == "reverse"  # 1950=庚寅（陽年）×女性
    assert len(daiun["items"]) == 10
    assert daiun["start_age_text"]
    result2 = core.calc_shichusuimei_from_payload(
        {"year": 1965, "month": 6, "day": 1, "hour": 10, "minute": 0, "gender": "male"}, as_of=AS_OF,
    )
    assert len(result2["normalized_data"]["daiun"]["items"]) == 10


def test_jdut_conversion_roundtrip_including_pre_epoch():
    for dt in (
        datetime(1950, 3, 6, 4, 30, tzinfo=timezone.utc),
        datetime(1969, 12, 7, 0, 0, tzinfo=timezone.utc),
        datetime(1990, 5, 5, 18, 35, tzinfo=timezone.utc),
        datetime(2026, 2, 3, 20, 2, tzinfo=timezone.utc),
    ):
        jd = core.julian_day(dt)
        back = core._jdut_to_datetime_utc(jd)
        assert abs((back - dt).total_seconds()) < 1.0


def test_strength_score_labels_leak_direction_without_delta():
    # Q07: 甲（木）×午月（火）= 日干が月支を生じる洩気方向。従来は「中立」と
    # 説明されていた。スコアは互換維持のため変更しない（delta 0）。
    result = core._calc_strength_score(core.Pillars4("庚午", "壬午", "甲子", "甲子"))
    tokurei = [b for b in result["breakdown"] if str(b.get("name", "")).startswith("得令")]
    assert len(tokurei) == 1
    assert tokurei[0]["name"] == "得令(洩気)"
    assert tokurei[0]["delta"] == 0
    assert "洩れる" in tokurei[0]["detail"]
