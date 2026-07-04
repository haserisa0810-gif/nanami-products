"""旅行目的に沿った簡易スコアリング。

MVP の方針:
- 旅行目的に関係する天体・アングル・ハウス・ACGラインを加点する。
- ハードアスペクトは「注意点」として扱い、過度に減点しない。
- スコアはあくまで娯楽的な目安。1〜5 の★で表示する。
断定的な良し悪しは出さず、「この旅で使いやすいテーマ」を示す材料に留める。
"""
from __future__ import annotations

from typing import Any

# 旅行目的ごとに重視する天体・アングル・ハウス。
# planets は英名、angles は ASC/DSC/MC/IC、houses は整数。
PURPOSE_FOCUS: dict[str, dict[str, Any]] = {
    "healing": {"planets": {"Moon", "Venus", "Neptune"}, "angles": {"IC"}, "houses": {4, 12}},
    "love": {"planets": {"Venus", "Moon"}, "angles": {"ASC", "DSC"}, "houses": {5, 7}},
    "work": {"planets": {"Sun", "Jupiter", "Saturn"}, "angles": {"MC"}, "houses": {10}},
    "creativity": {"planets": {"Sun", "Venus", "Mercury"}, "angles": {"ASC"}, "houses": {5, 3}},
    "learning": {"planets": {"Mercury", "Jupiter"}, "angles": {"MC"}, "houses": {3, 9}},
    "adventure": {"planets": {"Mars", "Jupiter"}, "angles": {"ASC"}, "houses": {9}},
    "fan_activity": {"planets": {"Venus", "Sun"}, "angles": {"ASC"}, "houses": {5, 11}},
    "money": {"planets": {"Venus", "Jupiter"}, "angles": {"MC"}, "houses": {2, 8}},
    "solo": {"planets": {"Sun", "Mercury"}, "angles": {"ASC"}, "houses": {9, 12}},
    "family": {"planets": {"Moon", "Venus"}, "angles": {"IC"}, "houses": {4}},
}

# 目的ごとの、おすすめの過ごし方（決定的テキスト。AI が無くても表示できる下地）。
PURPOSE_ACTIONS: dict[str, list[str]] = {
    "healing": ["自然や水辺でゆっくり過ごす", "予定を詰め込みすぎない", "温泉・スパ・静かな宿を選ぶ"],
    "love": ["景色のよい場所で人と過ごす", "自分の直感で行き先を選ぶ", "写真を残す"],
    "work": ["行きたかった街のカフェで仕事を整理する", "現地の人や場と交流する", "目標を1つだけ決めて動く"],
    "creativity": ["美術館・建築・市場をめぐる", "現地のカフェでアイデアを書き出す", "写真や文章で記録する"],
    "learning": ["博物館・書店・歴史地区を歩く", "現地の言葉や文化に触れる", "学んだことをメモに残す"],
    "adventure": ["少し遠くまで足を伸ばす", "アクティビティに挑戦する", "計画に余白を残す"],
    "fan_activity": ["聖地・会場・関連スポットをめぐる", "同じ趣味の人と交流する", "推し活の記録を残す"],
    "money": ["買い物は本当に欲しいものに絞る", "価値あるものにお金を使う", "予算を先に決めておく"],
    "solo": ["自分のペースで気ままに歩く", "気になった場所に立ち寄る", "静かに考える時間をつくる"],
    "family": ["みんなが無理なく回れる計画にする", "食事や休憩を大切にする", "思い出を一緒に残す"],
}

SOFT_ASPECTS = {"trine", "sextile", "conjunction"}
HARD_ASPECTS = {"square", "opposition"}
ANGULAR_HOUSES = {1, 4, 7, 10}


def _score_label(total: int, maximum: int) -> str:
    total = max(0, min(maximum, total))
    return "★" * total + "☆" * (maximum - total)


def compute_score(
    *,
    purpose_key: str,
    nearest_lines: list[dict[str, Any]],
    relocation_houses: list[dict[str, Any]],
    relocation_planets: list[dict[str, Any]],
    transit_highlights: list[dict[str, Any]],
) -> dict[str, Any]:
    """簡易スコア（1〜5）と根拠メモを返す。"""
    focus = PURPOSE_FOCUS.get(purpose_key, {"planets": set(), "angles": set(), "houses": set()})
    focus_planets: set[str] = set(focus.get("planets") or set())
    focus_angles: set[str] = set(focus.get("angles") or set())
    focus_houses: set[int] = set(focus.get("houses") or set())

    notes: list[str] = []
    maximum = 5
    score = 2  # 中立の下地

    # ACG: 目的に関係する近いラインを加点（最大 +2、500km 以内）
    acg_pts = 0
    for line in nearest_lines:
        if acg_pts >= 2:
            break
        if float(line.get("distance_km") or 9e9) > 500:
            continue
        planet = line.get("planet")
        angle = line.get("angle")
        if planet in focus_planets or angle in focus_angles:
            acg_pts += 1
            notes.append(f"{line.get('planet')}{line.get('angle')}線が近く、目的に沿った象意が出やすい配置")
    score += acg_pts

    # Relocation: 目的ハウスに出生天体が集まっている / 目的天体がアングルにある（最大 +1）
    reloc_pts = 0
    emphasized_houses = {int(h.get("house")) for h in relocation_houses if h.get("house") is not None}
    if focus_houses & emphasized_houses:
        reloc_pts = 1
        matched = sorted(focus_houses & emphasized_houses)
        notes.append(f"リロケーションで{ '・'.join(f'{h}ハウス' for h in matched) }が強調されやすい")
    else:
        for planet in relocation_planets:
            if planet.get("name") in focus_planets and int(planet.get("house") or 0) in ANGULAR_HOUSES:
                reloc_pts = 1
                notes.append(f"{planet.get('name')}が旅先ではアングル寄りになり、目的テーマが前に出やすい")
                break
    score += reloc_pts

    # Transit: 目的天体が絡むソフトアスペクトがあれば加点（最大 +1）
    transit_pts = 0
    for hl in transit_highlights:
        body = str(hl.get("body") or "")
        aspect = str(hl.get("aspect") or "")
        if body in focus_planets and aspect in SOFT_ASPECTS:
            transit_pts = 1
            notes.append(f"滞在中に{body}の{aspect}があり、追い風になりやすい")
            break
    score += transit_pts

    total = max(1, min(maximum, score))
    if not notes:
        notes.append("目的に強く直結する配置は控えめ。素直に旅そのものを楽しむのが吉")

    return {
        "total_score": total,
        "max_score": maximum,
        "score_label": _score_label(total, maximum),
        "notes": notes,
    }


def recommended_actions(purpose_key: str) -> list[str]:
    return list(PURPOSE_ACTIONS.get(purpose_key, ["自分のペースで旅を楽しむ"]))
