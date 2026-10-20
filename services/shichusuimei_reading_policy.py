"""Interpretation contract for computed materials; never recalculates a chart."""
from __future__ import annotations

from typing import Any

READING_POLICY = """【構造から読む・章立てより優先】
- 日主と月令を土台に、通根・透干・十神の力量と関係、格局候補と反証、柱同士の作用を照合し、主要構造を最大2つ選ぶ。身強弱や用神だけで全章を決めない。同じ根拠の別表示を複数の証拠として数えない。
- 構造と根拠→動機・判断基準→力が出る場面→条件が変わった時の行動・葛藤→使い方、の順で具体化する。単体の性格辞典で終えず、支える要素・例外・反証も読む。外面と内面の一致や安定も認め、生きづらさ・自己犠牲・本音の抑制へ結論を寄せない。
- normalized_data.structural_analysis.day_master_support を力量方式の候補指標とする。features.strength と structure_report.strength_index は別方式の参考値で、本文の主判定に混ぜない。新指標がない基本版・旧データでは旧値を参考値として使い、新指標を推測しない。指標間で加算・平均・多数決をしない。
- candidate は候補、ambiguous は境界・保留・条件依存。confirmed は計算上の存在確認だけを意味し、人物像・実体験・制化の機能の確認ではない。likely の昇格条件は未定義なので付与しない。confidence・conflicting_rules・methodology.limitations を内部で利用し、数値や英語ラベルの列挙はせず、重要な不確かさを自然な日本語にする。
- useful_god_selection.status=selected は指定方式での選択であり、確からしさとは別。「この鑑定では、この方式で○を用神として採用します」と伝え、境界・時刻依存・別の方式との対立を結論に関係する範囲で添える。basis の自然文と候補ラベルが食い違う古い原本では、構造化された候補状態を優先し、言い切りを強めない。
- 喜忌は選択方式の中での役割。忌の五行を人格・行動全般の悪さ、避けるべき表現、身体への害と同一視しない。他方式や制化での役割を消さず、alternatives・method_comparison の対立も必要に応じて説明する。
- ten_god_flow の both_present は併存、missing_endpoint は必要要素が揃わない状態。併存だけで成格・制化・成功を確定しない。格局候補は成敗の確定ではなく、神殺は主役に関連する場合だけ補助として使う。
- 宮位は伝統的な対応であり、実際の養育体験や親の性格の証拠ではない。原家族由来の原因、自己消失の経験、特定の身体症状・部位・発症時期を命式だけで事実化しない。本人申告があっても命式がその原因を証明したとは書かず、質問形で問題の存在を埋め込まない。
- 強い根拠のある葛藤・弱点・リスクは条件と行動の出方を明確に書く。根拠のある厳しい読みを励ましで消さず、各章に長所・問題点を一つずつ作らない。関連が薄い領域は短縮・統合してよい。大運・流年だけから生来の性格や出来事を確定しない。"""


def build_reading_context(shichu: dict[str, Any]) -> dict[str, Any]:
    nd = shichu.get("normalized_data") or {}
    analysis = nd.get("structural_analysis") or {}
    support = analysis.get("day_master_support") or {}
    useful = analysis.get("useful_god_analysis") or {}
    selection = useful.get("useful_god_selection") or {}
    legacy_source = "structure_report.strength_index" if (shichu.get("structure_report") or {}).get("strength_index") else "features.strength" if (shichu.get("features") or {}).get("strength") else None
    reference = nd.get("time_sensitive_reference") or {}
    hour_excluded = bool(support.get("hour_excluded"))
    boundary_pillars = bool(reference.get("undetermined_pillars"))
    strength_ambiguous = support.get("label") == "balanced_candidate" or bool(support.get("special_pattern_review_required")) or boundary_pillars
    conflict = any(row.get("status") == "conflict" for row in (useful.get("method_comparison") or {}).get("elements", []))
    return {
        "version": "shichu_reading_policy_v1",
        "strength": {
            "source": "normalized_data.structural_analysis.day_master_support" if support else legacy_source,
            "role": "weighted_candidate" if support else "legacy_reference",
            "status": "ambiguous" if strength_ambiguous or not support else "candidate",
            "time_basis": (analysis.get("methodology") or {}).get("time_basis", "follow_source_flags"),
        },
        "useful_god": {
            "selection_status": selection.get("status", "not_available"),
            "status": "ambiguous" if not selection or strength_ambiguous or hour_excluded or conflict else "candidate",
            "method": selection.get("method"),
            "method_conflict": conflict,
        },
        "pattern_candidates": {"status": "candidate", "confirmation": "not_assessed"},
    }
