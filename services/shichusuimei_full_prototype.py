"""Full-YAML variant builders and saved-document validation.

Product year selection reuses load_saved_full; variant builders remain offline.

Recommended preserves every source value and occurrence. Only equal values
within the same target scope, and long shared wording, may use named YAML
anchors. Ordinary has an explicit, narrower coverage contract.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import re
from typing import Any

import yaml

PILLAR_NAMES = {"year", "month", "day", "hour"}
SHICHU_PATH = ("systems", "shichusuimei")
# libyaml があれば C 実装で読む（同じ安全なローダー。本番で1回数秒かかっていたため）。
_SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load_fast(text):
    return yaml.load(text, Loader=_SAFE_LOADER)


def load_saved_full(raw: bytes) -> dict:
    try:
        doc = safe_load_fast(raw.decode("utf-8-sig"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("保存済みFull YAMLを読み取れません。") from exc
    if not isinstance(doc, dict) or not isinstance((doc.get("systems") or {}).get("shichusuimei"), dict):
        raise ValueError("四柱推命を含む保存済みFull YAMLが必要です。")
    if (doc.get("systems") or {}).get("western"):
        raise ValueError("今回の試作は四柱推命単独のFull YAMLを対象にします。")
    _typed_tree(doc)  # Also reject recursive YAML aliases.
    return doc


def _typed_tree(value: Any, ancestors: frozenset[int] = frozenset()):
    if isinstance(value, (dict, list)):
        if id(value) in ancestors:
            raise ValueError("循環するYAML参照には対応していません。")
        parents = ancestors | {id(value)}
        if isinstance(value, dict):
            return ("mapping", tuple((_typed_tree(k, parents), _typed_tree(v, parents)) for k, v in value.items()))
        return ("sequence", tuple(_typed_tree(v, parents) for v in value))
    return (type(value).__name__, repr(value))


def pointer(path: tuple) -> str:
    return "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1") for x in path)


def walk(value: Any, path: tuple = ()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, path + (i,))


def _get(doc, path):
    value = doc
    for part in path:
        value = value[part]
    return value


def _feature_aliases(doc: dict) -> set[str]:
    shichu = doc["systems"]["shichusuimei"]
    nd = shichu.get("normalized_data") or {}
    return {key for key, value in (shichu.get("features") or {}).items()
            if key in nd and _typed_tree(value) == _typed_tree(nd[key])}


def _canonical_path(path: tuple, doc: dict, verified_aliases: set[str] | None = None) -> tuple:
    # Only verified equality permits old compatibility aliases to share scope.
    if path[:3] == SHICHU_PATH + ("features",) and len(path) > 3:
        candidate = SHICHU_PATH + ("normalized_data", path[3])
        if verified_aliases is not None:
            return candidate + path[4:] if path[3] in verified_aliases else path
        try:
            if _typed_tree(_get(doc, candidate)) == _typed_tree(_get(doc, path[:4])):
                return candidate + path[4:]
        except KeyError:
            pass
    return path


def target_scope(doc: dict, path: tuple, value: Any, verified_aliases: set[str] | None = None) -> str:
    """Bind occurrence to original owner, never to kanshi/ten-god text alone."""
    if isinstance(value, str):
        return "shared_wording"  # String sharing cannot merge target objects.
    original_path = path
    path = _canonical_path(path, doc, verified_aliases)
    # An explicit natal target remains the same natal target across luck frames.
    candidates = [(original_path[:i], _get(doc, original_path[:i])) for i in range(len(original_path), 0, -1)]
    for candidate_path, node in candidates:
        if not isinstance(node, dict):
            continue
        name = node.get("name") or node.get("pillar")
        if isinstance(name, str) and name in PILLAR_NAMES:
            return f"natal_{name}"
        if candidate_path and candidate_path[-1] == "target_ten_gods":
            parent = _get(doc, candidate_path[:-1])
            right = (parent.get("right") or {}).get("name")
            if right in PILLAR_NAMES:
                return f"natal_{right}"
    for i, part in enumerate(path[:-1]):
        if part in {"pillars", "hidden_stems", "main_hidden_stems", "twelve_fortune"} and path[i + 1] in PILLAR_NAMES:
            return f"natal_{path[i + 1]}"
    for i, part in enumerate(path):
        if part == "annual_forecasts" and len(path) > i + 2 and path[i + 1] == "items" and isinstance(path[i + 2], int):
            item = _get(doc, original_path[:i + 3])
            scope = f"annual_{item.get('effective_year', path[i + 2])}"
            if "daiun_contexts" in path[i + 3:]:
                j = path.index("daiun_contexts", i + 3)
                if len(path) > j + 1 and isinstance(path[j + 1], int):
                    context = _get(doc, original_path[:j + 2])
                    scope += f"_daiun_{context.get('index', path[j + 1])}"
            return scope
        if part == "annual_fortune":
            item = _get(doc, original_path[:i + 1])
            return f"current_annual_{item.get('effective_year', item.get('year', 'unspecified'))}"
        if part == "daiun" and len(path) > i + 2 and path[i + 1] == "items" and isinstance(path[i + 2], int):
            item = _get(doc, original_path[:i + 3])
            return f"daiun_{item.get('index', path[i + 2])}"
    return "natal_chart"


TABLE_MARKER = "__local_trial_table__"


def _flat_record(value: dict, prefix: tuple = ()) -> list[tuple[tuple, Any]]:
    result = []
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("Table columns require string keys")
        if isinstance(item, dict) and item:
            result.extend(_flat_record(item, prefix + (key,)))
        else:
            result.append((prefix + (key,), item))
    return result


def _table(value):
    if not isinstance(value, list) or len(value) < 3 or not all(isinstance(x, dict) and x for x in value):
        return None
    try:
        flattened = [_flat_record(x) for x in value]
    except TypeError:
        return None
    paths = [path for path, _ in flattened[0]]
    if any([path for path, _ in row] != paths for row in flattened[1:]):
        return None
    result = {TABLE_MARKER: "rows_with_named_columns", "columns": [pointer(p) for p in paths],
              "rows": [[item for _, item in row] for row in flattened]}
    return result if len(repr(value)) > len(repr(result)) + 80 else None


def restore_variant(serialized: bytes) -> dict:
    """Expand standard YAML anchors and readable tables within this document."""
    parsed = yaml.safe_load(serialized)
    def expand(value):
        if isinstance(value, dict):
            if set(value) == {TABLE_MARKER, "columns", "rows"} and value[TABLE_MARKER] == "rows_with_named_columns":
                columns = value["columns"]
                if len(set(columns)) != len(columns) or not all(isinstance(x, str) and x.startswith("/") for x in columns):
                    raise ValueError("表の列参照が不正です。")
                records = []
                for row in value["rows"]:
                    if len(row) != len(columns):
                        raise ValueError("表の列数と行の値数が一致しません。")
                    record = {}
                    for column, item in zip(columns, row):
                        parts = [x.replace("~1", "/").replace("~0", "~") for x in column[1:].split("/")]
                        parent = record
                        for key in parts[:-1]:
                            parent = parent.setdefault(key, {})
                        if parts[-1] in parent:
                            raise ValueError("表の列が重複しています。")
                        parent[parts[-1]] = expand(item)
                    records.append(record)
                return records
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(x) for x in value]
        return deepcopy(value)
    return expand(parsed)


def _compact_dump(doc: Any, anchors: dict[int, str] | None = None, *, tables: bool = False) -> bytes:
    anchor_names = anchors or {}

    class NamedDumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return id(data) not in anchor_names

        def generate_anchor(self, node):
            return getattr(node, "trial_anchor", super().generate_anchor(node))

        def represent_data(self, data):
            node = super().represent_data(data)
            if id(data) in anchor_names:
                node.trial_anchor = anchor_names[id(data)]
            return node

        def represent_mapping(self, tag, mapping, flow_style=None):
            if isinstance(mapping, dict) and mapping and len(mapping) <= 7 and all(not isinstance(v, (dict, list)) for v in mapping.values()):
                flow_style = True
            return super().represent_mapping(tag, mapping, flow_style)

        def represent_trial_list(self, data):
            table = _table(data) if tables else None
            if table:
                return self.represent_mapping("tag:yaml.org,2002:map", table)
            return self.represent_sequence("tag:yaml.org,2002:seq", data,
                                           flow_style=True if data and all(not isinstance(x, (dict, list)) for x in data) else None)

    NamedDumper.add_representer(list, NamedDumper.represent_trial_list)
    return yaml.dump(doc, Dumper=NamedDumper, allow_unicode=True, sort_keys=False, width=120).encode("utf-8")


def build_recommended(raw: bytes, *, tables: bool = True) -> tuple[bytes, dict]:
    doc = load_saved_full(raw)
    aliases = _feature_aliases(doc)
    # Candidates are exact type/value trees, scoped by their original targets.
    nodes = list(walk(doc))
    counts = Counter()
    keys = {}
    for path, value in nodes:
        size = len(repr(value))
        if (isinstance(value, (dict, list)) and size >= 150) or (isinstance(value, str) and len(value) >= 65):
            key = (target_scope(doc, path, value, aliases), _typed_tree(value))
            keys[path] = key
            counts[key] += 1
    pool, anchors, occurrences = {}, {}, []
    used_names = Counter()

    def clone(value, path=()):
        key = keys.get(path)
        if key and counts[key] > 1:
            if key in pool:
                shared, name, definition = pool[key]
                occurrences.append({"source": pointer(path), "definition": definition,
                                    "anchor": name, "scope": key[0], "action": "duplicate_value_reference"})
                return shared
        if isinstance(value, dict):
            copied = {k: clone(v, path + (k,)) for k, v in value.items()}
        elif isinstance(value, list):
            copied = [clone(v, path + (i,)) for i, v in enumerate(value)]
        else:
            copied = deepcopy(value)
        if key and counts[key] > 1:
            field = str(path[-1]) if path and not isinstance(path[-1], int) else "items"
            label = re.sub(r"[^A-Za-z0-9_]", "_", f"{key[0]}_{field}")
            used_names[label] += 1
            name = label if used_names[label] == 1 else f"{label}_{used_names[label]}"
            anchors[id(copied)] = name
            pool[key] = (copied, name, pointer(path))
            occurrences.append({"source": pointer(path), "definition": pointer(path), "anchor": name,
                                "scope": key[0], "action": "shared_value_definition"})
        return copied

    result = _compact_dump(clone(doc), anchors, tables=tables)
    expanded = restore_variant(result)
    if _typed_tree(expanded) != _typed_tree(doc):
        raise ValueError("推奨版の型・値・項目・順序が原本と一致しません。")
    for item in occurrences:
        source = tuple(_pointer_parts(item["source"], doc))
        definition = tuple(_pointer_parts(item["definition"], doc))
        if target_scope(doc, source, _get(doc, source), aliases) != target_scope(doc, definition, _get(doc, definition), aliases):
            raise ValueError("異なる対象への参照付け替えを検出しました。")
    return result, {"variant": "recommended_local_trial", "source_sha256": hashlib.sha256(raw).hexdigest(),
                    "recommended_sha256": hashlib.sha256(result).hexdigest(),
                    "lossless_all_source_fields": True, "excluded_development_fields": [],
                    "table_sections": [{"source": pointer(path), "columns": table["columns"],
                                        "rows": len(table["rows"]), "owner_scope": target_scope(doc, path, value, aliases)}
                                       for path, value in nodes if tables and (table := _table(value))],
                    "references": occurrences,
                    "reference_policy": "同一対象内の同値表現と共通の長文のみ。各柱・大運・流年・関係の出現位置は保持。"}


def _pointer_parts(ptr: str, doc: dict):
    value = doc
    for part in ptr.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        key = int(part) if isinstance(value, list) else part
        yield key
        value = value[key]


def build_ordinary(raw: bytes) -> tuple[bytes, dict]:
    doc = load_saved_full(raw)
    source = doc["systems"]["shichusuimei"]
    nd_source = source.get("normalized_data") or source.get("features")
    if not isinstance(nd_source, dict) or not nd_source:
        raise ValueError("通常版に必要な保存済み計算結果がありません。")
    output = {k: deepcopy(v) for k, v in doc.items() if k != "systems"}
    output["meta"] = {**(output.get("meta") or {}), "yaml_variant": "ordinary_local_trial"}
    nd = {k: deepcopy(v) for k, v in nd_source.items() if k != "annual_forecasts"}
    if "pillars" not in nd and isinstance(source.get("pillars"), dict):
        nd["pillars"] = deepcopy(source["pillars"])
    compact_source = {k: deepcopy(v) for k, v in source.items() if k in {
        "module", "system", "engine_version", "generated_at", "input", "unknowns", "structure_report", "day_master",
    }}
    compact_source["normalized_data"] = nd
    # Strength is not a duplicate of normalized_data: retain the original.
    extra_features = {k: deepcopy(v) for k, v in (source.get("features") or {}).items()
                      if k not in nd_source or _typed_tree(v) != _typed_tree(nd_source[k])}
    if extra_features:
        compact_source["features"] = extra_features
    # Unexpected legacy keys are retained instead of silently discarded.
    known = {"ephemeris", "debug", "raw", "pillars", "summary", "features", "normalized_data", *compact_source}
    for k, v in source.items():
        if k not in known:
            compact_source[k] = deepcopy(v)
    forecasts = nd_source.get("annual_forecasts") or {}
    items = forecasts.get("items") or []
    omitted = ["systems.shichusuimei.normalized_data.annual_forecasts"] if "annual_forecasts" in nd_source else []
    output["systems"] = {"western": None, "shichusuimei": compact_source}
    output["local_trial_coverage"] = {
        "purpose": ["性質", "強みと弱み", "仕事運", "金運", "大運の基本的な流れ"],
        "retained": "原局の全計算・構造分析、大運全期と作用・概算期間、既存の単一流年と全作用、空亡・神殺、注意事項",
        "omitted_sections": omitted,
        "omitted_existing_forecast_years": [x.get("effective_year") for x in items],
        "omission_meaning": "通常版の収録範囲から省略。該当なし・未計算・別売への移動を意味しない。完全版と推奨版に保持。",
        "development_sections_omitted": [f"systems.shichusuimei.{k}" for k in ("ephemeris", "debug", "raw") if k in source],
        "source_missing_sections": [k for k in ("structural_analysis", "annual_forecasts", "kubo", "daiun") if k not in nd_source],
        "no_new_astrological_calculations": True,
    }
    result = _compact_dump(output)
    return result, {"variant": "ordinary_local_trial", "source_sha256": hashlib.sha256(raw).hexdigest(),
                    "omitted_sections": omitted, "coverage": output["local_trial_coverage"]}


def variant_prompt(variant: str) -> str:
    if variant not in {"complete", "recommended", "ordinary"}:
        raise ValueError("未対応の試作版です。")
    common = """この文書内の四柱推命計算値と注意事項を根拠に読み、生年月日から再計算しない。
計算事実と占術的解釈を区別し、強み・弱み・仕事・金運・大運の流れを必要に応じて説明する。
個数だけで用神や吉凶を確定せず、格局・用神候補の方式・根拠・確信度・競合条件を尊重する。
刑冲合害の参加柱・運・対象年を区別し、合化を自動適用しない。交運の概算と立春の年区間を保持する。
時刻不明・推定はtime_basisと参考値表示に従い、仮置き時柱を確定根拠にしない。
YAMLに存在する項目だけを用い、未計算・未対応・暫定を該当なしや確定値に置き換えない。
原本にある未解決のevidence_idは、存在する根拠と同一視せず、計算結果を補完しない。"""
    if variant == "recommended":
        common += "\n名前付きYAMLアンカーは同じ文書内の定義を参照する値の再利用。参照位置を持つ柱・大運・流年を同一対象として統合しない。"
    elif variant == "ordinary":
        common += "\nlocal_trial_coverageを確認する。省略された既存10年予測を該当なしと読まず、その年の詳しい分析や比較を推測で作らない。収録済みの原局・大運・単一流年だけを用いる。"
    if variant == "recommended":
        common += "\n__local_trial_table__は項目名付き表。columnsの各項目名とrowsの同じ位置の値を対応させ、行の大運番号・年・柱・期間を区別する。全計算値はこの文書内にある。"
    return common + "\n"


def verify_recommended(raw: bytes, recommended: bytes, manifest: dict) -> dict:
    original = load_saved_full(raw)
    aliases = _feature_aliases(original)
    restored = restore_variant(recommended)
    if _typed_tree(original) != _typed_tree(restored):
        raise ValueError("原本との意味・型・対象位置の差分を検出しました。")
    if hashlib.sha256(raw).hexdigest() != manifest["source_sha256"]:
        raise ValueError("参照マニフェストの原本ハッシュが一致しません。")
    if hashlib.sha256(recommended).hexdigest() != manifest["recommended_sha256"]:
        raise ValueError("参照・表を検証した試作バイト列からの変更を検出しました。")
    for ref in manifest["references"]:
        source = tuple(_pointer_parts(ref["source"], original))
        definition = tuple(_pointer_parts(ref["definition"], original))
        source_value, definition_value = _get(original, source), _get(original, definition)
        if _typed_tree(source_value) != _typed_tree(definition_value):
            raise ValueError("参照の値が原本と一致しません。")
        if target_scope(original, source, source_value, aliases) != ref["scope"] or target_scope(original, definition, definition_value, aliases) != ref["scope"]:
            raise ValueError("参照の対象・条件の付け替えを検出しました。")
    return {"all_typed_values_and_occurrences_equal": True, "reference_occurrences_checked": len(manifest["references"]),
            "astrological_results_recomputed": False, "external_ai_reading_tested": False}


def item_mapping(raw: bytes, recommended_manifest: dict, ordinary_manifest: dict) -> list[dict]:
    """Every original leaf has a mapping; exact reference paths also have rows."""
    doc = load_saved_full(raw)
    aliases = _feature_aliases(doc)
    refs = sorted(recommended_manifest["references"], key=lambda r: len(r["source"]), reverse=True)
    rows = []
    for path, value in walk(doc):
        if isinstance(value, (dict, list)) and value:
            continue
        source_path = pointer(path)
        ref = next((r for r in refs if source_path == r["source"] or source_path.startswith(r["source"] + "/")), None)
        ordinary = "retained"
        reason = "計算結果・対象位置・条件は原本のまま"
        destination = source_path
        if path == ("meta", "yaml_variant"):
            ordinary, reason = "trial_label_changed", "原本fullを通常版と誤認しないための試作ラベル。計算事実ではない"
        if path[:3] == SHICHU_PATH + ("normalized_data",) and len(path) > 3 and path[3] == "annual_forecasts":
            ordinary, reason, destination = "ordinary_only_omitted", "通常版の用途から外す既存詳細予測。推奨版・完全版には保持", "local_trial_coverage.omitted_existing_forecast_years"
        elif path[:3] == SHICHU_PATH + ("features",) and len(path) > 3:
            canonical = _canonical_path(path, doc, aliases)
            if canonical != path:
                ordinary, destination = "duplicate_consolidated", pointer(canonical)
                if canonical[3] == "annual_forecasts":
                    ordinary, destination = "ordinary_only_omitted", "local_trial_coverage.omitted_existing_forecast_years"
        elif path[:3] == SHICHU_PATH + ("pillars",) and len(path) > 3:
            dest = SHICHU_PATH + ("normalized_data", "pillars", path[3])
            if isinstance(_get(doc, dest), dict):
                dest += ("kanshi",)
            ordinary, destination = "duplicate_consolidated", pointer(dest)
        elif path[:3] == SHICHU_PATH + ("summary",):
            name = str(path[-1]).removesuffix("_kanshi")
            dest = SHICHU_PATH + ("normalized_data", "pillars", name)
            if isinstance(_get(doc, dest), dict):
                dest += ("kanshi",)
            ordinary, destination = "duplicate_consolidated", pointer(dest)
        elif path[:3] in {SHICHU_PATH + ("ephemeris",), SHICHU_PATH + ("debug",), SHICHU_PATH + ("raw",)}:
            ordinary, destination = "ordinary_only_omitted", "local_trial_coverage.development_sections_omitted"
            reason = "通常版では検証ログ・実行環境・互換表示を省略。推奨版では意味を否定せず全保持"
        rows.append({"source": source_path, "recommended_destination": ref["definition"] + source_path[len(ref["source"]):] if ref else source_path,
                     "recommended_action": "duplicate_value_reference" if ref else "retained",
                     "ordinary_destination": destination, "ordinary_action": ordinary, "reason": reason})
    return rows
