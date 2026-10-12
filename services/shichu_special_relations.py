from __future__ import annotations

"""伏吟・反吟（天剋地冲）・天干冲の検出（大運・流年 × 原局/現大運）。

nanami-astro `services/shichu_interactions.py`（フェーズ2・2026-07-14、
`docs/CODEX_TASK_shichu_timing_phase2.md`）の天干冲4組の表と
`detect_special_kanshi_relations` を nanami-products へ移植・適応したもの。
計算事実とタグだけを返し、吉凶・自然言語の解釈は出さない。

対の相互作用（干合・支合・冲・刑・自刑・害・破・三合・半会・三刑）は、
`services/shichusuimei_structure.analyze_luck` の `interactions_with_natal` が
大運・流年について既に収録しているため、本モジュールでは扱わない（重複収録を避ける）。
"""

from typing import Iterable

# 天干冲は4組のみ（甲庚・乙辛・丙壬・丁癸）。戊・己に天干冲は無い。
# nanami-astro の `_STEM_CLASHES` と同一表。lunar_python 1.4.8 の `CHONG_GAN_4` との
# 一致は docs/claude_shichu_calc_verification_20261012.md G節で照合済み。追加・変更禁止。
STEM_CLASHES = {
    frozenset(("甲", "庚")),
    frozenset(("乙", "辛")),
    frozenset(("丙", "壬")),
    frozenset(("丁", "癸")),
}

# services/shichusuimei_calc.BRANCH_CLASHES と同一の六冲表。
# 循環importを避けるためここに再掲する（同一性はテストで担保する）。
BRANCH_CLASHES = {
    frozenset(("子", "午")),
    frozenset(("丑", "未")),
    frozenset(("寅", "申")),
    frozenset(("卯", "酉")),
    frozenset(("辰", "戌")),
    frozenset(("巳", "亥")),
}


def detect_special_kanshi_relations(
    natal_pillars: Iterable[tuple[str, str]],
    luck_kanshi: str,
    luck_name: str,
    *,
    scope: str,
) -> list[dict]:
    """命式（または現大運）の各柱と、運の干支の特殊関係を検出する。

    - 伏吟: 干支の完全一致（``fukugin_v1``）
    - 反吟: 天干冲と地支冲の同時成立（``hangin_v1``、天剋地冲）
    - 天干冲: 天干冲のみの成立（``stem_clash_v1``）。反吟が成立した柱には
      天干冲を重複して記録しない。

    出生時刻が不明・推定の場合は、呼び出し側が時柱を ``natal_pillars`` から
    除外する（エンジン0.5.0の時柱除外方針と同じ）。
    """
    items: list[dict] = []
    luck_kanshi = str(luck_kanshi)
    if len(luck_kanshi) < 2:
        return items
    for natal_name, natal_kanshi in natal_pillars:
        natal_kanshi = str(natal_kanshi)
        if len(natal_kanshi) < 2:
            continue
        stem_clash = frozenset((natal_kanshi[0], luck_kanshi[0])) in STEM_CLASHES
        branch_clash = frozenset((natal_kanshi[1], luck_kanshi[1])) in BRANCH_CLASHES
        if natal_kanshi == luck_kanshi:
            rule_id, type_, category = "fukugin_v1", "伏吟", "kanshi"
            tags = ["repetition", "stagnation_or_emphasis"]
        elif stem_clash and branch_clash:
            rule_id, type_, category = "hangin_v1", "反吟", "kanshi"
            tags = ["reversal", "upheaval"]
        elif stem_clash:
            rule_id, type_, category = "stem_clash_v1", "天干冲", "stem"
            tags = ["tension", "polarity"]
        else:
            continue
        items.append({
            "rule_id": rule_id,
            "type": type_,
            "category": category,
            "scope": scope,
            "pillars": [str(natal_name), str(luck_name)],
            "members": [natal_kanshi, luck_kanshi],
            "status": "detected",
            "tags": tags,
            "detail": {},
        })
    return items
