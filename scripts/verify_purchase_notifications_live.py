"""Read-only original-mail regression; writes only anonymous purchase fields.

Expected codes below are the fixed observations from the manual structural audit,
not values obtained from the current parser. Seller order API reconciliation is
still separate. No sync(), database, mail mutation, or raw mail persistence.
"""
from __future__ import annotations

import email
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_marketplace_notifications import cloud_mail_config
from services.gmail_mail_api import GmailApiClient
from services import stores_mail_sync as sync

EXPECTED = {
    "payhip": [["NP-WB"], ["NP-WB"], ["NP-WF"], ["NP-AA"], ["NP-AA"],
               ["NP-WF", "NP-WB", "NP-AA", "NP-TA"],
               ["NP-WF", "NP-WB", "NP-WA", "NP-WT"], []],
    "stores": [["NP-WF"], ["NP-WB"], ["NP-WB"], ["NP-SC"], ["NP-SC"], ["NP-SC"]],
    "etsy": [[]],
}


def anonymous_fixture(provider, ordinal, body, subject):
    lines = [line.strip() for line in html.unescape(body).splitlines() if line.strip()]
    codes = re.findall(r"NP-[A-Z0-9-]+", body)
    if provider == "payhip":
        download = bool(re.search(r"requested a download|been\s+downloaded", f"{subject}\n{body}", re.I))
        heading = "items have been downloaded:" if download else "items have been purchased:"
        result = f"The following\n{heading}\nBuyer: fixture@example.invalid\nDate: 1 January 2000\nOrder ID: Fixture{ordinal}\n"
        for code in codes:
            result += f"Fixture product [{code}]\n&nbsp;\n&#36;1.00\n"
        result += "Total\n&#36;1.00\nView order details\n"
        fixture_subject = "Someone Requested a Download!" if download else "You've Sold An Item!"
        reason = "non_purchase_notification" if download else None
    elif provider == "stores":
        if ordinal <= 5:
            result = "アイテムが購入されました\n--------------------\n"
            for index, code in enumerate(codes, 1):
                result += f"{index}. [{code}] Fixture\nhttps://fixture.stores.jp/items/fixture\n￥100 x 1 = ￥100\n"
            result += "小計：￥100\n合計：￥100\n--------------------\n"
        else:
            result = f"お問い合わせは購入後にお願いします。\n注文番号：9123456789\n注文商品：\n・[{codes[0]}] Fixture\nお問い合わせ：\nFixture\n"
        fixture_subject = "【STORES】アイテムが購入されました（オーダー番号：9123456789）"
        reason = None
    else:
        result = "注文の詳細\n注文番号：9123456789\n商品：Fixture\n個数：1\n合計：US$1.00\n"
        fixture_subject, reason = "Etsy order details", "product_code_missing"
    return {"provider": provider, "sample": ordinal, "subject": fixture_subject,
            "body": result, "expected_codes": EXPECTED[provider][ordinal - 1], "expected_hold": reason,
            "provenance": "anonymized minimal fields from original mail; identifiers and prices replaced"}


def main():
    fixtures, results = [], []
    client = GmailApiClient(cloud_mail_config())
    for provider, senders in [("payhip", [sync.PAYHIP_FROM_DEFAULT]), ("stores", [sync.STORES_FROM_DEFAULT]),
                              ("etsy", sync._etsy_sender_filters())]:
        ordinal = 0
        for raw in client.fetch_original_messages(senders=senders, limit=10):
            msg = email.message_from_bytes(raw)
            subject, sender, body = sync._decode_header(msg.get("Subject")), sync._decode_header(msg.get("From")), sync._extract_text(msg)
            parsed = getattr(sync, f"_parse_{provider}_mail")(subject, body, None, None, sender)
            if not parsed:
                continue
            ordinal += 1
            if ordinal > len(EXPECTED[provider]):
                raise RuntimeError("Notification sample changed; repeat the structural audit")
            fixture = anonymous_fixture(provider, ordinal, body, subject)
            fixtures.append(fixture)
            actual = [item["sku"] for item in parsed["line_items"]]
            results.append({"provider": provider, "sample": ordinal, "expected_codes": fixture["expected_codes"],
                            "actual_codes": actual, "hold_reason": parsed["hold_reason"],
                            "evidence": parsed["purchase_evidence"],
                            "pass": actual == fixture["expected_codes"] and parsed["hold_reason"] == fixture["expected_hold"]})
        if ordinal != len(EXPECTED[provider]):
            raise RuntimeError("Notification sample count changed; repeat the structural audit")
    target = ROOT / "tests/fixtures/marketplace/notifications_anonymous_20261011.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"original_mail_count": len(results), "database_access": False, "mail_mutations": False,
              "results": results, "pass": all(result["pass"] for result in results)}
    (ROOT / "docs/purchase_notifications_live_regression_20261011.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"pass": False, "error_type": type(exc).__name__}))
        raise SystemExit(1)
