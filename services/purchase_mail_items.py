"""Extract purchase fields, never product codes from arbitrary mail prose."""
from __future__ import annotations

import html
import re
from services import product_catalog

_FIELD = re.compile(r"^(?:商品|商品名|アイテム|アイテム名|Product|Item)\s*[:：]\s*(.*)$", re.I)
_GUIDANCE = re.compile(
    r"^(?:Other products|Other items|More products|Recommended|Related products|You may also like|"
    r"Instructions|How to|Guide|(?:Message|Note|Description|Help)\s*[:：]|"
    r"こちらもおすすめ|関連商品|他の商品|ご利用方法|利用方法|お問い合わせ|案内|注意事項|備考)", re.I
)
_QUANTITY = re.compile(r"^(?:数量|個数|Qty|Quantity)\s*[:：]?\s*(\d+)\s*$", re.I)
_PRICE = re.compile(r"^(?:[¥￥$€£]|USD|JPY|EUR|GBP)\s*[\d,]+(?:\.\d{1,2})?\s*$")
_TOTAL = re.compile(r"^(?:Total|Subtotal|小計|合計)\s*[:：]?", re.I)


def _lines(body: str) -> list[str]:
    body = html.unescape(body)
    return [line.strip() for line in body.splitlines() if line.strip()]


def _explicit_rows(lines: list[str]) -> list[tuple[str, int, str]]:
    rows = []
    for index, line in enumerate(lines):
        if _GUIDANCE.search(line):
            break
        field = _FIELD.fullmatch(line)
        if not field:
            continue
        title = field[1]
        next_index = index + 1
        if not title and next_index < len(lines) and not re.search(r"[:：]", lines[next_index]):
            title = lines[next_index]
            next_index += 1
        quantity = 1
        for nearby in lines[next_index:next_index + 3]:
            if _FIELD.match(nearby) or _GUIDANCE.search(nearby) or _TOTAL.match(nearby):
                break
            match = _QUANTITY.fullmatch(nearby)
            if match:
                quantity = int(match[1])
                break
            if re.match(r"^(?:数量|個数|Qty|Quantity)\s*[:：]", nearby, re.I):
                quantity = 0  # Invalid quantities must not become a default purchase.
                break
        rows.append((title, quantity, "labeled_product_field"))
    return rows


def _payhip_rows(lines: list[str], body: str) -> list[tuple[str, int, str]] | None:
    heading = re.search(r"The\s+following\s+items?\s+ha(?:s|ve)\s+been\s+purchased\s*:", body, re.I)
    if not heading:
        return None
    # The observed template has Buyer/Date/Order ID before the item-price rows.
    order = re.search(r"Order\s*ID\s*[:：][^\r\n]*", body[heading.end():], re.I)
    if not order:
        return []
    section = _lines(body[heading.end() + order.end():])
    rows = []
    index = 0
    while index < len(section):
        title = section[index]
        if _TOTAL.match(title) or _GUIDANCE.search(title):
            break
        if index + 1 >= len(section) or not _PRICE.fullmatch(section[index + 1]):
            return []  # Do not silently omit an unrecognized purchase row.
        rows.append((title, 1, "payhip_purchased_item_price_row"))
        index += 2
    return rows


def _stores_rows(lines: list[str]) -> list[tuple[str, int, str]]:
    rows = []
    for index, line in enumerate(lines):
        if _TOTAL.match(line) or _GUIDANCE.search(line):
            break
        match = re.fullmatch(r"\d+\.\s+(.+)", line)
        if not match:
            continue
        found_quantity = False
        for nearby in lines[index + 1:index + 4]:
            # STORES owner template: title, optional item URL, unit price x qty = total.
            amount = re.fullmatch(r"[¥￥][\d,]+\s*[x×]\s*(\d+)\s*=\s*[¥￥][\d,]+", nearby, re.I)
            if amount:
                rows.append((match[1], int(amount[1]), "stores_numbered_item_price_quantity_row"))
                found_quantity = True
                break
        if not found_quantity:
            return []  # A partial table is not a verified multi-product order.
    if rows:
        return rows
    for index, line in enumerate(lines):
        # This legacy template includes contact instructions before the order
        # fields. Scope by the exact field, not by where the first help text is.
        field = re.fullmatch(r"注文商品\s*[:：]\s*(.*)", line)
        if field:
            title = field[1] or (lines[index + 1] if index + 1 < len(lines) else "")
            return [(title, 1, "stores_order_product_field")]
    return []


def analyze_purchase_items(provider: str, subject: str, body: str) -> dict:
    body = html.unescape(body)
    lines = _lines(body)
    if provider == "payhip" and re.search(
        r"requested a download|been\s+downloaded|download notification", f"{subject}\n{body}", re.I
    ):
        return {"line_items": [], "product_type": None, "hold_reason": "non_purchase_notification",
                "purchase_evidence": []}
    rows = _payhip_rows(lines, body) if provider == "payhip" else None
    if rows is None:
        rows = _explicit_rows(lines)
        if not rows and provider == "stores":
            rows = _stores_rows(lines)
        if not rows and provider == "coconala":
            rows = [(body.strip(), 1, "coconala_title_field")]
    items, evidence, occurrences = [], [], {}
    reason = "purchase_fields_missing" if not rows else None
    for title, quantity, field in rows:
        tokens = product_catalog.code_tokens(title)
        sku = product_catalog.sku_from_text(title)
        if len(tokens) > 1:
            reason = "ambiguous_product_field"
            break
        if not sku:
            reason = "unknown_product_code" if tokens else "product_code_missing"
            break
        if len(tokens) != 1:
            reason = "ambiguous_product_field"
            break
        if not 1 <= quantity <= 100:
            reason = "invalid_quantity"
            break
        product_type = product_catalog.resolve_text(title)
        if not product_type:
            reason = "unknown_product_code"
            break
        occurrences[sku] = occurrences.get(sku, 0) + 1
        items.append({"sku": sku, "product_type": product_type, "quantity": quantity,
                      "line_item_key": f"{sku}:{occurrences[sku]}"})
        evidence.append(field)
    if reason:
        items, evidence = [], []  # Ambiguous orders cannot create new purchase rights.
    types = {item["product_type"] for item in items}
    return {"line_items": items, "product_type": next(iter(types)) if len(types) == 1 else None,
            "hold_reason": reason, "purchase_evidence": evidence}
