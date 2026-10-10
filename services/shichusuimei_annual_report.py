"""One Lichun year of calculation data, separate from the saved Full YAML."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from itertools import combinations
from zoneinfo import ZoneInfo

import yaml

from services import shichusuimei_calc as core

# Same published solar-ephemeris window as the existing ACG service; the end
# boundary (Lichun 2400) is also supported. No birth-age/current-year restriction.
MIN_YEAR = 1800
MAX_YEAR = 2399


def validate_selected_year(year: int) -> None:
    if type(year) is not int or not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"対象年は{MIN_YEAR}〜{MAX_YEAR}年の整数で指定してください。")


def _item(name: str, kanshi: str) -> dict:
    if kanshi not in core.KANSHI_60:
        raise ValueError("基礎命式の干支が不正です。")
    return {"name": name, **core._pillar_dict(kanshi)}


def _scope(items: list[dict], required: set[str]) -> list[dict]:
    """Cross-source pairs and distinct-branch group witnesses, with provenance.

    A repeated branch cannot supply two members of a triad. Alternative natal
    placements are recorded on one group, rather than counted as new groups.
    """
    def sources(participants):
        return {p["name"] if p["name"] in {"annual", "daiun"} else "natal" for p in participants}

    pairs = core._interactions_for_items(items)
    result = [r for key in ("branch_relations", "stem_relations") for r in pairs[key]
              if sources([r["left"], r["right"]]) == required]
    groups = {}
    for size in (2, 3):
        for witness in combinations(items, size):
            if sources(witness) != required or len({p["branch"] for p in witness}) != size:
                continue
            relations = core._branch_triads(list(witness)) + core._branch_three_punishments(list(witness))
            for r in relations:
                if len(r["branches"]) != size:
                    continue
                key = (r["type"], r.get("group", r.get("detail")), tuple(r["branches"]))
                if key not in groups:
                    groups[key] = {k: v for k, v in r.items() if k != "pillars"}
                    groups[key]["participant_sets"] = []
                groups[key]["participant_sets"].append(list(witness))
    for r in groups.values():
        if r["level"] == "partial" and any(
            full["type"] == r["type"] and full["level"] == "full"
            and set(r["branches"]) <= set(full["branches"]) for full in groups.values()
        ):
            continue
        result.append(r)
    for r in result:
        if r["type"] in {"stem_combination", "six_harmony", "triad"}:
            r["element_change_applied"] = False
    return result


def _counts(items: list[dict]) -> dict:
    visible = core._empty_five_counts()
    hidden = core._empty_five_counts()
    for item in items:
        visible[core.STEM_ELEMENT[item["stem"]]] += 1
        visible[core.BRANCH_ELEMENT[item["branch"]]] += 1
        for stem in core.HIDDEN_STEMS[item["branch"]]:
            hidden[core.STEM_ELEMENT[stem]] += 1
    return {"visible": visible, "with_hidden_stems": {e: n + hidden[e] for e, n in visible.items()}}


def _project_periods(birth: datetime, first_kanshi: str, direction: str, years: int, months: int, count: int) -> list[dict]:
    """Project saved starting parameters; do not recalculate the starting age.

    This is an isolated prototype adapter. The existing engine and its default
    ten periods are untouched. Calendar arithmetic reuses the engine helper.
    """
    first = core.KANSHI_60.index(first_kanshi)
    step = 1 if direction == "forward" else -1
    age0 = years + months / 12
    result = []
    for i in range(count):
        start = core._add_calendar_months(birth, years * 12 + months + 120 * i)
        end = core._add_calendar_months(birth, years * 12 + months + 120 * (i + 1))
        result.append({"index": i + 1, "kanshi": core.KANSHI_60[(first + step * i) % 60],
                       "age_from": round(age0 + 10 * i, 2), "age_to": round(age0 + 10 * (i + 1), 2),
                       "approx_start_year": start.year, "approx_start_at": start.isoformat(), "approx_end_at": end.isoformat()})
    return result


def _daiun_periods(shichu: dict, data: dict, year: int, tz: ZoneInfo) -> list[dict]:
    daiun = data.get("daiun") or {}
    saved = daiun.get("items") or []
    if not saved:
        raise ValueError("基礎命式に大運の計算結果がありません。基礎命式を再発行してください。")
    # Reconstruct old YAML calendar intervals from its saved start age, without
    # recalculating either the natal pillars or the solar-term starting age.
    birth_iso = (daiun.get("debug") or {}).get("birth_local")
    if birth_iso:
        birth = datetime.fromisoformat(birth_iso).astimezone(tz)
    else:
        raw = (shichu.get("input") or {}).get("raw") or {}
        try:
            birth = datetime(int(raw["year"]), int(raw["month"]), int(raw["day"]),
                             int(raw.get("hour") or 0), int(raw.get("minute") or 0), tzinfo=tz)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("大運の概算期間を復元する出生情報が不足しています。") from exc
    start_age = daiun.get("start_age") or {}
    if "years" not in start_age or "months" not in start_age or daiun.get("direction") not in {"forward", "reverse"}:
        raise ValueError("大運の起運年齢または順逆情報が不足しています。")
    # Beyond the default ten cycles, continue exactly the existing sequence.
    count = max(len(saved), (year + 1 - birth.year) // 10 + 2)
    calculated = _project_periods(birth, saved[0]["kanshi"], daiun["direction"],
                                 int(start_age["years"]), int(start_age["months"]), count)
    for i, original in enumerate(saved):
        for key in calculated[i]:
            if key in original:
                calculated[i][key] = deepcopy(original[key])
    return calculated


def build_annual_fortune_report(base_doc: dict, selected_year: int) -> dict:
    validate_selected_year(selected_year)
    shichu = (base_doc.get("systems") or {}).get("shichusuimei") or {}
    data = shichu.get("normalized_data") or shichu.get("features") or {}
    pillars = data.get("pillars") or shichu.get("pillars") or {}
    if not pillars:
        raise ValueError("四柱推命の基礎命式が含まれていません。")
    assumptions = (shichu.get("input") or {}).get("assumptions") or {}
    base_input = base_doc.get("input") or {}
    tz_name = assumptions.get("tz_name") or base_input.get("timezone") or "Asia/Tokyo"
    tz = ZoneInfo(tz_name)
    accuracy = assumptions.get("birth_time_accuracy") or base_input.get("birth_time_accuracy")
    # Legacy exact charts have no accuracy marker. Unknown or approximate charts
    # carry either a Full-YAML birth_time marker or a normalized reference flag.
    accuracy = accuracy or (base_doc.get("birth_time") or {}).get("accuracy") or "exact"
    reliable = accuracy == "exact" and not data.get("time_sensitive_reference")
    natal = [_item(name, value.get("kanshi") if isinstance(value, dict) else value)
             for name, value in pillars.items() if name in {"year", "month", "day", "hour"}
             and (name != "hour" or reliable)]
    by_name = {p["name"]: p for p in natal}
    if not {"year", "month", "day"} <= by_name.keys():
        raise ValueError("基礎命式の年柱・月柱・日柱が不足しています。")
    day_master = by_name["day"]["stem"]
    annual = _item("annual", core._year_kanshi_from_effective_year(selected_year))
    start = core._lichun_utc_for_year(selected_year, tz_name).astimezone(tz)
    end = core._lichun_utc_for_year(selected_year + 1, tz_name).astimezone(tz)
    periods = _daiun_periods(shichu, data, selected_year, tz)
    contexts = []
    for period in periods:
        left, right = (datetime.fromisoformat(period[key]) for key in ("approx_start_at", "approx_end_at"))
        if left >= end or right <= start:
            continue
        luck = _item("daiun", period["kanshi"])
        contexts.append({
            **period, "stem": luck["stem"], "branch": luck["branch"],
            "ten_god_to_day_master": core.ten_god(day_master, luck["stem"]),
            "twelve_fortune_to_day_master": core.twelve_fortune(day_master, luck["branch"]),
            "boundary_provisional": True,
            "boundary_in_selected_year": start < left < end or start < right < end,
            "overlap_start_approx": max(start, left).isoformat(),
            "overlap_end_approx": min(end, right).isoformat(),
        })
    interactions = {"natal_annual": _scope(natal + [annual], {"natal", "annual"}),
                    "natal_daiun": [], "daiun_annual": [], "combined": []}
    for context in contexts:
        luck = _item("daiun", context["kanshi"])
        for key, participants, required in (
            ("natal_daiun", natal + [luck], {"natal", "daiun"}),
            ("daiun_annual", [luck, annual], {"daiun", "annual"}),
            ("combined", natal + [luck, annual], {"natal", "daiun", "annual"}),
        ):
            interactions[key].extend({"daiun_index": context["index"], **r} for r in _scope(participants, required))
    kubo = data.get("kubo") or core.kubo_from_day_kanshi(by_name["day"]["kanshi"])
    empty = kubo["empty_branches"]
    daiun_counts, combined = [], []
    for context in contexts:
        luck = _item("daiun", context["kanshi"])
        daiun_counts.append({"daiun_index": context["index"], **_counts([luck])})
        combined.append({"daiun_index": context["index"], **_counts(natal + [luck, annual])})
    first = datetime.fromisoformat(periods[0]["approx_start_at"])
    return {"annual_fortune_report": {
        "schema_version": "1.0", "base_chart_id": (base_doc.get("meta") or {}).get("chart_id"),
        "selected_year": selected_year,
        "calculation": {"engine": "nanami-shichusuimei-annual-v1", "base_engine_version": shichu.get("engine_version"),
                        "year_boundary_rule": "lichun(315deg)", "daiun_calc_mode": "approx_days_to_years",
                        "daiun_selection_method": "approx_calendar_intervals_intersect_lichun_year",
                        "timezone": tz_name, "supported_years": {"min": MIN_YEAR, "max": MAX_YEAR},
                        "natal_time_basis": "four_pillars" if reliable else "three_pillars_hour_excluded"},
        "base_chart_usage": {"full_yaml_required": True,
                             "note": "同じbase_chart_idのFull YAMLと併用。出生四柱は照合用。格局・用神などは基礎命式を参照。"},
        "natal_reference": {"day_master": day_master, "pillars": {p["name"]: p["kanshi"] for p in natal}},
        "annual": {"effective_year": selected_year, **{k: v for k, v in annual.items() if k != "name"},
                   "period_start": start.isoformat(), "period_end": end.isoformat(), "period_end_exclusive": True,
                   "ten_god_to_day_master": core.ten_god(day_master, annual["stem"]),
                   "twelve_fortune_to_day_master": core.twelve_fortune(day_master, annual["branch"])},
        "daiun": {"status": "overlapping_periods" if contexts else "before_first_daiun",
                  "contexts": contexts, "boundary_in_selected_year": any(c["boundary_in_selected_year"] for c in contexts),
                  "uncovered_before_first_daiun": {"start": start.isoformat(), "end": min(first, end).isoformat()}
                      if start < first else None,
                  "note": "起運・交運日時は既存の簡易換算による概算。境界付近の大運を確定値として扱わない。"},
        "interactions": interactions,
        "kubo": {"empty_branches": deepcopy(empty), "annual_hit": annual["branch"] in empty,
                 "natal_hits": [p["name"] for p in natal if p["branch"] in empty],
                 "daiun_hits": [{"daiun_index": c["index"], "hit": c["branch"] in empty} for c in contexts],
                 "method": "membership_in_natal_day_jun_empty_branches"},
        "five_elements": {"natal": deepcopy(data.get("five_elements")), "natal_reference_only": not reliable,
                          "included_natal_reference": _counts(natal), "annual": _counts([annual]),
                          "daiun": daiun_counts, "combined_reference": combined,
                          "method": "existing_visible_stem_plus_branch_and_additive_hidden_stem_counts",
                          "note": "合算は参考個数。強弱・吉凶・合化の成立を示さない。時刻不明・推定の場合、合算から時柱を除外。"},
        "interpretation_flags": {"calculation_only": True, "automatic_good_bad_judgment": False,
                                 "automatic_element_transformation": False},
    }}


def build_annual_fortune_yaml(base_doc: dict, selected_year: int) -> str:
    return yaml.safe_dump(build_annual_fortune_report(base_doc, selected_year), allow_unicode=True, sort_keys=False, width=120)
