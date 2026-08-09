"""注文取込（Payhip/STORES メール解析）と redeem 判定まわりのテスト。

- Payhip: Order ID を一意キーとして抽出できること（メールアドレスはキーにしない）
- 商品コード [NP-XX] の判定が routes.PAYHIP_PRODUCTS と食い違わないこと
- provider 解決と Gumroad relaxed の適用範囲
- reset_once 再発行時に redemptions が新しい token に付け替わること
"""
from __future__ import annotations

import re
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

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

ETSY_MAIL_BODY = """\
注文の詳細
注文番号： 4125350780
取引番号： 5152950642
商品： [NP-WBT] AI-Readable Natal Data + Transits
個数： 1
商品価格： US$12.00
合計: US$12.00
"""

COCONALA_MAIL_BODY = """\
おめでとうございます！
あなたが出品した以下のコンテンツがsample_buyer さんに購入されました。
販売日時：2026/07/26 18:56:24
価格：500円
購入者名：sample_buyer
コンテンツ詳細：https://example.invalid/content
タイトル：[NP-ACG] ACG Bundle
"""


class CoconalaMailParseTest(unittest.TestCase):
    def test_purchase_uses_unique_username_and_message_id(self) -> None:
        parsed = sync._parse_coconala_mail(
            "出品コンテンツが購入されました",
            COCONALA_MAIL_BODY,
            "<coconala-message-1>",
            None,
            "ココナラ <no-reply@mail.coconala.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["provider"], "coconala")
        self.assertEqual(parsed["buyer_reference"], "sample_buyer")
        self.assertEqual(parsed["product_type"], "acg_bundle")
        self.assertEqual(parsed["amount"], 500)
        self.assertRegex(parsed["stores_order_no"], r"^COCONALA-[a-f0-9]{24}$")

    def test_same_message_is_idempotent(self) -> None:
        args = (
            "出品コンテンツが購入されました",
            COCONALA_MAIL_BODY,
            "<coconala-message-1>",
            None,
            "ココナラ <no-reply@mail.coconala.com>",
        )
        first = sync._parse_coconala_mail(*args)
        second = sync._parse_coconala_mail(*args)
        self.assertEqual(first["stores_order_no"], second["stores_order_no"])

    def test_same_buyer_different_products_create_distinct_purchases(self) -> None:
        acg = sync._parse_coconala_mail(
            "出品コンテンツが購入されました",
            COCONALA_MAIL_BODY,
            "<coconala-acg-purchase>",
            None,
            "ココナラ <no-reply@mail.coconala.com>",
        )
        basic = sync._parse_coconala_mail(
            "出品コンテンツが購入されました",
            COCONALA_MAIL_BODY.replace("[NP-ACG] ACG Bundle", "[NP-WB] Basic"),
            "<coconala-basic-purchase>",
            None,
            "ココナラ <no-reply@mail.coconala.com>",
        )
        self.assertEqual(acg["buyer_reference"], basic["buyer_reference"])
        self.assertEqual(acg["product_type"], "acg_bundle")
        self.assertEqual(basic["product_type"], "western_basic")
        self.assertNotEqual(acg["stores_order_no"], basic["stores_order_no"])

    def test_same_buyer_repeated_product_still_creates_distinct_purchases(self) -> None:
        first = sync._parse_coconala_mail(
            "出品コンテンツが購入されました",
            COCONALA_MAIL_BODY,
            "<coconala-acg-purchase-1>",
            None,
            "ココナラ <no-reply@mail.coconala.com>",
        )
        second = sync._parse_coconala_mail(
            "出品コンテンツが購入されました",
            COCONALA_MAIL_BODY,
            "<coconala-acg-purchase-2>",
            None,
            "ココナラ <no-reply@mail.coconala.com>",
        )
        self.assertEqual(first["buyer_reference"], second["buyer_reference"])
        self.assertEqual(first["product_type"], second["product_type"])
        self.assertNotEqual(first["stores_order_no"], second["stores_order_no"])


class EtsyMailParseTest(unittest.TestCase):
    def test_etsy_order_uses_order_number_and_product_code(self) -> None:
        parsed = sync._parse_etsy_mail(
            "初めての販売おめでとうございます！注文の詳細はこちらです。",
            ETSY_MAIL_BODY,
            "<etsy-1>",
            None,
            "Etsy <emails@mail.etsy.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["stores_order_no"], "4125350780")
        self.assertEqual(parsed["provider"], "etsy")
        self.assertEqual(parsed["product_type"], "western_transit")
        self.assertEqual(parsed["payment_status"], "paid")
        self.assertEqual(parsed["amount"], 12)

    def test_etsy_product_composition_mapping(self) -> None:
        cases = {
            "[NP-WB] Basic": "western_basic",
            "[NP-WBA] Basic + Asteroids": "western_asteroids",
            "[NP-WBT] Basic + Transit": "western_transit",
            "[NP-WF] FULL": "western_full",
            "[NP-ACG] ACG Bundle": "acg_bundle",
        }
        for title, expected in cases.items():
            self.assertEqual(sync._guess_product_type("", f"商品： {title}"), expected)

    def test_exact_test_listing_is_treated_as_basic_for_live_e2e(self) -> None:
        parsed = sync._parse_etsy_mail(
            "初めての販売おめでとうございます！注文の詳細はこちらです。",
            ETSY_MAIL_BODY.replace(
                "[NP-WBT] AI-Readable Natal Data + Transits",
                "テスト",
            ),
            "<etsy-unknown>",
            None,
            "Etsy <emails@mail.etsy.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["product_type"], "western_basic")

    def test_refund_and_cancellation_words_do_not_change_payment_status(self) -> None:
        parsed = sync._parse_etsy_mail(
            "Order cancelled and refunded",
            ETSY_MAIL_BODY + "\nThis order was cancelled and refunded.",
            None,
            None,
            "Etsy <emails@mail.etsy.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["payment_status"], "paid")

    def test_product_name_merely_containing_test_is_not_guessed(self) -> None:
        parsed = sync._parse_etsy_mail(
            "初めての販売おめでとうございます！注文の詳細はこちらです。",
            ETSY_MAIL_BODY.replace(
                "[NP-WBT] AI-Readable Natal Data + Transits",
                "テスト用ではない商品",
            ),
            "<etsy-not-exact-test>",
            None,
            "Etsy <emails@mail.etsy.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed["product_type"])


class EtsyStrictVerificationTest(unittest.TestCase):
    def _check(self, order_row: dict, product_type: str = "western_basic"):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), patch.object(
            routes,
            "_verify_strict_stores_order",
            return_value=("ok", order_row),
        ):
            return routes._check_order_for_redeem(
                order_id="4125350780",
                provider="etsy",
                product_type=product_type,
            )

    def test_unknown_product_is_rejected_without_consuming_order(self) -> None:
        status, _row, error, code = self._check({
            "stores_order_no": "4125350780",
            "provider": "etsy",
            "payment_status": "paid",
            "product_type": None,
        })
        self.assertEqual(status, "product_unverified")
        self.assertIn("商品", error)
        self.assertEqual(code, 409)

    def test_matching_product_is_accepted(self) -> None:
        status, _row, error, code = self._check({
            "stores_order_no": "4125350780",
            "provider": "etsy",
            "payment_status": "paid",
            "product_type": "western_basic",
        })
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.assertEqual(code, 200)

    def test_different_product_is_rejected(self) -> None:
        status, _row, error, code = self._check({
            "stores_order_no": "4125350780",
            "provider": "etsy",
            "payment_status": "paid",
            "product_type": "western_full",
        })
        self.assertEqual(status, "product_mismatch")
        self.assertIsNotNone(error)
        self.assertEqual(code, 409)

    def test_non_etsy_mail_row_is_rejected(self) -> None:
        status, _row, error, code = self._check({
            "stores_order_no": "4125350780",
            "provider": "stores",
            "payment_status": "paid",
            "product_type": "western_basic",
        })
        self.assertEqual(status, "not_found")
        self.assertIn("Etsy", error)
        self.assertEqual(code, 400)


class StrictMailSyncFailureTest(unittest.TestCase):
    def test_imap_failure_is_not_reported_as_order_not_found(self) -> None:
        with patch.object(
            routes.stores_mail_sync,
            "verify_order_no",
            return_value=("not_found", None),
        ), patch.object(
            routes.stores_mail_sync,
            "sync",
            return_value={
                "ok": False,
                "fetched": 0,
                "parsed": 0,
                "inserted": 0,
                "skipped": 0,
                "errors": 0,
                "message": "authentication failed",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "購入履歴の同期に失敗"):
                routes._verify_strict_stores_order("4125350780")

    def test_successful_sync_rechecks_the_order(self) -> None:
        order_row = {
            "stores_order_no": "4125350780",
            "provider": "etsy",
            "product_type": "western_basic",
            "payment_status": "paid",
        }
        with patch.object(
            routes.stores_mail_sync,
            "verify_order_no",
            side_effect=[("not_found", None), ("ok", order_row)],
        ) as verify, patch.object(
            routes.stores_mail_sync,
            "sync",
            return_value={
                "ok": True,
                "fetched": 1,
                "parsed": 1,
                "inserted": 1,
                "skipped": 0,
                "errors": 0,
                "message": "",
            },
        ):
            status, row = routes._verify_strict_stores_order("4125350780")
        self.assertEqual(status, "ok")
        self.assertEqual(row, order_row)
        self.assertEqual(verify.call_count, 2)


class ExistingChartRedirectTest(unittest.TestCase):
    def test_chart_redirect_url_preserves_language_and_download_flags(self) -> None:
        self.assertEqual(
            routes._chart_redirect_url("new-token", lang="ja", download=True),
            "/chart/new-token?chart_download=1",
        )
        self.assertEqual(
            routes._chart_redirect_url("new-token", lang="en", download=True),
            "/chart/new-token?chart_download=1&lang=en",
        )
        self.assertEqual(
            routes._chart_redirect_url("new-token", lang="en", download=False),
            "/chart/new-token?lang=en",
        )
        self.assertEqual(
            routes._chart_redirect_url(
                "new-token",
                lang="en",
                download=True,
                personal_download=True,
            ),
            "/chart/new-token?personal_download=1&lang=en",
        )

    def test_existing_redemption_redirects_with_download_and_language(self) -> None:
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), patch.object(
            routes.pg_store,
            "get_redemption_by_order_code",
            return_value={"token": "existing-token"},
        ):
            response = routes._existing_chart_redirect("4125350780", lang="en")

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            response.headers["location"],
            "/chart/existing-token?chart_download=1&lang=en",
        )

    def test_missing_existing_chart_does_not_redirect(self) -> None:
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), patch.object(
            routes.pg_store,
            "get_redemption_by_order_code",
            return_value=None,
        ), patch.object(
            routes.pg_store,
            "list_charts_by_order_code",
            return_value=[],
        ):
            response = routes._existing_chart_redirect("4125350780")

        self.assertIsNone(response)


class AcgDeliveryOptionsTest(unittest.TestCase):
    def test_supported_acg_stores_are_permanent_personal_editions(self) -> None:
        for provider, lang in {
            "stores": "ja",
            "coconala": "ja",
            "payhip": "en",
            "etsy": "en",
        }.items():
            options = routes._acg_personal_edition_options(
                product_type="acg_bundle",
                order_provider=provider,
                lang=lang,
            )
            self.assertTrue(options["personal_edition"])
            self.assertEqual(options["personal_edition_product_type"], "acg_bundle")
            self.assertEqual(options["personal_edition_locale"], lang)
            self.assertEqual(options["expires_policy"], routes.NO_EXPIRY_CHART_POLICY)

    def test_non_acg_products_are_unchanged(self) -> None:
        self.assertEqual(
            routes._acg_personal_edition_options(
                product_type="western_full",
                order_provider="etsy",
                lang="en",
            ),
            {},
        )


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

    def test_refunded_word_does_not_change_payment_status(self) -> None:
        parsed = sync._parse_payhip_mail(
            "Order Refunded",
            PAYHIP_MAIL_BODY + "\nThis order has been refunded.",
            None,
            None,
            "Payhip <contact@payhip.com>",
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["payment_status"], "paid")

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

    def test_cancellation_word_does_not_change_payment_status(self) -> None:
        parsed = sync._parse_stores_mail(
            "【STORES】アイテムが購入されました（オーダー番号：9824333454）",
            "商品: AI占いデータ [NP-WB]\n注文確定後はキャンセルできません。",
            None,
            None,
            "STORES <hello@stores.jp>",
        )
        self.assertIsNotNone(parsed)
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
    def test_provider_links_lock_purchase_source(self) -> None:
        client = TestClient(routes.app)
        for provider, lang in {
            "stores": "ja",
            "coconala": "ja",
            "payhip": "en",
            "etsy": "en",
        }.items():
            response = client.get(
                f"/redeem/acg-bundle?lang={lang}&provider={provider}"
            )
            self.assertEqual(response.status_code, 200)
            self.assertRegex(
                response.text,
                rf'<input type="hidden" name="order_provider" id="order-provider" value="{provider}">',
            )
            self.assertNotIn('<select name="order_provider"', response.text)

    def test_missing_or_unknown_provider_keeps_selector(self) -> None:
        client = TestClient(routes.app)
        for url in (
            "/redeem/acg-bundle?lang=ja",
            "/redeem/acg-bundle?lang=ja&provider=unknown",
        ):
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('<select name="order_provider"', response.text)
            self.assertIn('<option value="coconala"', response.text)

    def test_shichu_coconala_link_uses_username_instead_of_stores_order(self) -> None:
        client = TestClient(routes.app)
        response = client.get("/redeem/shichu?lang=ja&provider=coconala")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            '<input type="hidden" name="order_provider" id="order-provider" value="coconala">',
            response.text,
        )
        self.assertIn("ココナラのユーザー名", response.text)
        self.assertIn('placeholder="例：nanami_user"', response.text)
        self.assertNotIn('pattern="[0-9]{10}"', response.text)

    def test_shichu_without_provider_keeps_stores_coconala_selector(self) -> None:
        client = TestClient(routes.app)
        response = client.get("/redeem/shichu?lang=ja")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<select name="order_provider" id="order-provider">', response.text)
        self.assertIn('<option value="stores"', response.text)
        self.assertIn('<option value="coconala"', response.text)

    def test_name_example_matches_selected_language(self) -> None:
        client = TestClient(routes.app)
        english = client.get("/redeem/acg-bundle?lang=en&provider=etsy")
        japanese = client.get("/redeem/acg-bundle?lang=ja&provider=stores")

        self.assertIn('placeholder="e.g. Hanako Yamada"', english.text)
        self.assertNotIn("山田 花子", english.text)
        self.assertIn('placeholder="例：山田 花子"', japanese.text)

    def test_etsy_order_hint_and_language_links_match_provider(self) -> None:
        client = TestClient(routes.app)
        response = client.get("/redeem/acg-bundle?lang=en&provider=etsy")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Enter the order number shown on your Etsy purchase receipt or confirmation email.",
            response.text,
        )
        self.assertNotIn(
            '<small id="order-code-hint">Enter the order number shown in the purchase completion email from STORES.',
            response.text,
        )
        self.assertIn(
            'href="/redeem/acg-bundle?provider=etsy&amp;lang=ja"',
            response.text,
        )
        self.assertIn(
            'href="/redeem/acg-bundle?provider=etsy&amp;lang=en"',
            response.text,
        )
        self.assertNotIn('href="http://', response.text)

    def test_ten_digit_numeric_is_stores(self) -> None:
        self.assertEqual(routes._resolve_order_provider("9824333454"), "stores")

    def test_explicit_provider_wins(self) -> None:
        self.assertEqual(routes._resolve_order_provider("LWR6I4Y4Wa", "payhip"), "payhip")
        self.assertEqual(routes._resolve_order_provider("9824333454", "stores"), "stores")
        self.assertEqual(routes._resolve_order_provider("4125350780", "etsy"), "etsy")
        self.assertEqual(routes._resolve_order_provider("C12345", "coconala"), "coconala")


class CoconalaBuyerResolutionTest(unittest.TestCase):
    def test_database_lookup_is_scoped_by_username_and_product(self) -> None:
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            {
                "stores_order_no": "COCONALA-unused-acg",
                "provider": "coconala",
                "product_type": "acg_bundle",
                "buyer_reference": "sample_buyer",
                "already_used": False,
            }
        ]
        with patch.object(sync, "_get_conn", return_value=connection):
            status, row = sync.verify_coconala_buyer(
                "sample_buyer",
                product_type="acg_bundle",
            )
        self.assertEqual(status, "ok")
        self.assertEqual(row["stores_order_no"], "COCONALA-unused-acg")
        execute_args = cursor.execute.call_args.args
        self.assertIn("o.product_type = %s", execute_args[0])
        self.assertEqual(execute_args[1], ("sample_buyer", "acg_bundle"))

    def test_repeated_product_uses_next_unredeemed_purchase(self) -> None:
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            {"stores_order_no": "COCONALA-used", "already_used": True},
            {"stores_order_no": "COCONALA-unused", "already_used": False},
        ]
        with patch.object(sync, "_get_conn", return_value=connection):
            status, row = sync.verify_coconala_buyer(
                "sample_buyer",
                product_type="acg_bundle",
            )
        self.assertEqual(status, "ok")
        self.assertEqual(row["stores_order_no"], "COCONALA-unused")

    def test_resolves_username_to_internal_order_code(self) -> None:
        row = {
            "stores_order_no": "COCONALA-1234567890abcdef12345678",
            "provider": "coconala",
            "product_type": "acg_bundle",
        }
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), patch.object(
            routes.stores_mail_sync,
            "verify_coconala_buyer",
            return_value=("ok", row),
        ):
            order_code, resolved, error, status_code = (
                routes._resolve_coconala_order_from_buyer(
                    buyer_reference="sample_buyer",
                    product_type="acg_bundle",
                )
            )
        self.assertEqual(order_code, row["stores_order_no"])
        self.assertEqual(resolved["_redemption_status"], "ok")
        self.assertIsNone(error)
        self.assertEqual(status_code, 200)

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

    def test_already_used_order_reaches_common_redirect_check(self) -> None:
        order_row = {
            "stores_order_no": "LWR6l4Y4Wa",
            "payment_status": "paid",
            "product_type": "western_basic",
        }
        metadata = {
            "purchaser_email": "buyer@example.com",
            "selected_product_code": "NP-WB",
            "optional_order_id": "LWR6l4Y4Wa",
        }
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}), patch.object(
            routes.stores_mail_sync,
            "verify_order_no",
            return_value=("already_used", order_row),
        ):
            order_code, resolved_row, error, code = routes._resolve_payhip_order_from_metadata(metadata)

        self.assertEqual(order_code, "LWR6l4Y4Wa")
        self.assertEqual(resolved_row["_redemption_status"], "already_used")
        self.assertIsNone(error)
        self.assertEqual(code, 200)

        status, _row, check_error, check_code = routes._check_payhip_order_row_for_redeem(
            order_id=order_code,
            order_row=resolved_row,
            product_type="western_basic",
        )
        self.assertEqual(status, "already_used")
        self.assertIsNotNone(check_error)
        self.assertEqual(check_code, 409)

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

    def test_payhip_reusable_order_row_stays_reusable(self) -> None:
        for payment_status in ("reusable", "test", "permanent"):
            status, row, error, code = routes._check_payhip_order_row_for_redeem(
                order_id="LWR6l4Y4Wa",
                order_row={
                    "stores_order_no": "LWR6l4Y4Wa",
                    "payment_status": payment_status,
                    "product_type": "western_basic",
                },
                product_type="western_basic",
            )

            self.assertEqual(status, "reusable", payment_status)
            self.assertIsNotNone(row, payment_status)
            self.assertIsNone(error, payment_status)
            self.assertEqual(code, 200, payment_status)

    def test_payhip_reusable_order_row_still_checks_product_type(self) -> None:
        status, row, error, code = routes._check_payhip_order_row_for_redeem(
            order_id="LWR6l4Y4Wa",
            order_row={
                "stores_order_no": "LWR6l4Y4Wa",
                "payment_status": "reusable",
                "product_type": "western_full",
            },
            product_type="western_basic",
        )

        self.assertEqual(status, "product_mismatch")
        self.assertIsNotNone(row)
        self.assertIsNotNone(error)
        self.assertEqual(code, 409)

    def test_payhip_missing_order_row_is_not_found(self) -> None:
        status, row, error, code = routes._check_payhip_order_row_for_redeem(
            order_id="LWR6l4Y4Wa",
            order_row=None,
            product_type="western_basic",
        )

        self.assertEqual(status, "not_found")
        self.assertIsNone(row)
        self.assertIsNotNone(error)
        self.assertEqual(code, 400)


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
