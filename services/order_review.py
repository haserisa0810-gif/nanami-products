"""Explicit admin review of held purchases. Callers must authenticate first."""
from collections import Counter
import re

from services import order_holds, product_catalog, stores_mail_sync as sync


class ReviewError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code, self.status = code, status


def validate_identity(provider: str, order_code: str) -> None:
    if provider not in {"stores", "payhip", "etsy"} or not re.fullmatch(r"[A-Za-z0-9=_-]{1,160}", order_code):
        raise ReviewError("INVALID_ORDER_IDENTITY", 400)


def load_locked_review(con, provider: str, order_code: str) -> tuple[dict, list[dict]]:
    validate_identity(provider, order_code)
    with con.cursor() as cur:
        order_holds.lock_order(cur, provider=provider, order_code=order_code, schema=sync.SCHEMA)
    review = order_holds.get_review(con, provider=provider, order_code=order_code)
    if not review:
        raise ReviewError("HOLD_NOT_FOUND", 404)
    with con.cursor() as cur:
        cur.execute(f"SELECT line_item_key, sku, product_type, unit_index, status "
                    f"FROM {sync.SCHEMA}.order_entitlements WHERE provider = %s AND order_code = %s "
                    "ORDER BY line_item_key, unit_index FOR UPDATE", (provider, order_code))
        saved = [dict(row) for row in cur.fetchall()]
    return review, saved


def validate_candidate(candidate: dict | None) -> list[dict]:
    if (not isinstance(candidate, dict) or candidate.get("purchase_evidence") is not True
            or candidate.get("payment_status") != "paid"
            or candidate.get("hold_reason") not in {None, "purchase_details_conflict"}):
        raise ReviewError("PURCHASE_EVIDENCE_REQUIRED")
    items = candidate.get("items")
    if not isinstance(items, list) or not items or len(items) > 100:
        raise ReviewError("PURCHASE_EVIDENCE_REQUIRED")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ReviewError("INVALID_REVIEW_ITEMS")
        key, sku, quantity = item.get("line_item_key"), item.get("sku"), item.get("quantity")
        if (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,160}", key)
                or key in seen or not isinstance(sku, str) or not product_catalog.normalize_sku(sku)
                or not product_catalog.verified_identity(item.get("product_type"), sku)
                or type(quantity) is not int or not 1 <= quantity <= 100):
            raise ReviewError("INVALID_REVIEW_ITEMS")
        seen.add(key)
    return items


def approve(con, *, provider: str, order_code: str, expected_version: int) -> dict:
    """Commit rights and approval together, or roll back everything on failure."""
    try:
        review, saved = load_locked_review(con, provider, order_code)
        if type(expected_version) is not int or expected_version < 1:
            raise ReviewError("INVALID_REVIEW_VERSION", 400)
        if review["review_version"] != expected_version:
            raise ReviewError("REVIEW_CHANGED")
        if review["status"] == "resolved" and review.get("approved_version") == expected_version:
            con.commit()
            return {"ok": True, "already_approved": True, "review_version": expected_version}
        if review["status"] != "held":
            raise ReviewError("ORDER_NOT_HELD")
        items = validate_candidate(review.get("candidate"))
        desired = {(item["line_item_key"], unit): (item["sku"], item["product_type"])
                   for item in items for unit in range(1, item["quantity"] + 1)}
        # Never relabel, remove, revive, or re-create existing units.
        for row in saved:
            if desired.get((row["line_item_key"], row["unit_index"])) != (row["sku"], row["product_type"]):
                raise ReviewError("EXISTING_RIGHTS_CONFLICT")
        quantities = Counter()
        for item in items:
            quantities[item["product_type"]] += item["quantity"]
        with con.cursor() as cur:
            cur.execute(f"SELECT options->>'product_type' AS product_type, COUNT(*) AS quantity "
                        f"FROM {sync.SCHEMA}.charts WHERE order_code = %s AND "
                        "(options->>'order_provider' = %s OR "
                        "(%s = 'stores' AND COALESCE(options->>'order_provider', '') = '')) "
                        "GROUP BY options->>'product_type'", (order_code, provider, provider))
            for row in cur.fetchall():
                if row["quantity"] > quantities[row["product_type"]]:
                    raise ReviewError("ISSUED_CHARTS_CONFLICT")
            product = items[0]["product_type"] if len(quantities) == 1 else None
            cur.execute(f"UPDATE {sync.SCHEMA}.marketplace_orders SET product_type = %s, "
                        "payment_status = CASE WHEN payment_status IN ('reset_once','reusable','test','permanent') "
                        "THEN payment_status ELSE 'paid' END, updated_at = NOW() "
                        "WHERE provider = %s AND order_code = %s RETURNING order_code",
                        (product, provider, order_code))
            if not cur.fetchone():
                raise ReviewError("ORDER_NOT_FOUND", 404)
            cur.execute(f"INSERT INTO {sync.SCHEMA}.stores_orders "
                        "(stores_order_no, provider, product_type, payment_status) VALUES (%s,%s,%s,'paid') "
                        "ON CONFLICT (stores_order_no) DO UPDATE SET product_type = EXCLUDED.product_type, "
                        "provider = EXCLUDED.provider, updated_at = NOW(), "
                        "payment_status = CASE WHEN stores_orders.payment_status IN "
                        "('reset_once','reusable','test','permanent') THEN stores_orders.payment_status ELSE 'paid' END "
                        "WHERE stores_orders.provider = EXCLUDED.provider OR "
                        "(stores_orders.provider IS NULL AND EXCLUDED.provider = 'stores')",
                        (order_code, provider, product))
        sync._upsert_order_entitlements(con, {"provider": provider, "stores_order_no": order_code,
                                              "line_items": items})
        order_holds.resolve_hold(con, provider=provider, order_code=order_code, approved_version=expected_version)
        con.commit()
        return {"ok": True, "already_approved": False, "review_version": expected_version}
    except Exception:
        con.rollback()
        raise
