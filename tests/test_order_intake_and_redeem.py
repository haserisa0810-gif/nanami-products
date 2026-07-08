"""注文取込（Payhip/STORES メール解析）と redeem 判定まわりのテスト。

- Payhip: Order ID を一意キーとして抽出できること（メールアドレスはキーにしない）
- 商品コード [NP-XX] の判定が routes.PAYHIP_PRODUCTS と食い違わないこと
- provider 解決と Gumroad relaxed の適用範囲
- reset_once 再発行時に redemptions が新しい token に付け替わること
"""
from __future__ import annotations

import re
import unittest
from unittest.mock import patch

import services.pg_store as pg_store
import services.stores_mail_sync as sync
import routes


PAYHIP_MAIL_BODY = """\
You've Sold An Item!

Buyer: buyer@example.com
Date: 8th July 2026
Order ID: LWR6I4Y4Wa
Product: AI-Readable Natal Data Core Pack [NP-WB]
Total: $7.00
"""


class PayhipMailParseTest(unittest.TestCase):
    def test_sample_mail_uses_order_id_as_key(self) -> None:
        parsed = sync._parse_payhip_mail(
            "You've Sold An Item!",
            PAYHIP_MAIL_BODY,
            "<msg-1@payhip>",
            None,
            "Payhip <contact@payhip.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["stores_order_no"], "LWR6I4Y4Wa")
        self.assertEqual(parsed["product_type"], "western_basic")
        self.assertEqual(parsed["payment_status"], "paid")
        self.assertEqual(parsed["amount"], 7)

    def test_refunded_mail_is_cancelled(self) -> None:
        parsed = sync._parse_payhip_mail(
            "Order Refunded",
            PAYHIP_MAIL_BODY + "\nThis order has been refunded.",
            None,
            None,
            "Payhip <contact@payhip.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["payment_status"], "cancelled")

    def test_mail_without_order_id_is_skipped(self) -> None:
        parsed = sync._parse_payhip_mail(
            "You've Sold An Item!",
            "Buyer: buyer@example.com\nTotal: $7.00",
            None,
            None,
            "Payhip <contact@payhip.com>",
        )
        self.assertIsNone(parsed)

    def test_order_id_normalization(self) -> None:
        self.assertEqual(sync._normalize_payhip_order_id(" LWR6I4Y4Wa "), "LWR6I4Y4Wa")
        self.assertEqual(sync._normalize_payhip_order_id("Order ID: abc-123="), "abc-123=")
        self.assertIsNone(sync._normalize_payhip_order_id("  "))
        self.assertIsNone(sync._normalize_payhip_order_id(None))


class StoresMailParseTest(unittest.TestCase):
    def test_subject_order_no_extraction(self) -> None:
        parsed = sync._parse_stores_mail(
            "【STORES】アイテムが購入されました（オーダー番号：9824333454）",
            "商品: AI占いデータ [NP-WB]\n合計（税込）: ¥1,000",
            None,
            None,
            "STORES <hello@stores.jp>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["stores_order_no"], "9824333454")
        self.assertEqual(parsed["product_type"], "western_basic")
        self.assertEqual(parsed["payment_status"], "paid")

    def test_non_order_mail_is_skipped(self) -> None:
        parsed = sync._parse_stores_mail(
            "本日のニュースレター",
            "特に注文とは関係ない本文です。",
            None,
            None,
            "newsletter@example.com",
        )
        self.assertIsNone(parsed)


class ProductCodeConsistencyTest(unittest.TestCase):
    def test_payhip_product_codes_resolve_to_same_product_type(self) -> None:
        """routes.PAYHIP_PRODUCTS の全コードが、メール取込側でも同じ product_type に解決されること。

        ここが食い違うと stores_orders.product_type が NULL になり、
        redeem 時の商品種別チェック（product_mismatch）が働かなくなる。
        """
        for code, product in routes.PAYHIP_PRODUCTS.items():
            subject = "You've Sold An Item!"
            body = f"Product: Something [{code}]\nOrder ID: X1\nTotal: $5.00"
            guessed = sync._guess_product_type(subject, body)
            self.assertEqual(
                guessed,
                product["product_type"],
                f"code={code}: mail-sync guessed {guessed!r}, "
                f"routes expects {product['product_type']!r}",
            )


class OrderProviderResolutionTest(unittest.TestCase):
    def test_ten_digit_numeric_is_stores(self) -> None:
        self.assertEqual(routes._resolve_order_provider("9824333454"), "stores")

    def test_explicit_provider_wins(self) -> None:
        self.assertEqual(routes._resolve_order_provider("LWR6I4Y4Wa", "payhip"), "payhip")
        self.assertEqual(routes._resolve_order_provider("9824333454", "stores"), "stores")

    def test_non_numeric_without_provider_falls_back_to_gumroad(self) -> None:
        self.assertEqual(routes._resolve_order_provider("LWR6I4Y4Wa"), "gumroad")

    def test_invalid_code_resolves_to_none(self) -> None:
        self.assertIsNone(routes._resolve_order_provider("bad code!"))


class GumroadRelaxedScopeTest(unittest.TestCase):
    def test_relaxed_accepts_western_basic(self) -> None:
        with patch.dict("os.environ", {"GUMROAD_ORDER_STRICT": "0"}):
            status, _row, error, code = routes._check_order_for_redeem(
                order_id="AnyCode123",
                provider="gumroad",
                product_type="western_basic",
            )
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.assertEqual(code, 200)

    def test_relaxed_rejects_shichu_and_transit(self) -> None:
        for product_type in ("shichu", "transit_yaml"):
            with patch.dict("os.environ", {"GUMROAD_ORDER_STRICT": "0"}):
                status, _row, error, code = routes._check_order_for_redeem(
                    order_id="AnyCode123",
                    provider="gumroad",
                    product_type=product_type,
                )
            self.assertEqual(status, "not_found", product_type)
            self.assertIsNotNone(error, product_type)
            self.assertEqual(code, 400, product_type)


class PayhipMetadataFormTest(unittest.TestCase):
    def test_email_is_normalized_and_kept_as_metadata_only(self) -> None:
        metadata, error = routes._payhip_metadata_from_form(
            payhip_email="  Buyer@Example.COM ",
            payhip_product_code="np-wb",
            payhip_order_id="LWR6I4Y4Wa",
            expected_product_type="western_basic",
        )
        self.assertIsNone(error)
        self.assertEqual(metadata["purchaser_email"], "buyer@example.com")
        self.assertEqual(metadata["selected_product_code"], "NP-WB")
        self.assertEqual(metadata["provider"], "payhip")

    def test_order_id_is_required(self) -> None:
        metadata, error = routes._payhip_metadata_from_form(
            payhip_email="buyer@example.com",
            payhip_product_code="NP-WB",
            payhip_order_id="",
            expected_product_type="western_basic",
        )
        self.assertEqual(metadata, {})
        self.assertIsNotNone(error)

    def test_invalid_order_id_characters_rejected(self) -> None:
        metadata, error = routes._payhip_metadata_from_form(
            payhip_email="buyer@example.com",
            payhip_product_code="NP-WB",
            payhip_order_id="abc def!",
            expected_product_type="western_basic",
        )
        self.assertEqual(metadata, {})
        self.assertIsNotNone(error)

    def test_payhip_order_row_without_provider_is_accepted(self) -> None:
        status, row, error, code = routes._check_payhip_order_row_for_redeem(
            order_id="LWR6l4Y4Wa",
            order_row={
                "stores_order_no": "LWR6l4Y4Wa",
                "payment_status": "paid",
                "product_type": "western_basic",
            },
            product_type="western_basic",
        )

        self.assertEqual(status, "ok")
        self.assertIsNotNone(row)
        self.assertIsNone(error)
        self.assertEqual(code, 200)


class _RecordingCursor:
    """redeem_and_save の SQL 発行順を記録するダミーカーソル。"""

    def __init__(self, fetchone_results: list) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone_results = list(fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((re.sub(r"\s+", " ", str(sql)).strip(), params))

    def fetchone(self):
        return self._fetchone_results.pop(0) if self._fetchone_results else None


class _RecordingConn:
    def __init__(self, cursor: _RecordingCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class RedeemAndSaveResetPathTest(unittest.TestCase):
    def test_reset_once_reissue_updates_redemption_token(self) -> None:
        # 1回目 fetchone（redemptions INSERT）= None → 使用済み
        # 2回目 fetchone（stores_orders reset_once → paid）= row → 再発行許可
        cursor = _RecordingCursor([None, {"stores_order_no": "9824333454"}])
        with patch.object(pg_store, "_conn", return_value=_RecordingConn(cursor)), patch.object(
            pg_store, "_insert_chart"
        ):
            ok = pg_store.redeem_and_save(
                order_code="9824333454",
                email="new@example.com",
                buyer_name="New Buyer",
                token="new-token",
                birth_date="2000-01-01",
                birth_time="12:00",
                birth_place="Tokyo",
                options={"product_type": "western_basic"},
                yaml_text="yaml",
                prompt_text="prompt",
            )
        self.assertTrue(ok)
        updates = [
            (sql, params)
            for sql, params in cursor.executed
            if sql.startswith("UPDATE") and ".redemptions" in sql
        ]
        self.assertEqual(len(updates), 1, cursor.executed)
        sql, params = updates[0]
        self.assertIn("SET email = %s", sql)
        self.assertEqual(params, ("new@example.com", "New Buyer", "new-token", "9824333454"))

    def test_already_used_without_reset_returns_false(self) -> None:
        # redemptions INSERT conflict + stores_orders が reset_once でない → False
        cursor = _RecordingCursor([None, None])
        with patch.object(pg_store, "_conn", return_value=_RecordingConn(cursor)), patch.object(
            pg_store, "_insert_chart"
        ) as insert_chart:
            ok = pg_store.redeem_and_save(
                order_code="9824333454",
                email=None,
                buyer_name=None,
                token="tok",
                birth_date="2000-01-01",
                birth_time=None,
                birth_place=None,
                options={},
                yaml_text="yaml",
                prompt_text="prompt",
            )
        self.assertFalse(ok)
        insert_chart.assert_not_called()
        redemption_updates = [
            sql for sql, _ in cursor.executed if sql.startswith("UPDATE") and ".redemptions" in sql
        ]
        self.assertEqual(redemption_updates, [])


if __name__ == "__main__":
    unittest.main()
