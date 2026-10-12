"""Read-only notification audit; saves aggregate facts, never mail or secrets.

Does not call sync(), connect to a database, acknowledge mail, or send mail.
Cloud configuration and OAuth credentials stay in this process's memory.
Requires the local pre-catalog snapshot in tmp/product-catalog-before/ for
comparison. Recognized code candidates are not proof of purchased items.
"""
from __future__ import annotations

import ast
import email
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services import stores_mail_sync as sync, product_catalog
from services.gmail_mail_api import GmailApiClient, GmailApiConfig


def cloud_mail_config() -> GmailApiConfig:
    gcloud = shutil.which("gcloud.cmd")
    if not gcloud:
        raise RuntimeError("Cloud SDK unavailable")
    result = subprocess.run([gcloud, "run", "services", "describe", "nanami-products",
        "--region", "asia-northeast1", "--project", "nanami-astro", "--format=json"],
        capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError("Cloud configuration read failed")
    service = json.loads(result.stdout)
    allowed = {"GMAIL_API_CLIENT_ID", "GMAIL_API_CLIENT_SECRET", "GMAIL_API_REFRESH_TOKEN",
        "GMAIL_API_EXPECTED_EMAIL", "GMAIL_API_TOKEN_URL", "GMAIL_API_BASE_URL"}
    entries = service["spec"]["template"]["spec"]["containers"][0]["env"]
    backend = next((entry.get("value") for entry in entries
                    if entry["name"] == "STORES_MAIL_BACKEND"), None)
    if backend != "gmail_api":
        raise RuntimeError("Production mailbox does not use the Gmail read-only adapter")
    values = {}
    for entry in entries:
        if entry["name"] not in allowed:
            continue
        if "value" in entry:
            values[entry["name"]] = entry["value"]
            continue
        ref = entry["valueFrom"]["secretKeyRef"]
        secret = subprocess.run([gcloud, "secrets", "versions", "access", ref["key"],
            "--secret", ref["name"], "--project", "nanami-astro"],
            capture_output=True, timeout=30)
        if secret.returncode:
            raise RuntimeError("Mail credential read failed")
        values[entry["name"]] = secret.stdout.decode("utf-8").strip()
    # Only whitelisted mail configuration is set, never DATABASE_URL or sync tokens.
    os.environ.update(values)
    return GmailApiConfig.from_env()


def previous_classifier(provider):
    path = ROOT / "tmp/product-catalog-before/services/stores_mail_sync.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"_PRODUCT_CODE_PATTERNS", "_PRODUCT_TYPE_PATTERNS"}
    selected = [node for node in tree.body if (
        isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names
                                             for target in node.targets)
        or isinstance(node, ast.FunctionDef) and node.name in {"_guess_product_type", "_etsy_product_type"})]
    namespace = {"re": re}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_etsy_product_type" if provider == "etsy" else "_guess_product_type"]


def audit_provider(client, provider, senders, limit=10):
    raw_messages = client.fetch_original_messages(senders=senders, limit=limit)
    old_guess = previous_classifier(provider)
    counters, codes, differences, dates, structures = Counter(), Counter(), Counter(), [], []
    for raw in raw_messages:
        message = email.message_from_bytes(raw)
        subject = sync._decode_header(message.get("Subject"))
        sender = sync._decode_header(message.get("From"))
        body = sync._extract_text(message)
        parsed = getattr(sync, f"_parse_{provider}_mail")(subject, body, None, None, sender)
        if not parsed:
            counters["not_order_notice"] += 1
            continue
        counters["parsed_orders"] += 1
        date = sync._parse_datetime(message.get("Date"))
        if date:
            dates.append(date.date().isoformat())
        before, after = old_guess(subject, body), parsed.get("product_type")
        items = parsed.get("line_items") or []
        if len(items) > 1:
            code_lines = []
            for line in body.splitlines():
                products = [product_catalog.product_for_sku(token)
                            for token in product_catalog.code_tokens(line)]
                known = [product.code for product in products if product]
                if known:
                    code_lines.append({"codes": known,
                        "product_field_label": bool(re.match(
                            r"^\s*(?:商品|商品名|アイテム|アイテム名|Product|Item)\s*[:：]", line, re.I)),
                        "quantity_field_on_same_line": bool(re.search(r"Quantity|数量|個数|Qty", line, re.I))})
            structures.append({"code_lines": code_lines,
                "subject_codes": [product.code for token in product_catalog.code_tokens(subject)
                    if (product := product_catalog.product_for_sku(token))]})
        if after or items:
            counters["recognized_code_candidates_available"] += 1
        else:
            counters["identity_unverified"] += 1
        if before != after:
            differences[f"{before or 'unclassified'} -> {after or 'unclassified'}"] += 1
        if before and not after and not items:
            counters["lost_classification"] += 1
        counters["multiple_items"] += int(len(items) > 1)
        counters["quantity_above_one"] += int(any(item["quantity"] > 1 for item in items))
        for token in product_catalog.code_tokens(f"{subject}\n{body}"):
            product = product_catalog.product_for_sku(token)
            if product:
                codes[product.code] += 1
        for key, pattern in {
            "sku_label_present": r"(?im)^\s*SKU\s*[:：]",
            "product_id_label_present": r"(?im)^\s*(?:Product|Listing|Item)[ _-]*ID\s*[:：]",
            "product_link_present": r"https?://(?:www\.)?(?:payhip\.com/b/|[^\s/]+\.stores\.jp/items/|etsy\.com/listing/)",
        }.items():
            counters[key] += int(bool(re.search(pattern, body)))
    return {"fetched": len(raw_messages), "counts": dict(counters),
        "recognized_code_occurrences": dict(codes), "classification_differences": dict(differences),
        "multiple_code_line_structures": structures,
        "notice_date_range": [min(dates), max(dates)] if dates else None}


def main():
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
        "source": "current Cloud Run Gmail configuration; read-only original mail",
        "database_access": False, "mail_mutations": False,
        "customer_or_order_identifiers_saved": False, "providers": {}}
    try:
        client = GmailApiClient(cloud_mail_config())
        for provider, senders in [
            ("payhip", [sync.PAYHIP_FROM_DEFAULT]),
            ("stores", [sync.STORES_FROM_DEFAULT]),
            ("etsy", sync._etsy_sender_filters()),
        ]:
            result = audit_provider(client, provider, senders)
            report["providers"][provider] = result
            print(json.dumps({"provider": provider, "result": result}), flush=True)
        report["ok"] = True
    except Exception as exc:
        # No raw exception text: do not risk exposing response bodies or credentials.
        report.update(ok=False, error_type=type(exc).__name__)
    target = ROOT / "docs/marketplace_notification_audit_20261011.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "report": str(target)}), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
