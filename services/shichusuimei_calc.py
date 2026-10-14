from __future__ import annotations

"""四柱推命 計算（年/月/日/時） + 基本特徴量

実装済み:
- 年柱 / 月柱（節入り）
- 日柱 / 時柱
- 蔵干
- 十神
- 五行カウント（表示用 / 蔵干込み）
- 空亡（旬空）
- 十二運
- 身強スコア目安
- 大運（年干陰陽 × 出生時の性別 で順逆判定）

注意:
- 日替わり境界は流派差があるため option(day_change_at_23) で切替
- 性別は四柱推命の計算上は「出生時の性別」を使う
"""

from dataclasses import dataclass, asdict
import calendar
from datetime import datetime, timezone, timedelta
import os
from zoneinfo import ZoneInfo
from typing import Any
from services.birth_datetime import resolve_birth_datetime

ENGINE_VERSION = "0.7.0"

# 販売商品ごとの出力範囲。計算エンジンは共通で、basic は従来の基本版（NP-SC）と同じ項目に
# 計算不具合の修正と不確実性の明示（D-1 の大運保留を含む）だけを加えたもの、full は
# 構造分析・各大運の作用・伏吟/反吟/天干冲・10年予測（annual_forecasts）を含む FULL 版（NP-SCF）。
SHICHUSUIMEI_EDITIONS = ("basic", "full")


def apply_shichusuimei_edition(result: dict[str, Any], edition: str) -> dict[str, Any]:
    """calc_shichusuimei_from_payload() の戻り値を販売版の出力範囲にそろえる（その場で変更）。"""
    if edition not in SHICHUSUIMEI_EDITIONS:
        raise ValueError(f"shichusuimei edition must be one of {SHICHUSUIMEI_EDITIONS}")
    result["edition"] = edition
    if edition == "full":
        return result
    nd = result.get("normalized_data") or {}
    nd.pop("structural_analysis", None)
    nd.pop("annual_forecasts", None)
    full_only_item_keys = ("structural_analysis", "special_relations_natal")
    for item in (nd.get("daiun") or {}).get("items") or []:
        for key in full_only_item_keys:
            item.pop(key, None)
    annual = nd.get("annual_fortune") or {}
    for key in ("structural_analysis", "special_relations_natal", "special_relations_daiun"):
        annual.pop(key, None)
    if isinstance(annual.get("current_daiun"), dict):
        for key in full_only_item_keys:
            annual["current_daiun"].pop(key, None)
    reference = nd.get("time_sensitive_reference")
    if isinstance(reference, dict):
        reference["note"] = "時柱を含む五行集計・身強スコア等は参考値。原局・流年の関係は時柱を除外"
    assumptions = (result.get("input") or {}).get("assumptions") or {}
    assumptions.pop("structural_time_basis", None)
    assumptions.pop("special_relations_rules", None)
    result["unknowns"] = [
        ("時柱・五行・身強スコアは仮置き／推定時刻の参考値。原局・流年の関係は時柱を除外"
         if u.startswith("構造分析は時柱を除外") else u.replace("大運・年別予測を保留", "大運を保留"))
        for u in result.get("unknowns") or []
    ]
    return result

from pathlib import Path
import swisseph as swe

def _ephe_candidates() -> list[Path]:
    candidates: list[Path] = []

    env_path = os.getenv("SWEPH_EPHE_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend([
        Path(__file__).resolve().parents[1] / "ephe",
        Path("/app/ephe"),
    ])

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _resolve_ephe_dir() -> Path | None:
    for ephe_dir in _ephe_candidates():
        if ephe_dir.exists() and any(ephe_dir.glob("*.se1")):
            return ephe_dir
    return None


def configure_ephemeris() -> int:
    ephe_dir = _resolve_ephe_dir()
    if ephe_dir is not None:
        swe.set_ephe_path(str(ephe_dir))
        return swe.FLG_SWIEPH
    return swe.FLG_MOSEPH

def ephemeris_debug_info() -> dict:
    resolved = _resolve_ephe_dir()
    candidates = _ephe_candidates()
    ephe_dir = resolved or candidates[0]
    files = sorted([p.name for p in ephe_dir.glob("*")]) if ephe_dir.exists() else []
    return {
        "ephe_dir": str(ephe_dir),
        "ephe_dir_exists": ephe_dir.exists(),
        "ephe_files": files,
        "has_se1": any(name.endswith(".se1") for name in files),
        "resolved_ephe_dir": str(resolved) if resolved is not None else None,
        "searched_ephe_dirs": [str(p) for p in candidates],
        "env_sweph_ephe_path": os.getenv("SWEPH_EPHE_PATH", "").strip() or None,
    }

# Swiss Ephemeris（節気計算に使用）
try:
    import swisseph as swe  # type: ignore
except Exception:  # pragma: no cover
    swe = None  # type: ignore


# 0=甲子 ... 59=癸亥
KANSHI_60 = [
    "甲子","乙丑","丙寅","丁卯","戊辰","己巳","庚午","辛未","壬申","癸酉",
    "甲戌","乙亥","丙子","丁丑","戊寅","己卯","庚辰","辛巳","壬午","癸未",
    "甲申","乙酉","丙戌","丁亥","戊子","己丑","庚寅","辛卯","壬辰","癸巳",
    "甲午","乙未","丙申","丁酉","戊戌","己亥","庚子","辛丑","壬寅","癸卯",
    "甲辰","乙巳","丙午","丁未","戊申","己酉","庚戌","辛亥","壬子","癸丑",
    "甲寅","乙卯","丙辰","丁巳","戊午","己未","庚申","辛酉","壬戌","癸亥",
]

STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

# 月支（節入り）順：立春=寅月スタート
MONTH_BRANCHES = ["寅","卯","辰","巳","午","未","申","酉","戌","亥","子","丑"]

# 干の五行
STEM_ELEMENT = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# 支の本気（代表五行）
BRANCH_ELEMENT = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

STEM_COMBINATIONS = {
    frozenset(("甲", "己")): "土",
    frozenset(("乙", "庚")): "金",
    frozenset(("丙", "辛")): "水",
    frozenset(("丁", "壬")): "木",
    frozenset(("戊", "癸")): "火",
}

BRANCH_CLASHES = {
    frozenset(("子", "午")),
    frozenset(("丑", "未")),
    frozenset(("寅", "申")),
    frozenset(("卯", "酉")),
    frozenset(("辰", "戌")),
    frozenset(("巳", "亥")),
}

BRANCH_SIX_HARMONIES = {
    frozenset(("子", "丑")): "土",
    frozenset(("寅", "亥")): "木",
    frozenset(("卯", "戌")): "火",
    frozenset(("辰", "酉")): "金",
    frozenset(("巳", "申")): "水",
    frozenset(("午", "未")): "火",
}

BRANCH_HARMS = {
    frozenset(("子", "未")),
    frozenset(("丑", "午")),
    frozenset(("寅", "巳")),
    frozenset(("卯", "辰")),
    frozenset(("申", "亥")),
    frozenset(("酉", "戌")),
}

# 六破（刑冲合害と独立して併記する）。巳申・寅亥は六合とも重なる。
BRANCH_DESTRUCTIONS = {
    frozenset(("子", "酉")), frozenset(("卯", "午")),
    frozenset(("辰", "丑")), frozenset(("未", "戌")),
    frozenset(("寅", "亥")), frozenset(("巳", "申")),
}

BRANCH_PUNISHMENTS = {
    frozenset(("子", "卯")): "無礼の刑",
}

BRANCH_SELF_PUNISHMENTS = {"辰", "午", "酉", "亥"}

BRANCH_THREE_PUNISHMENTS = {
    frozenset(("寅", "巳", "申")): "無恩の刑",
    frozenset(("丑", "戌", "未")): "持勢の刑",
}

BRANCH_TRIADS = {
    frozenset(("申", "子", "辰")): "水局",
    frozenset(("亥", "卯", "未")): "木局",
    frozenset(("寅", "午", "戌")): "火局",
    frozenset(("巳", "酉", "丑")): "金局",
}

# 神殺（代表的な表）。日干基準を基本に、天徳は月支基準。
TENOTSU_KIJIN_BY_DAY_STEM = {
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["卯", "巳"], "癸": ["卯", "巳"],
    "辛": ["寅", "午"],
}

BUNSHO_BY_DAY_STEM = {
    "甲": ["巳"], "乙": ["午"], "丙": ["申"], "丁": ["酉"], "戊": ["申"],
    "己": ["酉"], "庚": ["亥"], "辛": ["子"], "壬": ["寅"], "癸": ["卯"],
}

TENTOKU_BY_MONTH_BRANCH = {
    "寅": "丁", "卯": "申", "辰": "壬", "巳": "辛",
    "午": "亥", "未": "甲", "申": "癸", "酉": "寅",
    "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚",
}

# 蔵干（代表的な表）
HIDDEN_STEMS = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 陰陽
YIN_YANG = {
    "甲": "陽", "乙": "陰",
    "丙": "陽", "丁": "陰",
    "戊": "陽", "己": "陰",
    "庚": "陽", "辛": "陰",
    "壬": "陽", "癸": "陰",
}

# 空亡（旬空）
KUBO_BY_JUN = [
    ["戌", "亥"],  # 甲子旬
    ["申", "酉"],  # 甲戌旬
    ["午", "未"],  # 甲申旬
    ["辰", "巳"],  # 甲午旬
    ["寅", "卯"],  # 甲辰旬
    ["子", "丑"],  # 甲寅旬
]

JUN_LABELS = ["甲子旬", "甲戌旬", "甲申旬", "甲午旬", "甲辰旬", "甲寅旬"]


# 時支の境界（ローカル時刻）
# 子:23:00-00:59, 丑:01:00-02:59, ... 戌:19:00-20:59, 亥:21:00-22:59
def _time_branch_index(local_dt: datetime) -> int:
    h = local_dt.hour
    m = local_dt.minute
    minutes = h * 60 + m

    # 子だけ日跨ぎなので特別扱い
    if minutes >= 23 * 60 or minutes < 1 * 60:
        return 0  # 子
    # それ以外は 2時間刻み：1:00-2:59 が丑(1) ... 21:00-22:59 が亥(11)
    # 1:00 を起点に 120分ブロック
    return 1 + ((minutes - 60) // 120)


def julian_day(dt_utc: datetime) -> float:
    """グレゴリオ暦のUTC datetime -> JD

    dt_utc は timezone.utc の aware datetime を想定
    """
    if dt_utc.tzinfo is None:
        raise ValueError("dt_utc must be timezone-aware (UTC).")
    dt_utc = dt_utc.astimezone(timezone.utc)

    y = dt_utc.year
    m = dt_utc.month
    d = dt_utc.day
    frac_day = (dt_utc.hour + (dt_utc.minute + dt_utc.second / 60) / 60) / 24

    if m <= 2:
        y -= 1
        m += 12

    A = y // 100
    B = 2 - A + (A // 4)

    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5
    return jd + frac_day


def _dt_utc_to_jdut(dt_utc: datetime) -> float:
    """UTC datetime -> Swiss Ephemeris 用の JD(UT)"""
    if swe is None:
        raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")
    dt_utc = dt_utc.astimezone(timezone.utc)
    hour = dt_utc.hour + (dt_utc.minute + dt_utc.second / 60) / 60
    return float(swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour))


def _sun_lon_deg(jd_ut: float) -> float:
    """太陽黄経（0-360）"""
    if swe is None:
        raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")
    flags = configure_ephemeris()
    xx, _ = swe.calc_ut(jd_ut, swe.SUN, flags)
    return float(xx[0]) % 360.0


def _angle_diff_deg(a: float, b: float) -> float:
    """角度差 a-b を [-180, 180) に正規化"""
    return ((a - b + 180.0) % 360.0) - 180.0


def _find_solar_longitude_crossing(
    *,
    target_lon_deg: float,
    approx_dt_utc: datetime,
    search_days: int = 7,
) -> datetime:
    """太陽黄経が target_lon_deg を横切る瞬間を近傍探索して返す（UTC）。"""
    if swe is None:
        raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")

    target = target_lon_deg % 360.0
    approx = approx_dt_utc.astimezone(timezone.utc)

    step = timedelta(hours=6)
    start = approx - timedelta(days=search_days)
    end = approx + timedelta(days=search_days)

    t = start
    jd0 = _dt_utc_to_jdut(t)
    f0 = _angle_diff_deg(_sun_lon_deg(jd0), target)

    while t < end:
        t1 = t + step
        jd1 = _dt_utc_to_jdut(t1)
        f1 = _angle_diff_deg(_sun_lon_deg(jd1), target)

        if f0 == 0:
            return t

        if (f0 < 0 <= f1) or (f0 > 0 >= f1):
            lo_t, hi_t = t, t1
            lo_f, hi_f = f0, f1
            for _ in range(60):
                mid_t = lo_t + (hi_t - lo_t) / 2
                mid_jd = _dt_utc_to_jdut(mid_t)
                mid_f = _angle_diff_deg(_sun_lon_deg(mid_jd), target)
                if abs((hi_t - lo_t).total_seconds()) <= 1:
                    return mid_t
                if (lo_f < 0 <= mid_f) or (lo_f > 0 >= mid_f):
                    hi_t, hi_f = mid_t, mid_f
                else:
                    lo_t, lo_f = mid_t, mid_f
            return lo_t

        t, f0 = t1, f1

    raise RuntimeError("節気計算に失敗しました（探索範囲不足の可能性）")


def _lichun_utc_for_year(year: int, tz_name: str) -> datetime:
    """指定年の立春（太陽黄経315°）の瞬間を UTC で返す。"""
    tz = ZoneInfo(tz_name)
    approx_local = datetime(year, 2, 4, 12, 0, 0, tzinfo=tz)
    return _find_solar_longitude_crossing(
        target_lon_deg=315.0,
        approx_dt_utc=approx_local.astimezone(timezone.utc),
    )


def _month_index_from_sun_lon(sun_lon_deg: float) -> int:
    """太陽黄経から節入り月インデックス（0=寅月..11=丑月）"""
    return int(((sun_lon_deg - 315.0) % 360.0) // 30.0)


def _year_kanshi_from_effective_year(y: int) -> str:
    idx = (y - 4) % 60
    return KANSHI_60[idx]


def _month_kanshi_from_year_stem_and_index(year_stem: str, month_index: int) -> str:
    start_map = {
        "甲": "丙", "己": "丙",
        "乙": "戊", "庚": "戊",
        "丙": "庚", "辛": "庚",
        "丁": "壬", "壬": "壬",
        "戊": "甲", "癸": "甲",
    }
    if year_stem not in start_map:
        raise ValueError(f"Unknown year stem: {year_stem}")
    start = start_map[year_stem]
    stem = STEMS[(STEMS.index(start) + month_index) % 10]
    branch = MONTH_BRANCHES[month_index]
    return stem + branch


def _element_generate(elem: str) -> str:
    order = ["木", "火", "土", "金", "水"]
    return order[(order.index(elem) + 1) % 5]


def _element_control(elem: str) -> str:
    control = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    return control[elem]


def ten_god(day_stem: str, other_stem: str) -> str:
    """日干から見た十神（通変星）"""
    dm_elem = STEM_ELEMENT[day_stem]
    ot_elem = STEM_ELEMENT[other_stem]
    dm_yy = YIN_YANG[day_stem]
    ot_yy = YIN_YANG[other_stem]
    same_polarity = (dm_yy == ot_yy)

    if ot_elem == dm_elem:
        return "比肩" if same_polarity else "劫財"
    if _element_generate(dm_elem) == ot_elem:
        return "食神" if same_polarity else "傷官"
    if _element_control(dm_elem) == ot_elem:
        return "偏財" if same_polarity else "正財"
    if _element_control(ot_elem) == dm_elem:
        return "偏官" if same_polarity else "正官"
    if _element_generate(ot_elem) == dm_elem:
        return "偏印" if same_polarity else "印綬"
    return "不明"


def _effective_local_date_for_day_pillar(
    local_dt: datetime,
    *,
    day_change_at_23: bool,
    day_boundary_hour: int | None = None,
) -> tuple[datetime.date, str]:
    """Civil-calendar modes: 01:00 standard, 23:00 next day, explicit 00:00.

    The boolean is a new-calculation UI adapter, never an old-YAML migration.
    Version <=0.4.0 had different boolean behavior; stored results stay intact.
    """
    boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
    local_date = local_dt.date()
    if boundary == 1 and local_dt.hour < 1:
        local_date -= timedelta(days=1)
    elif boundary == 23 and local_dt.hour >= 23:
        local_date += timedelta(days=1)
    return local_date, f"{boundary:02d}:00切替"


def resolve_day_boundary_hour(day_change_at_23: bool = False, day_boundary_hour: int | None = None) -> int:
    if type(day_change_at_23) is not bool:
        raise ValueError("day_change_at_23 must be a boolean; use day_boundary_hour for 0, 1 or 23")
    if day_boundary_hour is None:
        return 23 if day_change_at_23 else 1
    if type(day_boundary_hour) is not int or day_boundary_hour not in (0, 1, 23):
        raise ValueError("day_boundary_hour must be 0, 1 or 23")
    if day_change_at_23 and day_boundary_hour != 23:
        raise ValueError("day_change_at_23 conflicts with day_boundary_hour")
    return day_boundary_hour


def day_kanshi_from_birth(
    birth_dt: datetime,
    tz_name: str = "Asia/Tokyo",
    day_change_at_23: bool = False,
    *, day_boundary_hour: int | None = None,
) -> str:
    """Sexagenary day of the selected LOCAL civil date; UTC is not used.

    Gregorian ordinal +14 == Gregorian noon JDN +49 (0 = 甲子).
    Anchor: 2000-01-07 = 甲子. Astronomy continues to use UTC independently.
    """
    local_dt = resolve_birth_datetime(birth_dt, tz_name)
    local_date, _rule_label = _effective_local_date_for_day_pillar(
        local_dt,
        day_change_at_23=day_change_at_23,
        day_boundary_hour=day_boundary_hour,
    )
    idx = (local_date.toordinal() + 14) % 60
    return KANSHI_60[idx]


def hour_kanshi_from_day_stem_and_time(
    day_stem: str,
    birth_dt: datetime,
    tz_name: str = "Asia/Tokyo",
) -> str:
    """日干とローカル時刻から時柱（時干支）を算出。"""
    local_dt = resolve_birth_datetime(birth_dt, tz_name)

    b_idx = _time_branch_index(local_dt)
    branch = BRANCHES[b_idx]

    # 甲己日→子刻は甲、乙庚日→子刻は丙、丙辛日→子刻は戊、丁壬日→子刻は庚、戊癸日→子刻は壬
    start_stem_map = {
        "甲": "甲", "己": "甲",
        "乙": "丙", "庚": "丙",
        "丙": "戊", "辛": "戊",
        "丁": "庚", "壬": "庚",
        "戊": "壬", "癸": "壬",
    }
    if day_stem not in start_stem_map:
        raise ValueError(f"Unknown day stem: {day_stem}")

    start = start_stem_map[day_stem]
    start_idx = STEMS.index(start)
    stem = STEMS[(start_idx + b_idx) % 10]
    return stem + branch


@dataclass(frozen=True)
class Pillars:
    day: str
    hour: str


@dataclass(frozen=True)
class Pillars4:
    year: str
    month: str
    day: str
    hour: str


def pillars_day_hour(
    birth_dt: datetime,
    tz_name: str = "Asia/Tokyo",
    day_change_at_23: bool = False,
    *, day_boundary_hour: int | None = None,
) -> Pillars:
    day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=day_boundary_hour)
    day_stem = day[0]
    hour = hour_kanshi_from_day_stem_and_time(day_stem, birth_dt, tz_name=tz_name)
    return Pillars(day=day, hour=hour)


def year_month_pillars(
    birth_dt: datetime,
    tz_name: str = "Asia/Tokyo",
) -> tuple[str, str, dict[str, Any]]:
    """年柱・月柱（節入り）。

    戻り値: (year_kanshi, month_kanshi, debug)
    debug には立春時刻や太陽黄経などの内部情報を入れる。
    """
    tz = ZoneInfo(tz_name)
    local_dt = resolve_birth_datetime(birth_dt, tz_name)
    utc_dt = local_dt.astimezone(timezone.utc)

    if swe is None:
        raise RuntimeError("pyswisseph が読み込めません（requirements.txt を確認）")

    # 立春（年境界）
    lichun_utc = _lichun_utc_for_year(local_dt.year, tz_name)
    lichun_local = lichun_utc.astimezone(tz)
    effective_year = local_dt.year if local_dt >= lichun_local else (local_dt.year - 1)

    year_kanshi = _year_kanshi_from_effective_year(effective_year)

    # 月柱（節入り月）：太陽黄経で判定
    sun_lon = _sun_lon_deg(_dt_utc_to_jdut(utc_dt))
    month_index = _month_index_from_sun_lon(sun_lon)
    month_kanshi = _month_kanshi_from_year_stem_and_index(year_kanshi[0], month_index)

    debug = {
        "tz_name": tz_name,
        "local_datetime": local_dt.isoformat(),
        "lichun_local": lichun_local.isoformat(),
        "effective_year": effective_year,
        "sun_lon_deg": round(sun_lon, 6),
        "month_index": month_index,
        "month_branch": MONTH_BRANCHES[month_index],
    }
    return year_kanshi, month_kanshi, debug


def pillars4(
    birth_dt: datetime,
    tz_name: str = "Asia/Tokyo",
    day_change_at_23: bool = False,
    *, day_boundary_hour: int | None = None,
) -> Pillars4:
    """四柱（年/月/日/時）をまとめて算出。"""
    y, m, _dbg = year_month_pillars(birth_dt, tz_name=tz_name)
    day = day_kanshi_from_birth(birth_dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=day_boundary_hour)
    hour = hour_kanshi_from_day_stem_and_time(day[0], birth_dt, tz_name=tz_name)
    return Pillars4(year=y, month=m, day=day, hour=hour)


def _empty_five_counts() -> dict[str, int]:
    return {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}


def _five_elements_counts_visible(p: Pillars4) -> dict[str, int]:
    """表示用五行カウント（天干+地支のみ）。"""
    counts = _empty_five_counts()
    for stem in (p.year[0], p.month[0], p.day[0], p.hour[0]):
        counts[STEM_ELEMENT.get(stem, "土")] += 1
    for br in (p.year[1], p.month[1], p.day[1], p.hour[1]):
        counts[BRANCH_ELEMENT.get(br, "土")] += 1
    return counts


def _five_elements_counts_with_hidden(p: Pillars4) -> dict[str, int]:
    """蔵干込み五行カウント。"""
    counts = _five_elements_counts_visible(p)
    for br in (p.year[1], p.month[1], p.day[1], p.hour[1]):
        for hs in HIDDEN_STEMS.get(br, []):
            counts[STEM_ELEMENT.get(hs, "土")] += 1
    return counts


def _five_elements_counts(p: Pillars4) -> dict[str, Any]:
    return {
        "visible": _five_elements_counts_visible(p),
        "with_hidden_stems": _five_elements_counts_with_hidden(p),
    }


def _ten_gods_for_pillars(p: Pillars4) -> dict[str, Any]:
    dm = p.day[0]
    out: dict[str, Any] = {
        "day_master": dm,
        "pillars": {
            "year": {"stem": p.year[0], "ten_god": ten_god(dm, p.year[0])},
            "month": {"stem": p.month[0], "ten_god": ten_god(dm, p.month[0])},
            "hour": {"stem": p.hour[0], "ten_god": ten_god(dm, p.hour[0])},
        },
        "hidden_stems": {},
    }
    for key, br in (
        ("year", p.year[1]),
        ("month", p.month[1]),
        ("day", p.day[1]),
        ("hour", p.hour[1]),
    ):
        hs = HIDDEN_STEMS.get(br, [])
        out["hidden_stems"][key] = [{"stem": s, "ten_god": ten_god(dm, s)} for s in hs]
    return out



# =========================
# 追加：十二運 / 身強スコア / 大運
# =========================

# 十二運（Wikipediaの表に準拠：胎,養,長生,...,絶）
# 胎 養 長生 沐浴 冠帯 建禄 帝旺 衰 病 死 墓 絶
_TWELVE_FORTUNE_TABLE: dict[str, list[str]] = {
    "甲": ["酉","戌","亥","子","丑","寅","卯","辰","巳","午","未","申"],
    "乙": ["申","未","午","巳","辰","卯","寅","丑","子","亥","戌","酉"],
    "丙": ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"],
    "丁": ["亥","戌","酉","申","未","午","巳","辰","卯","寅","丑","子"],
    # 土は流派差があるが、本実装は「火土同根」で丙/丁と同形を採用（よく使われる形）
    "戊": ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"],
    "己": ["亥","戌","酉","申","未","午","巳","辰","卯","寅","丑","子"],
    "庚": ["卯","辰","巳","午","未","申","酉","戌","亥","子","丑","寅"],
    "辛": ["寅","丑","子","亥","戌","酉","申","未","午","巳","辰","卯"],
    "壬": ["午","未","申","酉","戌","亥","子","丑","寅","卯","辰","巳"],
    "癸": ["巳","辰","卯","寅","丑","子","亥","戌","酉","申","未","午"],
}

_TWELVE_FORTUNE_STAGES = ["胎","養","長生","沐浴","冠帯","建禄","帝旺","衰","病","死","墓","絶"]

# 「強い/弱い」断定を避けるため、ステージにエネルギー値(目安)を付与
# （帝旺を最大に近く、絶を最小に近くする単調なスケール）
_TWELVE_FORTUNE_ENERGY = {
    "胎": 2, "養": 3, "長生": 5, "沐浴": 4, "冠帯": 6, "建禄": 8,
    "帝旺": 9, "衰": 7, "病": 4, "死": 3, "墓": 3, "絶": 1,
}


def twelve_fortune(day_stem: str, branch: str) -> str:
    """日干×地支 → 十二運（胎〜絶）"""
    table = _TWELVE_FORTUNE_TABLE.get(day_stem)
    if not table or branch not in table:
        return "不明"
    idx = table.index(branch)
    return _TWELVE_FORTUNE_STAGES[idx]


def _twelve_fortune_for_pillars(p4: Pillars4) -> dict[str, str]:
    dm = p4.day[0]
    return {
        "year": twelve_fortune(dm, p4.year[1]),
        "month": twelve_fortune(dm, p4.month[1]),
        "day": twelve_fortune(dm, p4.day[1]),
        "hour": twelve_fortune(dm, p4.hour[1]),
    }


def _parse_gender(payload_gender: Any) -> str:
    """Keep unrecognized/unspecified gender unknown; never choose a direction."""
    g = (str(payload_gender) if payload_gender is not None else "").strip().lower()
    if g in ("male", "m", "man", "男性", "男"):
        return "male"
    if g in ("female", "f", "woman", "女性", "女"):
        return "female"
    return "unknown"


def _is_yang_stem(stem: str) -> bool:
    # 甲丙戊庚壬 が陽
    return stem in ("甲", "丙", "戊", "庚", "壬")


def _daiun_direction_from_year_stem(year_stem: str, gender: str) -> str | None:
    """年干陰陽 × 出生時の性別で大運方向を返す。"""
    gender = _parse_gender(gender)
    if gender == "unknown":
        return None
    is_yang = _is_yang_stem(year_stem)
    if is_yang:
        return "forward" if gender == "male" else "reverse"
    return "reverse" if gender == "male" else "forward"


def _month_branch_element(month_branch: str) -> str:
    return BRANCH_ELEMENT.get(month_branch, "土")


def _calc_strength_score(
    p4: Pillars4,
) -> dict[str, Any]:
    """身強身弱を“断定せず”スコア化するための材料。

    ここでは厳密な格局判定はせず、次の根拠を点数化する：
    - 得令（季節）：月支の五行が日干を助ける/削ぐ
    - 通根：日干と同五行の蔵干がどれだけ地支にあるか（特に月支を重視）
    - 透干：通根に近い要素が天干に現れているか

    返す score は「目安（0-100）」。
    """
    dm = p4.day[0]
    dm_elem = STEM_ELEMENT[dm]
    month_br = p4.month[1]
    month_elem = _month_branch_element(month_br)

    breakdown: list[dict[str, Any]] = []
    score = 50  # 中央から

    # 1) 得令（季節）
    # - 月支五行が日干五行と同じ：+12
    # - 月支五行が日干を生じる：+8
    # - 月支五行が日干に剋される：-6（消耗）
    # - 月支五行が日干を剋す：-12（圧力）
    if month_elem == dm_elem:
        score += 12
        breakdown.append({"name": "得令(同気)", "delta": 12, "detail": f"月支({month_br})={month_elem} が日干({dm})={dm_elem} と同じ"})
    elif _element_generate(month_elem) == dm_elem:
        score += 8
        breakdown.append({"name": "得令(相生)", "delta": 8, "detail": f"月支({month_br})={month_elem} が日干({dm})={dm_elem} を生じる"})
    elif _element_control(dm_elem) == month_elem:
        score -= 6
        breakdown.append({"name": "得令(泄耗)", "delta": -6, "detail": f"日干({dm})={dm_elem} が月支({month_br})={month_elem} を剋す側で消耗しやすい"})
    elif _element_control(month_elem) == dm_elem:
        score -= 12
        breakdown.append({"name": "得令(相剋)", "delta": -12, "detail": f"月支({month_br})={month_elem} が日干({dm})={dm_elem} を剋す"})
    elif _element_generate(dm_elem) == month_elem:
        # 洩気（日干が月支を生じて力が洩れる）。説明のみ正しくし、係数は従来スコアとの
        # 互換のため 0 のまま（係数変更は別の占術レビューを要する。Q07）。
        breakdown.append({"name": "得令(洩気)", "delta": 0, "detail": f"日干({dm})={dm_elem} が月支({month_br})={month_elem} を生じて力が洩れる関係（独自スコアでは係数未調整のため加減なし・参考表示）"})
    else:
        breakdown.append({"name": "得令(中立)", "delta": 0, "detail": f"月支({month_br})={month_elem} と日干({dm})={dm_elem} の直接関係が弱い"})

    # 2) 通根（同五行の蔵干）
    roots = []
    for pillar_name, br in (("month", p4.month[1]), ("day", p4.day[1]), ("hour", p4.hour[1]), ("year", p4.year[1])):
        hs = HIDDEN_STEMS.get(br, [])
        for s in hs:
            if STEM_ELEMENT.get(s) == dm_elem:
                roots.append({"pillar": pillar_name, "branch": br, "hidden_stem": s})

    # 重み：月>日>時>年
    w = {"month": 10, "day": 6, "hour": 4, "year": 3}
    root_points = 0
    for r in roots:
        root_points += w.get(r["pillar"], 2)
    if roots:
        score += min(25, root_points)
        breakdown.append({"name": "通根", "delta": min(25, root_points), "detail": f"同五行の蔵干が {len(roots)} 件", "roots": roots})
    else:
        breakdown.append({"name": "通根", "delta": 0, "detail": "同五行の蔵干が見当たらない（通根弱めの可能性）"})

    # 3) 透干（同五行が天干に見えるか）
    visible = []
    for pillar_name, stem in (("year", p4.year[0]), ("month", p4.month[0]), ("hour", p4.hour[0])):
        if STEM_ELEMENT.get(stem) == dm_elem:
            visible.append({"pillar": pillar_name, "stem": stem})
    if visible:
        delta = 8 + 2 * max(0, len(visible) - 1)
        delta = min(delta, 14)
        score += delta
        breakdown.append({"name": "透干", "delta": delta, "detail": f"同五行の天干が {len(visible)} 件", "visible": visible})
    else:
        breakdown.append({"name": "透干", "delta": 0, "detail": "同五行の天干は少なめ"})

    # 4) 十二運（四柱の地支に出る“勢い”を軽く加点）
    tf = _twelve_fortune_for_pillars(p4)
    tf_points = 0
    for k, stage in tf.items():
        tf_points += _TWELVE_FORTUNE_ENERGY.get(stage, 0)
    # 4柱合計を 0-36 くらい → 0-12 に圧縮
    delta = int(round(tf_points / 3))
    score += delta
    breakdown.append({"name": "十二運(合算目安)", "delta": delta, "detail": tf})

    # clamp
    score = max(0, min(100, int(round(score))))

    # “身強/身弱”の断定は避け、レンジラベルだけ付ける
    if score >= 70:
        label = "強め寄り（目安）"
    elif score <= 40:
        label = "弱め寄り（目安）"
    else:
        label = "中庸寄り（目安）"

    return {"score": score, "label": label, "breakdown": breakdown}


def _sexagenary_index(kanshi: str) -> int:
    try:
        return KANSHI_60.index(kanshi)
    except ValueError:
        return -1


def _jieqi_boundary_utc_for_birth_month(
    birth_local: datetime,
    tz_name: str,
) -> tuple[datetime, datetime]:
    """出生が属する節入り区間の境界（前/次）を返す。

    - 月柱判定に使う「30度刻み境界」を“節入り”として扱う。
    - 近似でも良いので、AIに渡す際の根拠は debug に残す。
    """
    tz = ZoneInfo(tz_name)
    local_dt = birth_local.astimezone(tz)
    utc_dt = local_dt.astimezone(timezone.utc)
    jdut = _dt_utc_to_jdut(utc_dt)

    sun_lon = _sun_lon_deg(jdut)
    cur_idx = _month_index_from_sun_lon(sun_lon)

    # その月の開始境界と次境界の太陽黄経ターゲット
    start_lon = (315 + 30 * cur_idx) % 360
    next_lon = (start_lon + 30) % 360

    prev_utc = _solve_time_for_sun_lon_near(jdut, target_lon=start_lon, direction=-1)
    next_utc = _solve_time_for_sun_lon_near(jdut, target_lon=next_lon, direction=+1)
    return prev_utc, next_utc


def _solve_time_for_sun_lon_near(jd_start: float, *, target_lon: float, direction: int) -> datetime:
    """太陽黄経が target_lon になる時刻(UTC)を近傍探索（簡易二分探索）。

    direction:
      +1: 未来方向に探す
      -1: 過去方向に探す
    """
    # 探索幅：最大 40日（節気は約15日〜16日間隔だが30度境界は約30日）
    step_days = 1.0
    jd0 = jd_start
    lon0 = _sun_lon_deg(jd0)

    # 角度差を -180..180 に正規化
    def ang_diff(a: float, b: float) -> float:
        d = (a - b) % 360.0
        if d > 180:
            d -= 360
        return d

    # bracket
    jd_a = jd0
    jd_b = jd0
    diff_a = ang_diff(lon0, target_lon)

    for _ in range(50):
        jd_b = jd_a + direction * step_days
        diff_b = ang_diff(_sun_lon_deg(jd_b), target_lon)
        # sign change or close enough
        if diff_a == 0 or diff_b == 0 or (diff_a > 0) != (diff_b > 0):
            break
        jd_a = jd_b
        diff_a = diff_b
        step_days *= 1.2
        if step_days > 40:
            break

    lo, hi = (jd_a, jd_b) if jd_a < jd_b else (jd_b, jd_a)

    # binary refine
    for _ in range(40):
        mid = (lo + hi) / 2
        diff_mid = ang_diff(_sun_lon_deg(mid), target_lon)
        diff_lo = ang_diff(_sun_lon_deg(lo), target_lon)
        if diff_mid == 0:
            lo = hi = mid
            break
        if (diff_lo > 0) != (diff_mid > 0):
            hi = mid
        else:
            lo = mid

    jd_final = (lo + hi) / 2
    # jdut -> utc datetime
    return _jdut_to_datetime_utc(jd_final)


def _jdut_to_datetime_utc(jdut: float) -> datetime:
    # JDUT -> Gregorian UTC datetime
    # この用途は“節入り差分”なので秒精度は不要。簡易変換。
    # 参考：JD 2440587.5 が Unix epoch (1970-01-01 00:00 UTC)
    # fromtimestamp は Windows で負の値に OSError を出すため、epoch からの加算で求める（Q06）。
    unix = (jdut - 2440587.5) * 86400.0
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=unix)


def kubo_from_day_kanshi(day_kanshi: str) -> dict[str, Any]:
    idx = _sexagenary_index(day_kanshi)
    if idx < 0:
        return {
            "day_kanshi": day_kanshi,
            "jun_index": None,
            "jun_label": None,
            "empty_branches": [],
            "error": "day_kanshi not in KANSHI_60",
        }
    jun_index = idx // 10
    return {
        "day_kanshi": day_kanshi,
        "jun_index": jun_index,
        "jun_label": JUN_LABELS[jun_index],
        "empty_branches": KUBO_BY_JUN[jun_index],
    }


def kubo_for_pillars(p4: Pillars4) -> dict[str, Any]:
    base = kubo_from_day_kanshi(p4.day)
    empty = set(base.get("empty_branches", []))
    hits = {
        "year": p4.year[1] in empty,
        "month": p4.month[1] in empty,
        "day": p4.day[1] in empty,
        "hour": p4.hour[1] in empty,
    }
    return {
        **base,
        "hits": hits,
        "hit_pillars": [name for name, hit in hits.items() if hit],
        "pillars": {
            "year": {"kanshi": p4.year, "branch": p4.year[1]},
            "month": {"kanshi": p4.month, "branch": p4.month[1]},
            "day": {"kanshi": p4.day, "branch": p4.day[1]},
            "hour": {"kanshi": p4.hour, "branch": p4.hour[1]},
        },
    }


def _add_calendar_months(dt: datetime, months: int) -> datetime:
    """Add calendar months directly to birth; clamp leap/end-of-month dates."""
    year, month0 = divmod(dt.year * 12 + dt.month - 1 + months, 12)
    month = month0 + 1
    return dt.replace(year=year, month=month, day=min(dt.day, calendar.monthrange(year, month)[1]))


def _calendar_age(birth: datetime, reference: datetime) -> float:
    reference = reference.astimezone(birth.tzinfo)
    years = reference.year - birth.year
    anniversary = _add_calendar_months(birth, years * 12)
    if reference < anniversary:
        years -= 1
        anniversary = _add_calendar_months(birth, years * 12)
    next_anniversary = _add_calendar_months(birth, (years + 1) * 12)
    return years + (reference - anniversary) / (next_anniversary - anniversary)


def _calc_daiun(
    birth_dt: datetime,
    p4: Pillars4,
    *,
    tz_name: str,
    gender: str,
) -> dict[str, Any]:
    """大運（10年運）を算出。

    - 順逆：年干の陰陽 × 出生時の性別
    - 起運：出生〜節入り差分の近似換算（3日=1年, 1日=4ヶ月）
    """
    tz = ZoneInfo(tz_name)
    local_birth = birth_dt.replace(tzinfo=tz) if birth_dt.tzinfo is None else birth_dt.astimezone(tz)

    gender_norm = _parse_gender(gender)
    year_stem = p4.year[0]
    direction = _daiun_direction_from_year_stem(year_stem, gender_norm)
    if direction is None:
        return {
            "status": "undetermined_gender", "direction": None, "gender": "unknown",
            "start_age": None, "start_age_text": None, "items": [],
            "timing_method": "birth_plus_approx_start_age_calendar_months",
            "note": "性別未指定のため大運順逆・起運・交運を保留。命式と原局に対する流年は計算済み。",
            "debug": {"gender": "unknown", "birth_local": local_birth.isoformat(),
                      "direction_rule": "year_stem_yinyang_x_birth_gender"},
        }
    forward = direction == "forward"

    prev_jieqi_utc, next_jieqi_utc = _jieqi_boundary_utc_for_birth_month(local_birth, tz_name)
    birth_utc = local_birth.astimezone(timezone.utc)

    if forward:
        delta = next_jieqi_utc - birth_utc
        ref = next_jieqi_utc
    else:
        delta = birth_utc - prev_jieqi_utc
        ref = prev_jieqi_utc

    total_days = max(0.0, delta.total_seconds() / 86400.0)
    years = int(total_days // 3)
    rem_days = total_days - years * 3
    months = int(rem_days) * 4 + int(round((rem_days - int(rem_days)) * 4))
    years += months // 12
    months = months % 12

    start_age = {"years": years, "months": months}
    start_age_text = f"{years}年{months}ヶ月"

    m_idx = _sexagenary_index(p4.month)
    if m_idx < 0:
        return {
            "direction": direction,
            "gender": gender_norm,
            "start_age": start_age,
            "start_age_text": start_age_text,
            "note": "month_kanshi not in KANSHI_60",
        }

    step = 1 if forward else -1
    luck0 = (m_idx + step) % 60

    items = []
    age0 = years + months / 12.0
    for i in range(10):
        k = KANSHI_60[(luck0 + step * i) % 60]
        start = _add_calendar_months(local_birth, years * 12 + months + 120 * i)
        end = _add_calendar_months(local_birth, years * 12 + months + 120 * (i + 1))
        items.append({
            "index": i + 1,
            "kanshi": k,
            "age_from": round(age0 + 10 * i, 2),
            "age_to": round(age0 + 10 * (i + 1), 2),
            "approx_start_year": start.year,
            "approx_start_at": start.isoformat(),
            "approx_end_at": end.isoformat(),
        })

    debug = {
        "gender": gender_norm,
        "birth_local": local_birth.isoformat(),
        "year_stem": year_stem,
        "year_stem_yang": _is_yang_stem(year_stem),
        "direction_rule": "year_stem_yinyang_x_birth_gender",
        "jieqi_ref_utc": ref.isoformat(),
        "delta_days": round(total_days, 6),
    }

    return {
        "status": "determined_direction_approx_timing",
        "direction": direction,
        "gender": gender_norm,
        "start_age": start_age,
        "start_age_text": start_age_text,
        "items": items,
        "timing_method": "birth_plus_approx_start_age_calendar_months",
        "debug": debug,
    }


def _parse_birth_time_window(payload: dict[str, Any], time_accuracy: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """unknown/approximate の出生可能時刻（現地時計時刻）の両端を返す（D-1）。"""
    if time_accuracy == "approximate":
        rng = payload.get("birth_time_range")
        text = str(rng.get("estimated_range") or "") if isinstance(rng, dict) else ""
        try:
            start_text, end_text = text.split("-")
            sh, sm = (int(x) for x in start_text.split(":"))
            eh, em = (int(x) for x in end_text.split(":"))
            if 0 <= sh <= 23 and 0 <= eh <= 23 and 0 <= sm <= 59 and 0 <= em <= 59 and (sh, sm) <= (eh, em):
                return (sh, sm, 0), (eh, em, 59)
        except (ValueError, AttributeError):
            pass
        # レンジ不明・不正・日跨ぎは全日扱いへ縮退する（安全側）。
    return (0, 0, 0), (23, 59, 59)


def _evaluate_birth_time_window(
    payload: dict[str, Any], *, tz_name: str, time_accuracy: str,
) -> dict[str, Any]:
    """出生可能時刻の両端で年柱・月柱を評価し、一意性を返す（D-1）。

    節入りは約15日間隔のため1現地日に2回は入らず、両端一致＝範囲内で不変が成立する。
    DSTの重複・不存在時刻は fold=0 の寛容な解釈で評価する（この評価専用。
    本計算の出生日時解決は resolve_birth_datetime の厳格検証のまま）。
    """
    tz = ZoneInfo(tz_name)
    (sh, sm, ss), (eh, em, es) = _parse_birth_time_window(payload, time_accuracy)
    endpoints = []
    for h, mi, s in ((sh, sm, ss), (eh, em, es)):
        local = datetime(int(payload["year"]), int(payload["month"]), int(payload["day"]), h, mi, s, tzinfo=tz)
        year_k, month_k, _dbg = year_month_pillars(local, tz_name=tz_name)
        endpoints.append({"local_datetime": local.isoformat(), "year_pillar": year_k, "month_pillar": month_k})
    return {
        "evaluated": True,
        "accuracy": time_accuracy,
        "window_start_local": endpoints[0]["local_datetime"],
        "window_end_local": endpoints[-1]["local_datetime"],
        "endpoints": endpoints,
        "year_pillar_stable": len({e["year_pillar"] for e in endpoints}) == 1,
        "month_pillar_stable": len({e["month_pillar"] for e in endpoints}) == 1,
        "dst_handling": "fold0_permissive_for_window_only",
        "method": "endpoint_evaluation_single_jie_per_local_day",
    }


def _undetermined_time_daiun(
    window: dict[str, Any], *, tz_name: str, gender: Any, p4: Pillars4, undetermined: list[str],
) -> dict[str, Any]:
    """節入り日×出生時刻未確定の大運保留出力（D-1）。candidates は端点の参考計算。"""
    gender_norm = _parse_gender(gender)
    candidates = []
    seen: set[tuple[str, str]] = set()
    for endpoint in window["endpoints"]:
        key = (endpoint["year_pillar"], endpoint["month_pillar"])
        if key in seen:
            continue
        seen.add(key)
        candidate_p4 = Pillars4(year=endpoint["year_pillar"], month=endpoint["month_pillar"], day=p4.day, hour=p4.hour)
        candidate_dt = datetime.fromisoformat(endpoint["local_datetime"])
        candidate_daiun = _calc_daiun(candidate_dt, candidate_p4, tz_name=tz_name, gender=gender)
        candidates.append({
            "year_pillar": endpoint["year_pillar"],
            "month_pillar": endpoint["month_pillar"],
            "direction": candidate_daiun.get("direction"),
            "first_daiun_kanshi": ((candidate_daiun.get("items") or [{}])[0]).get("kanshi"),
            "start_age_text": candidate_daiun.get("start_age_text"),
            "evaluated_at_local": endpoint["local_datetime"],
            "note": "出生可能時刻の端での参考計算。確定値ではない",
        })
    status = "undetermined_year_pillar" if "year" in undetermined else "undetermined_month_pillar"
    return {
        "status": status,
        "direction": None,
        "gender": gender_norm,
        "start_age": None,
        "start_age_text": None,
        "items": [],
        "timing_method": "birth_plus_approx_start_age_calendar_months",
        "undetermined_pillars": list(undetermined),
        "candidates": candidates,
        "note": "出生日に節入り（立春を含む）があり、出生時刻により年柱・月柱・大運が変わるため確定提示を保留。時刻が判明すれば確定できる。",
        "debug": {
            "gender": gender_norm,
            "window_start_local": window["window_start_local"],
            "window_end_local": window["window_end_local"],
            "direction_rule": "year_stem_yinyang_x_birth_gender",
        },
    }


def _pillar_dict(kanshi: str) -> dict[str, Any]:
    return {
        "stem": kanshi[0],
        "branch": kanshi[1],
        "kanshi": kanshi,
    }


def _pillar_items(p4: Pillars4, *, include_day_master: bool = True) -> list[dict[str, str]]:
    items = [
        {"name": "year", "kanshi": p4.year, "stem": p4.year[0], "branch": p4.year[1]},
        {"name": "month", "kanshi": p4.month, "stem": p4.month[0], "branch": p4.month[1]},
        {"name": "day", "kanshi": p4.day, "stem": p4.day[0], "branch": p4.day[1]},
        {"name": "hour", "kanshi": p4.hour, "stem": p4.hour[0], "branch": p4.hour[1]},
    ]
    if include_day_master:
        return items
    return [item for item in items if item["name"] != "day"]


def _branch_pair_relations(left: dict[str, str], right: dict[str, str]) -> list[dict[str, Any]]:
    b1 = left["branch"]
    b2 = right["branch"]
    pair = frozenset((b1, b2))
    relations: list[dict[str, Any]] = []

    if b1 == b2 and b1 in BRANCH_SELF_PUNISHMENTS:
        relations.append({
            "type": "self_punishment",
            "type_ja": "自刑",
            "detail": f"{b1}{b2}",
        })
    if pair in BRANCH_PUNISHMENTS:
        relations.append({
            "type": "punishment",
            "type_ja": "刑",
            "detail": BRANCH_PUNISHMENTS[pair],
        })
    if pair in BRANCH_CLASHES:
        relations.append({
            "type": "clash",
            "type_ja": "冲",
            "detail": f"{b1}{b2}冲",
        })
    if pair in BRANCH_SIX_HARMONIES:
        relations.append({
            "type": "six_harmony",
            "type_ja": "六合",
            "element": BRANCH_SIX_HARMONIES[pair],
            "detail": f"{b1}{b2}合",
        })
    if pair in BRANCH_HARMS:
        relations.append({
            "type": "harm",
            "type_ja": "害",
            "detail": f"{b1}{b2}害",
        })
    if pair in BRANCH_DESTRUCTIONS:
        relations.append({"type": "destruction", "type_ja": "破", "detail": f"{b1}{b2}破"})
    return relations


def _stem_pair_relations(left: dict[str, str], right: dict[str, str]) -> list[dict[str, Any]]:
    s1 = left["stem"]
    s2 = right["stem"]
    pair = frozenset((s1, s2))
    if pair not in STEM_COMBINATIONS:
        return []
    return [{
        "type": "stem_combination",
        "type_ja": "干合",
        "element": STEM_COMBINATIONS[pair],
        "detail": f"{s1}{s2}合",
    }]


def _format_relation(left: dict[str, str], right: dict[str, str], relation: dict[str, Any]) -> dict[str, Any]:
    return {
        "left": left,
        "right": right,
        **relation,
    }


def _branch_triads(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    branches = {item["branch"] for item in items}
    for triad, label in BRANCH_TRIADS.items():
        hit = branches.intersection(triad)
        if len(hit) == 3:
            level = "full"
            type_ja = "三合"
        elif len(hit) == 2:
            level = "partial"
            type_ja = "半会"
        else:
            continue
        out.append({
            "type": "triad",
            "type_ja": type_ja,
            "level": level,
            "group": label,
            "branches": sorted(hit, key=lambda x: BRANCHES.index(x)),
            "pillars": [item for item in items if item["branch"] in hit],
        })
    return out


def _branch_three_punishments(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    branches = {item["branch"] for item in items}
    for group, label in BRANCH_THREE_PUNISHMENTS.items():
        hit = branches.intersection(group)
        if len(hit) == 3:
            level = "full"
        elif len(hit) == 2:
            level = "partial"
        else:
            continue
        out.append({
            "type": "three_punishment",
            "type_ja": "三刑",
            "level": level,
            "detail": label,
            "branches": sorted(hit, key=lambda x: BRANCHES.index(x)),
            "pillars": [item for item in items if item["branch"] in hit],
        })
    return out


def _interactions_for_items(items: list[dict[str, str]]) -> dict[str, Any]:
    branch_relations: list[dict[str, Any]] = []
    stem_relations: list[dict[str, Any]] = []
    for i, left in enumerate(items):
        for right in items[i + 1:]:
            for rel in _branch_pair_relations(left, right):
                branch_relations.append(_format_relation(left, right, rel))
            for rel in _stem_pair_relations(left, right):
                stem_relations.append(_format_relation(left, right, rel))
    return {
        "branch_relations": branch_relations,
        "stem_relations": stem_relations,
        "triads": _branch_triads(items),
        "three_punishments": _branch_three_punishments(items),
    }


def _current_daiun_item(
    daiun: dict[str, Any], *, birth_year: int, current_year: int, current_dt: datetime | None = None,
) -> dict[str, Any] | None:
    age = current_year - birth_year
    if current_dt is not None and daiun.get("debug", {}).get("birth_local"):
        age = round(_calendar_age(datetime.fromisoformat(daiun["debug"]["birth_local"]), current_dt), 4)
    for item in daiun.get("items", []) or []:
        if current_dt is not None and item.get("approx_start_at") and item.get("approx_end_at"):
            if datetime.fromisoformat(item["approx_start_at"]) <= current_dt < datetime.fromisoformat(item["approx_end_at"]):
                return {**item, "current_age_approx": age, "selection_basis": "approx_calendar_interval"}
            continue
        if item.get("age_from") is None or item.get("age_to") is None:
            continue
        if float(item["age_from"]) <= age < float(item["age_to"]):
            return {**item, "current_age_approx": age}
    return None


def _annual_fortune(
    p4: Pillars4,
    daiun: dict[str, Any],
    *,
    birth_year: int,
    current_dt: datetime,
    tz_name: str,
    include_hour: bool = True,
    excluded_pillars: list | None = None,
) -> dict[str, Any]:
    tz = ZoneInfo(tz_name)
    local_dt = current_dt.astimezone(tz)
    current_year = local_dt.year
    lichun_local = _lichun_utc_for_year(current_year, tz_name).astimezone(tz)
    effective_year = current_year if local_dt >= lichun_local else current_year - 1
    kanshi = _year_kanshi_from_effective_year(effective_year)
    annual_item = {
        "name": "annual",
        "kanshi": kanshi,
        "stem": kanshi[0],
        "branch": kanshi[1],
    }
    natal_items = [p for p in _pillar_items(p4)
                   if (include_hour or p["name"] != "hour") and p["name"] not in (excluded_pillars or ())]
    daiun_item = _current_daiun_item(daiun, birth_year=birth_year, current_year=current_year, current_dt=local_dt)

    # current_daiun が null になる理由を明示する（I2）。起運前は大運依存の解釈を行わない。
    if daiun_item is not None:
        current_daiun_status = "selected"
    elif daiun.get("status") == "undetermined_gender":
        current_daiun_status = "undetermined_gender"
    else:
        items = daiun.get("items") or []
        first_start = items[0].get("approx_start_at") if items else None
        if first_start and local_dt < datetime.fromisoformat(str(first_start)):
            current_daiun_status = "before_first_daiun"
        else:
            current_daiun_status = "out_of_approximation_range"

    relation_targets = natal_items[:]
    if daiun_item and daiun_item.get("kanshi"):
        dk = str(daiun_item["kanshi"])
        relation_targets.append({"name": "current_daiun", "kanshi": dk, "stem": dk[0], "branch": dk[1]})

    branch_relations: list[dict[str, Any]] = []
    stem_relations: list[dict[str, Any]] = []
    for target in relation_targets:
        for rel in _branch_pair_relations(annual_item, target):
            branch_relations.append(_format_relation(annual_item, target, rel))
        for rel in _stem_pair_relations(annual_item, target):
            stem_relations.append(_format_relation(annual_item, target, rel))

    return {
        "year": current_year,
        "effective_year": effective_year,
        "kanshi": kanshi,
        "stem": kanshi[0],
        "branch": kanshi[1],
        "ten_god_to_day_master": ten_god(p4.day[0], kanshi[0]),
        "twelve_fortune_to_day_master": twelve_fortune(p4.day[0], kanshi[1]),
        "current_daiun": daiun_item,
        "current_daiun_status": current_daiun_status,
        **({"current_daiun_note": "起運前（第1大運の開始前）。大運に依存する解釈は行わない"}
           if current_daiun_status == "before_first_daiun" else {}),
        "daiun_direction_status": daiun.get("status"),
        "natal_time_basis": "four_pillars" if include_hour else "three_pillars_hour_excluded",
        "relations": {
            "branch_relations": branch_relations,
            "stem_relations": stem_relations,
            "triads_with_natal": _branch_triads([annual_item, *natal_items]),
            "triads_with_natal_and_daiun": _branch_triads([annual_item, *relation_targets]),
            "three_punishments_with_natal": _branch_three_punishments([annual_item, *natal_items]),
            "three_punishments_with_natal_and_daiun": _branch_three_punishments([annual_item, *relation_targets]),
        },
        "debug": {
            "calculated_at": local_dt.isoformat(),
            "lichun_local": lichun_local.isoformat(),
            "year_boundary_rule": "lichun(315deg)",
        },
    }


def _shinsatsu_hits_by_branch(
    *,
    name: str,
    name_ja: str,
    basis: dict[str, Any],
    target_branches: list[str],
    pillar_items: list[dict[str, str]],
) -> dict[str, Any]:
    hits = [
        {
            "pillar": item["name"],
            "kanshi": item["kanshi"],
            "branch": item["branch"],
        }
        for item in pillar_items
        if item["branch"] in target_branches
    ]
    return {
        "name": name,
        "name_ja": name_ja,
        "basis": basis,
        "targets": [{"type": "branch", "value": br} for br in target_branches],
        "hits": hits,
        "hit": bool(hits),
    }


def _shinsatsu_hits_by_stem_or_branch(
    *,
    name: str,
    name_ja: str,
    basis: dict[str, Any],
    target: str | None,
    pillar_items: list[dict[str, str]],
) -> dict[str, Any]:
    if not target:
        return {
            "name": name,
            "name_ja": name_ja,
            "basis": basis,
            "targets": [],
            "hits": [],
            "hit": False,
        }
    target_type = "stem" if target in STEMS else "branch"
    hits = []
    for item in pillar_items:
        if target_type == "stem" and item["stem"] == target:
            hits.append({"pillar": item["name"], "kanshi": item["kanshi"], "stem": item["stem"]})
        elif target_type == "branch" and item["branch"] == target:
            hits.append({"pillar": item["name"], "kanshi": item["kanshi"], "branch": item["branch"]})
    return {
        "name": name,
        "name_ja": name_ja,
        "basis": basis,
        "targets": [{"type": target_type, "value": target}],
        "hits": hits,
        "hit": bool(hits),
    }


def _shinsatsu_for_pillars(p4: Pillars4) -> dict[str, Any]:
    pillar_items = _pillar_items(p4)
    day_stem = p4.day[0]
    month_branch = p4.month[1]
    tenotsu_targets = TENOTSU_KIJIN_BY_DAY_STEM.get(day_stem, [])
    bunsho_targets = BUNSHO_BY_DAY_STEM.get(day_stem, [])
    tentoku_target = TENTOKU_BY_MONTH_BRANCH.get(month_branch)
    stars = [
        _shinsatsu_hits_by_branch(
            name="tenotsu_kijin",
            name_ja="天乙貴人",
            basis={"type": "day_stem", "value": day_stem},
            target_branches=tenotsu_targets,
            pillar_items=pillar_items,
        ),
        _shinsatsu_hits_by_branch(
            name="bunsho",
            name_ja="文昌",
            basis={"type": "day_stem", "value": day_stem},
            target_branches=bunsho_targets,
            pillar_items=pillar_items,
        ),
        _shinsatsu_hits_by_stem_or_branch(
            name="tentoku",
            name_ja="天徳",
            basis={"type": "month_branch", "value": month_branch},
            target=tentoku_target,
            pillar_items=pillar_items,
        ),
    ]
    return {
        "calc_policy": {
            "tenotsu_kijin": "day_stem_to_branch",
            "bunsho": "day_stem_to_branch",
            "tentoku": "month_branch_to_stem_or_branch",
            "note": "神殺は流派差があるため、代表的な表に基づく補助情報として扱う",
        },
        "stars": stars,
        "hit_stars": [star for star in stars if star.get("hit")],
    }


def _build_unknowns(payload: dict[str, Any], *, day_change_at_23: bool, day_boundary_hour: int | None = None) -> list[str]:
    unknowns: list[str] = []
    if payload.get("hour") in (None, "", "不明"):
        unknowns.append("出生時刻が未入力のため 12:00 を仮置きして計算")
    if payload.get("minute") in (None, "", "不明"):
        unknowns.append("出生分が未入力のため 00 分として計算")
    boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
    unknowns.append(f"日替わり境界は {boundary:02d}:00 切替設定を使用（出生地の現地暦日）")
    if _parse_gender(payload.get("gender")) == "unknown":
        unknowns.append("性別未指定のため大運順逆・起運は未確定。大運を女性扱いで補完しない")
    unknowns.append("大運開始年齢は簡易換算（3日=1年, 1日=4ヶ月）")
    return unknowns


def _build_structure_report(
    p4: Pillars4,
    strength: dict[str, Any],
    five: dict[str, Any],
    ten: dict[str, Any],
    tf: dict[str, str],
    daiun: dict[str, Any],
) -> dict[str, Any]:
    dm = p4.day[0]
    dm_elem = STEM_ELEMENT[dm]
    month_branch = p4.month[1]
    month_element = _month_branch_element(month_branch)

    if month_element == dm_elem:
        relation = "same_element"
    elif _element_generate(month_element) == dm_elem:
        relation = "generated_by_month"
    elif _element_control(month_element) == dm_elem:
        relation = "controlled_by_month"
    elif _element_control(dm_elem) == month_element:
        relation = "day_master_controls_month"
    elif _element_generate(dm_elem) == month_element:
        relation = "day_master_generates_month"
    else:
        relation = "neutral"

    hidden = ten.get("hidden_stems", {}) if isinstance(ten, dict) else {}
    roots_count = 0
    for items in hidden.values():
        if isinstance(items, list):
            for item in items:
                stem = item.get("stem") if isinstance(item, dict) else None
                if stem and STEM_ELEMENT.get(stem) == dm_elem:
                    roots_count += 1

    visible_same = 0
    for pillar_name in ("year", "month", "hour"):
        pillar = ten.get("pillars", {}).get(pillar_name, {}) if isinstance(ten, dict) else {}
        stem = pillar.get("stem") if isinstance(pillar, dict) else None
        if stem and STEM_ELEMENT.get(stem) == dm_elem:
            visible_same += 1

    tf_total = sum(_TWELVE_FORTUNE_ENERGY.get(stage, 0) for stage in tf.values())

    dominant_features: list[str] = []
    visible_counts = five.get("visible", {}) if isinstance(five, dict) else {}
    if isinstance(visible_counts, dict) and visible_counts:
        ordered = sorted(visible_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top_elem, top_count = ordered[0]
        bottom_elem, bottom_count = sorted(visible_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
        dominant_features.append(f"visible五行で {top_elem} が相対的に多い ({top_count})")
        dominant_features.append(f"visible五行で {bottom_elem} が相対的に少ない ({bottom_count})")
    dominant_features.append(f"月支は {month_branch} ({month_element})")
    dominant_features.append(f"大運方向は {daiun['direction']}" if daiun.get("direction") else "大運方向は未確定（性別未指定）")

    notes = [
        "年柱は立春基準、月柱は節入り基準で判定",
        "AI翻訳前の構造材料として整理されたデータ",
    ]

    return {
        "day_master": dm,
        "day_master_element": dm_elem,
        "seasonal_context": {
            "month_branch": month_branch,
            "month_element": month_element,
            "relation_to_day_master": relation,
        },
        "strength_index": {
            "score": strength.get("score"),
            "label": strength.get("label"),
            "breakdown": strength.get("breakdown", []),
        },
        "support_signals": {
            "roots_count": roots_count,
            "visible_same_element_count": visible_same,
            "twelve_fortune_total": tf_total,
        },
        "dominant_features": dominant_features,
        "notes": notes,
    }


def calc_shichusuimei_from_payload(
    payload: dict[str, Any],
    *,
    tz_name: str = "Asia/Tokyo",
    day_change_at_23: bool = False,
    as_of: datetime | None = None,
    annual_years: int = 10,
    day_boundary_hour: int | None = None,
    annual_start_year: int | None = None,
) -> dict[str, Any]:
    """routes.py の payload から四柱推命結果を作る。

    返却は従来互換キーを残しつつ、StructurePayload 寄りの
    input / unknowns / normalized_data / structure_report を含める。
    """
    if not isinstance(annual_years, int) or isinstance(annual_years, bool) or not 1 <= annual_years <= 20:
        raise ValueError("annual_years must be an integer between 1 and 20")
    if annual_start_year is not None and (type(annual_start_year) is not int or not 1800 <= annual_start_year <= 2399):
        raise ValueError("annual_start_year must be an integer between 1800 and 2399")
    boundary = resolve_day_boundary_hour(day_change_at_23, day_boundary_hour)
    day_change_at_23 = boundary == 23
    current_dt = as_of or datetime.now(ZoneInfo(tz_name))
    if current_dt.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    current_dt = current_dt.astimezone(ZoneInfo(tz_name))
    raw_hour = payload.get("hour")
    raw_minute = payload.get("minute", 0)
    hour = 12 if raw_hour in (None, "") else int(raw_hour)
    minute = 0 if raw_minute in (None, "") else int(raw_minute)
    time_accuracy = payload.get("birth_time_accuracy") or ("exact" if raw_hour not in (None, "") else "unknown")
    if raw_hour in (None, ""):
        time_accuracy = "unknown"
    elif time_accuracy == "auto":
        time_accuracy = "exact"
    time_reliable = time_accuracy == "exact" and raw_hour not in (None, "")
    dt = datetime(
        int(payload["year"]),
        int(payload["month"]),
        int(payload["day"]),
        hour,
        minute,
        0,
    )

    dt = resolve_birth_datetime(dt, tz_name, fold=payload.get("birth_fold"), utc_offset_hours=payload.get("birth_utc_offset_hours"))
    effective_date, boundary_label = _effective_local_date_for_day_pillar(dt, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
    time_context = {
        "local_datetime": dt.isoformat(), "timezone": tz_name,
        "utc_offset_hours": dt.utcoffset().total_seconds() / 3600,
        "utc_datetime": dt.astimezone(timezone.utc).isoformat(), "fold": dt.fold,
        "day_pillar_reference_datetime": dt.isoformat(), "day_pillar_date": effective_date.isoformat(),
        "day_boundary_hour": boundary, "day_boundary_rule": boundary_label,
        "calendar_time_basis": "local_civil_time", "true_solar_time_applied": False,
        "hour_stem_rule": "five_rat_from_effective_day_stem",
        "astronomical_time_basis": "UTC_for_solar_terms",
    }
    p4 = pillars4(dt, tz_name=tz_name, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
    _, _, ym_debug = year_month_pillars(dt, tz_name=tz_name)

    # D-1: 時刻不明・推定時は出生可能時刻の両端で年柱・月柱の一意性を評価する。
    time_window_evaluation = None
    undetermined_pillars: list[str] = []
    if not time_reliable:
        time_window_evaluation = _evaluate_birth_time_window(payload, tz_name=tz_name, time_accuracy=time_accuracy)
        time_context["time_window_evaluation"] = time_window_evaluation
        if not time_window_evaluation["year_pillar_stable"]:
            undetermined_pillars = ["year", "month"]
        elif not time_window_evaluation["month_pillar_stable"]:
            undetermined_pillars = ["month"]

    five = _five_elements_counts(p4)
    ten = _ten_gods_for_pillars(p4)
    tf = _twelve_fortune_for_pillars(p4)
    strength = _calc_strength_score(p4)
    daiun = _calc_daiun(dt, p4, tz_name=tz_name, gender=payload.get("gender"))
    if undetermined_pillars:
        daiun = _undetermined_time_daiun(
            time_window_evaluation, tz_name=tz_name, gender=payload.get("gender"),
            p4=p4, undetermined=undetermined_pillars,
        )
    elif time_window_evaluation is not None and daiun.get("items"):
        # D-1: 柱が一意でも、起運年齢は時刻に依存して幅を持つ（端点の参考値を開示）。
        window_ages = []
        for endpoint in time_window_evaluation["endpoints"]:
            endpoint_daiun = _calc_daiun(
                datetime.fromisoformat(endpoint["local_datetime"]), p4,
                tz_name=tz_name, gender=payload.get("gender"),
            )
            window_ages.append({
                "evaluated_at_local": endpoint["local_datetime"],
                "start_age": endpoint_daiun.get("start_age"),
                "start_age_text": endpoint_daiun.get("start_age_text"),
            })
        daiun["start_age_window"] = {
            "endpoints": window_ages,
            "note": "出生時刻が未確定のため、起運年齢は出生可能時刻の端点間の幅を持つ参考値",
        }
    kubo = kubo_for_pillars(p4)
    interactions = _interactions_for_items([
        p for p in _pillar_items(p4)
        if (time_reliable or p["name"] != "hour") and p["name"] not in undetermined_pillars
    ])
    interactions["time_basis"] = "four_pillars" if time_reliable else "three_pillars_hour_excluded"
    if undetermined_pillars:
        interactions["undetermined_excluded_pillars"] = list(undetermined_pillars)
    shinsatsu = _shinsatsu_for_pillars(p4)
    annual_fortune = _annual_fortune(
        p4,
        daiun,
        birth_year=int(payload["year"]),
        current_dt=current_dt,
        tz_name=tz_name,
        include_hour=time_reliable,
        excluded_pillars=undetermined_pillars,
    )
    if undetermined_pillars:
        annual_fortune["undetermined_excluded_pillars"] = list(undetermined_pillars)

    hidden_all = {
        "year": HIDDEN_STEMS.get(p4.year[1], []),
        "month": HIDDEN_STEMS.get(p4.month[1], []),
        "day": HIDDEN_STEMS.get(p4.day[1], []),
        "hour": HIDDEN_STEMS.get(p4.hour[1], []),
    }
    hidden_main = {k: (v[0] if v else None) for k, v in hidden_all.items()}
    gender_norm = _parse_gender(payload.get("gender"))
    unknowns = _build_unknowns(payload, day_change_at_23=day_change_at_23, day_boundary_hour=boundary)
    if undetermined_pillars:
        unknowns.append("出生日に節入り（立春を含む）があり、時刻により年柱・月柱・大運が変わるため、大運・年別予測を保留（daiun.candidates に端点の参考値のみ収録）")

    from services.shichusuimei_structure import analyze_structure, analyze_luck, concurrent_luck_analysis
    from services.shichu_special_relations import detect_special_kanshi_relations
    if not time_reliable:
        unknowns.append("構造分析は時柱を除外。従来キーの時柱・五行・身強スコアは仮置き／推定時刻の参考値")
    structural_analysis = analyze_structure(p4, time_reliable=time_reliable)
    # 伏吟・反吟・天干冲の照合対象。時刻不明・推定時は時柱を除外する（0.5.0方針）。
    special_natal_pillars = [(p["name"], p["kanshi"]) for p in _pillar_items(p4)
                             if (time_reliable or p["name"] != "hour") and p["name"] not in undetermined_pillars]
    for item in daiun.get("items", []):
        item["structural_analysis"] = analyze_luck(
            p4, item["kanshi"], time_reliable=time_reliable, structural_analysis=structural_analysis,
        )
        item["special_relations_natal"] = detect_special_kanshi_relations(
            special_natal_pillars, item["kanshi"], "daiun", scope="daiun_natal",
        )
    current_daiun = annual_fortune.get("current_daiun") or {}
    if current_daiun:
        # current_daiun は items からのコピーで、コピー後に items へ付けた分析
        # （structural_analysis・special_relations_natal）を持たないため、同じ index の値を反映する（I1）。
        for item in daiun.get("items", []):
            if item.get("index") == current_daiun.get("index"):
                current_daiun["structural_analysis"] = item.get("structural_analysis")
                current_daiun["special_relations_natal"] = item.get("special_relations_natal")
                break
    annual_fortune["structural_analysis"] = analyze_luck(
        p4, annual_fortune["kanshi"], time_reliable=time_reliable,
        other_luck=current_daiun.get("kanshi"), structural_analysis=structural_analysis,
    )
    annual_fortune["special_relations_natal"] = detect_special_kanshi_relations(
        special_natal_pillars, annual_fortune["kanshi"], "ryunen", scope="ryunen_natal",
    )
    annual_fortune["special_relations_daiun"] = detect_special_kanshi_relations(
        [("current_daiun", str(current_daiun["kanshi"]))], annual_fortune["kanshi"], "ryunen",
        scope="ryunen_daiun",
    ) if current_daiun.get("kanshi") else []
    forecasts = []
    # 年別予測の開始年だけを指定できる。原本作成時の流年・現在の大運は as_of（発行日）のまま。
    first_year = annual_start_year if annual_start_year is not None else annual_fortune["effective_year"]
    # D-1: 年柱・月柱が未確定の場合、大運対応と月令依存の分析を含む年別予測は生成しない。
    forecast_years = [] if undetermined_pillars else list(range(first_year, first_year + annual_years))
    boundaries = {year: _lichun_utc_for_year(year, tz_name).astimezone(ZoneInfo(tz_name))
                  for year in range(first_year, first_year + annual_years + 1)} if forecast_years else {}
    for year in forecast_years:
        annual_kanshi = _year_kanshi_from_effective_year(year)
        year_start, year_end = boundaries[year], boundaries[year + 1]
        # Intersect actual calendar periods; a rounded integer year-age shifts late births.
        contexts = [item for item in daiun.get("items", [])
                    if datetime.fromisoformat(item["approx_start_at"]) < year_end
                    and datetime.fromisoformat(item["approx_end_at"]) > year_start]
        forecasts.append({
            "effective_year": year, "kanshi": annual_kanshi,
            "year_boundary_rule": "lichun(315deg)",
            "period_start": year_start.isoformat(), "period_end": year_end.isoformat(),
            "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
            "daiun_direction_status": daiun["status"],
            "daiun_boundary_in_window": any(
                year_start <= datetime.fromisoformat(item["approx_start_at"]) < year_end
                or year_start < datetime.fromisoformat(item["approx_end_at"]) <= year_end for item in contexts
            ),
            "natal_analysis": analyze_luck(
                p4, annual_kanshi, time_reliable=time_reliable, structural_analysis=structural_analysis,
            ),
            "special_relations_natal": detect_special_kanshi_relations(
                special_natal_pillars, annual_kanshi, "ryunen", scope="ryunen_natal",
            ),
            "daiun_contexts": [{
                "index": item["index"], "kanshi": item["kanshi"],
                "age_from": item["age_from"], "age_to": item["age_to"],
                "overlap_start_approx": max(year_start, datetime.fromisoformat(item["approx_start_at"])).isoformat(),
                "overlap_end_approx": min(year_end, datetime.fromisoformat(item["approx_end_at"])).isoformat(),
                "analysis": concurrent_luck_analysis(analyze_luck(
                    p4, annual_kanshi, time_reliable=time_reliable,
                    other_luck=item["kanshi"], structural_analysis=structural_analysis,
                )),
                "special_relations_daiun": detect_special_kanshi_relations(
                    [("daiun", item["kanshi"])], annual_kanshi, "ryunen", scope="ryunen_daiun",
                ),
            } for item in contexts],
        })
    annual_forecasts = {
        "start_effective_year": first_year, "years": annual_years,
        "items": forecasts,
        "daiun_direction_status": daiun["status"],
        "note": (
            "出生時刻が未確定で出生日に節入りがあるため、年別予測を保留。daiun.candidates と時刻判明後の再発行を参照"
            if undetermined_pillars else
            "流年は立春から翌立春まで。大運は出生日時に近似起運年齢の年月を加えた期間で対応付け。交運日時は近似であり確定しない"
        ),
    }

    normalized_data = {
        "pillars": {
            "year": _pillar_dict(p4.year),
            "month": _pillar_dict(p4.month),
            "day": _pillar_dict(p4.day),
            "hour": _pillar_dict(p4.hour),
        },
        "hidden_stems": hidden_all,
        "main_hidden_stems": hidden_main,
        "ten_gods": ten,
        "five_elements": {
            **five,
            "display_policy": "visible",
        },
        "twelve_fortune": tf,
        "kubo": kubo,
        "daiun": {
            **daiun,
            "calc_mode": "approx",
        },
        "interactions": interactions,
        "annual_fortune": annual_fortune,
        "shinsatsu": shinsatsu,
        "structural_analysis": structural_analysis,
        "annual_forecasts": annual_forecasts,
    }
    if not time_reliable:
        normalized_data["time_sensitive_reference"] = {
            "birth_time_accuracy": time_accuracy, "assumed_time": f"{hour:02d}:{minute:02d}",
            "valid_for_assertive_interpretation": False,
            "reference_only_metrics": ["five_elements", "features.strength", "structure_report.strength_index", "structure_report.support_signals"],
            "hour_reference_only_sections": ["pillars.hour", "hidden_stems.hour", "ten_gods.hidden_stems.hour", "ten_gods.pillars.hour", "twelve_fortune.hour", "kubo", "shinsatsu"],
            "note": "時柱を含む旧集計は参考値。原局・流年の関係と新しい構造分析は時柱を除外",
        }
        if undetermined_pillars:
            normalized_data["time_sensitive_reference"]["undetermined_pillars"] = list(undetermined_pillars)
            normalized_data["time_sensitive_reference"]["undetermined_note"] = (
                "出生日に節入りがあり年柱・月柱が時刻で変わる。月令に依存する structural_analysis と "
                "annual_fortune.structural_analysis も参考値として扱う"
            )

    structure_report = _build_structure_report(
        p4=p4,
        strength=strength,
        five=five,
        ten=ten,
        tf=tf,
        daiun=daiun,
    )

    return {
        "module": "shichusuimei",
        "system": "shichusuimei",
        "ephemeris": ephemeris_debug_info(),
        "engine_version": ENGINE_VERSION,
        "generated_at": current_dt.isoformat(),
        "input": {
            "raw": {
                "year": int(payload["year"]),
                "month": int(payload["month"]),
                "day": int(payload["day"]),
                "hour": hour,
                "minute": minute,
                "gender": gender_norm,
                "gender_supplied": payload.get("gender"),
                "city": payload.get("city"),
                "lat": payload.get("lat"),
                "lng": payload.get("lng"),
            },
            "assumptions": {
                "tz_name": tz_name,
                "day_change_at_23": day_change_at_23,
                "day_boundary_hour": boundary,
                "day_boundary_rule": boundary_label,
                "year_boundary_rule": "lichun(315deg)",
                "month_boundary_rule": "solar_terms(315deg+30deg_step)",
                "daiun_start_mode": "approx_days_to_years",
                "special_relations_rules": "伏吟=干支一致、反吟=天干冲(甲庚/乙辛/丙壬/丁癸)と地支冲の同時成立。天干冲のみはstem_clashとして記録し、反吟成立柱には重複記録しない",
                "time_window_policy": "出生時刻が不明・推定の場合、出生可能時刻の両端で年柱・月柱の一意性を評価し、不一致時は大運・年別予測を保留（候補のみ収録）",
                "birth_time_accuracy": time_accuracy,
                "structural_time_basis": structural_analysis["methodology"]["time_basis"],
            },
            "time_context": time_context,
        },
        "unknowns": unknowns,
        "normalized_data": normalized_data,
        "structure_report": structure_report,
        "debug": {
            "year_month": ym_debug,
            "daiun": daiun.get("debug", {}),
        },
        # backward compatibility for current templates / prompts
        "pillars": asdict(p4),
        "day_master": p4.day[0],
        "raw": {
            "pillars": asdict(p4),
            "options": {
                "tz_name": tz_name,
                "day_change_at_23": day_change_at_23,
                "day_boundary_hour": boundary,
                "day_boundary_rule": boundary_label,
                "year_boundary": "lichun(315deg)",
                "month_boundary": "solar_terms(315deg+30deg_step)",
            },
            "debug": {"year_month": ym_debug},
        },
        "features": {
            "five_elements": normalized_data["five_elements"],
            "ten_gods": ten,
            "twelve_fortune": tf,
            "strength": strength,
            "daiun": normalized_data["daiun"],
            "annual_fortune": annual_fortune,
            "interactions": interactions,
            "shinsatsu": shinsatsu,
            "hidden_stems": hidden_all,
            "main_hidden_stems": hidden_main,
            "kubo": kubo,
        },
        "summary": {
            "year_kanshi": p4.year,
            "month_kanshi": p4.month,
            "day_kanshi": p4.day,
            "hour_kanshi": p4.hour,
        },
    }
