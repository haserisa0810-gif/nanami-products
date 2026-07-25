"""
services/stores_mail_sync.py
----------------------------
STORES・Payhip・Etsyの購入完了メールをIMAPで取得し、注文番号を
nanami_products.stores_orders テーブルに登録する独立モジュール。

nanami-astroの routes_public_orders.py の実装をベースに、
nanami-productsの用途に合わせてシンプル化したもの。

依存: psycopg2（pg_store.py と同じ接続方式）
環境変数:
  STORES_MAIL_IMAP_HOST    (default: imap.gmail.com)
  STORES_MAIL_IMAP_PORT    (default: 993)
  STORES_MAIL_USERNAME     必須
  STORES_MAIL_PASSWORD     必須（Gmailはアプリパスワード）
  STORES_MAIL_FROM_FILTER  (default: hello@stores.jp)
  PAYHIP_MAIL_FROM_FILTER  (default: contact@payhip.com)
  ETSY_MAIL_FROM_FILTER    (default: emails@mail.etsy.com)
  STORES_MAIL_SYNC_TOKEN   Cloud Schedulerからの呼び出し認証トークン
"""

from __future__ import annotations

import email
import email.utils
import html
import imaplib
import os
import re
from datetime import datetime
from email.header import decode_header as _decode_header_raw
from email.message import Message
from typing import Any
import psycopg2
from psycopg2.extras import RealDictCursor

# ── 定数 ──────────────────────────────────────────────────────────

SCHEMA = "nanami_products"
STORES_FROM_DEFAULT = "hello@stores.jp"
PAYHIP_FROM_DEFAULT = "contact@payhip.com"
ETSY_FROM_DEFAULT = "emails@mail.etsy.com"

# STORESの通知メールを識別するパターン
_OWNER_NOTICE_PATTERN = re.compile(
    r"アイテムが購入されました|注文がありました|初売上おめでとうございます",
    re.I,
)
_PAID_HINT_PATTERN = re.compile(
    r"アイテムが購入されました|ご注文ありがとうございました|購入完了|"
    r"お支払いが完了|支払い完了|入金完了|PayPay|クレジットカード|"
    r"コンビニ決済|銀行振込",
    re.I,
)
# 10桁の数字 = STORES注文番号
_ORDER_NO_RE = re.compile(r"\b(\d{10})\b")
# 件名に含まれる注文番号パターン
_SUBJECT_ORDER_NO_RE = re.compile(
    r"[（(]\s*(?:オーダー番号|注文番号)\s*[：:]\s*([0-9]{10})\s*[)）]"
)
# 商品名コードからフォーム種別を判定する。STORESの商品名に
# [NP-WB] / [NP-WF] / [NP-WA] / [NP-WT] / [NP-SF] / [NP-SC] / [NP-TY] を入れておく前提。
# Payhip商品は [NP-AA]（小惑星addon）/ [NP-TA]（31日トランジットaddon）も使う
# （routes.PAYHIP_PRODUCTS と対応させること）。
_PRODUCT_CODE_PATTERNS = [
    (re.compile(r"[\[［【]?\s*NP[-_ ]?ACG\s*[\]］】]?", re.I), "acg_bundle"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WBA\s*[\]］】]?", re.I), "western_asteroids"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WBT\s*[\]］】]?", re.I), "western_transit"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WB\s*[\]］】]?", re.I), "western_basic"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WF\s*[\]］】]?", re.I), "western_full"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WA\s*[\]］】]?", re.I), "western_asteroids_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?AA\s*[\]］】]?", re.I), "western_asteroids_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WT\s*[\]］】]?", re.I), "western_31days_transit_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?TA\s*[\]］】]?", re.I), "western_31days_transit_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?SF\s*[\]］】]?", re.I), "shichu_fortune_cycles_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?SC\s*[\]］】]?", re.I), "shichu"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?TY\s*[\]］】]?", re.I), "transit_yaml"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?API\s*[\]］】]?", re.I), "api_key"),
]
# 旧商品名や手動テスト用の補助判定。通常運用では商品名コードを使う。
_PRODUCT_TYPE_PATTERNS = [
    (re.compile(r"ACG\s*(?:bundle|バンドル)|アストロカートグラフィ.*(?:bundle|バンドル)|astrocartography.*(?:bundle|premium)", re.I), "acg_bundle"),
    (re.compile(r"(?:基本|basic|core).*(?:小惑星|asteroids?)|(?:小惑星|asteroids?).*(?:基本|basic|core)", re.I), "western_asteroids"),
    (re.compile(r"(?:基本|basic|core).*(?:トランジット|transit)|(?:トランジット|transit).*(?:基本|basic|core)", re.I), "western_transit"),
    (re.compile(r"FULL|フル|プレミアム|premium", re.I), "western_full"),
    (re.compile(r"小惑星.*追加|追加.*小惑星|asteroids? addon|asteroids?追加", re.I), "western_asteroids_addon"),
    (re.compile(r"(31日|３１日|1ヶ月|１ヶ月|一ヶ月|トランジット).*追加|追加.*(31日|３１日|1ヶ月|１ヶ月|一ヶ月|トランジット)|transit.*addon", re.I), "western_31days_transit_addon"),
    (re.compile(r"(大運|流年).*追加|追加.*(大運|流年)|fortune cycles? addon", re.I), "shichu_fortune_cycles_addon"),
    (re.compile(r"四柱|しちゅう|シチュウ"), "shichu"),
    (re.compile(r"トランジット|transit|イベント|歴史", re.I), "transit_yaml"),
    (re.compile(r"API|クレジット|credits?", re.I), "api_key"),
    (re.compile(r"ライト|基本|ホロスコープ|western|basic", re.I), "western_basic"),
]
# ── DB接続（pg_store.py と同じ方式） ──────────────────────────────

def _get_conn():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL が未設定です")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=5)


# ── テーブル初期化 ────────────────────────────────────────────────

STORES_ORDERS_DDL = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.stores_orders (
    stores_order_no  TEXT        PRIMARY KEY,
    provider         TEXT,
    product_type     TEXT,
    amount           INTEGER,
    payment_status   TEXT        DEFAULT 'paid',
    mail_subject     TEXT,
    raw_message_id   TEXT,
    mail_received_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def ensure_table() -> None:
    """テーブルが存在しない場合は作成する。起動時に呼ぶ。"""
    con = _get_conn()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT to_regnamespace(%s) AS schema_oid", (SCHEMA,))
            if not cur.fetchone()["schema_oid"]:
                cur.execute(f"CREATE SCHEMA {SCHEMA}")
            cur.execute(STORES_ORDERS_DDL)
            cur.execute(f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS product_type TEXT")
            cur.execute(f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS provider TEXT")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _require_stores_orders_table(con) -> None:
    """同期時はDDLを実行せず、既存テーブルを使えることだけ確認する。"""
    with con.cursor() as cur:
        cur.execute(f"SELECT stores_order_no FROM {SCHEMA}.stores_orders LIMIT 0")


# ── メール解析ユーティリティ ──────────────────────────────────────

def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, charset in _decode_header_raw(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _extract_text(msg: Message) -> str:
    texts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = (part.get_content_type() or "").lower()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if ct == "text/plain":
                texts.append(content)
            elif ct == "text/html" and not texts:
                content = re.sub(r"<br\s*/?>", "\n", content, flags=re.I)
                content = re.sub(r"</p\s*>", "\n", content, flags=re.I)
                content = re.sub(r"<[^>]+>", " ", content)
                texts.append(html.unescape(content))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            texts.append(payload.decode(charset, errors="replace"))

    body = "\n".join(x for x in texts if x).strip()
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", raw, flags=re.I)
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _extract_first(patterns: list[str], text_value: str) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text_value, flags=re.I | re.M)
        if m:
            return (m.group(1) or "").strip()
    return None


def _extract_amount(text_value: str) -> int | None:
    patterns = [
        r"(?:Total|合計)\s*[：:]?\s*US\$\s*([0-9][0-9,]*)(?:\.[0-9]+)?",
        r"(?:Total|Amount)\s*[：:]?\s*(?:USD\s*)?[$＄]\s*([0-9][0-9,]*)(?:\.[0-9]+)?",
        r"(?:お支払い金額|合計金額|ご請求金額|金額|合計（税込）)\s*[：:]?\s*[¥￥]?\s*([0-9][0-9,]*)",
        r"[¥￥]\s*([0-9][0-9,]*)",
    ]
    for pat in patterns:
        m = re.search(pat, text_value, flags=re.I)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except Exception:
                pass
    return None


def _normalize_payhip_order_id(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    value = re.sub(r"(Order\s*ID|Invoice\s*Number|注文ID)\s*[：:]?\s*", "", value, flags=re.I)
    value = re.sub(r"[^A-Za-z0-9=_-]", "", value)
    return value or None


def _guess_product_type(subject: str, body: str) -> str | None:
    text = f"{subject}\n{body}"
    if re.search(r"[\[［【]?\s*NP[-_ ]?API\s*[\]］】]?", text, re.I):
        if re.search(r"お試し|trial|try|starter|ライト", text, re.I):
            return "api_key_trial"
        if re.search(r"standard|スタンダード|通常|APIクレジット|クレジット", text, re.I):
            return "api_key_standard"
        return "api_key"
    for pattern, product_type in _PRODUCT_CODE_PATTERNS:
        if pattern.search(text):
            return product_type
    for pattern, product_type in _PRODUCT_TYPE_PATTERNS:
        if pattern.search(text):
            return product_type
    return None


def _parse_stores_mail(
    subject: str,
    body: str,
    message_id: str | None,
    received_at: datetime | None,
    from_value: str,
) -> dict[str, object] | None:
    """
    STORESのオーナー通知メールを解析して辞書を返す。
    対象外メールは None を返す。
    """
    combined = f"{subject}\n{body}"
    combined_lower = combined.lower()
    if (
        "stores" not in combined_lower
        and "ストアーズ" not in combined
        and "オーダー番号" not in combined
        and "注文番号" not in combined
        and not _OWNER_NOTICE_PATTERN.search(combined)
        and not _PAID_HINT_PATTERN.search(combined)
    ):
        return None

    # 注文番号を抽出（件名 → 本文の順で探す）
    order_no = None
    m = _SUBJECT_ORDER_NO_RE.search(subject)
    if m:
        order_no = m.group(1)
    if not order_no:
        order_no = _extract_first(
            [
                r"オーダー番号[：:\s]*([0-9]{10})",
                r"注文番号[：:\s]*([0-9]{10})",
                r"注文ID[：:\s]*([0-9]{10})",
            ],
            combined,
        )
    if not order_no:
        m = _ORDER_NO_RE.search(combined)
        order_no = m.group(1) if m else None
    if not order_no:
        return None

    payment_status = "paid" if _OWNER_NOTICE_PATTERN.search(combined) or _PAID_HINT_PATTERN.search(combined) else "ordered"
    if "キャンセル" in combined:
        payment_status = "cancelled"

    return {
        "stores_order_no": order_no,
        "provider": "stores",
        "product_type": _guess_product_type(subject, body),
        "amount": _extract_amount(body),
        "mail_subject": subject,
        "raw_message_id": message_id,
        "mail_received_at": received_at,
        "payment_status": payment_status,
    }


def _parse_payhip_mail(
    subject: str,
    body: str,
    message_id: str | None,
    received_at: datetime | None,
    from_value: str,
) -> dict[str, object] | None:
    combined = f"{from_value}\n{subject}\n{body}"
    combined_lower = combined.lower()
    if (
        "payhip" not in combined_lower
        and "you've sold an item" not in combined_lower
        and "you have sold an item" not in combined_lower
        and "order id:" not in combined_lower
    ):
        return None

    order_id = _normalize_payhip_order_id(
        _extract_first(
            [
                r"Order\s*ID\s*[：:]\s*([A-Za-z0-9=_-]+)",
                r"Invoice\s*Number\s*[：:]\s*([A-Za-z0-9=_-]+)",
            ],
            combined,
        )
    )
    if not order_id:
        return None

    payment_status = "paid"
    if "cancelled" in combined_lower or "refunded" in combined_lower:
        payment_status = "cancelled"

    return {
        "stores_order_no": order_id,
        "provider": "payhip",
        "product_type": _guess_product_type(subject, body),
        "amount": _extract_amount(body),
        "mail_subject": subject,
        "raw_message_id": message_id,
        "mail_received_at": received_at,
        "payment_status": payment_status,
    }


def _parse_etsy_mail(
    subject: str,
    body: str,
    message_id: str | None,
    received_at: datetime | None,
    from_value: str,
) -> dict[str, object] | None:
    """Etsyのショップ向け注文通知メールを解析する。"""
    combined = f"{from_value}\n{subject}\n{body}"
    combined_lower = combined.lower()
    if (
        "etsy" not in combined_lower
        and "mail.etsy.com" not in combined_lower
        and "注文の詳細" not in combined
        and "order details" not in combined_lower
    ):
        return None

    order_no = _extract_first(
        [
            r"注文番号\s*[：:]\s*([0-9]{10})",
            r"Order\s*(?:number|#)\s*[：:#]?\s*([0-9]{10})",
        ],
        combined,
    )
    if not order_no:
        return None

    payment_status = "paid"
    if re.search(r"キャンセル|返金|cancelled|canceled|refunded", combined, re.I):
        payment_status = "cancelled"

    return {
        "stores_order_no": order_no,
        "provider": "etsy",
        "product_type": _guess_product_type(subject, body),
        "amount": _extract_amount(body),
        "mail_subject": subject,
        "raw_message_id": message_id,
        "mail_received_at": received_at,
        "payment_status": payment_status,
    }


# ── DB upsert ──────────────────────────────────────────────────────

def _upsert_order(con, parsed: dict[str, Any]) -> bool:
    """
    stores_ordersにupsert。
    新規登録の場合True、既存スキップの場合Falseを返す。
    """
    with con.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.stores_orders
                (stores_order_no, provider, product_type, amount, payment_status,
                 mail_subject, raw_message_id, mail_received_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (stores_order_no) DO UPDATE SET
                provider         = COALESCE(EXCLUDED.provider,         {SCHEMA}.stores_orders.provider),
                product_type     = COALESCE(EXCLUDED.product_type,     {SCHEMA}.stores_orders.product_type),
                amount           = COALESCE(EXCLUDED.amount,           {SCHEMA}.stores_orders.amount),
                payment_status   = CASE
                    WHEN EXCLUDED.payment_status = 'cancelled' THEN 'cancelled'
                    WHEN EXCLUDED.payment_status = 'paid' THEN 'paid'
                    ELSE COALESCE({SCHEMA}.stores_orders.payment_status, EXCLUDED.payment_status)
                END,
                mail_subject     = COALESCE(EXCLUDED.mail_subject,     {SCHEMA}.stores_orders.mail_subject),
                raw_message_id   = COALESCE(EXCLUDED.raw_message_id,   {SCHEMA}.stores_orders.raw_message_id),
                mail_received_at = COALESCE(EXCLUDED.mail_received_at, {SCHEMA}.stores_orders.mail_received_at),
                updated_at       = NOW()
            RETURNING (xmax = 0) AS is_new
            """,
            (
                parsed["stores_order_no"],
                parsed.get("provider"),
                parsed.get("product_type"),
                parsed.get("amount"),
                parsed.get("payment_status", "paid"),
                parsed.get("mail_subject"),
                parsed.get("raw_message_id"),
                parsed.get("mail_received_at"),
            ),
        )
        row = cur.fetchone()
        return bool(row and row["is_new"])


# ── メイン同期関数 ─────────────────────────────────────────────────

def sync(*, limit: int = 100) -> dict[str, Any]:
    """
    IMAPでSTORES・Payhip・Etsyメールを取得し、stores_ordersに登録する。

    Returns:
        {ok, fetched, parsed, inserted, skipped, errors, message}
    """
    host     = os.getenv("STORES_MAIL_IMAP_HOST", "imap.gmail.com")
    port     = int(os.getenv("STORES_MAIL_IMAP_PORT", "993"))
    username = (os.getenv("STORES_MAIL_USERNAME") or "").strip()
    password = (os.getenv("STORES_MAIL_PASSWORD") or "").strip()
    from_filter = (os.getenv("STORES_MAIL_FROM_FILTER", STORES_FROM_DEFAULT) or "").strip()
    payhip_from_filter = (os.getenv("PAYHIP_MAIL_FROM_FILTER", PAYHIP_FROM_DEFAULT) or "").strip()
    etsy_from_filter = (os.getenv("ETSY_MAIL_FROM_FILTER", ETSY_FROM_DEFAULT) or "").strip()

    counters = dict(fetched=0, parsed=0, inserted=0, skipped=0, errors=0)

    if not username or not password:
        return {**counters, "ok": False, "message": "STORES_MAIL_USERNAME/PASSWORD が未設定です"}

    conn_imap = None
    con_db = None
    try:
        conn_imap = imaplib.IMAP4_SSL(host, port)
        conn_imap.login(username, password)
        conn_imap.select("INBOX")

        status = "OK"
        search_ids: list[bytes] = []
        for candidate in dict.fromkeys([from_filter, payhip_from_filter, etsy_from_filter]):
            if not candidate:
                continue
            candidate_status, candidate_data = conn_imap.search(None, "FROM", f'"{candidate}"')
            if candidate_status == "OK" and candidate_data and candidate_data[0]:
                search_ids.extend(candidate_data[0].split())

        if not search_ids:
            status, data = conn_imap.search(None, "ALL")
            if status == "OK" and data and data[0]:
                search_ids = data[0].split()
        if status != "OK":
            return {**counters, "ok": False, "message": "IMAP検索失敗"}

        ids = sorted(set(search_ids), key=lambda item: int(item))
        recent_ids = list(reversed(ids[-limit:]))

        con_db = _get_conn()
        _require_stores_orders_table(con_db)

        for msg_id in recent_ids:
            status, payload = conn_imap.fetch(msg_id, "(RFC822)")
            if status != "OK" or not payload or not payload[0]:
                counters["errors"] += 1
                continue

            counters["fetched"] += 1
            raw_email = payload[0][1]
            msg = email.message_from_bytes(raw_email)

            from_value  = _decode_header(msg.get("From"))
            subject     = _decode_header(msg.get("Subject"))
            body        = _extract_text(msg)
            received_at = _parse_datetime(msg.get("Date"))
            message_id  = _decode_header(msg.get("Message-Id") or msg.get("Message-ID")) or None

            # STORESメール以外をスキップ
            combined_lower = f"{from_value}\n{subject}\n{body}".lower()
            if (
                from_filter.lower() not in combined_lower
                and payhip_from_filter.lower() not in combined_lower
                and etsy_from_filter.lower() not in combined_lower
                and "payhip" not in combined_lower
                and "etsy" not in combined_lower
                and "you've sold an item" not in combined_lower
                and "you have sold an item" not in combined_lower
                and "order id:" not in combined_lower
                and "stores" not in combined_lower
                and "ストアーズ" not in f"{from_value}{subject}{body}"
                and "アイテムが購入されました" not in body
                and "注文番号" not in body
                and "オーダー番号" not in body
            ):
                counters["skipped"] += 1
                continue

            parsed = (
                _parse_etsy_mail(subject, body, message_id, received_at, from_value)
                or _parse_payhip_mail(subject, body, message_id, received_at, from_value)
                or _parse_stores_mail(subject, body, message_id, received_at, from_value)
            )
            if not parsed:
                counters["skipped"] += 1
                continue

            counters["parsed"] += 1

            is_new = _upsert_order(con_db, parsed)
            if is_new:
                counters["inserted"] += 1
            else:
                counters["skipped"] += 1

        con_db.commit()
        return {**counters, "ok": True, "message": ""}

    except Exception as e:
        if con_db:
            con_db.rollback()
        return {**counters, "ok": False, "message": str(e)}
    finally:
        if conn_imap:
            try:
                conn_imap.logout()
            except Exception:
                pass
        if con_db:
            con_db.close()


# ── 注文番号照合（redeem_post から呼ぶ） ──────────────────────────

def verify_order_no(order_no: str) -> tuple[str, dict | None]:
    """
    注文番号がstores_ordersに存在するか照合する。

    Returns:
        ("ok", row)          存在して未使用
        ("not_found", None)  存在しない
        ("already_used", row) 既にcharts/redemptionsに登録済み
        ("cancelled", row)    キャンセル扱い
        ("reusable", row)     テスト・身内用の再利用可能番号
    """
    con = _get_conn()
    try:
        with con.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {SCHEMA}.stores_orders WHERE stores_order_no = %s",
                (order_no,),
            )
            row = cur.fetchone()
            if not row:
                return "not_found", None

            payment_status = (row.get("payment_status") or "").lower()
            if payment_status == "cancelled":
                return "cancelled", dict(row)
            if payment_status == "reset_once":
                return "ok", dict(row)
            if payment_status in {"reusable", "test", "permanent"}:
                return "reusable", dict(row)

            # redemptionsに同じ注文番号があれば使用済み
            cur.execute(
                f"SELECT order_code FROM {SCHEMA}.redemptions WHERE order_code = %s",
                (order_no,),
            )
            used = cur.fetchone()
            if used:
                return "already_used", dict(row)

        return "ok", dict(row)
    finally:
        con.close()
