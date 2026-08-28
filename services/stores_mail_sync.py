"""
services/stores_mail_sync.py
----------------------------
STORES・Payhip・Etsy・ココナラの購入完了メールをIMAPで取得し、注文番号を
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
  ETSY_MAIL_FROM_FILTER    (default: transaction@etsy.com; legacy sender also searched)
  COCONALA_MAIL_FROM_FILTER (default: no-reply@mail.coconala.com)
  STORES_MAIL_SYNC_TOKEN   Cloud Schedulerからの呼び出し認証トークン
"""

from __future__ import annotations

import email
import email.utils
import hashlib
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
ETSY_FROM_DEFAULT = "transaction@etsy.com"
ETSY_FROM_LEGACY = "emails@mail.etsy.com"
COCONALA_FROM_DEFAULT = "no-reply@mail.coconala.com"

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
    (re.compile(r"[\[［【]?\s*NP[-_ ]?WL\s*[\]］】]?", re.I), "western_long_term_transits_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?SF\s*[\]］】]?", re.I), "shichu_fortune_cycles_addon"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?SC\s*[\]］】]?", re.I), "shichu"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?TY\s*[\]］】]?", re.I), "transit_yaml"),
    (re.compile(r"[\[［【]?\s*NP[-_ ]?API\s*[\]］】]?", re.I), "api_key"),
]
_PRODUCT_CODE_CAPTURE_RE = re.compile(
    r"\bNP[-_ ]?(ACG|WBA|WBT|API|WB|WF|WA|AA|WT|TA|WL|SF|SC|TY)"
    r"(?:[-_ ]?(JA|EN|ES|DE))?\b",
    re.I,
)
_QUANTITY_RE = re.compile(
    r"(?:個数|数量|Qty|Quantity)\s*[：:]?\s*([0-9]+)",
    re.I,
)
# 旧商品名や手動テスト用の補助判定。通常運用では商品名コードを使う。
_PRODUCT_TYPE_PATTERNS = [
    (re.compile(r"ACG\s*(?:bundle|バンドル)|アストロカートグラフィ.*(?:bundle|バンドル)|astrocartography.*(?:bundle|premium)", re.I), "acg_bundle"),
    (re.compile(r"(?:基本|basic|core).*(?:小惑星|asteroids?)|(?:小惑星|asteroids?).*(?:基本|basic|core)", re.I), "western_asteroids"),
    (re.compile(r"(?:基本|basic|core).*(?:トランジット|transit)|(?:トランジット|transit).*(?:基本|basic|core)", re.I), "western_transit"),
    (re.compile(
        r"(?=[\s\S]*(?:birth\s+chart|natal\s+chart|出生図|ホロスコープ))"
        r"(?=[\s\S]*(?:transits?|トランジット))"
        r"(?=[\s\S]*(?:asteroids?|小惑星))",
        re.I,
    ), "western_full"),
    (re.compile(r"FULL|フル|プレミアム|premium", re.I), "western_full"),
    (re.compile(r"小惑星.*追加|追加.*小惑星|asteroids? addon|asteroids?追加", re.I), "western_asteroids_addon"),
    # STORESの商品コードが通知本文に含まれない場合でも、38日／月替わりの
    # トランジット追加商品を、イベント単発の transit_yaml と取り違えない。
    (re.compile(
        r"(?:38\s*日|３８\s*日|月替わり|指定月|38[- ]?day).*(?:トランジット|transit)"
        r"|(?:トランジット|transit).*(?:38\s*日|３８\s*日|月替わり|指定月|38[- ]?day)"
        r"|(?:トランジット|transit).*(?:追加|add[- ]?on)"
        r"|(?:追加|add[- ]?on).*(?:トランジット|transit)",
        re.I,
    ), "western_31days_transit_addon"),
    (re.compile(r"(31日|３１日|1ヶ月|１ヶ月|一ヶ月|トランジット).*追加|追加.*(31日|３１日|1ヶ月|１ヶ月|一ヶ月|トランジット)|transit.*addon", re.I), "western_31days_transit_addon"),
    (re.compile(r"(大運|流年).*追加|追加.*(大運|流年)|fortune cycles? addon", re.I), "shichu_fortune_cycles_addon"),
    (re.compile(r"四柱|しちゅう|シチュウ"), "shichu"),
    # 単に Transits を含む出生図商品をイベント用 transit_yaml にしない。
    # コードなし旧商品は、イベント／歴史／YAML版だと明示された場合だけ受け付ける。
    (re.compile(
        r"(?:トランジット|transit).*(?:YAML|イベント|歴史|特定日時)"
        r"|(?:イベント|歴史|特定日時).*(?:トランジット|transit)",
        re.I,
    ), "transit_yaml"),
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
    buyer_reference  TEXT,
    mail_received_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

MARKETPLACE_ORDERS_DDL = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.marketplace_orders (
    provider         TEXT        NOT NULL,
    order_code       TEXT        NOT NULL,
    product_type     TEXT,
    amount           INTEGER,
    payment_status   TEXT        DEFAULT 'paid',
    mail_subject     TEXT,
    raw_message_id   TEXT,
    buyer_reference  TEXT,
    mail_received_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (provider, order_code)
)
"""

ORDER_ENTITLEMENTS_DDL = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.order_entitlements (
    id              BIGSERIAL   PRIMARY KEY,
    provider        TEXT        NOT NULL,
    order_code      TEXT        NOT NULL,
    line_item_key   TEXT        NOT NULL,
    sku             TEXT,
    product_type    TEXT,
    unit_index      INTEGER     NOT NULL CHECK (unit_index >= 1),
    status          TEXT        NOT NULL DEFAULT 'available'
                    CHECK (status IN ('available', 'redeemed', 'revoked')),
    chart_token     TEXT        UNIQUE,
    redeemed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, order_code, line_item_key, unit_index)
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
            cur.execute(MARKETPLACE_ORDERS_DDL)
            cur.execute(ORDER_ENTITLEMENTS_DDL)
            cur.execute(f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS product_type TEXT")
            cur.execute(f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS provider TEXT")
            cur.execute(f"ALTER TABLE {SCHEMA}.stores_orders ADD COLUMN IF NOT EXISTS buyer_reference TEXT")
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_stores_orders_provider_buyer "
                f"ON {SCHEMA}.stores_orders (provider, buyer_reference)"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_marketplace_orders_buyer "
                f"ON {SCHEMA}.marketplace_orders (provider, buyer_reference)"
            )
            # Existing installations used stores_order_no as the global primary
            # key. Copy those rows into the provider-scoped table without
            # rewriting or deleting the legacy records.
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.marketplace_orders
                    (provider, order_code, product_type, amount, payment_status,
                     mail_subject, raw_message_id, buyer_reference,
                     mail_received_at, created_at, updated_at)
                SELECT COALESCE(NULLIF(LOWER(provider), ''), 'stores'),
                       stores_order_no, product_type, amount, payment_status,
                       mail_subject, raw_message_id, buyer_reference,
                       mail_received_at, created_at, updated_at
                FROM {SCHEMA}.stores_orders
                ON CONFLICT (provider, order_code) DO NOTHING
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_order_entitlements_lookup "
                f"ON {SCHEMA}.order_entitlements "
                f"(order_code, provider, product_type, status)"
            )
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
        cur.execute(f"SELECT order_code FROM {SCHEMA}.marketplace_orders LIMIT 0")
        cur.execute(f"SELECT id FROM {SCHEMA}.order_entitlements LIMIT 0")


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
        r"(?:お支払い金額|合計金額|ご請求金額|金額|価格|合計（税込）)\s*[：:]?\s*[¥￥]?\s*([0-9][0-9,]*)",
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


def _etsy_sender_filters(configured: str | None = None) -> list[str]:
    """現在・旧Etsy通知アドレスを両方検索対象にする。"""
    values = [configured or "", ETSY_FROM_DEFAULT, ETSY_FROM_LEGACY]
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


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


def _normalize_sku(value: str) -> str:
    """商品コードを ``NP-WF-ES`` 形式へ正規化する（言語制限には使わない）。"""
    match = _PRODUCT_CODE_CAPTURE_RE.search(value or "")
    if not match:
        return ""
    parts = ["NP", match.group(1).upper()]
    if match.group(2):
        parts.append(match.group(2).upper())
    return "-".join(parts)


def _extract_line_items(subject: str, body: str) -> list[dict[str, object]]:
    """通知本文から商品明細と数量を抽出する。

    SKU の言語サフィックスは発行権の識別情報として保持するが、フォームの
    表示言語を制限する用途には使わない。メール形式に明細情報がない場合は、
    従来の商品判定結果を数量1の明細として補完する。
    """
    lines = [re.sub(r"\s+", " ", line).strip() for line in body.splitlines()]
    lines = [line for line in lines if line]
    candidates: list[dict[str, object]] = []

    for index, line in enumerate(lines):
        sku = _normalize_sku(line)
        product_type = _guess_product_type("", line)
        is_labeled_product = bool(
            re.match(r"^(?:商品|商品名|アイテム|アイテム名|Product|Item)\s*[：:]", line, re.I)
        )
        # SKU、明示的な商品行、または既知の現行商品名を候補とする。
        if not sku and not is_labeled_product:
            if not re.search(
                r"Personalized Birth Chart Bundle|Personalized Astrology Planner|"
                r"Astrocartography|AI-Readable (?:Natal|Astrology|Asteroid|Transit)",
                line,
                re.I,
            ):
                continue
        if not product_type:
            continue

        quantity = None
        for nearby in lines[index : min(len(lines), index + 5)]:
            quantity_match = _QUANTITY_RE.search(nearby)
            if quantity_match:
                quantity = int(quantity_match.group(1))
                break
            if nearby is not line and (
                _normalize_sku(nearby)
                or re.match(r"^(?:商品|商品名|アイテム|アイテム名|Product|Item)\s*[：:]", nearby, re.I)
            ):
                break
        quantity = max(1, min(quantity or 1, 100))
        candidates.append(
            {
                "sku": sku or None,
                "product_type": product_type,
                "quantity": quantity,
            }
        )

    if not candidates:
        product_type = _guess_product_type(subject, body)
        if product_type:
            quantity_match = _QUANTITY_RE.search(body)
            candidates.append(
                {
                    "sku": _normalize_sku(f"{subject}\n{body}") or None,
                    "product_type": product_type,
                    "quantity": max(1, min(int(quantity_match.group(1)) if quantity_match else 1, 100)),
                }
            )

    # 同じ商品行をHTML/plain text双方から拾った場合でも、出現順を安定キーにする。
    occurrences: dict[str, int] = {}
    result: list[dict[str, object]] = []
    for item in candidates:
        identity = str(item.get("sku") or item.get("product_type") or "unknown")
        occurrences[identity] = occurrences.get(identity, 0) + 1
        result.append(
            {
                **item,
                "line_item_key": f"{identity}:{occurrences[identity]}",
            }
        )
    return result


def _etsy_product_type(subject: str, body: str) -> str | None:
    product_type = _guess_product_type(subject, body)
    if product_type:
        return product_type
    # Etsyの実注文を使うE2E試験専用。商品行が「テスト」完全一致の場合だけ
    # 基本版として扱い、「テストを含む」一般商品には波及させない。
    if re.search(r"^\s*(?:商品|Product)\s*[：:]\s*テスト\s*$", body, re.I | re.M):
        return "western_basic"
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

    return {
        "stores_order_no": order_no,
        "provider": "stores",
        "product_type": _guess_product_type(subject, body),
        "line_items": _extract_line_items(subject, body),
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

    return {
        "stores_order_no": order_id,
        "provider": "payhip",
        "product_type": _guess_product_type(subject, body),
        "line_items": _extract_line_items(subject, body),
        "amount": _extract_amount(body),
        "mail_subject": subject,
        "raw_message_id": message_id,
        "mail_received_at": received_at,
        "payment_status": "paid",
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

    return {
        "stores_order_no": order_no,
        "provider": "etsy",
        "product_type": _etsy_product_type(subject, body),
        "line_items": _extract_line_items(subject, body),
        "amount": _extract_amount(body),
        "mail_subject": subject,
        "raw_message_id": message_id,
        "mail_received_at": received_at,
        "payment_status": "paid",
    }


def _parse_coconala_mail(
    subject: str,
    body: str,
    message_id: str | None,
    received_at: datetime | None,
    from_value: str,
) -> dict[str, object] | None:
    """ココナラコンテンツマーケットの販売通知を解析する。"""
    combined = f"{from_value}\n{subject}\n{body}"
    if (
        "mail.coconala.com" not in combined.lower()
        or "出品コンテンツが購入されました" not in combined
    ):
        return None

    buyer_reference = _extract_first(
        [
            r"購入者名\s*[：:]\s*([^\r\n]+)",
            r"以下のコンテンツが\s*([^\r\n]+?)\s*さんに購入されました",
        ],
        body,
    )
    title = _extract_first([r"タイトル\s*[：:]\s*([^\r\n]+)"], body)
    if not buyer_reference or not title:
        return None

    unique_source = message_id or "|".join(
        [
            buyer_reference,
            title,
            received_at.isoformat() if received_at else "",
        ]
    )
    order_no = f"COCONALA-{hashlib.sha256(unique_source.encode('utf-8')).hexdigest()[:24]}"
    return {
        "stores_order_no": order_no,
        "provider": "coconala",
        "product_type": _guess_product_type(subject, title),
        "line_items": _extract_line_items(subject, title),
        "amount": _extract_amount(body),
        "buyer_reference": buyer_reference,
        "mail_subject": subject,
        "raw_message_id": message_id,
        "mail_received_at": received_at,
        "payment_status": "paid",
    }


# ── DB upsert ──────────────────────────────────────────────────────

def _upsert_order(con, parsed: dict[str, Any]) -> bool:
    """
    stores_ordersにupsert。
    新規登録の場合True、既存スキップの場合Falseを返す。
    """
    provider = str(parsed.get("provider") or "").strip().lower()
    order_code = str(parsed.get("stores_order_no") or "").strip()
    if not provider or not order_code:
        return False

    values = (
        provider,
        order_code,
        parsed.get("product_type"),
        parsed.get("amount"),
        parsed.get("payment_status", "paid"),
        parsed.get("mail_subject"),
        parsed.get("raw_message_id"),
        parsed.get("buyer_reference"),
        parsed.get("mail_received_at"),
    )
    with con.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.marketplace_orders
                (provider, order_code, product_type, amount, payment_status,
                 mail_subject, raw_message_id, buyer_reference, mail_received_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider, order_code) DO UPDATE SET
                product_type     = COALESCE(EXCLUDED.product_type,     {SCHEMA}.marketplace_orders.product_type),
                amount           = COALESCE(EXCLUDED.amount,           {SCHEMA}.marketplace_orders.amount),
                payment_status   = CASE
                    WHEN {SCHEMA}.marketplace_orders.payment_status
                         IN ('reset_once', 'reusable', 'test', 'permanent')
                    THEN {SCHEMA}.marketplace_orders.payment_status
                    WHEN EXCLUDED.payment_status = 'paid' THEN 'paid'
                    ELSE COALESCE({SCHEMA}.marketplace_orders.payment_status, EXCLUDED.payment_status)
                END,
                mail_subject     = COALESCE(EXCLUDED.mail_subject,     {SCHEMA}.marketplace_orders.mail_subject),
                raw_message_id   = COALESCE(EXCLUDED.raw_message_id,   {SCHEMA}.marketplace_orders.raw_message_id),
                buyer_reference  = COALESCE(EXCLUDED.buyer_reference,  {SCHEMA}.marketplace_orders.buyer_reference),
                mail_received_at = COALESCE(EXCLUDED.mail_received_at, {SCHEMA}.marketplace_orders.mail_received_at),
                updated_at       = NOW()
            RETURNING (xmax = 0) AS is_new
            """,
            values,
        )
        row = cur.fetchone()
        is_new = bool(row and row["is_new"])

        # Keep the old table as a compatibility mirror. A collision from a
        # different marketplace must never overwrite its existing row.
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.stores_orders
                (stores_order_no, provider, product_type, amount, payment_status,
                 mail_subject, raw_message_id, buyer_reference, mail_received_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (stores_order_no) DO UPDATE SET
                provider         = COALESCE({SCHEMA}.stores_orders.provider, EXCLUDED.provider),
                product_type     = COALESCE(EXCLUDED.product_type,     {SCHEMA}.stores_orders.product_type),
                amount           = COALESCE(EXCLUDED.amount,           {SCHEMA}.stores_orders.amount),
                payment_status   = CASE
                    WHEN {SCHEMA}.stores_orders.payment_status
                         IN ('reset_once', 'reusable', 'test', 'permanent')
                    THEN {SCHEMA}.stores_orders.payment_status
                    WHEN EXCLUDED.payment_status = 'paid' THEN 'paid'
                    ELSE COALESCE({SCHEMA}.stores_orders.payment_status, EXCLUDED.payment_status)
                END,
                mail_subject     = COALESCE(EXCLUDED.mail_subject,     {SCHEMA}.stores_orders.mail_subject),
                raw_message_id   = COALESCE(EXCLUDED.raw_message_id,   {SCHEMA}.stores_orders.raw_message_id),
                buyer_reference  = COALESCE(EXCLUDED.buyer_reference,  {SCHEMA}.stores_orders.buyer_reference),
                mail_received_at = COALESCE(EXCLUDED.mail_received_at, {SCHEMA}.stores_orders.mail_received_at),
                updated_at       = NOW()
            WHERE {SCHEMA}.stores_orders.provider IS NULL
               OR LOWER({SCHEMA}.stores_orders.provider) = EXCLUDED.provider
            """,
            (order_code, provider, *values[2:]),
        )
    _upsert_order_entitlements(con, parsed)
    return is_new


def _upsert_order_entitlements(con, parsed: dict[str, Any]) -> None:
    """解析済み明細を、再同期しても増殖しない発行権へ展開する。"""
    provider = str(parsed.get("provider") or "").strip().lower()
    order_code = str(parsed.get("stores_order_no") or "").strip()
    if not provider or not order_code:
        return
    line_items = list(parsed.get("line_items") or [])
    if not line_items and parsed.get("product_type"):
        line_items = [
            {
                "line_item_key": f"{parsed['product_type']}:1",
                "sku": None,
                "product_type": parsed["product_type"],
                "quantity": 1,
            }
        ]

    with con.cursor() as cur:
        for item in line_items:
            try:
                quantity = max(1, min(int(item.get("quantity") or 1), 100))
            except (TypeError, ValueError):
                quantity = 1
            for unit_index in range(1, quantity + 1):
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.order_entitlements
                        (provider, order_code, line_item_key, sku, product_type, unit_index)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, order_code, line_item_key, unit_index)
                    DO UPDATE SET
                        sku = COALESCE(EXCLUDED.sku, {SCHEMA}.order_entitlements.sku),
                        product_type = COALESCE(
                            EXCLUDED.product_type,
                            {SCHEMA}.order_entitlements.product_type
                        ),
                        updated_at = NOW()
                    """,
                    (
                        provider,
                        order_code,
                        str(item.get("line_item_key") or f"item:{unit_index}"),
                        item.get("sku"),
                        item.get("product_type"),
                        unit_index,
                    ),
                )

        # 旧方式ですでに発行済みの注文を再同期した場合、既存チャート数だけ
        # 対応する未使用枠を消し込む。既存URLとredemptions行は変更しない。
        cur.execute(
            f"""
            SELECT c.token, c.options->>'product_type' AS product_type
            FROM {SCHEMA}.charts c
            LEFT JOIN {SCHEMA}.order_entitlements linked
              ON linked.chart_token = c.token
            WHERE c.order_code = %s
              AND (
                c.options->>'order_provider' = %s
                OR (
                  %s = 'stores'
                  AND COALESCE(c.options->>'order_provider', '') = ''
                )
              )
              AND linked.id IS NULL
            ORDER BY c.created_at, c.token
            """,
            (order_code, provider, provider),
        )
        for chart in cur.fetchall():
            cur.execute(
                f"""
                SELECT id
                FROM {SCHEMA}.order_entitlements
                WHERE provider = %s
                  AND order_code = %s
                  AND status = 'available'
                  AND (%s IS NULL OR product_type = %s)
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (provider, order_code, chart.get("product_type"), chart.get("product_type")),
            )
            entitlement = cur.fetchone()
            if not entitlement:
                continue
            cur.execute(
                f"""
                UPDATE {SCHEMA}.order_entitlements
                SET status = 'redeemed', chart_token = %s,
                    redeemed_at = COALESCE(redeemed_at, NOW()), updated_at = NOW()
                WHERE id = %s AND status = 'available'
                """,
                (chart["token"], entitlement["id"]),
            )


# ── メイン同期関数 ─────────────────────────────────────────────────

def _fetch_imap_order_messages(*, senders: list[str], limit: int) -> list[bytes]:
    host = os.getenv("STORES_MAIL_IMAP_HOST", "imap.gmail.com")
    port = int(os.getenv("STORES_MAIL_IMAP_PORT", "993"))
    username = (os.getenv("STORES_MAIL_USERNAME") or "").strip()
    password = (os.getenv("STORES_MAIL_PASSWORD") or "").strip()
    if not username or not password:
        raise RuntimeError("STORES_MAIL_USERNAME/PASSWORD が未設定です")

    conn_imap = imaplib.IMAP4_SSL(host, port)
    try:
        conn_imap.login(username, password)
        status, _ = conn_imap.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("IMAP INBOX選択失敗")

        search_ids: list[bytes] = []
        for candidate in dict.fromkeys(sender for sender in senders if sender):
            candidate_status, candidate_data = conn_imap.search(None, "FROM", f'"{candidate}"')
            if candidate_status == "OK" and candidate_data and candidate_data[0]:
                search_ids.extend(candidate_data[0].split())
        if not search_ids:
            status, data = conn_imap.search(None, "ALL")
            if status == "OK" and data and data[0]:
                search_ids = data[0].split()
        if status != "OK":
            raise RuntimeError("IMAP検索失敗")

        ids = sorted(set(search_ids), key=lambda item: int(item))
        recent_ids = list(reversed(ids[-limit:]))
        raw_messages: list[bytes] = []
        for message_id in recent_ids:
            fetch_status, payload = conn_imap.fetch(message_id, "(BODY.PEEK[])")
            if fetch_status != "OK" or not payload or not payload[0]:
                continue
            raw_messages.append(payload[0][1])
        return raw_messages
    finally:
        try:
            conn_imap.logout()
        except Exception:
            pass

def sync(*, limit: int = 100) -> dict[str, Any]:
    """
    STORES・Payhip・Etsy・ココナラメールを取得し、stores_ordersに登録する。

    ``STORES_MAIL_BACKEND=gmail_api`` または ``zoho_api`` の場合は各メール
    APIを読み取り専用で使用する。それ以外は移行期間用のIMAPを使用する。

    Returns:
        {ok, fetched, parsed, inserted, skipped, errors, message}
    """
    backend = (os.getenv("STORES_MAIL_BACKEND") or "imap").strip().lower()
    from_filter = (os.getenv("STORES_MAIL_FROM_FILTER", STORES_FROM_DEFAULT) or "").strip()
    payhip_from_filter = (os.getenv("PAYHIP_MAIL_FROM_FILTER", PAYHIP_FROM_DEFAULT) or "").strip()
    etsy_from_filters = _etsy_sender_filters(os.getenv("ETSY_MAIL_FROM_FILTER"))
    coconala_from_filter = (
        os.getenv("COCONALA_MAIL_FROM_FILTER", COCONALA_FROM_DEFAULT) or ""
    ).strip()

    counters = dict(fetched=0, parsed=0, inserted=0, skipped=0, errors=0)

    con_db = None
    try:
        senders = [from_filter, payhip_from_filter, *etsy_from_filters, coconala_from_filter]
        if backend == "gmail_api":
            from services.gmail_mail_api import fetch_order_messages

            raw_messages = fetch_order_messages(senders=senders, limit=limit)
        elif backend == "zoho_api":
            from services.zoho_mail_api import fetch_order_messages

            raw_messages = fetch_order_messages(senders=senders, limit=limit)
        elif backend == "imap":
            raw_messages = _fetch_imap_order_messages(senders=senders, limit=limit)
        else:
            raise RuntimeError(f"Unsupported STORES_MAIL_BACKEND: {backend}")

        con_db = _get_conn()
        _require_stores_orders_table(con_db)

        for raw_email in raw_messages:
            counters["fetched"] += 1
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
                and not any(sender.lower() in combined_lower for sender in etsy_from_filters)
                and coconala_from_filter.lower() not in combined_lower
                and "payhip" not in combined_lower
                and "etsy" not in combined_lower
                and "coconala" not in combined_lower
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
                _parse_coconala_mail(subject, body, message_id, received_at, from_value)
                or _parse_etsy_mail(subject, body, message_id, received_at, from_value)
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
        if con_db:
            con_db.close()


# ── 注文番号照合（redeem_post から呼ぶ） ──────────────────────────

def verify_order_no(order_no: str, *, provider: str | None = None) -> tuple[str, dict | None]:
    """
    注文番号がstores_ordersに存在するか照合する。

    Returns:
        ("ok", row)          存在して未使用
        ("not_found", None)  存在しない
        ("already_used", row) 既にcharts/redemptionsに登録済み
        ("reusable", row)     テスト・身内用の再利用可能番号
    """
    con = _get_conn()
    try:
        with con.cursor() as cur:
            provider_clean = (provider or "").strip().lower()
            cur.execute(
                "SELECT to_regclass(%s) AS table_name",
                (f"{SCHEMA}.marketplace_orders",),
            )
            marketplace_table = cur.fetchone()
            if provider_clean and marketplace_table and marketplace_table.get("table_name"):
                cur.execute(
                    f"""
                    SELECT order_code AS stores_order_no, provider, product_type,
                           amount, payment_status, mail_subject, raw_message_id,
                           buyer_reference, mail_received_at, created_at, updated_at
                    FROM {SCHEMA}.marketplace_orders
                    WHERE provider = %s AND order_code = %s
                    """,
                    (provider_clean, order_no),
                )
            elif provider_clean:
                cur.execute(
                    f"""
                    SELECT * FROM {SCHEMA}.stores_orders
                    WHERE stores_order_no = %s
                      AND (LOWER(provider) = %s OR (provider IS NULL AND %s = 'stores'))
                    """,
                    (order_no, provider_clean, provider_clean),
                )
            else:
                cur.execute(
                    f"SELECT * FROM {SCHEMA}.stores_orders WHERE stores_order_no = %s",
                    (order_no,),
                )
            row = cur.fetchone()
            if not row:
                return "not_found", None

            payment_status = (row.get("payment_status") or "").lower()
            if payment_status == "reset_once":
                return "ok", dict(row)
            if payment_status in {"reusable", "test", "permanent"}:
                return "reusable", dict(row)

            # Provider-scoped flows must not treat another marketplace's
            # identical order number as used. Charts carry the provider in
            # options; legacy Japanese STORES charts may omit it.
            if provider_clean:
                cur.execute(
                    f"""
                    SELECT token
                    FROM {SCHEMA}.charts
                    WHERE order_code = %s
                      AND (
                        options->>'order_provider' = %s
                        OR (%s = 'stores' AND COALESCE(options->>'order_provider', '') = '')
                      )
                    LIMIT 1
                    """,
                    (order_no, provider_clean, provider_clean),
                )
            else:
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


def verify_order_entitlement(
    order_no: str,
    *,
    provider: str,
    product_type: str,
) -> tuple[str, dict | None]:
    """注文内の対象商品について、残っている発行権を照合する。

    発行権テーブルにまだ移行されていない旧注文は ``verify_order_no`` の
    結果をそのまま返す。言語別SKUは記録するが、言語一致は要求しない。
    """
    provider_clean = (provider or "").strip().lower()
    legacy_status, legacy_row = verify_order_no(order_no, provider=provider_clean)
    if not legacy_row or legacy_status in {"not_found", "reusable"}:
        return legacy_status, legacy_row

    con = _get_conn()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) AS table_name", (f"{SCHEMA}.order_entitlements",))
            table_row = cur.fetchone()
            if not table_row or not table_row.get("table_name"):
                return legacy_status, legacy_row
            cur.execute(
                f"""
                SELECT provider, product_type, status, COUNT(*) AS unit_count
                FROM {SCHEMA}.order_entitlements
                WHERE order_code = %s AND provider = %s
                GROUP BY provider, product_type, status
                """,
                (order_no, provider_clean),
            )
            groups = [dict(row) for row in cur.fetchall()]
    finally:
        con.close()

    if not groups:
        return legacy_status, legacy_row

    matching = [
        group
        for group in groups
        if str(group.get("provider") or "").lower() == provider_clean
        and group.get("product_type") == product_type
    ]
    row = dict(legacy_row)
    row["_entitlement_mode"] = True
    row["_entitlement_groups"] = groups
    row["_available_entitlements"] = sum(
        int(group.get("unit_count") or 0)
        for group in matching
        if group.get("status") == "available"
    )
    row["_redeemed_entitlements"] = sum(
        int(group.get("unit_count") or 0)
        for group in matching
        if group.get("status") == "redeemed"
    )
    if not matching:
        row["_purchased_product_types"] = sorted(
            {
                str(group["product_type"])
                for group in groups
                if group.get("product_type")
            }
        )
        return "product_mismatch", row
    # 後続の商品照合は、stores_orders の代表値ではなく選択した明細を使う。
    row["product_type"] = product_type
    if str(row.get("payment_status") or "").lower() == "reset_once":
        row["_entitlement_reset_once"] = True
        return "ok", row
    if row["_available_entitlements"] <= 0:
        return "already_used", row
    if row["_redeemed_entitlements"] > 0:
        return "partial", row
    return "ok", row


def verify_coconala_buyer(
    buyer_reference: str,
    *,
    product_type: str,
) -> tuple[str, dict | None]:
    """ココナラの一意なユーザー名と商品種別から未使用購入を照合する。"""
    con = _get_conn()
    try:
        with con.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.*,
                       EXISTS (
                           SELECT 1
                           FROM {SCHEMA}.redemptions r
                           WHERE r.order_code = o.stores_order_no
                       )
                       AND COALESCE(o.payment_status, '') <> 'reset_once'
                       AS already_used
                FROM {SCHEMA}.stores_orders o
                WHERE o.provider = 'coconala'
                  AND LOWER(o.buyer_reference) = LOWER(%s)
                  AND o.product_type = %s
                ORDER BY o.mail_received_at DESC NULLS LAST, o.created_at DESC
                """,
                (buyer_reference.strip(), product_type),
            )
            rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            return "not_found", None
        for row in rows:
            if not row.get("already_used"):
                return "ok", row
        return "already_used", rows[0]
    finally:
        con.close()
