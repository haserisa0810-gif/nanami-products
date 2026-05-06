from __future__ import annotations

from typing import Any


def _tag(
    tag_id: str,
    label: str,
    category: str,
    *,
    strength: int = 0,
    basis: list[str] | None = None,
    writing_hint: str = "",
) -> dict[str, Any]:
    return {
        "id": tag_id,
        "label": label,
        "strength": int(strength),
        "category": category,
        "basis": basis or [],
        "writing_hint": writing_hint,
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _body_aspects(aspects: list[dict[str, Any]], body_names: set[str], kinds: set[str] | None = None) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in aspects:
        if not isinstance(item, dict):
            continue
        b1 = item.get("body1")
        b2 = item.get("body2")
        if b1 not in body_names and b2 not in body_names:
            continue
        if kinds and item.get("aspect") not in kinds:
            continue
        hits.append(item)
    return hits


def _format_aspect_basis(items: list[dict[str, Any]], limit: int = 4) -> list[str]:
    basis: list[str] = []
    for item in items[:limit]:
        basis.append(f"{item.get('body1')} {item.get('aspect')} {item.get('body2')} orb={item.get('orb')}")
    return basis


def western_tags(western: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not western:
        return []

    natal = western.get("natal", {}) if isinstance(western, dict) else {}
    summary = natal.get("summary", {}) if isinstance(natal, dict) else {}
    bodies = natal.get("bodies", {}) if isinstance(natal, dict) else {}
    houses = natal.get("houses", {}) if isinstance(natal, dict) else {}
    aspects = natal.get("aspects", []) if isinstance(natal, dict) else []

    element_counts = summary.get("elements", {}) if isinstance(summary, dict) else {}
    mode_counts = summary.get("modes", {}) if isinstance(summary, dict) else {}

    def dominant_basis(counts: dict[str, Any]) -> tuple[int, int, list[str]]:
        if not counts:
            return 0, 0, []
        ordered = sorted(((str(k), int(v)) for k, v in counts.items()), key=lambda kv: (-kv[1], kv[0]))
        if not ordered:
            return 0, 0, []
        top_key, top_value = ordered[0]
        bottom_key, bottom_value = sorted(((str(k), int(v)) for k, v in counts.items()), key=lambda kv: (kv[1], kv[0]))[0]
        return top_value, bottom_value, [f"top={top_key}:{top_value}", f"bottom={bottom_key}:{bottom_value}"]

    top_element, low_element, element_basis = dominant_basis(element_counts)
    top_mode, low_mode, mode_basis = dominant_basis(mode_counts)

    sun_moon_hits = _body_aspects(aspects, {"Sun", "Moon"}, {"conjunction", "square", "trine", "opposition"})
    saturn_hits = _body_aspects(aspects, {"Saturn"}, {"conjunction", "square", "opposition"})
    jupiter_hits = _body_aspects(aspects, {"Jupiter"}, {"conjunction", "sextile", "trine"})
    venus_hits = _body_aspects(aspects, {"Venus"}, {"conjunction", "sextile", "square", "trine", "opposition"})
    mercury_hits = _body_aspects(aspects, {"Mercury"}, {"conjunction", "sextile", "square", "trine", "opposition"})
    career_hits = [
        item for item in aspects
        if item.get("aspect") in {"conjunction", "sextile", "square", "trine", "opposition"}
        and any(name in {item.get("body1"), item.get("body2")} for name in {"Sun", "Jupiter", "Saturn", "Venus", "MC"})
    ]
    relationship_hits = [
        item for item in aspects
        if item.get("aspect") in {"conjunction", "sextile", "square", "trine", "opposition"}
        and any(name in {item.get("body1"), item.get("body2")} for name in {"Venus", "Moon", "Uranus", "Pluto", "ASC", "7th"})
    ]

    house10 = houses.get("10", {}) if isinstance(houses, dict) else {}
    house6 = houses.get("6", {}) if isinstance(houses, dict) else {}
    house7 = houses.get("7", {}) if isinstance(houses, dict) else {}
    house3 = houses.get("3", {}) if isinstance(houses, dict) else {}

    tags = [
        _tag(
            "elemental_bias",
            "五行相当の偏りに近い元素傾向",
            "structure",
            strength=2 if top_element >= 4 else 1 if top_element >= 3 else 0,
            basis=element_basis if element_basis else [],
            writing_hint="多い元素を強み、少ない元素を使い方の癖として読む",
        ),
        _tag(
            "mode_bias",
            "活動モードの偏り",
            "structure",
            strength=2 if top_mode >= 4 else 1 if top_mode >= 3 else 0,
            basis=mode_basis if mode_basis else [],
            writing_hint="動き方の速さ・粘り・変化の出方として読む",
        ),
        _tag(
            "sun_moon_axis",
            "自我と感情の軸",
            "structure",
            strength=min(3, len(sun_moon_hits)),
            basis=_format_aspect_basis(sun_moon_hits),
            writing_hint="表向きの意志と内側の反応の噛み合わせとして読む",
        ),
        _tag(
            "saturn_pressure",
            "責任・制限・継続課題",
            "timing",
            strength=min(3, len(saturn_hits)),
            basis=_format_aspect_basis(saturn_hits),
            writing_hint="無理に進めるより、整えながら続けるテーマとして読む",
        ),
        _tag(
            "jupiter_expansion",
            "拡大・学び・追い風",
            "timing",
            strength=min(3, len(jupiter_hits)),
            basis=_format_aspect_basis(jupiter_hits),
            writing_hint="広げる対象を絞って使う",
        ),
        _tag(
            "relationship_activation",
            "対人テーマの活性化",
            "relationship",
            strength=min(3, len(relationship_hits) + len(venus_hits)),
            basis=_format_aspect_basis((relationship_hits + venus_hits)[:6]),
            writing_hint="相手との距離感、反応、関係の動き方を読む",
        ),
        _tag(
            "career_visibility",
            "仕事・役割の可視化",
            "career",
            strength=min(3, len(career_hits) + (1 if house10.get("absolute_longitude") is not None else 0)),
            basis=(
                _format_aspect_basis(career_hits, 5)
                + ([f"house10={house10.get('sign_ja') or house10.get('sign')}"] if house10.get("absolute_longitude") is not None else [])
                + ([f"house6={house6.get('sign_ja') or house6.get('sign')}"] if house6.get("absolute_longitude") is not None else [])
            ),
            writing_hint="社会的な見え方、仕事の出し方、評価されやすい場面として読む",
        ),
        _tag(
            "communication_focus",
            "言葉・理解・伝達の集中",
            "expression",
            strength=min(3, len(mercury_hits) + (1 if house3.get("absolute_longitude") is not None else 0)),
            basis=_format_aspect_basis(mercury_hits)
            + ([f"house3={house3.get('sign_ja') or house3.get('sign')}"] if house3.get("absolute_longitude") is not None else []),
            writing_hint="伝え方、書き方、説明の癖として読む",
        ),
    ]

    return tags


def shichu_tags(shichu: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not shichu:
        return []

    normalized = shichu.get("normalized_data", {}) if isinstance(shichu, dict) else {}
    structure = shichu.get("structure_report", {}) if isinstance(shichu, dict) else {}
    five = normalized.get("five_elements", {}) if isinstance(normalized, dict) else {}
    ten = normalized.get("ten_gods", {}) if isinstance(normalized, dict) else {}
    daiun = normalized.get("daiun", {}) if isinstance(normalized, dict) else {}
    annual = normalized.get("annual_fortune", {}) if isinstance(normalized, dict) else {}
    shinsatsu = normalized.get("shinsatsu", {}) if isinstance(normalized, dict) else {}

    visible = five.get("visible", {}) if isinstance(five, dict) else {}
    hidden = five.get("with_hidden_stems", {}) if isinstance(five, dict) else {}
    visible_counts = [int(v) for v in visible.values()] if isinstance(visible, dict) else []
    hidden_counts = [int(v) for v in hidden.values()] if isinstance(hidden, dict) else []

    score = structure.get("strength_index", {}).get("score") if isinstance(structure, dict) else None
    label = structure.get("strength_index", {}).get("label") if isinstance(structure, dict) else None
    month_context = structure.get("seasonal_context", {}) if isinstance(structure, dict) else {}

    def collect_ten_gods(targets: set[str]) -> list[str]:
        hits: list[str] = []
        pillars = ten.get("pillars", {}) if isinstance(ten, dict) else {}
        for pillar_name, pillar in pillars.items():
            god = pillar.get("ten_god") if isinstance(pillar, dict) else None
            if god in targets:
                hits.append(f"{pillar_name}:{god}")
        hidden_stems = ten.get("hidden_stems", {}) if isinstance(ten, dict) else {}
        for pillar_name, items in hidden_stems.items():
            for item in _as_list(items):
                if not isinstance(item, dict):
                    continue
                god = item.get("ten_god")
                if god in targets:
                    stem = item.get("stem")
                    hits.append(f"{pillar_name}:{stem}:{god}")
        return hits

    wealth_hits = collect_ten_gods({"偏財", "正財"})
    officer_hits = collect_ten_gods({"偏官", "正官"})
    resource_hits = collect_ten_gods({"偏印", "印綬"})
    output_hits = collect_ten_gods({"食神", "傷官"})

    current_daiun = annual.get("current_daiun") if isinstance(annual, dict) else None
    current_relations = annual.get("relations", {}) if isinstance(annual, dict) else {}
    branch_relations = _as_list(current_relations.get("branch_relations")) if isinstance(current_relations, dict) else []
    stem_relations = _as_list(current_relations.get("stem_relations")) if isinstance(current_relations, dict) else []
    triads = _as_list(current_relations.get("triads_with_natal_and_daiun")) if isinstance(current_relations, dict) else []
    punishments = _as_list(current_relations.get("three_punishments_with_natal_and_daiun")) if isinstance(current_relations, dict) else []

    shinsatsu_hits = _as_list(shinsatsu.get("hit_stars")) if isinstance(shinsatsu, dict) else []
    shinsatsu_names = [str(item.get("name_ja") or item.get("name")) for item in shinsatsu_hits if isinstance(item, dict)]

    strongest_god = None
    strongest_count = 0
    for label_name, hits in (
        ("財星", wealth_hits),
        ("官星", officer_hits),
        ("印星", resource_hits),
        ("食傷", output_hits),
    ):
        if len(hits) > strongest_count:
            strongest_count = len(hits)
            strongest_god = label_name

    tags = [
        _tag(
            "strength_index",
            "身強身弱の目安",
            "structure",
            strength=3 if isinstance(score, int) and score >= 70 else 2 if isinstance(score, int) and score <= 40 else 1 if isinstance(score, int) else 0,
            basis=[f"score={score}", f"label={label}"] if score is not None else [],
            writing_hint="断定ではなく、使いやすさの方向として読む",
        ),
        _tag(
            "five_element_imbalance",
            "五行の偏り",
            "structure",
            strength=2 if len(visible_counts) and max(visible_counts) - min(visible_counts) >= 3 else 1 if len(visible_counts) and max(visible_counts) - min(visible_counts) >= 2 else 0,
            basis=[f"visible={visible}", f"hidden={hidden}"] if visible_counts else [],
            writing_hint="不足を埋めるより、偏りをどう使うかとして読む",
        ),
        _tag(
            "daiun_flow",
            "大運の流れ",
            "timing",
            strength=2 if current_daiun else 0,
            basis=(
                [f"direction={daiun.get('direction')}"]
                + ([f"start_age={daiun.get('start_age_text')}"] if isinstance(daiun, dict) and daiun.get("start_age_text") else [])
                + ([f"current={current_daiun.get('kanshi')}"] if isinstance(current_daiun, dict) and current_daiun.get("kanshi") else [])
            ) if current_daiun or daiun else [],
            writing_hint="今の10年運がどこに向いているかを読む",
        ),
        _tag(
            "annual_theme",
            "流年と今年のテーマ",
            "timing",
            strength=2 if annual else 0,
            basis=(
                [f"year={annual.get('year')}"]
                + ([f"effective_year={annual.get('effective_year')}"] if annual.get("effective_year") is not None else [])
                + ([f"ten_god={annual.get('ten_god_to_day_master')}"] if annual.get("ten_god_to_day_master") else [])
                + ([f"branch_relations={len(branch_relations)}"] if branch_relations else [])
            ) if annual else [],
            writing_hint="今年の動き方を、命式と大運に重ねて読む",
        ),
        _tag(
            "shinsatsu_support",
            "神殺の補助的な強み",
            "structure",
            strength=min(3, len(shinsatsu_names)),
            basis=shinsatsu_names,
            writing_hint="補助線として、使える場面だけを拾う",
        ),
        _tag(
            "career_pressure",
            "仕事・責任の圧力",
            "career",
            strength=min(3, len(officer_hits) + len(branch_relations) + len(punishments)),
            basis=_format_aspect_basis([]) + [f"官星={len(officer_hits)}", f"branch_relations={len(branch_relations)}", f"punishments={len(punishments)}"],
            writing_hint="負荷がかかるなら、役割の持ち方を調整する",
        ),
        _tag(
            "wealth_opportunity",
            "収入・交換・受け取り",
            "career",
            strength=min(3, len(wealth_hits)),
            basis=wealth_hits,
            writing_hint="受け取る、売る、交換するテーマとして読む",
        ),
        _tag(
            "expression_drive",
            "表現・発信・制作",
            "expression",
            strength=min(3, len(output_hits)),
            basis=output_hits,
            writing_hint="言葉、制作、見せ方の出方を読む",
        ),
        _tag(
            "support_resource",
            "学び・回復・蓄積",
            "structure",
            strength=min(3, len(resource_hits)),
            basis=resource_hits,
            writing_hint="蓄える力、整える力として読む",
        ),
        _tag(
            "seasonal_context",
            "月令との噛み合わせ",
            "structure",
            strength=1 if isinstance(month_context, dict) and month_context.get("relation_to_day_master") else 0,
            basis=[f"month_branch={month_context.get('month_branch')}", f"relation={month_context.get('relation_to_day_master')}"] if month_context else [],
            writing_hint="季節感が日干にどう働くかを読む",
        ),
        _tag(
            "strongest_god",
            "目立つ十神",
            "structure",
            strength=strongest_count if strongest_god else 0,
            basis=[f"strongest={strongest_god}", f"count={strongest_count}"] if strongest_god else [],
            writing_hint="今の柱になっている十神を読む",
        ),
    ]

    return tags


def transit_tags(transit: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not transit:
        return []

    daily = transit.get("daily", []) if isinstance(transit, dict) else []
    day_count = len(daily)
    tight_hits: list[dict[str, Any]] = []
    moon_hits: list[dict[str, Any]] = []
    jupiter_hits: list[dict[str, Any]] = []
    saturn_hits: list[dict[str, Any]] = []
    pressure_days = 0

    for day in daily:
        if not isinstance(day, dict):
            continue
        natal_aspects = _as_list(day.get("natal_aspects"))
        day_tight = False
        for aspect in natal_aspects:
            if not isinstance(aspect, dict):
                continue
            orb = aspect.get("orb")
            body = aspect.get("transit_body")
            kind = aspect.get("aspect")
            if orb is None:
                continue
            orb_f = float(orb)
            if orb_f <= 1.0:
                tight_hits.append(aspect)
                day_tight = True
            if body == "Moon":
                moon_hits.append(aspect)
            if body == "Jupiter" and kind in {"conjunction", "sextile", "trine"}:
                jupiter_hits.append(aspect)
            if body == "Saturn" and kind in {"conjunction", "square", "opposition"}:
                saturn_hits.append(aspect)
                day_tight = True
        if day_tight:
            pressure_days += 1

    top_tight = sorted(tight_hits, key=lambda x: (float(x.get("orb", 99)), str(x.get("transit_body")), str(x.get("natal_body"))))[:4]
    moon_timepoints_total = sum(len(_as_list(day.get("moon_timepoints"))) for day in daily if isinstance(day, dict))

    tags = [
        _tag(
            "timing_activation",
            "タイミングの活性化",
            "timing",
            strength=2 if tight_hits else 0,
            basis=_format_aspect_basis(top_tight),
            writing_hint="今すぐ動くか、少し待つかの判断材料として読む",
        ),
        _tag(
            "pressure_period",
            "圧力がかかりやすい",
            "timing",
            strength=min(3, len(saturn_hits)),
            basis=_format_aspect_basis(saturn_hits),
            writing_hint="負荷のかけ方を調整する",
        ),
        _tag(
            "change_window",
            "変化の入口",
            "timing",
            strength=2 if pressure_days >= 2 or len(tight_hits) >= 3 else 0,
            basis=[f"pressure_days={pressure_days}", f"tight_aspects={len(tight_hits)}", f"days={day_count}"] if tight_hits else [],
            writing_hint="切り替えや見直しの入口として読む",
        ),
        _tag(
            "emotional_wave",
            "感情の波",
            "timing",
            strength=2 if moon_hits or moon_timepoints_total else 0,
            basis=[f"moon_aspects={len(moon_hits)}", f"moon_timepoints={moon_timepoints_total}"] if (moon_hits or moon_timepoints_total) else [],
            writing_hint="朝昼夜の使い分けに落とし込む",
        ),
        _tag(
            "expansion_window",
            "広がりやすい流れ",
            "timing",
            strength=min(3, len(jupiter_hits)),
            basis=_format_aspect_basis(jupiter_hits),
            writing_hint="広げる対象を絞って使う",
        ),
        _tag(
            "short_term_focus",
            "直近数日の焦点",
            "timing",
            strength=2 if day_count <= 5 and tight_hits else 0,
            basis=[f"day_count={day_count}", f"tight_aspects={len(tight_hits)}"] if tight_hits else [],
            writing_hint="数日単位の切り替え点として読む",
        ),
    ]
    return tags


def integration_tags(western: dict[str, Any] | None, shichu: dict[str, Any] | None, transit: dict[str, Any] | None) -> list[dict[str, Any]]:
    western_list = western_tags(western)
    shichu_list = shichu_tags(shichu)
    transit_list = transit_tags(transit)

    western_active = [tag for tag in western_list if tag.get("strength", 0) > 0]
    shichu_active = [tag for tag in shichu_list if tag.get("strength", 0) > 0]
    transit_active = [tag for tag in transit_list if tag.get("strength", 0) > 0]

    western_ids = {tag["id"] for tag in western_active}
    shichu_ids = {tag["id"] for tag in shichu_active}
    transit_ids = {tag["id"] for tag in transit_active}
    western_cats = {tag["category"] for tag in western_active}
    shichu_cats = {tag["category"] for tag in shichu_active}
    transit_cats = {tag["category"] for tag in transit_active}

    return [
        _tag(
            "structure_alignment",
            "構造の噛み合い",
            "integration",
            strength=2 if western_active and shichu_active else 0,
            basis=[
                f"western={','.join(sorted(western_cats))}" if western_active else "western=none",
                f"shichu={','.join(sorted(shichu_cats))}" if shichu_active else "shichu=none",
            ],
            writing_hint="二つの体系が同じ方向を指しているかを読む",
        ),
        _tag(
            "timing_activation_of_core_theme",
            "主要テーマの動き出し",
            "integration",
            strength=2 if transit_active and (western_active or shichu_active) else 0,
            basis=[
                f"transit={','.join(sorted(transit_cats))}" if transit_active else "transit=none",
                f"western_or_shichu={','.join(sorted((western_cats | shichu_cats)))}" if (western_active or shichu_active) else "western_or_shichu=none",
            ],
            writing_hint="今の流れが核テーマを押しているかを見る",
        ),
        _tag(
            "western_shichu_double_emphasis",
            "西洋・四柱の二重強調",
            "integration",
            strength=2 if western_active and shichu_active and (western_cats & shichu_cats) else 1 if western_active and shichu_active else 0,
            basis=([f"shared_categories={','.join(sorted(western_cats & shichu_cats))}"] if (western_cats & shichu_cats) else [f"western_tags={len(western_ids)}", f"shichu_tags={len(shichu_ids)}"] if western_active and shichu_active else []),
            writing_hint="同じ論点が二系統で重なるかを確認する",
        ),
        _tag(
            "risk_overlap",
            "負荷の重なり",
            "integration",
            strength=2 if ("timing" in transit_cats and "career" in shichu_cats) or ("timing" in transit_cats and "timing" in shichu_cats) else 0,
            basis=[
                f"transit={','.join(sorted(transit_cats))}" if transit_active else "transit=none",
                f"shichu={','.join(sorted(shichu_cats))}" if shichu_active else "shichu=none",
            ],
            writing_hint="忙しさや負荷が重なる箇所を読む",
        ),
        _tag(
            "structure_conflict",
            "構造のズレ",
            "integration",
            strength=1 if western_active and transit_active and not shichu_active else 0,
            basis=[
                f"western={','.join(sorted(western_cats))}" if western_active else "western=none",
                f"transit={','.join(sorted(transit_cats))}" if transit_active else "transit=none",
            ] if western_active and transit_active and not shichu_active else [],
            writing_hint="どの体系のテーマが先に出ているかを読む",
        ),
    ]
