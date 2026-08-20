from __future__ import annotations

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")

from services import stores_mail_sync as sync

# nanami-astro.stores.jp で実際に販売している商品と、その商品コード。
# 判定できないと product_type が NULL で登録され、
# routes._check_order_for_redeem の商品種別チェックが素通りする
# （purchased_type が falsy だと比較が行われない）ため、
# 安い注文番号で高い商品を発行できてしまう。
LIVE_STORES_PRODUCTS = [
    ("[NP-WB] AI占い for AI｜西洋占星術 出生図データ 基本版", "western_basic"),
    ("[NP-SC] AI占い for AI｜四柱推命 命式データ", "shichu"),
    (
        "[NP-WF] AI占い for AI｜西洋占星術 出生図データ FULL版（小惑星＋トランジット31日分）",
        "western_full",
    ),
    ("[NP-WT] 月替わりトランジット｜指定月の星読みデータ38日分", "western_31days_transit_addon"),
    ("[NP-WA] ホロスコープ・小惑星データ", "western_asteroids_addon"),
    ("[NP-WL] 長期トランジット（1年間）", "western_long_term_transits_addon"),
]

STORES_SUBJECT = "【STORES】アイテムが購入されました！（オーダー番号：9123456789）"


class LiveStoresProductCodeTest(unittest.TestCase):
    def test_every_live_product_is_classified(self) -> None:
        for title, expected in LIVE_STORES_PRODUCTS:
            with self.subTest(title=title):
                actual = sync._guess_product_type(STORES_SUBJECT, f"商品名: {title}\n数量: 1")
                self.assertEqual(
                    actual,
                    expected,
                    f"{title} が {actual} と判定されました。"
                    "未分類(None)だと商品種別チェックが素通りします。",
                )

    def test_classification_survives_extra_body_text(self) -> None:
        # STORESの通知本文は定型文が続く。周辺の語に引きずられて
        # 別商品に化けないこと（特に「追加」「トランジット」）。
        noise = (
            "\n数量: 1\n合計: 800円\n"
            "※追加のご案内はマイページをご確認ください。\n"
            "※トランジットデータの追加購入もご検討ください。\n"
        )
        for title, expected in LIVE_STORES_PRODUCTS:
            with self.subTest(title=title):
                self.assertEqual(
                    sync._guess_product_type(STORES_SUBJECT, f"商品名: {title}{noise}"),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
