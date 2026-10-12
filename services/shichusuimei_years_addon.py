"""四柱推命 年運アドオン（FULL版購入者向け、指定した立春年からN年分の年運）。

FULL版の原本から出生情報と計算設定を引き継ぎ、同じエンジンで指定年から
annual_forecasts を計算する。ホロスコープのアドオンと同じく、発行物は
「元の FULL 版＋追加した年」をまとめた1つの鑑定データ（merge_years_into_full）。
注文の消込・保存は行わない（routes 側の責務）。
発行前に、計算し直した命式・大運の並びが元の FULL 版と一致することを確認し、
一致しない・大運が保留されている等の場合は ValueError で止める（消込前に止めるため）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from services.prompt_builder import ensure_shichusuimei_structure_guidance

# addon_type -> 年数。購入できるのは product_catalog に登録した種別だけ
# （2026-10-12 時点では 5年のみ。10年・20年は AI の読み取り確認後に登録する）。
YEARS_ADDON_TYPES = {
    "shichu_annual_5y_addon": 5,
    "shichu_annual_10y_addon": 10,
    "shichu_annual_20y_addon": 20,
}
YEARS_ADDON_LABELS = {
    "ja": "四柱推命：年運追加（{years}年）",
    "en": "Four Pillars annual add-on ({years} years)",
    "es": "Complemento anual de Cuatro Pilares ({years} años)",
    "de": "Vier-Säulen-Jahres-Add-on ({years} Jahre)",
}
# 出生年からこの年数先までを開始年として受け付ける（大運10期の範囲の目安）。
MAX_START_OFFSET_YEARS = 100

YEARS_ADDON_PROMPT = ensure_shichusuimei_structure_guidance("""あなたは四柱推命の鑑定者です。以下のYAMLは、四柱推命FULL版に後から追加する年運データです。

重要ルール:
- このYAML単体を命式全体として扱わないでください。先に読み込ませた四柱推命FULL版YAMLと一緒に使ってください。FULL版YAMLが無い場合は、解釈の前に貼り付けを依頼してください。
- systems.shichusuimei.normalized_data.annual_forecasts の各年（effective_year）が、このアドオンで追加された年です。included_years 以外の年を推測・再計算しないでください。
- reference の命式・大運の並びは、FULL版と一致することを発行時に確認済みです。値を変更しないでください。
- 生年月日から再計算しないでください。
- 各年は立春から翌年の立春までです。大運の切替年は daiun_contexts の overlap_start_approx / overlap_end_approx を参照し、正確な交運日時を断定しないでください。

以下のYAMLを読み込んで、FULL版のデータと組み合わせて、指定された年の流れを読んでください。
""")


class YearsAddonError(ValueError):
    pass


def years_for_addon(addon_type: str) -> int:
    if addon_type not in YEARS_ADDON_TYPES:
        raise YearsAddonError("年運アドオンの種類が正しくありません。")
    return YEARS_ADDON_TYPES[addon_type]


def addon_label(addon_type: str, lang: str = "ja") -> str:
    return YEARS_ADDON_LABELS.get(lang, YEARS_ADDON_LABELS["ja"]).format(years=years_for_addon(addon_type))


def _shichu(doc: dict) -> dict:
    systems = doc.get("systems") if isinstance(doc, dict) else None
    shichu = systems.get("shichusuimei") if isinstance(systems, dict) else None
    return shichu if isinstance(shichu, dict) else {}


def full_base_info(doc: dict) -> dict[str, Any]:
    """FULL版の原本か確認し、収録済みの年と出生年を返す。"""
    shichu = _shichu(doc)
    if shichu.get("edition") != "full":
        raise YearsAddonError("年運アドオンは四柱推命FULL版のデータに追加する商品です。FULL版の鑑定ページURLまたはYAMLを指定してください。")
    nd = shichu.get("normalized_data") or {}
    daiun = nd.get("daiun") or {}
    if str(daiun.get("status") or "").startswith("undetermined_") and daiun.get("status") != "undetermined_gender":
        raise YearsAddonError("出生時刻が未確定で、生まれた日に節入りがあるため、大運と年運を確定できません。出生時刻が分かる場合はお問い合わせください。")
    items = (nd.get("annual_forecasts") or {}).get("items") or []
    included = sorted(int(i["effective_year"]) for i in items if isinstance(i, dict) and "effective_year" in i)
    birth_year = int(str((doc.get("input") or {}).get("birth_date") or "0000")[:4])
    return {
        "included_years": included,
        "default_start_year": (included[-1] + 1) if included else None,
        "birth_year": birth_year,
    }


def _pillars(shichu: dict) -> dict[str, str]:
    pillars = (shichu.get("normalized_data") or {}).get("pillars") or {}
    return {k: (v.get("kanshi") if isinstance(v, dict) else v) for k, v in pillars.items()}


def _daiun_signature(shichu: dict) -> tuple:
    daiun = (shichu.get("normalized_data") or {}).get("daiun") or {}
    return (daiun.get("status"), daiun.get("direction"),
            tuple(str(i.get("kanshi")) for i in daiun.get("items") or []))


def build_years_addon(
    base_doc: dict,
    addon_type: str,
    start_year: int,
    *,
    engine_args: dict[str, Any],
) -> tuple[str, str, dict]:
    """FULL版原本と開始年から年運アドオンの YAML・指示文・文書を作る。

    engine_args は build_product_yaml に渡す出生情報と計算設定（routes で原本から復元したもの）。
    """
    from services.shichusuimei_calc import _lichun_utc_for_year
    from services.yaml_exporter import build_product_yaml, validate_yaml_option_section_consistency

    years = years_for_addon(addon_type)
    info = full_base_info(base_doc)
    if type(start_year) is not int:
        raise YearsAddonError("開始年は西暦の整数で指定してください。")
    if not info["birth_year"] <= start_year <= info["birth_year"] + MAX_START_OFFSET_YEARS:
        raise YearsAddonError(f"開始年は {info['birth_year']}年〜{info['birth_year'] + MAX_START_OFFSET_YEARS}年の範囲で指定してください。")
    overlap = sorted(set(range(start_year, start_year + years)) & set(info["included_years"]))
    if overlap:
        raise YearsAddonError(
            f"{overlap[0]}年〜{overlap[-1]}年はすでにお手元のデータに入っています。"
            f"入っていない年から始まるように開始年を選んでください（例：{info['default_start_year']}年）。"
        )

    tz_name = str(engine_args.get("tz_name") or "Asia/Tokyo")
    # 開始年の立春の1日後を基準日にし、annual_forecasts を開始年の立春年から始める。
    as_of = _lichun_utc_for_year(start_year, tz_name).astimezone(ZoneInfo(tz_name)) + timedelta(days=1)
    _text, _prompt, full_doc = build_product_yaml(
        **engine_args,
        include_shichusuimei=True,
        include_asteroids=False,
        include_transit=False,
        data_role="addon",
        shichusuimei_edition="full",
        shichusuimei_as_of=as_of,
        shichusuimei_annual_years=years,
    )
    base_shichu = _shichu(base_doc)
    new_shichu = _shichu(full_doc)
    # 元の FULL 版と同じ命式・大運であることを確認してから発行する（不一致なら消込前に停止）。
    if _pillars(base_shichu) != _pillars(new_shichu) or _daiun_signature(base_shichu) != _daiun_signature(new_shichu):
        raise YearsAddonError("保存済みのFULL版と計算結果が一致しないため、年運アドオンを作成できません。お手数ですがお問い合わせください。")
    nd = new_shichu.get("normalized_data") or {}
    forecasts = nd.get("annual_forecasts") or {}
    included = [int(i["effective_year"]) for i in forecasts.get("items") or []]
    if included != list(range(start_year, start_year + years)):
        raise YearsAddonError("指定した開始年から年運を作成できませんでした。開始年を確認してください。")
    daiun = nd.get("daiun") or {}
    assumptions = (new_shichu.get("input") or {}).get("assumptions") or {}
    base_meta = base_doc.get("meta") or {}

    doc = {
        "version": "nanami-products-yaml-addon-v1",
        "meta": {
            "schema_version": "1.0",
            "product_type": addon_type,
            "data_role": "addon",
            "addon_type": "shichu_annual_years",
            "generated_at": full_doc.get("generated_at"),
        },
        "base": {
            "target_product_type": "shichu_full",
            "target_system": "shichusuimei",
            "base_chart_id": base_meta.get("chart_id"),
            "base_engine_version": base_shichu.get("engine_version"),
            "full_included_years": info["included_years"],
            "compatible_with": ["shichu_full"],
        },
        "product": {
            "type": addon_type,
            "label": addon_label(addon_type),
            "options": {"addon": True, "western_natal": False, "asteroids": False, "transit": False,
                        "shichusuimei": True, "annual_years": years},
        },
        "generated_at": full_doc.get("generated_at"),
        "calculation": {
            "engine": "nanami-products shichusuimei",
            "engine_version": new_shichu.get("engine_version"),
            "timezone": tz_name,
            "day_boundary_rule": assumptions.get("day_boundary_rule"),
            "year_boundary_rule": assumptions.get("year_boundary_rule"),
            "daiun_start_mode": assumptions.get("daiun_start_mode"),
        },
        "birth_time": full_doc.get("birth_time") or {},
        "interpretation_flags": full_doc.get("interpretation_flags") or {},
        "input": full_doc.get("input") or {},
        "usage_note": {
            "for_ai": "これは追加部品データです。四柱推命FULL版YAMLと一緒にAIへ貼り付けて使ってください。",
            "included_years": f"{start_year}年〜{start_year + years - 1}年（各年は立春から翌年の立春まで）",
            "not_included": "命式の構造分析・神殺・五行集計などの基本データは含みません。FULL版YAMLを参照してください。",
        },
        "systems": {
            "western": None,
            "shichusuimei": {
                "normalized_data": {"annual_forecasts": forecasts},
                "reference": {
                    "day_master": new_shichu.get("day_master"),
                    "pillars": _pillars(new_shichu),
                    "daiun_status": daiun.get("status"),
                    "daiun_direction": daiun.get("direction"),
                    "daiun_summary": [
                        {k: item.get(k) for k in ("index", "kanshi", "age_from", "age_to", "approx_start_at", "approx_end_at")}
                        for item in daiun.get("items") or []
                    ],
                    "included_years": included,
                    "note": "命式・大運は FULL版と一致することを発行時に確認済み。年運の解釈に必要な最小参照です。",
                },
            },
        },
    }
    validate_yaml_option_section_consistency(doc)

    class _PlainDumper(yaml.SafeDumper):
        def ignore_aliases(self, data):  # AIが読むため、YAMLアンカー（&id/*id）を使わない
            return True

    yaml_text = yaml.dump(doc, Dumper=_PlainDumper, allow_unicode=True, sort_keys=False, width=120)
    return yaml_text, YEARS_ADDON_PROMPT.strip() + "\n", doc


def merge_years_into_full(base_doc: dict, addon_doc: dict, addon_type: str) -> dict:
    """元の FULL 版のコピーに、アドオンで計算した年を加えた鑑定データを返す（元の文書は変更しない）。

    ホロスコープのアドオンと同じく、発行後は1つの鑑定ページで命式・大運・全収録年を扱い、
    年選択画面から読む年を選べるようにする。命式・大運は build_years_addon で一致確認済み。
    """
    from copy import deepcopy

    chart_doc = deepcopy(base_doc)
    nd = chart_doc["systems"]["shichusuimei"]["normalized_data"]
    forecasts = nd.setdefault("annual_forecasts", {})
    added = (addon_doc["systems"]["shichusuimei"]["normalized_data"]["annual_forecasts"]).get("items") or []
    added_years = [item["effective_year"] for item in added]
    items = list(forecasts.get("items") or []) + deepcopy(added)
    items.sort(key=lambda item: item["effective_year"])
    if len({item["effective_year"] for item in items}) != len(items):
        raise YearsAddonError("同じ年が重複するため、年運を追加できません。")
    forecasts["items"] = items
    forecasts["start_effective_year"] = items[0]["effective_year"]
    forecasts["years"] = len(items)
    forecasts.setdefault("addon_periods", []).append({
        "addon_type": addon_type,
        "years": added_years,
        "generated_at": addon_doc.get("generated_at"),
    })
    meta = chart_doc.setdefault("meta", {})
    meta.setdefault("addons", []).append({
        "addon_type": addon_type,
        "years": added_years,
        "engine_version": (addon_doc.get("calculation") or {}).get("engine_version"),
        "generated_at": addon_doc.get("generated_at"),
    })
    options = chart_doc.setdefault("product", {}).setdefault("options", {})
    options["annual_addon_years"] = sorted(set(options.get("annual_addon_years") or []) | set(added_years))
    return chart_doc
