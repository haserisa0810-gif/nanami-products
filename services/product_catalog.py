"""Channel-independent product identities; no prices or new product activation.

Extract the whole SKU first, then resolve it by dictionary equality. Language
suffixes identify existing order units, not a different calculation product.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable


@dataclass(frozen=True)
class Product:
    code: str
    product_type: str
    payhip_label: str | None = None


_EXISTING_PRODUCTS = (
    Product("NP-ACG", "acg_bundle"),
    Product("NP-WBA", "western_asteroids"),
    Product("NP-WBT", "western_transit"),
    Product("NP-WB", "western_basic", "NP-WB / AI-Readable Natal Data Core Pack"),
    Product("NP-WF", "western_full", "NP-WF / AI-Readable Astrology Data Full Version"),
    Product("NP-WA", "western_asteroids_addon"),
    Product("NP-AA", "western_asteroids_addon", "NP-AA / AI-Readable Asteroid Data Add-on"),
    Product("NP-WT", "western_31days_transit_addon"),
    Product("NP-TA", "western_31days_transit_addon", "NP-TA / AI-Readable Transit Data Add-on"),
    Product("NP-SF", "shichu_fortune_cycles_addon"),
    Product("NP-SC", "shichu"),
    # 四柱推命FULL版。予約済みの NP-SFULL は既存の注文保留テストで「未登録コード」の例として
    # 使われているため、衝突しない NP-SCF を割り当てる。
    Product("NP-SCF", "shichu_full"),
    # 四柱推命 年運アドオン。10年・20年（NP-SY10 / NP-SY20）は AI の読み取り確認後に登録する。
    Product("NP-SY05", "shichu_annual_5y_addon"),
    Product("NP-TY", "transit_yaml"),
    # Already supported in this checkout, including the issuance route.
    Product("NP-WL", "western_long_term_transits_addon"),
    Product("NP-API", "api_key"),
)
PRODUCTS = MappingProxyType({product.code: product for product in _EXISTING_PRODUCTS})
RESERVED_CODES = frozenset({"NP-SB", "NP-SFULL", "NP-SY10", "NP-SY20"})
REGISTERED_PRODUCT_TYPES = frozenset(
    {product.product_type for product in PRODUCTS.values()} | {"api_key_trial", "api_key_standard"}
)

# Preserve spelling normalization of existing codes, but consume unknown suffixes
# too: NP-SFULL, NP-WF-BOGUS and NP-WBA2 must never match a shorter code.
_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])NP[-_ ]?[A-Za-z0-9][A-Za-z0-9_-]*"
    r"(?: (?:JA|EN|ES|DE))?(?![A-Za-z0-9_])", re.I,
)
_SKU_RE = re.compile(r"NP[-_ ]?([A-Z0-9]+)(?:[-_ ](JA|EN|ES|DE))?", re.I)


def normalize_sku(value: str) -> str | None:
    match = _SKU_RE.fullmatch((value or "").strip())
    if not match:
        return None
    code = f"NP-{match.group(1).upper()}"
    if code not in PRODUCTS:
        return None
    return code + (f"-{match.group(2).upper()}" if match.group(2) else "")


def product_for_sku(value: str) -> Product | None:
    sku = normalize_sku(value)
    return PRODUCTS.get("-".join(sku.split("-")[:2])) if sku else None


def code_tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in _TOKEN_RE.finditer(text or ""))


def sku_from_text(text: str) -> str | None:
    tokens = code_tokens(text)
    skus = {normalize_sku(token) for token in tokens}
    return next(iter(skus)) if len(skus) == 1 and None not in skus else None


def resolve_text(text: str) -> str | None:
    tokens = code_tokens(text)
    if not tokens:
        return None
    products = [product_for_sku(token) for token in tokens]
    if any(product is None for product in products):
        return None
    types = {product.product_type for product in products}
    if len(types) != 1:
        return None
    product_type = next(iter(types))
    # Existing API plan qualifiers remain scoped to the exact NP-API code.
    if product_type == "api_key":
        if re.search(r"お試し|trial|try|starter|ライト", text, re.I):
            return "api_key_trial"
        if re.search(r"standard|スタンダード|通常|APIクレジット|クレジット", text, re.I):
            return "api_key_standard"
    return product_type


def verified_identity(product_type: str | None, sku: str | None = None) -> bool:
    """Old classified orders without a SKU remain usable; unknown types do not."""
    if product_type not in REGISTERED_PRODUCT_TYPES:
        return False
    if not sku:
        return True
    product = product_for_sku(sku)
    return bool(product and (
        product.product_type == product_type
        or product.code == "NP-API" and product_type in {"api_key_trial", "api_key_standard"}
    ))


def payhip_products() -> dict[str, dict[str, str]]:
    # Preserve the existing Payhip choices and labels, including AA and TA.
    return {
        code: {"label": product.payhip_label, "product_type": product.product_type}
        for code, product in PRODUCTS.items() if product.payhip_label
    }


@dataclass(frozen=True)
class ChannelProductBinding:
    channel: str
    external_product_id: str
    product_code: str


def resolve_channel_product_id(
    channel: str, external_product_id: str, bindings: Iterable[ChannelProductBinding] = (),
) -> Product | None:
    """Future channel-ID adapter. No real marketplace IDs are invented here."""
    matches = {binding.product_code for binding in bindings
               if binding.channel == channel and binding.external_product_id == external_product_id}
    if len(matches) > 1:
        raise ValueError("Conflicting channel product bindings")
    code = next(iter(matches), None)
    if code is not None and code not in PRODUCTS:
        raise ValueError("Channel binding refers to an unregistered product")
    return PRODUCTS.get(code)
