"""四柱推命の販売版（基本版／FULL版）と、既存購入者の旧原本の扱い。

- 新規発行の YAML には systems.shichusuimei.edition（"basic" / "full"）が必ず入る。
- edition を持たない四柱推命単独の原本は、この区分より前に発行された既存購入者の原本
  （旧原本）。保存データは変更せず、画面・コピー・ZIP・prompt.txt の AI 指示文も
  本番 8c25fc0 と同じ固定文を返す。
"""
from __future__ import annotations

from typing import Any

from services.shichusuimei_legacy_prompts import LEGACY_COMPANION_PROMPTS, LEGACY_READING_PROMPTS
from services.shichusuimei_years_addon import YEARS_ADDON_TYPES

# 年運アドオンの発行物は「FULL版＋追加した年」をまとめた鑑定ページ（FULL版と同じ扱い）。
FULL_CHART_PRODUCT_TYPES = frozenset({"shichu_full", *YEARS_ADDON_TYPES})
SHICHU_PRODUCT_TYPES = frozenset({"shichu", *FULL_CHART_PRODUCT_TYPES})
EDITION_BY_PRODUCT_TYPE = {"shichu": "basic", "shichu_full": "full"}
_LEGACY_LANGS = ("ja", "en", "es", "de")


def is_shichu_product(product_type: object) -> bool:
    return str(product_type or "") in SHICHU_PRODUCT_TYPES


def is_full_chart_product(product_type: object) -> bool:
    """年選択を使える四柱推命の鑑定ページ（FULL版と、年運アドオンで年を追加したもの）か。"""
    return str(product_type or "") in FULL_CHART_PRODUCT_TYPES


def edition_for_product_type(product_type: object) -> str:
    return EDITION_BY_PRODUCT_TYPE.get(str(product_type or ""), "full")


def _shichu_system(doc: Any) -> dict | None:
    if not isinstance(doc, dict):
        return None
    systems = doc.get("systems")
    if not isinstance(systems, dict):
        return None
    shichu = systems.get("shichusuimei")
    return shichu if isinstance(shichu, dict) and shichu else None


def doc_edition(doc: Any) -> str | None:
    shichu = _shichu_system(doc)
    edition = shichu.get("edition") if shichu else None
    return edition if edition in EDITION_BY_PRODUCT_TYPE.values() else None


def _version_tuple(version: object) -> tuple[int, ...] | None:
    parts: list[int] = []
    for piece in str(version or "").split("."):
        if not piece.isdigit():
            return None
        parts.append(int(piece))
    return tuple(parts) or None


# 版（edition）の記録を始めたエンジン。これより前の版で発行された原本が旧原本。
EDITION_INTRODUCED_IN = (0, 5, 1)


def is_legacy_shichu_doc(doc: Any) -> bool:
    """版の区分より前に発行された、四柱推命単独の原本か。

    発行済み原本は最初の実装（0.2.7, 2026-04-30）から engine_version を必ず持つ。
    edition がなく engine_version が 0.5.1 未満のものだけを旧原本とし、
    版情報のない検証用の文書などは旧原本扱いしない。
    """
    shichu = _shichu_system(doc)
    if not shichu or doc_edition(doc) is not None:
        return False
    version = _version_tuple(shichu.get("engine_version"))
    if version is None or version >= EDITION_INTRODUCED_IN:
        return False
    western = (doc.get("systems") or {}).get("western")
    return not western


def _lang(lang: str | None) -> str:
    return lang if lang in _LEGACY_LANGS else "ja"


def legacy_reading_prompt(doc: dict, lang: str | None) -> str:
    """8c25fc0 の build_prompt(include_shichusuimei=True) と同じ判定で固定文を返す。"""
    accuracy = str((doc.get("birth_time") or {}).get("accuracy") or "exact")
    flags = doc.get("interpretation_flags") or {}
    time_sensitive = accuracy in {"unknown", "approximate"} or bool(
        isinstance(flags, dict) and flags.get("use_houses_as_reference_only")
    )
    return LEGACY_READING_PROMPTS[f"{_lang(lang)}:{'time_sensitive' if time_sensitive else 'exact'}"]


def legacy_companion_prompt(lang: str | None) -> str:
    return LEGACY_COMPANION_PROMPTS[_lang(lang)]
