"""Explainable structural materials, independent of AI interpretation.

Coefficients belong to our versioned heuristic, not a canonical school.
Combination screening never changes elements or declares a transformation.
"""
from __future__ import annotations

from typing import Any

from services.shichusuimei_calc import (
    BRANCH_ELEMENT, HIDDEN_STEMS, STEM_ELEMENT, YIN_YANG, Pillars4,
    _element_control, _element_generate, _interactions_for_items, _pillar_items,
    ten_god, twelve_fortune,
)

ELEMENTS = ("木", "火", "土", "金", "水")
GODS = ("比肩", "劫財", "食神", "傷官", "偏財", "正財", "偏官", "正官", "偏印", "印綬")
GROUPS = {"比劫": ("比肩", "劫財"), "食傷": ("食神", "傷官"), "財": ("偏財", "正財"),
          "官殺": ("偏官", "正官"), "印": ("偏印", "印綬")}
WEIGHTS = {1: (1.0,), 2: (0.7, 0.3), 3: (0.6, 0.3, 0.1)}
POSITIONS = {"year": 0, "month": 1, "day": 2, "hour": 3}
VERSION = "structural_heuristic_v1"
LIMITATIONS = ["固定蔵干重み。節入り後の日数・司令は未評価", "五行強度は相対指標で吉凶や確率ではない",
               "月令代表五行による季節近似。調候は月支の寒暖燥湿による一般則のみで、日干別の調候表は未評価",
               "格の成敗・従格・専旺格は未確定",
               "合化で五行・十神・根を変更しない。冲で蔵干が消えるとは扱わない", "三合の争合・競合は未評価"]

# 調候（寒暖燥湿）の一般則。月支ごとの気候と、和らげる五行。日干別の調候表ではない。
# urgency: high=厳寒・酷暑など調候を強く要する / medium / low=要否に流派差が大きい / none=温和
CLIMATE_BY_MONTH = {
    "寅": dict(season="初春", temperature="cold", moisture="neutral", note="余寒が残る"),
    "卯": dict(season="仲春", temperature="mild", moisture="neutral", note="温和"),
    "辰": dict(season="晩春", temperature="mild", moisture="damp", note="温和・湿土"),
    "巳": dict(season="初夏", temperature="warm", moisture="neutral", note="暑さが増す"),
    "午": dict(season="仲夏", temperature="hot", moisture="dry", note="炎暑"),
    "未": dict(season="晩夏", temperature="hot", moisture="dry", note="暑・燥土"),
    "申": dict(season="初秋", temperature="cool", moisture="dry", note="残暑と乾燥"),
    "酉": dict(season="仲秋", temperature="cool", moisture="dry", note="涼・乾燥"),
    "戌": dict(season="晩秋", temperature="cool", moisture="dry", note="涼・燥土"),
    "亥": dict(season="初冬", temperature="cold", moisture="wet", note="寒・湿"),
    "子": dict(season="仲冬", temperature="freezing", moisture="wet", note="厳寒・湿"),
    "丑": dict(season="晩冬", temperature="freezing", moisture="wet", note="厳寒・凍土"),
}
CLIMATE_NEEDS = {
    # (temperature or moisture, value): (element, purpose, urgency)
    ("temperature", "freezing"): ("火", "warming", "high"),
    ("temperature", "cold"): ("火", "warming", "medium"),
    ("temperature", "hot"): ("水", "cooling", "high"),
    ("temperature", "warm"): ("水", "cooling", "medium"),
    ("moisture", "dry"): ("水", "moistening", "low"),
}
CLIMATE_PURPOSE_LABELS = {"warming": "温める", "cooling": "冷ます", "moistening": "潤す"}
USEFUL_METHOD_LABELS = {"fuyi_weighted_support": "扶抑", "tongguan_control_bridge": "通関",
                        "climate_adjustment": "調候"}
URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _natal_items(p4: Pillars4, time_reliable: bool) -> list[dict[str, str]]:
    return [p for p in _pillar_items(p4) if time_reliable or p["name"] != "hour"]


def _seasonal_multipliers(month_element: str) -> dict[str, float]:
    resource = next(e for e in ELEMENTS if _element_generate(e) == month_element)
    controller = next(e for e in ELEMENTS if _element_control(e) == month_element)
    return {month_element: 1.5, _element_generate(month_element): 1.2, resource: 1.0,
            controller: 0.8, _element_control(month_element): 0.6}


def _evidence(items, day, seasonal, *, natal=True):
    result = []
    for p in items:
        if not natal or p["name"] != "day":
            result.append(dict(id=f"{p['name']}:visible", pillar=p["name"], layer="visible",
                stem=p["stem"], element=STEM_ELEMENT[p["stem"]], ten_god=ten_god(day, p["stem"]),
                weight=seasonal[STEM_ELEMENT[p["stem"]]]))
        hidden = HIDDEN_STEMS[p["branch"]]
        for rank, (stem, weight) in enumerate(zip(hidden, WEIGHTS[len(hidden)])):
            result.append(dict(id=f"{p['name']}:hidden:{rank}", pillar=p["name"], branch=p["branch"],
                layer="hidden", stem=stem, element=STEM_ELEMENT[stem], ten_god=ten_god(day, stem),
                rank=rank, role="main" if rank == 0 else "secondary" if rank == 1 else "residual",
                base_weight=weight, weight=round(weight * seasonal[STEM_ELEMENT[stem]] *
                                          (1.5 if natal and p["name"] == "month" else 1), 4)))
    return result


def _root_hits(stem, evidence):
    return [{**x, "match": "same_stem" if x["stem"] == stem else "same_element"}
            for x in evidence if x["layer"] == "hidden" and x["element"] == STEM_ELEMENT[stem]]


def _totals(evidence):
    return {e: round(sum(x["weight"] for x in evidence if x["element"] == e), 4) for e in ELEMENTS}


def _god_strength(evidence):
    total = sum(x["weight"] for x in evidence)
    result = {}
    for god in GODS:
        hits = [x for x in evidence if x["ten_god"] == god]
        roots = {r["id"]: r for x in hits if x["layer"] == "visible" for r in _root_hits(x["stem"], evidence)}
        score = round(sum(x["weight"] for x in hits), 4)
        result[god] = dict(score=score, share=round(score / total, 4) if total else 0, placements=hits,
            visible_count=sum(x["layer"] == "visible" for x in hits),
            hidden_count=sum(x["layer"] == "hidden" for x in hits),
            visible_root_evidence_ids=list(roots), visible_root_score=round(sum(x["weight"] for x in roots.values()), 4))
    return result


def _group_strength(gods):
    return {group: dict(score=round(sum(gods[g]["score"] for g in members), 4),
                        visible_count=sum(gods[g]["visible_count"] for g in members),
                        hidden_count=sum(gods[g]["hidden_count"] for g in members),
                        root_evidence_ids=sorted({r for g in members for r in gods[g]["visible_root_evidence_ids"]}))
            for group, members in GROUPS.items()}


def _support(day, totals, roots, time_reliable):
    own = STEM_ELEMENT[day]
    resource = next(e for e in ELEMENTS if _element_generate(e) == own)
    ratio = (totals[own] + totals[resource]) / sum(totals.values())
    label = "strong_candidate" if ratio > .55 else "weak_candidate" if ratio < .4 else "balanced_candidate"
    return dict(support_ratio=round(ratio, 4), label=label, peer_element=own, resource_element=resource,
        root_score=round(sum(x["weight"] for x in roots), 4), root_evidence_ids=[x["id"] for x in roots],
        thresholds=dict(weak_below=.4, strong_above=.55),
        special_pattern_review_required=(ratio < .2 and not roots) or ratio > .85,
        confidence="low", hour_excluded=not time_reliable)


def _pattern(p4, items, evidence):
    main = HIDDEN_STEMS[p4.month[1]][0]
    candidates = []
    for stem in HIDDEN_STEMS[p4.month[1]]:
        exposed = [p["name"] for p in items if p["name"] != "day" and p["stem"] == stem]
        if stem != main and not exposed:
            continue
        god = ten_god(p4.day[0], stem)
        label = {"印綬": "正印格候補", "偏官": "七殺格候補"}.get(god, god + "格候補")
        if god in ("比肩", "劫財"):
            stage = twelve_fortune(p4.day[0], p4.month[1])
            label = "建禄格候補" if stage == "建禄" else "陽刃格候補" if stage == "帝旺" and YIN_YANG[p4.day[0]] == "陽" else "月令比劫・通常格判定保留"
        candidates.append(dict(ten_god=god, stem=stem, exposed_at=exposed, label=label, status="candidate",
            evidence_ids=[x["id"] for x in evidence if x["pillar"] == "month" and x["layer"] == "hidden" and x["stem"] == stem],
            reasons=(["月支本気"] if stem == main else []) + (["月支蔵干の透干"] if exposed else [])))
    candidates.sort(key=lambda x: (not bool(x["exposed_at"]), x["stem"] != main))
    return dict(method="month_hidden_stems_and_exposure", candidates=candidates, confidence="low",
        definitive_pattern=None, success_failure_status="not_assessed",
        conflicting_rules=["司令日数を使う方式とは異なる", "月令比劫と特殊格は別条件の検証が必要"])


def _climate(p4, items, evidence, totals, time_reliable):
    """調候の一般則：月支の寒暖燥湿と、それを和らげる五行が原局にあるか。用神は確定しない。"""
    month_branch = p4.month[1]
    climate = CLIMATE_BY_MONTH[month_branch]
    total = sum(totals.values()) or 1
    needs = {}
    for axis in ("temperature", "moisture"):
        need = CLIMATE_NEEDS.get((axis, climate[axis]))
        if not need:
            continue
        element, purpose, urgency = need
        entry = needs.setdefault(element, dict(element=element, purposes=[], urgency=urgency))
        entry["purposes"].append(purpose)
        if URGENCY_ORDER[urgency] < URGENCY_ORDER[entry["urgency"]]:
            entry["urgency"] = urgency
    result = []
    for entry in sorted(needs.values(), key=lambda x: URGENCY_ORDER[x["urgency"]]):
        element = entry["element"]
        visible = [p["name"] for p in items if STEM_ELEMENT[p["stem"]] == element]
        hidden = [x["id"] for x in evidence if x["layer"] == "hidden" and x["element"] == element]
        presence = "visible_and_rooted" if visible and hidden else "visible_unrooted" if visible \
            else "hidden_only" if hidden else "absent"
        result.append(dict(element=element, purposes=entry["purposes"],
            purpose_labels=[CLIMATE_PURPOSE_LABELS[x] for x in entry["purposes"]], urgency=entry["urgency"],
            natal_presence=dict(status=presence, visible_pillars=visible, hidden_evidence_ids=hidden,
                                element_share=round(totals[element] / total, 4)),
            status="candidate"))
    limitations = ["月支の寒暖燥湿による一般則。日干別の調候表（窮通宝鑑など）は未評価",
                   "秋の燥・初春の余寒をどこまで重視するかは流派差がある"]
    if not time_reliable:
        limitations.append("時柱を除外した原局で五行の有無を確認")
    return dict(method="climate_adjustment", version="seasonal_climate_v1", status="candidate_only",
        month_branch=month_branch, season=climate["season"], temperature=climate["temperature"],
        moisture=climate["moisture"], climate_note=climate["note"], needs=result, confidence="low",
        limitations=limitations)


def _method_comparison(fuyi, mediation, climate):
    """方式ごとの支持・反対を五行別に並べる。統合して一つに決めない。"""
    rows = []
    for element in ELEMENTS:
        support, oppose = [], []
        if element in fuyi["favorable_elements"]:
            support.append("fuyi_weighted_support")
        if element in fuyi["unfavorable_elements"]:
            oppose.append("fuyi_weighted_support")
        if any(c["element"] == element for c in mediation):
            support.append("tongguan_control_bridge")
        if any(n["element"] == element for n in climate["needs"]):
            support.append("climate_adjustment")
        if not support:
            continue
        status = "conflict" if oppose else "agreement" if len(support) >= 2 else "single_method"
        labels = "・".join(USEFUL_METHOD_LABELS[m] for m in support)
        note = f"{labels}が支持" + (f"、{'・'.join(USEFUL_METHOD_LABELS[m] for m in oppose)}は忌方向" if oppose else "")
        rows.append(dict(element=element, supported_by=support, opposed_by=oppose, status=status, note=note))
    rows.sort(key=lambda r: ({"agreement": 0, "single_method": 1, "conflict": 2}[r["status"]], -len(r["supported_by"])))
    return dict(method="per_element_method_votes", elements=rows,
        excluded_methods=[dict(method="month_pattern", reason="格局候補は十神の型であり五行の喜忌に変換しない")],
        interpretation="複数方式の一致は候補として比較的有力という材料。用神の確定ではない。食い違いは両論として扱う")


SELECTION_METHOD_LABEL = "扶抑を基本に、厳寒・酷暑の生まれは調候を優先する一般的な取り方"


def _relative_elements(own):
    output = _element_generate(own)
    wealth = _element_generate(output)
    return dict(peer=own, resource=next(e for e in ELEMENTS if _element_generate(e) == own),
                output=output, wealth=wealth, officer=_element_generate(wealth))


def _select_useful_god(support, totals, groups, climate, mediation):
    """用神を一つ選ぶ。流派共通の正解ではなく、明示した一般的な取り方での選択。"""
    rel = _relative_elements(support["peer_element"])
    ratio = support["support_ratio"]
    urgent = [n for n in climate["needs"] if n["urgency"] == "high"]
    others = {n["element"] for n in climate["needs"]} | {c["element"] for c in mediation}
    basis, notes, alternatives = [], [], []
    pattern_view = "regular"
    if support["special_pattern_review_required"] and ratio < .4:
        # 日主が極端に弱く根もない：勢いに従う（従格）見方。最も強い五行を用神とする。
        pattern_view = "follow_pattern"
        useful = max((e for e in ELEMENTS if e not in (rel["peer"], rel["resource"])), key=lambda e: totals[e])
        feeder = next(e for e in ELEMENTS if _element_generate(e) == useful)  # 従う五行を生じる五行
        favorable = [feeder] if feeder not in (rel["peer"], rel["resource"]) else []
        basis.append(f"日主が極端に弱く根がないため、従格（最も強い{useful}に従う）として見る")
        alternatives.append(dict(element=rel["resource"], view="通常の格として日主を助ける印を用いる見方"))
    elif support["special_pattern_review_required"]:
        # 日主が極端に強い：その勢いを用いる（専旺格）見方。
        pattern_view = "dominant_pattern"
        useful = rel["peer"]
        favorable = [rel["resource"], rel["output"]]
        basis.append(f"日主の勢いが極端に強いため、専旺格（日主と同じ{useful}を用いる）として見る")
        alternatives.append(dict(element=rel["output"], view="通常の格として強さを漏らす食傷を用いる見方"))
    else:
        weak = support["label"] == "weak_candidate" or (support["label"] == "balanced_candidate" and ratio < .475)
        fuyi_side = [rel["resource"], rel["peer"]] if weak else [rel["output"], rel["wealth"], rel["officer"]]
        if support["label"] == "balanced_candidate":
            notes.append("日主の強弱は中間。わずかに" + ("弱い" if weak else "強い") + "側として扶抑を判断")
        if urgent:
            useful = urgent[0]["element"]
            basis.append(f"{climate['season']}生まれ（{climate['climate_note']}）のため調候を優先し、"
                         f"{useful}で{'・'.join(urgent[0]['purpose_labels'])}")
            if useful not in fuyi_side:
                alternatives.append(dict(element=fuyi_side[0], view="扶抑（日主の強弱の調整）を優先する見方"))
        else:
            agreed = [e for e in fuyi_side if e in others]
            if agreed:
                useful = agreed[0]
                supporters = [USEFUL_METHOD_LABELS["climate_adjustment"]] if any(
                    n["element"] == useful for n in climate["needs"]) else []
                if any(c["element"] == useful for c in mediation):
                    supporters.append(USEFUL_METHOD_LABELS["tongguan_control_bridge"])
                basis.append(f"日主が{'弱い' if weak else '強い'}ため扶抑で{useful}を取り、{'・'.join(supporters)}とも一致")
            elif weak:
                drain = max(("官殺", "食傷", "財"), key=lambda g: groups[g]["score"])
                useful = rel["peer"] if drain == "財" else rel["resource"]
                basis.append(f"日主が弱く、最も強く弱めているのは{drain}のため、"
                             f"{'比劫' if drain == '財' else '印'}の{useful}で日主を助ける")
            else:
                heavy = max(("比劫", "印"), key=lambda g: groups[g]["score"])
                if heavy == "印":
                    useful = rel["wealth"]
                    basis.append(f"日主が強く印が重いため、財の{useful}で印を抑える")
                else:
                    useful = rel["officer"] if totals[rel["officer"]] else rel["output"]
                    basis.append(f"日主が強く比劫が重いため、{'官殺' if useful == rel['officer'] else '食傷'}の{useful}で強さを整える")
        favorable = [e for e in fuyi_side if e != useful]
        for c in mediation:
            if c["element"] != useful and c["element"] not in fuyi_side:
                alternatives.append(dict(element=c["element"], view=f"通関（{c['source']}と{c['target']}の対立をつなぐ）を重視する見方"))
    unfavorable = [e for e in ELEMENTS if e != useful and e not in favorable]
    if support["hour_excluded"]:
        notes.append("出生時刻が不明・推定のため時柱を除く三柱で判断。時刻が分かると変わる場合がある")
    return dict(method="general_fuyi_with_climate_priority_v1", method_label=SELECTION_METHOD_LABEL,
        status="selected", pattern_view=pattern_view, useful_god=useful, favorable_elements=favorable,
        unfavorable_elements=unfavorable, basis=basis, notes=notes, alternatives=alternatives,
        school_note="用神の取り方は流派で異なる。ここでは上記の一般的な取り方で一つに決めている")


def _useful_gods(support, totals, pattern, climate, groups):
    own, resource = support["peer_element"], support["resource_element"]
    reasons = [f"日主と印の重み付き支持比率={support['support_ratio']}", f"日主の通根重み={support['root_score']}"]
    held = support["special_pattern_review_required"] or support["hour_excluded"]
    favorable, unfavorable = [], []
    if not held and support["label"] == "weak_candidate":
        favorable = [resource, own]
        unfavorable = [e for e in ELEMENTS if e not in favorable]
    elif not held and support["label"] == "strong_candidate":
        favorable = [e for e in ELEMENTS if e not in (own, resource)]
        unfavorable = [resource, own]
    fuyi = dict(method="fuyi_weighted_support", status="held_for_review" if held else "candidate_only",
        favorable_elements=favorable, unfavorable_elements=unfavorable, reasons=reasons, confidence="low",
        candidate_policy="扶抑の支持・泄耗圧力方向。個別の用神を確定しない")
    mediation = []
    total = sum(totals.values())
    for source in ELEMENTS:
        target = _element_control(source)
        if totals[source] / total >= .2 and totals[target] / total >= .2:
            bridge = _element_generate(source)
            mediation.append(dict(element=bridge, source=source, target=target,
                present_in_natal=bool(totals[bridge]), status="candidate_material",
                reason=f"{source}剋{target}の両端が各20%以上。{source}→{bridge}→{target}を検討"))
    conflicts = ["格の成敗による喜忌は未評価", "調候は季節の一般則のみで日干別の調候表は未評価",
                 "月令用神と扶抑の用神は同じ定義として統合しない"]
    if held:
        conflicts.append("時柱未確定または特殊格の検討が必要なため扶抑の喜忌を保留")
    for c in mediation:
        if c["element"] in unfavorable:
            conflicts.append(f"通関候補の{c['element']}と扶抑の忌方向が食い違う")
    for n in climate["needs"]:
        if n["element"] in unfavorable:
            conflicts.append(f"調候候補の{n['element']}と扶抑の忌方向が食い違う")
    selection = _select_useful_god(support, totals, groups, climate, mediation)
    candidates = [dict(element=e, method="fuyi_weighted_support", status="candidate") for e in favorable]
    candidates += [dict(element=c["element"], method="tongguan_control_bridge", status="candidate_material") for c in mediation]
    candidates += [dict(element=n["element"], method="climate_adjustment", status="candidate", urgency=n["urgency"])
                   for n in climate["needs"]]
    # 用神は明示した一般的な取り方で一つに決め、先頭に置く。方式別の材料は根拠として残す。
    return dict(useful_god_selection=selection, method="separate_method_candidates_v2", confidence="low",
        candidates=candidates, favorable_elements=selection["favorable_elements"],
        unfavorable_elements=selection["unfavorable_elements"], reasons=reasons,
        methods=[fuyi, dict(method="tongguan_control_bridge", status="materials_only", candidates=mediation),
                 dict(method="month_pattern", status="reference_only", candidates=pattern["candidates"],
                      note="月令用神の意味での格局候補。五行の喜忌に変換しない"),
                 climate],
        method_comparison=_method_comparison(fuyi, mediation, climate),
        conflicting_rules=conflicts, definitive_useful_god=selection["useful_god"],
        definitive_basis=selection["method"])


def _element_flow(totals, day):
    edges = []
    paths = []
    for e in ELEMENTS:
        target = _element_generate(e)
        edges.append(dict(source=e, target=target, source_score=totals[e], target_score=totals[target],
            status="both_present" if totals[e] and totals[target] else "missing_endpoint",
            capacity_proxy=round(min(totals[e], totals[target]), 4)))
        end = _element_generate(target)
        if all(totals[x] for x in (e, target, end)):
            paths.append(dict(elements=[e, target, end], status="all_present",
                              capacity_proxy=min(totals[x] for x in (e, target, end))))
    own = STEM_ELEMENT[day]
    output = _element_generate(own)
    wealth = _element_generate(output)
    return dict(method="weighted_presence_only", element_scores=totals, edges=edges,
        bottlenecks=[x for x in edges if x["status"] == "missing_endpoint"],
        dominant_paths=sorted(paths, key=lambda x: -x["capacity_proxy"])[:3],
        day_master_output_wealth_path=dict(elements=[own, output, wealth],
            status="all_present" if all(totals[x] for x in (own, output, wealth)) else "missing_endpoint"),
        interpretation="存在・接続の材料。流通成立・現実の財運・吉凶の保証ではない")


def _ten_god_flow(gods):
    definitions = [("食神生財", ("食神",), GROUPS["財"], "generation"),
                   ("傷官生財", ("傷官",), GROUPS["財"], "generation"),
                   ("官印相生", ("正官",), GROUPS["印"], "generation"),
                   ("殺印相生", ("偏官",), GROUPS["印"], "generation"),
                   ("食神制殺", ("食神",), ("偏官",), "control"),
                   ("傷官見官", ("傷官",), ("正官",), "control"),
                   ("比劫剋財", GROUPS["比劫"], GROUPS["財"], "control"),
                   ("財剋印", GROUPS["財"], GROUPS["印"], "control")]
    result = []
    for label, sources, targets, relation in definitions:
        left = [x for g in sources for x in gods[g]["placements"]]
        right = [x for g in targets for x in gods[g]["placements"]]
        result.append(dict(label=label, relation=relation, source_gods=list(sources), target_gods=list(targets),
            source_score=round(sum(gods[g]["score"] for g in sources), 4),
            target_score=round(sum(gods[g]["score"] for g in targets), 4),
            source_evidence_ids=[x["id"] for x in left], target_evidence_ids=[x["id"] for x in right],
            status="both_present" if left and right else "missing_endpoint",
            interpretation="配置の併存。成格・成功・破財を断定する条件ではない"))
    return result


def _target_material(p, day):
    return dict(pillar=p["name"], kanshi=p["kanshi"], stem_ten_god=ten_god(day, p["stem"]),
                hidden_ten_gods=[dict(stem=s, ten_god=ten_god(day, s)) for s in HIDDEN_STEMS[p["branch"]]])


def analyze_interactions(items, *, day, month_branch):
    """Attach targets and conservative condition screening to existing relation tables."""
    relations = _interactions_for_items(items)
    materials = {p["name"]: _target_material(p, day) for p in items}
    for key in ("triads", "three_punishments"):
        relations[key] = [{**r, "targets": [materials[p["name"]] for p in r["pillars"]]}
                          for r in relations[key]]
    for key in ("branch_relations", "stem_relations"):
        relations[key] = [{**r, "targets": [materials[r["left"]["name"]], materials[r["right"]["name"]]]}
                          for r in relations[key]]
    screenings = []
    combinations = relations["stem_relations"] + [r for r in relations["branch_relations"] if r["type"] == "six_harmony"]
    for r in combinations:
        pair = [r["left"], r["right"]]
        target = r["element"]
        names = {p["name"] for p in pair}
        stem_pair = r["type"] == "stem_combination"
        field = "stem" if stem_pair else "branch"
        competition = [p["name"] for p in items if p["name"] not in names and p[field] in {x[field] for x in pair}]
        clashes = [x for x in relations["branch_relations"] if x["type"] == "clash" and
                   names.intersection((x["left"]["name"], x["right"]["name"]))]
        adjacent = (abs(POSITIONS[pair[0]["name"]] - POSITIONS[pair[1]["name"]]) == 1
                    if all(p["name"] in POSITIONS for p in pair) else None)
        checks = dict(month_element_supports_target=BRANCH_ELEMENT[month_branch] == target or
                      _element_generate(BRANCH_ELEMENT[month_branch]) == target,
                      target_visible=any(STEM_ELEMENT[p["stem"]] == target for p in items),
                      target_rooted=any(STEM_ELEMENT[s] == target for p in items for s in HIDDEN_STEMS[p["branch"]]),
                      adjacent_in_natal=adjacent, competing_partners=competition,
                      clashed_pillars=sorted({p["name"] for x in clashes for p in (x["left"], x["right"]) if p["name"] in names}))
        screenings.append(dict(type=r["type"], pillars=[p["name"] for p in pair], candidate_element=target,
            checks=checks, status="conditions_incomplete" if competition or clashes or not checks["month_element_supports_target"] or adjacent is False else "candidate_materials_only",
            confirmed=False, element_change_applied=False,
            conflicting_rules=["六合の化五行は流派差あり（午未は火・土）"] if not stem_pair and {p["branch"] for p in pair} == {"午", "未"} else []))
    for r in relations["triads"]:
        target = r["group"][0]
        center = {"木": "卯", "火": "午", "金": "酉", "水": "子"}[target]
        names = {p["name"] for p in r["pillars"]}
        clashed = sorted({x[side]["name"] for x in relations["branch_relations"] if x["type"] == "clash"
                          for side in ("left", "right") if x[side]["name"] in names})
        screenings.append(dict(type="triad", pillars=[p["name"] for p in r["pillars"]],
            candidate_element=target,
            status="candidate_materials_only" if r["level"] == "full" and not clashed else "conditions_incomplete",
            partial_form=None if r["level"] == "full" else "half_with_center" if center in r["branches"] else "arching_without_center",
            checks=dict(all_three_present=r["level"] == "full", center_present=center in r["branches"],
                        competition_status="not_assessed",
                        clashed_pillars=clashed, month_element_supports_target=BRANCH_ELEMENT[month_branch] == target or
                        _element_generate(BRANCH_ELEMENT[month_branch]) == target),
            confirmed=False, element_change_applied=False))
    return {**relations, "combination_screening": screenings,
            "policy": "組合せ・作用対象・条件材料。合化確定や冲による根の削除は行わない"}


def analyze_structure(p4: Pillars4, *, time_reliable: bool = True) -> dict[str, Any]:
    items = _natal_items(p4, time_reliable)
    day = p4.day[0]
    seasonal = _seasonal_multipliers(BRANCH_ELEMENT[p4.month[1]])
    evidence = _evidence(items, day, seasonal)
    interactions = analyze_interactions(items, day=day, month_branch=p4.month[1])
    rooting = []
    for p in items:
        hits = _root_hits(p["stem"], evidence)
        hit_names = {x["pillar"] for x in hits}
        rooting.append(dict(pillar=p["name"], stem=p["stem"], roots=hits,
            root_score=round(sum(x["weight"] for x in hits), 4),
            own_branch_root=any(x["pillar"] == p["name"] for x in hits),
            affected_root_pillars=sorted({x[side]["name"] for x in interactions["branch_relations"]
                if x["type"] in ("clash", "punishment", "self_punishment", "harm", "destruction")
                for side in ("left", "right") if x[side]["name"] in hit_names})))
    exposure = [{**x, "visible_pillars": [p["name"] for p in items if p["name"] != "day" and p["stem"] == x["stem"]],
                 "is_day_master_stem": x["stem"] == day} for x in evidence if x["layer"] == "hidden"]
    gods = _god_strength(evidence)
    totals = _totals(evidence)
    totals[STEM_ELEMENT[day]] = round(totals[STEM_ELEMENT[day]] + seasonal[STEM_ELEMENT[day]], 4)
    support = _support(day, totals, _root_hits(day, evidence), time_reliable)
    pattern = _pattern(p4, items, evidence)
    limitations = LIMITATIONS.copy()
    if not time_reliable:
        limitations.append("時柱を除外。年・月・日柱は仮置き／推定時刻に基づき、節入り・日替わり付近では要再確認")
    return dict(methodology=dict(version=VERSION, hidden_weights={str(k): list(v) for k, v in WEIGHTS.items()},
        visible_weight=1, month_hidden_multiplier=1.5, seasonal_multipliers=seasonal,
        time_basis="four_pillars" if time_reliable else "three_pillars_hour_excluded", limitations=limitations),
        roots_and_exposure=dict(rooting=rooting, exposure=exposure), ten_god_strength=gods,
        ten_god_groups=_group_strength(gods), ten_god_flow=_ten_god_flow(gods), day_master_support=support,
        pattern_analysis=pattern,
        useful_god_analysis=_useful_gods(support, totals, pattern, _climate(p4, items, evidence, totals, time_reliable),
                                         _group_strength(gods)),
        element_flow=_element_flow(totals, day), interactions=interactions)


def _stem_action(left, right):
    a, b = STEM_ELEMENT[left], STEM_ELEMENT[right]
    if a == b:
        return "same_element"
    if _element_generate(a) == b:
        return "generates_target"
    if _element_generate(b) == a:
        return "generated_by_target"
    if _element_control(a) == b:
        return "controls_target"
    return "controlled_by_target"


def analyze_luck(p4: Pillars4, kanshi: str, *, time_reliable: bool = True,
                 other_luck: str | None = None, structural_analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare an incoming pillar with natal; optionally include a concurrent 大運."""
    natal = _natal_items(p4, time_reliable)
    day = p4.day[0]
    luck = dict(name="luck", kanshi=kanshi, stem=kanshi[0], branch=kanshi[1])
    targets = natal.copy()
    if other_luck:
        targets.append(dict(name="current_daiun", kanshi=other_luck, stem=other_luck[0], branch=other_luck[1]))
    relations = analyze_interactions([luck, *targets], day=day, month_branch=p4.month[1])
    for key in ("branch_relations", "stem_relations"):
        relations[key] = [r for r in relations[key] if r["left"]["name"] == "luck"]
    for key in ("triads", "three_punishments"):
        relations[key] = [r for r in relations[key] if any(p["name"] == "luck" for p in r["pillars"])]
    relations["combination_screening"] = [r for r in relations["combination_screening"] if "luck" in r["pillars"]]
    for key in ("branch_relations", "stem_relations"):
        relations[key] = [{k: v for k, v in r.items() if k not in ("left", "right", "targets")} | {
            "left": {"name": r["left"]["name"]},
            "right": {"name": r["right"]["name"], "kanshi": r["right"]["kanshi"]},
            "target_ten_gods": {"stem": r["targets"][1]["stem_ten_god"],
                                "hidden": [x["ten_god"] for x in r["targets"][1]["hidden_ten_gods"]]},
        } for r in relations[key]]
    for key in ("triads", "three_punishments"):
        relations[key] = [{k: v for k, v in r.items() if k not in ("pillars", "targets")} | {
            "pillars": [{"name": p["name"], "kanshi": p["kanshi"]} for p in r["pillars"]],
        } for r in relations[key]]
    base = structural_analysis if structural_analysis is not None else analyze_structure(p4, time_reliable=time_reliable)
    seasonal = base["methodology"]["seasonal_multipliers"]
    incoming = _evidence([luck], day, seasonal, natal=False)
    delta = _totals(incoming)
    combined = {e: round(base["element_flow"]["element_scores"][e] + delta[e], 4) for e in ELEMENTS}
    if other_luck:
        other = _totals(_evidence([targets[-1]], day, seasonal, natal=False))
        combined = {e: round(combined[e] + other[e], 4) for e in ELEMENTS}
    natal_evidence = [x for g in base["ten_god_strength"].values() for x in g["placements"]]
    # Natal material is already described once in structural_analysis; reference its IDs.
    roots = [dict(evidence_id=x["id"], match=x["match"], weight=x["weight"])
             for x in _root_hits(kanshi[0], natal_evidence)]
    activated = {g: dict(score=v["score"], placements=[
        {k: x[k] for k in ("stem", "layer", "weight", "rank") if k in x} for x in v["placements"]])
        for g, v in _god_strength(incoming).items() if v["score"]}
    return dict(pillar=kanshi, time_basis=base["methodology"]["time_basis"],
        stem_ten_god=ten_god(day, kanshi[0]),
        branch_ten_gods=[ten_god(day, s) for s in HIDDEN_STEMS[kanshi[1]]], interactions_with_natal=relations,
        stem_actions=[dict(target=dict(pillar=p["name"], kanshi=p["kanshi"], ten_god=ten_god(day, p["stem"])),
                           relation=_stem_action(kanshi[0], p["stem"])) for p in targets],
        exposed_natal_hidden_stems=[dict(evidence_id=x["id"], pillar=x["pillar"], stem=x["stem"], ten_god=x["ten_god"])
                                   for x in natal_evidence if x["layer"] == "hidden" and x["stem"] == kanshi[0]],
        incoming_rooting=dict(natal_roots=roots, luck_roots=[dict(stem=x["stem"], rank=x["rank"], match=x["match"], weight=x["weight"])
                                                           for x in _root_hits(kanshi[0], incoming)]),
        activated_ten_gods=activated,
        added_elements=dict(stem=STEM_ELEMENT[kanshi[0]], hidden=[STEM_ELEMENT[s] for s in HIDDEN_STEMS[kanshi[1]]]),
        element_changes=dict(method="additive_materials_fixed_natal_season", incoming_scores=delta, combined_scores=combined,
                             note="運の干支を加えた材料量。合化・冲による減算や喜忌の変更を適用しない"),
        concurrent_daiun=other_luck, transformation_status="not_assessed_no_element_conversion")


def concurrent_luck_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """Project only the concurrent 大運 contribution for a forecast context."""
    relations = analysis["interactions_with_natal"]
    concurrent = {}
    for key in ("branch_relations", "stem_relations"):
        concurrent[key] = [r for r in relations[key] if r["right"]["name"] == "current_daiun"]
    for key in ("triads", "three_punishments"):
        concurrent[key] = [r for r in relations[key] if any(p["name"] == "current_daiun" for p in r["pillars"])]
    concurrent["combination_screening"] = [r for r in relations["combination_screening"] if "current_daiun" in r["pillars"]]
    return dict(pillar=analysis["pillar"], time_basis=analysis["time_basis"], concurrent_daiun=analysis["concurrent_daiun"],
        interactions_with_daiun=concurrent,
        stem_actions=[r for r in analysis["stem_actions"] if r["target"]["pillar"] == "current_daiun"],
        combined_element_scores=analysis["element_changes"]["combined_scores"],
        transformation_status=analysis["transformation_status"])
