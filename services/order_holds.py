"""Durable operator notices for unverified orders; no mail/customer data."""
from __future__ import annotations

import logging
import hashlib
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from psycopg2.extras import Json

SCHEMA = "nanami_products"
logger = logging.getLogger(__name__)
REASONS = {
    "purchase_fields_missing": "購入明細のフィールドを確認できません",
    "unknown_product_code": "購入明細の商品コードが未登録です",
    "product_code_missing": "購入明細に商品コードがありません",
    "ambiguous_product_field": "購入明細のコードを一意に特定できません",
    "invalid_quantity": "購入数量を確認できません",
    "non_purchase_notification": "購入通知ではありません（ダウンロード通知等）",
    "purchase_details_conflict": "再通知の購入明細が保存済みの発行権と一致しません",
}
DDL = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.marketplace_order_holds (
    provider TEXT NOT NULL,
    order_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'held' CHECK (status IN ('held', 'resolved')),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notification_status TEXT NOT NULL DEFAULT 'pending' CHECK (notification_status IN ('pending', 'sent')),
    notification_attempts INTEGER NOT NULL DEFAULT 0,
    last_notification_at TIMESTAMPTZ,
    PRIMARY KEY (provider, order_code)
)
;
ALTER TABLE {SCHEMA}.marketplace_order_holds
    ADD COLUMN IF NOT EXISTS candidate JSONB,
    ADD COLUMN IF NOT EXISTS review_version BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS review_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS approved_version BIGINT,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ
;
CREATE TABLE IF NOT EXISTS {SCHEMA}.marketplace_processed_notices (
    provider TEXT NOT NULL,
    order_code TEXT NOT NULL,
    notice_fingerprint TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (provider, order_code, notice_fingerprint)
)
"""


def audit_download_notice(*, order_code: str, source_id: str | None) -> None:
    """Privacy-safe audit only: no customer/body/source-ID text or DB writes."""
    safe_order = order_code if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", order_code) else "invalid"
    source_hash = hashlib.sha256(str(source_id or "").encode()).hexdigest() if source_id else "absent"
    logger.info("purchase_notice_ignored provider=payhip kind=download order_code=%s source_hash=%s",
                safe_order, source_hash)


def lock_order(cur, *, provider: str, order_code: str, schema: str = SCHEMA) -> None:
    """Same transaction lock for sync, approval and redemption, even before INSERT."""
    key = int.from_bytes(hashlib.sha256(f"{schema}:{provider}:{order_code}".encode()).digest()[:8],
                         byteorder="big", signed=True)
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (key,))


def get_review(con, *, provider: str, order_code: str) -> dict | None:
    with con.cursor() as cur:
        cur.execute(f"SELECT status, reason, candidate, review_version, approved_version, approved_at, "
                    f"review_history FROM {SCHEMA}.marketplace_order_holds "
                    "WHERE provider = %s AND order_code = %s FOR UPDATE", (provider, order_code))
        row = cur.fetchone()
        return dict(row) if row else None


def remember_notice(con, parsed: dict) -> bool:
    """Ignore exact source-message replays in the same transaction as ingestion.

    Changed purchase data with the same message ID is a different fingerprint.
    No source ID means no replay claim: process conservatively instead.
    """
    source_id = parsed.get("raw_message_id")
    if not isinstance(source_id, str) or not source_id.strip():
        return True
    evidence = {key: parsed.get(key) for key in
                ("line_items", "product_type", "purchase_evidence", "payment_status", "hold_reason")}
    fingerprint = hashlib.sha256((source_id + "\n" + json.dumps(evidence, sort_keys=True,
                                 ensure_ascii=True, separators=(",", ":"))).encode()).hexdigest()
    with con.cursor() as cur:
        cur.execute(f"INSERT INTO {SCHEMA}.marketplace_processed_notices "
                    "(provider, order_code, notice_fingerprint) VALUES (%s,%s,%s) "
                    "ON CONFLICT (provider, order_code, notice_fingerprint) DO NOTHING "
                    "RETURNING notice_fingerprint",
                    (parsed["provider"], parsed["stores_order_no"], fingerprint))
        return cur.fetchone() is not None


def save_candidate(con, parsed: dict) -> None:
    # Only calculated purchase identities; no raw mail, customer name or address.
    evidence = parsed.get("purchase_evidence")
    # The mail parser returns verified field names, not a boolean. Preserve its
    # result as a boolean for review, without treating arbitrary truthy values
    # (such as a string from a malformed caller) as purchase evidence.
    verified = evidence is True or (
        isinstance(evidence, list) and bool(evidence)
        and all(isinstance(field, str) and bool(field.strip()) for field in evidence)
    )
    candidate = {
        "purchase_evidence": verified,
        "payment_status": parsed.get("payment_status"),
        "hold_reason": parsed.get("hold_reason"),
        "items": [{key: item.get(key) for key in ("line_item_key", "sku", "product_type", "quantity")}
                  for item in parsed.get("line_items", [])],
    }
    with con.cursor() as cur:
        cur.execute(f"""UPDATE {SCHEMA}.marketplace_order_holds
            SET review_history = review_history || jsonb_build_array(jsonb_build_object(
                    'at', NOW(), 'before', candidate, 'after', %s::jsonb)),
                candidate = %s, review_version = review_version + 1, last_seen_at = NOW()
            WHERE provider = %s AND order_code = %s AND status = 'held'
              AND candidate IS DISTINCT FROM %s::jsonb""",
            (Json(candidate), Json(candidate), parsed["provider"], parsed["stores_order_no"], Json(candidate)))


def record_hold(con, *, provider: str, order_code: str, reason: str) -> bool:
    if provider not in {"stores", "payhip", "etsy", "coconala"}:
        raise ValueError("Unsupported hold provider")
    if not re.fullmatch(r"[A-Za-z0-9=_-]{1,160}", order_code) or reason not in REASONS:
        raise ValueError("Invalid hold identity/reason")
    with con.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {SCHEMA}.marketplace_order_holds (provider, order_code, reason)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, order_code) DO UPDATE SET
                reason = EXCLUDED.reason, status = 'held', last_seen_at = NOW(),
                notification_status = CASE
                    WHEN {SCHEMA}.marketplace_order_holds.status = 'resolved'
                      OR {SCHEMA}.marketplace_order_holds.reason <> EXCLUDED.reason THEN 'pending'
                    ELSE {SCHEMA}.marketplace_order_holds.notification_status END,
                last_notification_at = CASE
                    WHEN {SCHEMA}.marketplace_order_holds.status = 'resolved'
                      OR {SCHEMA}.marketplace_order_holds.reason <> EXCLUDED.reason THEN NULL
                    ELSE {SCHEMA}.marketplace_order_holds.last_notification_at END
            RETURNING (xmax = 0) AS is_new
        """, (provider, order_code, reason))
        row = cur.fetchone()
        return bool(row and row["is_new"])


def resolve_hold(con, *, provider: str, order_code: str, approved_version: int) -> None:
    with con.cursor() as cur:
        cur.execute(f"""
            UPDATE {SCHEMA}.marketplace_order_holds
            SET status = 'resolved', last_seen_at = NOW(), approved_at = NOW(), approved_version = %s
            WHERE provider = %s AND order_code = %s AND status = 'held' AND review_version = %s
            RETURNING order_code
        """, (approved_version, provider, order_code, approved_version))
        if not cur.fetchone():
            raise ValueError("Review changed before approval")


def notify_operator(*, provider: str, order_code: str, reason: str) -> None:
    # Fixed enums and validated order IDs only; never log the parsed mail dict.
    if provider not in {"stores", "payhip", "etsy", "coconala"} or reason not in REASONS:
        return
    if not re.fullmatch(r"[A-Za-z0-9=_-]{1,160}", order_code):
        return
    logger.warning("marketplace_order_held provider=%s order_id=%s reason=%s", provider, order_code, reason)


def list_holds(con, *, limit: int = 100, offset: int = 0) -> list[dict]:
    with con.cursor() as cur:
        cur.execute(f"""
            SELECT provider, order_code, reason, first_seen_at, last_seen_at,
                   notification_status, notification_attempts, review_version
            FROM {SCHEMA}.marketplace_order_holds WHERE status = 'held'
            ORDER BY first_seen_at DESC, provider, order_code LIMIT %s OFFSET %s
        """, (max(1, min(limit, 200)), max(0, offset)))
        return [{**dict(row), "reason_label": REASONS.get(row["reason"], "確認が必要です")}
                for row in cur.fetchall()]


def notification_config() -> dict | None:
    """SMTP is opt-in. Missing configuration leaves durable notices pending."""
    names = ["ORDER_HOLD_NOTIFY_TO", "ORDER_HOLD_NOTIFY_FROM", "ORDER_HOLD_SMTP_HOST",
             "ORDER_HOLD_SMTP_USERNAME", "ORDER_HOLD_SMTP_PASSWORD"]
    values = {name: os.getenv(name, "").strip() for name in names}
    if not all(values.values()):
        return None
    for name in ["ORDER_HOLD_NOTIFY_TO", "ORDER_HOLD_NOTIFY_FROM"]:
        if not re.fullmatch(r"[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+", values[name]):
            raise ValueError("Invalid operator notification address")
    mode = os.getenv("ORDER_HOLD_SMTP_SECURITY", "ssl").strip().lower()
    if mode not in {"ssl", "starttls"}:
        raise ValueError("SMTP encryption is required")
    port = int(os.getenv("ORDER_HOLD_SMTP_PORT", "465" if mode == "ssl" else "587"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid SMTP port")
    return {**values, "mode": mode, "port": port}


def send_notification_mail(config: dict, row: dict) -> None:
    message = EmailMessage()
    message["From"] = config["ORDER_HOLD_NOTIFY_FROM"]
    message["To"] = config["ORDER_HOLD_NOTIFY_TO"]
    message["Subject"] = "nanami-products：注文の発行を保留しました"
    message.set_content(
        f"販売サイト: {row['provider']}\n注文ID: {row['order_code']}\n"
        f"保留理由: {REASONS[row['reason']]} ({row['reason']})\n"
        "管理画面の保留一覧で確認してください。今回の通知に基づく追加発行は保留しています。\n"
        "既存の購入権限・発行物は変更していません。\n")
    factory = smtplib.SMTP_SSL if config["mode"] == "ssl" else smtplib.SMTP
    kwargs = {"timeout": 10}
    if config["mode"] == "ssl":
        kwargs["context"] = ssl.create_default_context()
    with factory(config["ORDER_HOLD_SMTP_HOST"], config["port"], **kwargs) as client:
        if config["mode"] == "starttls":
            client.starttls(context=ssl.create_default_context())
        client.login(config["ORDER_HOLD_SMTP_USERNAME"], config["ORDER_HOLD_SMTP_PASSWORD"])
        client.send_message(message)


def dispatch_pending_notices(con, *, limit: int = 3) -> dict:
    config = notification_config()
    if not config:
        return {"status": "unconfigured", "sent": 0, "failed": 0}
    result = {"status": "configured", "sent": 0, "failed": 0}
    try:
        with con.cursor() as cur:
            cur.execute(f"""
                SELECT provider, order_code, reason FROM {SCHEMA}.marketplace_order_holds
                WHERE status = 'held' AND notification_status = 'pending'
                  AND (last_notification_at IS NULL OR last_notification_at < NOW() - INTERVAL '5 minutes')
                ORDER BY first_seen_at FOR UPDATE SKIP LOCKED LIMIT %s
            """, (max(1, min(limit, 10)),))
            for row in cur.fetchall():
                sent = False
                try:
                    send_notification_mail(config, dict(row))
                    sent = True
                    result["sent"] += 1
                except Exception as exc:
                    result["failed"] += 1
                    logger.error("order_hold_email_failed provider=%s order_id=%s error_type=%s",
                                 row["provider"], row["order_code"], type(exc).__name__)
                cur.execute(f"""
                    UPDATE {SCHEMA}.marketplace_order_holds
                    SET notification_status = %s, notification_attempts = notification_attempts + 1,
                        last_notification_at = NOW()
                    WHERE provider = %s AND order_code = %s
                """, ("sent" if sent else "pending", row["provider"], row["order_code"]))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return result
