"""Local phase-one prototype. No HTTP routes, purchases, registrations or writes."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from urllib.parse import urlparse

import yaml

from services.shichusuimei_annual_report import build_annual_fortune_report, validate_selected_year

PROTOTYPE_PRODUCT_TYPE = "shichu_annual_details_addon_prototype"
AI_USAGE = [
    "同じ基本命式のFull YAMLと併用し、YAMLの計算結果を優先する。生年月日から再計算しない。",
    "systems.shichusuimei.annual_details.yearsから指定された年を正確に選ぶ。複数年比較では各年の根拠を示す。",
    "対象期間外の流年データは推測で生成しない。必要な場合は追加期間のデータを求める。",
    "出生の基本命式・大運・流年を区別する。共有の大運はdaiun_refでcatalogを参照する。",
    "刑冲合害・空亡だけで吉凶を一律に決めず、合化や五行の強弱を個数から確定しない。",
    "好ましい傾向に加え、注意点・リスク・複数の解釈を説明する。計算事実と占術的解釈を区別する。",
    "交運日時は概算。年途中の複数大運と適用期間を参照し、境界付近を確定値にしない。",
]


def load_prototype_base(*, base_yaml: str = "", previous_chart_url: str = "", allowed_hosts: set[str] | None = None) -> dict:
    """Reuse existing addon parsing, local DB lookup, expiry and type checks.

    Local caller only. Passing a URL performs the same read as the existing
    addon loader. It never fetches a remote URL. Tests mock the DB lookup.
    """
    from routes import _load_addon_base_yaml, _load_addon_base_doc_from_previous_chart_url, _validate_addon_base_doc

    if base_yaml.strip():  # Same YAML-first precedence as the existing form.
        doc = _load_addon_base_yaml(base_yaml)
    elif previous_chart_url.strip():
        parsed = urlparse(previous_chart_url.strip())
        hosts = allowed_hosts or {"chart.nanami-astro.com"}
        if parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None, 443, 80):
            raise ValueError("既存商品の発行URLを入力してください。許可されたホストのURLのみ利用できます。")
        doc = _load_addon_base_doc_from_previous_chart_url(previous_chart_url, "shichu_fortune_cycles_addon")
    else:
        raise ValueError("基本鑑定のURLまたはYAMLを入力してください。")
    _validate_addon_base_doc(doc, "shichu_fortune_cycles_addon")
    # Full-chart structure is mandatory; fortune-only addon YAML is not a base.
    data = doc["systems"]["shichusuimei"]["normalized_data"]
    pillars = data.get("pillars") or {}
    if not isinstance(pillars, dict) or not {"year", "month", "day"} <= pillars.keys():
        raise ValueError("出生四柱を含む四柱推命の基本鑑定Full YAMLが必要です。")
    return doc


def _base_reference(base_doc: dict, annual: dict) -> dict:
    chart_id = (base_doc.get("meta") or {}).get("chart_id")
    reference = {"chart_id": chart_id, "full_yaml_required": True, **annual["natal_reference"]}
    if not chart_id:
        # Hash calculated structure only. It is a matching aid, not proof of
        # identity/purchase, and never a hash of name/address/date of birth.
        data = base_doc["systems"]["shichusuimei"].get("normalized_data") or {}
        signature = {"pillars": annual["natal_reference"]["pillars"],
                     "natal_time_basis": annual["calculation"]["natal_time_basis"],
                     "daiun_start_age": (data.get("daiun") or {}).get("start_age"),
                     "daiun_direction": (data.get("daiun") or {}).get("direction")}
        reference["structural_fingerprint"] = hashlib.sha256(json.dumps(signature, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        reference["fingerprint_method"] = "sha256_calculated_pillars_time_basis_daiun_start_age_direction_v1"
        reference["fingerprint_note"] = "計算構造の照合補助。本人確認・購入証明ではなく、同一構造を持つ別人の区別はできない。"
    return reference


def build_period_prototype(base_doc: dict, start_year: int, years: int, *, layout: str = "shared") -> dict:
    """Build candidate 5/10/20 year packages; durations are experiment labels."""
    if type(years) is not int or years not in (5, 10, 20):
        raise ValueError("試作の比較期間は5・10・20年です。販売プランは未確定です。")
    if layout not in {"shared", "expanded"}:
        raise ValueError("未対応の試作レイアウトです。")
    validate_selected_year(start_year)
    validate_selected_year(start_year + years - 1)
    reports = [build_annual_fortune_report(base_doc, year)["annual_fortune_report"] for year in range(start_year, start_year + years)]
    first = reports[0]
    period = {"start_effective_year": start_year, "end_effective_year": start_year + years - 1, "years": years,
              "period_start": first["annual"]["period_start"], "period_end": reports[-1]["annual"]["period_end"],
              "period_end_exclusive": True}
    details = {"period": period, "base_reference": _base_reference(base_doc, first),
               "calculation": first["calculation"], "interpretation_flags": first["interpretation_flags"],
               "ai_usage": AI_USAGE, "layout": layout}
    if layout == "expanded":
        details["years"] = reports
    else:
        details["shared"] = {"kubo_empty_branches": first["kubo"]["empty_branches"],
                             "kubo_natal_hits": first["kubo"]["natal_hits"], "kubo_method": first["kubo"]["method"],
                             "five_elements_natal": first["five_elements"]["natal"],
                             "five_elements_natal_reference_only": first["five_elements"]["natal_reference_only"],
                             "five_elements_included_natal_reference": first["five_elements"]["included_natal_reference"],
                             "five_elements_method": first["five_elements"]["method"], "five_elements_note": first["five_elements"]["note"],
                             "daiun_note": first["daiun"]["note"]}
        catalog, annual_items = {}, []
        for report in reports:
            ref_for = {c["index"]: f"daiun_{c['index']}" for c in report["daiun"]["contexts"]}
            contexts = []
            for c in report["daiun"]["contexts"]:
                ref = ref_for[c["index"]]
                context_keys = ("overlap_start_approx", "overlap_end_approx", "boundary_in_selected_year")
                material = {k: v for k, v in c.items() if k not in context_keys}
                material["natal_interactions"] = [r for r in report["interactions"]["natal_daiun"] if r["daiun_index"] == c["index"]]
                material["five_elements"] = next(x for x in report["five_elements"]["daiun"] if x["daiun_index"] == c["index"])
                material["kubo_hit"] = next(x["hit"] for x in report["kubo"]["daiun_hits"] if x["daiun_index"] == c["index"])
                if ref in catalog and catalog[ref] != material:
                    raise ValueError("共有大運の計算結果が年によって一致しません。")
                catalog[ref] = material
                contexts.append({"daiun_ref": ref, **{k: c[k] for k in context_keys}})
            annual_items.append({"selected_year": report["selected_year"], "annual": report["annual"],
                                 "daiun": {"status": report["daiun"]["status"], "contexts": contexts,
                                           "boundary_in_selected_year": report["daiun"]["boundary_in_selected_year"],
                                           "uncovered_before_first_daiun": report["daiun"]["uncovered_before_first_daiun"]},
                                 "interactions": {"natal_annual": report["interactions"]["natal_annual"],
                                                  "natal_daiun_refs": list(ref_for.values()),
                                                  "daiun_annual": report["interactions"]["daiun_annual"],
                                                  "combined": report["interactions"]["combined"]},
                                 "kubo_annual_hit": report["kubo"]["annual_hit"],
                                 "five_elements_annual": report["five_elements"]["annual"],
                                 "five_elements_combined_reference": report["five_elements"]["combined_reference"]})
        details["daiun_catalog"] = catalog
        details["years"] = annual_items
    return {"version": "nanami-shichu-annual-prototype-v1", "meta": {"schema_version": "0.1-prototype",
            "product_type": PROTOTYPE_PRODUCT_TYPE, "data_role": "addon", "production_ready": False},
            "product": {"type": PROTOTYPE_PRODUCT_TYPE, "price": None, "sales_duration_decided": False},
            "systems": {"shichusuimei": {"annual_details": details}}}


def expand_shared_year(prototype: dict, selected_year: int) -> dict:
    """Resolve explicit shared references for verification and future year export."""
    details = prototype["systems"]["shichusuimei"]["annual_details"]
    item = next((item for item in details["years"] if item["selected_year"] == selected_year), None)
    if item is None:
        raise ValueError("対象期間に含まれない年です。")
    if details["layout"] == "expanded":
        return deepcopy(item)
    shared = details["shared"]
    contexts, natal_daiun, daiun_counts, daiun_hits = [], [], [], []
    for context in item["daiun"]["contexts"]:
        saved = deepcopy(details["daiun_catalog"][context["daiun_ref"]])
        natal_daiun.extend(saved.pop("natal_interactions"))
        daiun_counts.append(saved.pop("five_elements"))
        daiun_hits.append({"daiun_index": saved["index"], "hit": saved.pop("kubo_hit")})
        contexts.append({**saved, **{k: v for k, v in context.items() if k != "daiun_ref"}})
    return {"schema_version": "1.0", "base_chart_id": details["base_reference"]["chart_id"],
            "selected_year": selected_year, "calculation": deepcopy(details["calculation"]),
            "base_chart_usage": {"full_yaml_required": True,
                                 "note": "同じbase_chart_idのFull YAMLと併用。出生四柱は照合用。格局・用神などは基礎命式を参照。"},
            "natal_reference": {k: deepcopy(details["base_reference"][k]) for k in ("day_master", "pillars")},
            "annual": deepcopy(item["annual"]), "daiun": {**deepcopy(item["daiun"]), "contexts": contexts, "note": shared["daiun_note"]},
            "interactions": {"natal_annual": deepcopy(item["interactions"]["natal_annual"]), "natal_daiun": natal_daiun,
                             "daiun_annual": deepcopy(item["interactions"]["daiun_annual"]), "combined": deepcopy(item["interactions"]["combined"])},
            "kubo": {"empty_branches": deepcopy(shared["kubo_empty_branches"]), "natal_hits": deepcopy(shared["kubo_natal_hits"]),
                     "method": shared["kubo_method"], "annual_hit": item["kubo_annual_hit"], "daiun_hits": daiun_hits},
            "five_elements": {"natal": deepcopy(shared["five_elements_natal"]), "natal_reference_only": shared["five_elements_natal_reference_only"],
                              "included_natal_reference": deepcopy(shared["five_elements_included_natal_reference"]),
                              "annual": deepcopy(item["five_elements_annual"]), "daiun": daiun_counts,
                              "combined_reference": deepcopy(item["five_elements_combined_reference"]),
                              "method": shared["five_elements_method"], "note": shared["five_elements_note"]},
            "interpretation_flags": deepcopy(details["interpretation_flags"])}


def dump_period_prototype(doc: dict) -> str:
    # No automatic YAML anchors: explicit named references are easier for AI and
    # can be resolved without relying on a parser's alias interpretation.
    class NoAliasDumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True
    return yaml.dump(doc, Dumper=NoAliasDumper, allow_unicode=True, sort_keys=False, width=120)
