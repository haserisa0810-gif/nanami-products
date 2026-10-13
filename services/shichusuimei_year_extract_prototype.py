"""Offline selection from saved documents. No engine, DB or product wiring."""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
from datetime import datetime
import hashlib

import yaml

from services.shichusuimei_full_prototype import (
    load_saved_full, safe_load_fast, _typed_tree, walk, pointer, _get, _pointer_parts,
)
from services.shichusuimei_annual_prototype import expand_shared_year, PROTOTYPE_PRODUCT_TYPE

SP = ("systems", "shichusuimei")
FP = SP + ("normalized_data", "annual_forecasts")


class ExtractionError(ValueError):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def semantic_tree(value):
    """Only mapping key order is irrelevant; list order and scalar types remain."""
    if isinstance(value, dict):
        return ("mapping", tuple(sorted(((semantic_tree(k), semantic_tree(v)) for k,v in value.items()),key=repr)))
    if isinstance(value, list):
        return ("sequence", tuple(semantic_tree(v) for v in value))
    return (type(value).__name__, repr(value))


def dump_extraction(doc: dict) -> bytes:
    # libyaml があれば C 実装で書く（出力は Python 実装と同一であることを確認済み）。
    class PlainDumper(getattr(yaml, "CSafeDumper", yaml.SafeDumper)):
        def ignore_aliases(self, data):
            return True
    return yaml.dump(doc, Dumper=PlainDumper, allow_unicode=True, sort_keys=False, width=120).encode("utf-8")


def _requests(years):
    if not isinstance(years, (list, tuple)) or not years:
        raise ExtractionError("invalid_years", "空でない整数の年一覧が必要です。")
    if any(type(y) is not int for y in years):
        raise ExtractionError("invalid_years", "bool・文字列・小数は年指定として受け付けません。")
    if len(set(years)) != len(years):
        raise ExtractionError("duplicate_request", "要求年の重複は明示エラーにします。")
    return list(years)


def _index(items, key):
    if not isinstance(items, list):
        raise ExtractionError("invalid_source", "年別一覧が不正です。")
    result = {}
    for i, item in enumerate(items):
        year = item.get(key) if isinstance(item, dict) else None
        if type(year) is not int or year in result:
            raise ExtractionError("ambiguous_source_year", "保存年が不正または重複しています。")
        result[year] = (i, item)
    return result


def _base_index(doc):
    nd = doc["systems"]["shichusuimei"].get("normalized_data") or {}
    forecasts = nd.get("annual_forecasts")
    if forecasts is None:
        return {}, None
    if not isinstance(forecasts, dict):
        raise ExtractionError("invalid_source", "保存予測の構造が不正です。")
    return _index(forecasts.get("items"), "effective_year"), forecasts


def _require_all(requested, index):
    missing = [y for y in requested if y not in index]
    if missing:
        raise ExtractionError("years_not_saved", {"missing_years": missing, "available_years": list(index)})


def _common(doc, *, current):
    """Keep all other material, including debug and independent compatibility facts."""
    nd = doc["systems"]["shichusuimei"].get("normalized_data") or {}
    aliases, excluded = [], []
    def copy(value, path=()):
        if isinstance(value, dict):
            result = {}
            for k, v in value.items():
                child = path + (k,)
                if k == "annual_forecasts":
                    if child != FP and _typed_tree(v) != _typed_tree(nd.get(k)):
                        raise ExtractionError("independent_forecast_copy", pointer(child))
                    excluded.append({"source": pointer(child), "reason": "年別予測を別枠で選択。未選択年は出力しない"})
                    continue
                if k == "annual_fortune" and not current:
                    excluded.append({"source": pointer(child), "reason": "原本作成時の単一流年を選択年と取り違えないため除外"})
                    continue
                if path == SP + ("features",) and k in nd and _typed_tree(v) == _typed_tree(nd[k]):
                    aliases.append({"source": pointer(child), "destination": "/common" + pointer(SP + ("normalized_data", k)),
                                    "reason": "型・全値が一致する互換表示を共通の原本項目へ一本化"})
                    continue
                result[k] = copy(v, child)
            return result
        if isinstance(value, list):
            return [copy(v, path + (i,)) for i, v in enumerate(value)]
        return deepcopy(value)
    common = copy(doc)
    for p,v in walk(common):
        if isinstance(v,dict) and 'effective_year' in v and ('natal_analysis' in v or 'daiun_contexts' in v):
            raise ExtractionError("unclassified_forecast_copy", pointer(p))
    return common, aliases, excluded


def _base_source(raw, doc, index, forecasts):
    shichu = doc["systems"]["shichusuimei"]
    return {"sha256": hashlib.sha256(raw).hexdigest(), "chart_id": (doc.get("meta") or {}).get("chart_id"),
            "saved_generated_at": {"document": doc.get("generated_at"), "engine": shichu.get("generated_at")},
            "forecast_effective_years": list(index),
            "saved_forecast_metadata": {k: deepcopy(v) for k, v in (forecasts or {}).items() if k != "items"},
            "missing_original_sections": [k for k in ("annual_forecasts", "structural_analysis", "daiun")
                                          if k not in (shichu.get("normalized_data") or {})]}


def _leaf_mapping(doc, aliases, excluded, destinations):
    rows = []
    candidates = sorted(aliases + destinations, key=lambda x: len(x["source"]), reverse=True)
    for path, value in walk(doc):
        if isinstance(value, (list, dict)) and value:
            continue
        source = pointer(path)
        match = next((r for r in candidates if source == r["source"] or source.startswith(r["source"] + "/")), None)
        omitted = next((r for r in excluded if source == r["source"] or source.startswith(r["source"] + "/")), None)
        if match:
            destination = match["destination"] + source[len(match["source"]):]
            rows.append({"source": source, "destination": destination, "action": "retained", "reason": match.get("reason", "保存項目をそのまま選択")})
        elif omitted:
            rows.append({"source": source, "destination": None, "action": "excluded_from_this_output", "reason": omitted["reason"]})
        else:
            rows.append({"source": source, "destination": "/common" + source, "action": "retained", "reason": "共通の原局・大運・条件を保持"})
    return rows


def _finish(raw, doc, output, aliases, excluded, destinations):
    mapping = _leaf_mapping(doc, aliases, excluded, destinations)
    for r in mapping:
        if r["destination"]:
            a = _get(doc, tuple(_pointer_parts(r["source"], doc)))
            b = _get(output, tuple(_pointer_parts(r["destination"], output)))
            if _typed_tree(a) != _typed_tree(b):
                raise ExtractionError("retention_mismatch", r["source"])
    serialized = dump_extraction(output)
    if _typed_tree(safe_load_fast(serialized)) != _typed_tree(output):
        raise ExtractionError("serialization_mismatch", "通常の辞書・一覧の型・対象位置が変化しました。")
    return serialized, {"base_sha256": hashlib.sha256(raw).hexdigest(), "output_sha256": hashlib.sha256(serialized).hexdigest(),
                        "base_item_mapping": mapping, "retained_leaves_verified": sum(r["destination"] is not None for r in mapping),
                        "excluded_paths": excluded, "independent_compatibility_material_retained": True,
                        "engine_called": False, "external_ai_tested": False}


def extract_base(raw: bytes, years=None):
    doc = load_saved_full(raw)
    index, forecasts = _base_index(doc)
    basic = years is None
    requested = [] if basic else _requests(years)
    if not basic:
        _require_all(requested, index)
    validation_notes = [] if basic else [_validate_base_forecast(doc,index[y][1]) for y in requested]
    common, aliases, excluded = _common(doc, current=basic)
    output = {"local_year_extraction": {"schema_version": "0.1-local", "purpose": "basic_reading" if basic else "base_with_selected_years",
               "requested_years": requested, "included_years": requested, "source": _base_source(raw, doc, index, forecasts),
               "original_current_annual_policy": "原本作成時の流年としてcommon内に保持" if basic else "除外。指定年へ置換していない",
               "unselected_years": [y for y in index if y not in requested],
               "omission_meaning": "今回の送信範囲から除外。該当なし・未計算・別売への移動を意味しない",
               "interpretation_only_no_recalculation": True}, "common": common}
    output["local_year_extraction"]["saved_year_validation"] = validation_notes
    destinations = []
    destinations.extend({"source": pointer(FP + (k,)), "destination": f"/local_year_extraction/source/saved_forecast_metadata/{k}"}
                        for k in (forecasts or {}) if k != "items")
    if not basic:
        output["selected_base_forecasts"] = [deepcopy(index[y][1]) for y in requested]
        destinations = [{"source": pointer(FP + ("items", index[y][0])), "destination": f"/selected_base_forecasts/{j}"}
                        for j, y in enumerate(requested)]
    return _finish(raw, doc, output, aliases, excluded, destinations)


def _equal(a, b, fact):
    if semantic_tree(a) != semantic_tree(b):
        raise ExtractionError("source_conflict", fact)


def _validate_base_forecast(base, item):
    """Validate only facts saved in the source, with no inferred old fields."""
    missing = [k for k in ('period_start','period_end','natal_analysis','daiun_contexts') if k not in item]
    nd = base['systems']['shichusuimei'].get('normalized_data') or {}
    analysis = item.get('natal_analysis') or {}
    if 'pillar' in analysis:
        _equal(item['kanshi'],analysis['pillar'],'base forecast pillar')
    time_basis = ((nd.get('structural_analysis') or {}).get('methodology') or {}).get('time_basis')
    if time_basis and 'time_basis' in analysis:
        _equal(time_basis,analysis['time_basis'],'base forecast time_basis')
    contexts=item.get('daiun_contexts') or []
    if len({c['index'] for c in contexts})!=len(contexts):
        raise ExtractionError('ambiguous_daiun','基本予測の大運index重複')
    saved=(nd.get('daiun') or {}).get('items') or []
    by_index={c['index']:c for c in saved}
    for c in contexts:
        if c['index'] not in by_index:
            raise ExtractionError('source_conflict','基本予測の大運indexが共通大運にない')
        for k in ('kanshi','age_from','age_to'):
            if k in c and k in by_index[c['index']]:_equal(c[k],by_index[c['index']][k],f'base daiun {k}')
        if 'analysis' in c and 'concurrent_daiun' in c['analysis']:
            _equal(c['kanshi'],c['analysis']['concurrent_daiun'],'base concurrent daiun')
    if 'period_start' in item and 'period_end' in item:
        start,end=map(datetime.fromisoformat,(item['period_start'],item['period_end']))
        if not start.tzinfo or not end.tzinfo or not start<end or start.year!=item['effective_year'] or end.year!=item['effective_year']+1:
            raise ExtractionError('source_conflict','基本予測の保存年と年区間の矛盾')
        if saved and all('approx_start_at' in c and 'approx_end_at' in c for c in saved):
            overlapping=[c for c in saved if datetime.fromisoformat(c['approx_start_at'])<end and datetime.fromisoformat(c['approx_end_at'])>start]
            _equal([c['index'] for c in overlapping],[c['index'] for c in contexts],'base annual context coverage')
            for original,c in zip(overlapping,contexts):
                _equal(datetime.fromisoformat(c['overlap_start_approx']),max(start,datetime.fromisoformat(original['approx_start_at'])),'base overlap start')
                _equal(datetime.fromisoformat(c['overlap_end_approx']),min(end,datetime.fromisoformat(original['approx_end_at'])),'base overlap end')
        else:missing.append('saved_daiun_calendar_intervals')
    return {'effective_year':item['effective_year'],'missing_original_fields_not_filled':missing}


def _pair_facts(relations, pillars, annual, context=None, incoming='annual'):
    """Project saved two-party identities and rule data, preserving multiplicity."""
    facts=[]
    for r in relations:
        if 'left' not in r or 'right' not in r:continue
        participants=[]
        for side in ('left','right'):
            p=r[side];name=p['name']
            name=incoming if name=='luck' else 'daiun' if name=='current_daiun' else name
            if name=='annual':kanshi=annual
            elif name=='daiun':kanshi=context['kanshi']
            else:
                value=pillars[name];kanshi=value['kanshi'] if isinstance(value,dict) else value
            if 'kanshi' in p:_equal(p['kanshi'],kanshi,'relation participant kanshi')
            participants.append((name,context['index'] if name=='daiun' else None,kanshi))
        # detail is display-order dependent (卯午害 / 午卯害). Preserve it in
        # outputs; compare the saved rule and target set, not that spelling.
        facts.append((r['type'],r.get('element'),tuple(sorted(participants,key=str))))
    return Counter(facts)


def validate_annual_match(base, report):
    """Compare stored facts and explicit context IDs; never calculate missing facts."""
    shichu = base["systems"]["shichusuimei"]
    nd = shichu.get("normalized_data") or {}
    a = report["annual"]
    _equal(report["selected_year"], a["effective_year"], "selected_year/effective_year")
    start, end = map(datetime.fromisoformat, (a["period_start"], a["period_end"]))
    if not start.tzinfo or not end.tzinfo or not start < end or start.year != a["effective_year"] or end.year != a["effective_year"] + 1:
        raise ExtractionError("source_conflict", "保存年と立春年区間の年・順序が不一致")
    base_id = (base.get("meta") or {}).get("chart_id")
    if base_id and report.get("base_chart_id"):
        _equal(base_id, report["base_chart_id"], "chart_id")
    missing = []
    for name, kanshi in report["natal_reference"]["pillars"].items():
        value = (nd.get("pillars") or shichu.get("pillars") or {}).get(name)
        if value is None:
            raise ExtractionError("base_material_missing", f"pillars/{name}")
        _equal(value.get("kanshi") if isinstance(value, dict) else value, kanshi, f"pillars/{name}")
    day = (nd.get("pillars") or shichu.get("pillars"))["day"]
    _equal(day.get("stem") if isinstance(day, dict) else day[0], report["natal_reference"]["day_master"], "day_master")
    time_basis = ((nd.get("structural_analysis") or {}).get("methodology") or {}).get("time_basis")
    time_basis = time_basis or (shichu.get("input", {}).get("assumptions") or {}).get("structural_time_basis")
    if time_basis:
        _equal(time_basis, report["calculation"]["natal_time_basis"], "natal_time_basis")
        expected_names = {"year", "month", "day", "hour"} if time_basis == "four_pillars" else {"year", "month", "day"}
        _equal(sorted(expected_names), sorted(report["natal_reference"]["pillars"]), "natal_reference coverage")
    else:
        missing.append("natal_time_basis")
    if nd.get("five_elements") is not None:
        _equal(nd["five_elements"], report["five_elements"]["natal"], "five_elements/natal")
    if nd.get("kubo") is not None:
        _equal(nd["kubo"]["empty_branches"], report["kubo"]["empty_branches"], "kubo/empty_branches")
    saved_luck = {c["index"]: c for c in (nd.get("daiun") or {}).get("items", [])}
    contexts = report["daiun"]["contexts"]
    if len({c["index"] for c in contexts}) != len(contexts):
        raise ExtractionError("ambiguous_daiun", "年内大運のindexが重複")
    if saved_luck and all('approx_start_at' in c and 'approx_end_at' in c for c in saved_luck.values()):
        expected=[c['index'] for c in saved_luck.values() if datetime.fromisoformat(c['approx_start_at'])<end and datetime.fromisoformat(c['approx_end_at'])>start]
        _equal(expected,[c['index'] for c in contexts],'annual context coverage from saved periods')
    for key in ('natal_daiun','daiun_annual','combined'):
        for r in report['interactions'][key]:
            if r.get('daiun_index') not in {c['index'] for c in contexts}:
                raise ExtractionError('source_conflict','関係の大運indexが指定年の区間にない')
    for c in contexts:
        if c["index"] not in saved_luck:
            raise ExtractionError("base_material_missing", "大運indexが原本にない")
        for k in ("kanshi", "age_from", "age_to", "approx_start_at", "approx_end_at"):
            if k in saved_luck[c["index"]]:
                _equal(saved_luck[c["index"]][k], c[k], f"daiun/{c['index']}/{k}")
            else:
                missing.append(f"daiun/{c['index']}/{k}")
        lo, hi = map(datetime.fromisoformat, (c["overlap_start_approx"], c["overlap_end_approx"]))
        start, end = map(datetime.fromisoformat, (a["period_start"], a["period_end"]))
        if not start <= lo < hi <= end:
            raise ExtractionError("source_conflict", "年内大運の重複区間が年区間外")
        material=saved_luck[c['index']].get('structural_analysis') or {}
        rel=material.get('interactions_with_natal')
        if rel:
            before=_pair_facts(rel['branch_relations']+rel['stem_relations'],nd['pillars'],a['kanshi'],c,'daiun')
            after=_pair_facts([r for r in report['interactions']['natal_daiun'] if r['daiun_index']==c['index']],nd['pillars'],a['kanshi'],c)
            _equal(before,after,'natal_daiun two-party rules and targets')
    index, _ = _base_index(base)
    if a["effective_year"] in index:
        b = index[a["effective_year"]][1]
        for k in ("effective_year", "kanshi", "period_start", "period_end"):
            _equal(b[k], a[k], f"annual/{k}")
        _equal(b["natal_analysis"]["time_basis"], report["calculation"]["natal_time_basis"], "annual/time_basis")
        _equal(b["natal_analysis"]["stem_ten_god"], a["ten_god_to_day_master"], "annual/ten_god")
        fields = ("index", "kanshi", "age_from", "age_to", "overlap_start_approx", "overlap_end_approx")
        _equal([{k:c[k] for k in fields} for c in b["daiun_contexts"]], [{k:c[k] for k in fields} for c in contexts], "annual/daiun_contexts")
        _equal(b["daiun_boundary_in_window"], report["daiun"]["boundary_in_selected_year"], "annual/boundary_flag")
        rel=b['natal_analysis']['interactions_with_natal']
        _equal(_pair_facts(rel['branch_relations']+rel['stem_relations'],nd['pillars'],a['kanshi']),
               _pair_facts(report['interactions']['natal_annual'],nd['pillars'],a['kanshi']), 'natal_annual two-party rules and targets')
        for bc,c in zip(b['daiun_contexts'],contexts):
            rel=bc['analysis']['interactions_with_daiun']
            _equal(_pair_facts(rel['branch_relations']+rel['stem_relations'],nd['pillars'],a['kanshi'],c),
                   _pair_facts([r for r in report['interactions']['daiun_annual'] if r['daiun_index']==c['index']],nd['pillars'],a['kanshi'],c), 'daiun_annual two-party rules and targets')
    return {"matching_is_not_purchase_authorization": True, "missing_base_comparison_fields": missing}


def extract_annual(raw: bytes, annual_raw: bytes, years):
    base = load_saved_full(raw)
    requested = _requests(years)
    try:
        addon = yaml.safe_load(annual_raw)
        _typed_tree(addon)
        if addon["meta"]["product_type"] != PROTOTYPE_PRODUCT_TYPE:
            raise ExtractionError("wrong_source_type", "既存の流年ローカル試作が必要です。")
        details = addon["systems"]["shichusuimei"]["annual_details"]
        index = _index(details["years"], "selected_year")
        _require_all(requested, index)
        expanded = [expand_shared_year(addon, y) for y in requested]
        for report in expanded:
            _equal(report.get("base_chart_id"), details["base_reference"]["chart_id"], "annual source base_reference/chart_id")
            for k in ("day_master", "pillars"):
                _equal(report["natal_reference"][k], details["base_reference"][k], f"annual source base_reference/{k}")
        matches = [validate_annual_match(base, r) for r in expanded]
        if details["layout"] == "shared":
            for y in requested:
                item = index[y][1]
                refs = [c["daiun_ref"] for c in item["daiun"]["contexts"]]
                _equal(refs, item["interactions"]["natal_daiun_refs"], "natal_daiun_refs")
                for ref in refs:
                    saved = details["daiun_catalog"][ref]
                    if ref != f"daiun_{saved['index']}":
                        raise ExtractionError("reference_conflict", "大運の参照名とindexが不一致")
    except ExtractionError:
        raise
    except (KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise ExtractionError("invalid_annual_reference", "流年試作の構造または保存参照が不正です。") from exc
    basic_raw, _ = extract_base(raw)
    output = yaml.safe_load(basic_raw)
    common, aliases, excluded = _common(base, current=False)
    output["common"] = common
    scope = output["local_year_extraction"]
    scope.update(purpose="base_with_selected_annual_prototype_years", requested_years=requested, included_years=requested,
                 original_current_annual_policy="除外。追加由来の指定年へ置換していない")
    scope["annual_source"] = {"sha256": hashlib.sha256(annual_raw).hexdigest(), "product_type": addon["meta"]["product_type"],
                              "saved_period": deepcopy(details["period"]), "available_years": list(index), "layout": details["layout"],
                              "unselected_years": [y for y in index if y not in requested], "base_matches": matches,
                              "selection_policy": "追加由来を別枠で保持。基本の同年詳細と統合・置換しない"}
    # Only selected, expanded records; no full catalog or unselected years.
    output["selected_annual_reports"] = deepcopy(expanded)
    _, forecasts = _base_index(base)
    metadata_destinations = [{"source": pointer(FP + (k,)), "destination": f"/local_year_extraction/source/saved_forecast_metadata/{k}"}
                             for k in (forecasts or {}) if k != "items"]
    serialized, manifest = _finish(raw, base, output, aliases, excluded, metadata_destinations)
    manifest["annual_sha256"] = hashlib.sha256(annual_raw).hexdigest()
    manifest["annual_year_mapping"] = [{"year": y, "saved_year_path": f"/systems/shichusuimei/annual_details/years/{index[y][0]}",
                                       "destination": f"/selected_annual_reports/{j}", "saved_layout": details["layout"],
                                       "shared_sources": [f"/systems/shichusuimei/annual_details/daiun_catalog/{c['daiun_ref']}" for c in index[y][1]["daiun"]["contexts"]] if details["layout"] == "shared" else []}
                                      for j,y in enumerate(requested)]
    for j,r in enumerate(expanded):
        _equal(yaml.safe_load(serialized)["selected_annual_reports"][j], r, "selected report all fields")
    return serialized, manifest


def extraction_prompt(purpose):
    return """この保存済み計算データを根拠に解釈し、生年月日から再計算しない。
local_year_extractionの用途・included_years・除外理由を確認する。基本鑑定ではcommon内の原本作成時の単一流年をその時点の対象として読む。
指定年・比較ではselected_base_forecastsまたはselected_annual_reportsの指定年だけを使い、年別に出典を明示する。
共通の原局・全大運と、選択された流年を区別する。大運だけから未収録年の詳細を推測しない。完全原本に別年があることは今回の入力にあることを意味しない。
立春から翌立春の保存期間と期間端を尊重し、年途中の複数大運・概算境界・出生時刻不確実性・未計算条件を保持する。
同じ干支や関係でも柱・大運index・流年effective_year・参加者を統合しない。条件不十分な合化を確定しない。単純個数と季節重み付きスコアを混同しない。
対象外の年を尋ねられたら不足を明示し、その年の予測を作らない。計算事実と解釈、強みと注意点を区別する。
""" if purpose != "complete" else "この完全原本にある計算結果・期間・条件・注意事項を根拠に読み、出生情報から再計算しない。柱・大運・流年の対象を区別し、未収録年を推測しない。\n"
