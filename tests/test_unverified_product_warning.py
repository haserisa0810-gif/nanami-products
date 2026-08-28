from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")

import routes


class UnverifiedProductTypeWarningTest(unittest.TestCase):
    """
    商品種別を判定できない注文は、発行を止めずに warning を残す。

    product_type が NULL の注文は商品種別チェックを素通りするので
    （安い注文番号で高い商品を発行できてしまう）、運用で気づけるように
    ログに出す。商品コードの判定漏れが主因。
    """

    def _redeem_check(self, order_row, status="ok", provider="stores"):
        with patch(
            "routes.stores_mail_sync.verify_order_entitlement",
            return_value=(status, order_row),
        ):
            with self.assertLogs("nanami.chart", level="INFO") as captured:
                result = routes._check_order_for_redeem(
                    order_id="9123456789",
                    provider=provider,
                    product_type="western_full",
                    enforce_product_type=True,
                )
        return result, captured.output

    def test_warns_when_product_type_is_missing(self) -> None:
        row = {"stores_order_no": "9123456789", "provider": "stores", "product_type": None,
               "payment_status": "paid"}
        (status, _row, error, code), logs = self._redeem_check(row)
        # 発行は止めない
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.assertEqual(code, 200)
        warnings = [line for line in logs if "order_product_unverified" in line]
        self.assertEqual(len(warnings), 1, logs)
        self.assertIn("WARNING", warnings[0])
        self.assertIn("issued_as=western_full", warnings[0])
        self.assertIn("_PRODUCT_CODE_PATTERNS", warnings[0])

    def test_no_warning_when_product_type_is_known(self) -> None:
        row = {"stores_order_no": "9123456789", "provider": "stores",
               "product_type": "western_full", "payment_status": "paid"}
        (status, _row, error, _code), logs = self._redeem_check(row)
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.assertEqual([line for line in logs if "order_product_unverified" in line], [])

    def test_no_warning_for_reusable_test_numbers(self) -> None:
        # 身内・テスト用番号は product_type 未設定でも想定内なので黙らせる。
        row = {"stores_order_no": "9000000002", "provider": "stores", "product_type": None,
               "payment_status": "reusable"}
        (_status, _row, _error, _code), logs = self._redeem_check(row, status="reusable")
        self.assertEqual([line for line in logs if "order_product_unverified" in line], [])


class AddonUnverifiedProductWarningTest(unittest.TestCase):
    def test_addon_path_warns_but_still_issues(self) -> None:
        row = {"stores_order_no": "9123456789", "provider": "stores", "product_type": None,
               "payment_status": "paid"}
        with patch("routes.pg_store.redeem_addon_order", return_value=("ok", row)):
            with self.assertLogs("nanami.chart", level="INFO") as captured:
                result = routes._redeem_addon_order_or_raise(
                    "9123456789", "stores", "western_long_term_transits_addon",
                )
        self.assertEqual(result, "9123456789")
        warnings = [line for line in captured.output if "order_product_unverified" in line]
        self.assertEqual(len(warnings), 1, captured.output)
        self.assertIn("context=addon", warnings[0])

    def test_addon_path_stays_quiet_for_permanent_key(self) -> None:
        # 9700000007 は product_type 未設定の常設テストキー。毎回警告すると邪魔になる。
        row = {"stores_order_no": "9700000007", "provider": "stores", "product_type": None,
               "payment_status": "permanent"}
        with patch("routes.pg_store.redeem_addon_order", return_value=("ok", row)):
            with self.assertLogs("nanami.chart", level="INFO") as captured:
                routes._redeem_addon_order_or_raise(
                    "9700000007", "stores", "western_long_term_transits_addon",
                )
        self.assertEqual(
            [line for line in captured.output if "order_product_unverified" in line], []
        )


if __name__ == "__main__":
    unittest.main()
