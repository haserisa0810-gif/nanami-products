"""Read and parse live marketplace notification emails without writing to the DB.

The report is deliberately aggregate-only: it never prints subjects, order IDs,
buyer details, message IDs, or message bodies.
"""

from __future__ import annotations

import argparse
import email
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import stores_mail_sync as sync


def _fetch_messages(*, limit: int) -> tuple[str, list[bytes], dict[str, Any]]:
    backend = (os.getenv("STORES_MAIL_BACKEND") or "imap").strip().lower()
    stores_sender = (os.getenv("STORES_MAIL_FROM_FILTER", sync.STORES_FROM_DEFAULT) or "").strip()
    payhip_sender = (os.getenv("PAYHIP_MAIL_FROM_FILTER", sync.PAYHIP_FROM_DEFAULT) or "").strip()
    etsy_senders = sync._etsy_sender_filters(os.getenv("ETSY_MAIL_FROM_FILTER"))
    coconala_sender = (
        os.getenv("COCONALA_MAIL_FROM_FILTER", sync.COCONALA_FROM_DEFAULT) or ""
    ).strip()
    senders = [stores_sender, payhip_sender, *etsy_senders, coconala_sender]
    if backend == "gmail_api":
        from services.gmail_mail_api import fetch_order_messages

        messages = fetch_order_messages(senders=senders, limit=limit)
    elif backend == "zoho_api":
        from services.zoho_mail_api import fetch_order_messages

        messages = fetch_order_messages(senders=senders, limit=limit)
    elif backend == "imap":
        messages = sync._fetch_imap_order_messages(senders=senders, limit=limit)
    else:
        raise RuntimeError(f"Unsupported STORES_MAIL_BACKEND: {backend}")
    return backend, messages, {
        "stores": stores_sender,
        "payhip": payhip_sender,
        "etsy": etsy_senders,
        "coconala": coconala_sender,
    }


def _parse_message(raw_email: bytes) -> dict[str, Any] | None:
    msg = email.message_from_bytes(raw_email)
    from_value = sync._decode_header(msg.get("From"))
    subject = sync._decode_header(msg.get("Subject"))
    body = sync._extract_text(msg)
    received_at = sync._parse_datetime(msg.get("Date"))
    message_id = sync._decode_header(msg.get("Message-Id") or msg.get("Message-ID")) or None
    return (
        sync._parse_coconala_mail(subject, body, message_id, received_at, from_value)
        or sync._parse_etsy_mail(subject, body, message_id, received_at, from_value)
        or sync._parse_payhip_mail(subject, body, message_id, received_at, from_value)
        or sync._parse_stores_mail(subject, body, message_id, received_at, from_value)
    )


def build_redacted_report(*, limit: int) -> dict[str, Any]:
    backend, messages, _senders = _fetch_messages(limit=limit)
    providers: Counter[str] = Counter()
    products: Counter[str] = Counter()
    quantity_totals: Counter[str] = Counter()
    unknown_products_by_provider: Counter[str] = Counter()
    parsed_count = 0
    multi_item_messages = 0
    multi_quantity_messages = 0
    unknown_product_messages = 0

    for raw_email in messages:
        parsed = _parse_message(raw_email)
        if not parsed:
            continue
        parsed_count += 1
        provider = str(parsed.get("provider") or "unknown")
        product_type = str(parsed.get("product_type") or "unknown")
        providers[provider] += 1
        products[product_type] += 1
        if product_type == "unknown":
            unknown_product_messages += 1
            unknown_products_by_provider[provider] += 1
        items = list(parsed.get("line_items") or [])
        if len(items) > 1:
            multi_item_messages += 1
        total_quantity = 0
        for item in items:
            try:
                quantity = max(1, min(int(item.get("quantity") or 1), 100))
            except (TypeError, ValueError):
                quantity = 1
            total_quantity += quantity
            item_product = str(item.get("product_type") or "unknown")
            quantity_totals[item_product] += quantity
        if total_quantity > max(1, len(items)):
            multi_quantity_messages += 1

    return {
        "ok": True,
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "backend": backend,
        "fetched": len(messages),
        "parsed": parsed_count,
        "unparsed": len(messages) - parsed_count,
        "providers": dict(sorted(providers.items())),
        "products": dict(sorted(products.items())),
        "unit_quantities": dict(sorted(quantity_totals.items())),
        "multi_item_messages": multi_item_messages,
        "multi_quantity_messages": multi_quantity_messages,
        "unknown_product_messages": unknown_product_messages,
        "unknown_products_by_provider": dict(sorted(unknown_products_by_provider.items())),
        "contains_customer_or_order_identifiers": False,
        "database_writes": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        report = build_redacted_report(limit=max(1, min(args.limit, 500)))
    except Exception as exc:  # noqa: BLE001 - CLI must return a safe diagnostic
        report = {
            "ok": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "contains_customer_or_order_identifiers": False,
            "database_writes": False,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
