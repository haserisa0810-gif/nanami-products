from __future__ import annotations

import os
import pathlib
import re
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")

from fastapi.testclient import TestClient

from routes import app

client = TestClient(app)

ORDER_FORM_PATHS = [
    "/addon/new",
    "/redeem/western-basic",
    "/redeem/western-full",
    "/redeem/shichu",
    "/redeem/transit-yaml",
]


class OrderCodeTrimAssetTest(unittest.TestCase):
    """注文番号欄の前後空白は、pattern検証にかかる前にクライアント側で除去する。"""

    def test_shared_trim_script_is_served(self) -> None:
        response = client.get("/static/order_code_input.js")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("data-trim-order-code", body)
        self.assertIn("replace(/^\\s+|\\s+$/g, '')", body)

    def test_every_order_form_loads_the_trim_script(self) -> None:
        for path in ORDER_FORM_PATHS:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("order_code_input.js", response.text)

    def test_order_code_inputs_are_marked_for_trimming(self) -> None:
        for path in ORDER_FORM_PATHS:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertIn("data-trim-order-code", response.text)


class AddonFormPayhipFieldsTest(unittest.TestCase):
    """Payhip購入者向けガイドPDFが案内する ?provider=payhip でOrder IDを入力できる。"""

    def test_payhip_provider_renders_order_id_field(self) -> None:
        response = client.get("/addon/new?provider=payhip")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('name="payhip_order_id"', body)
        self.assertIn('name="payhip_email"', body)
        self.assertIn('name="payhip_product_code"', body)
        self.assertIn('value="payhip"', body)

    def test_payhip_provider_hides_the_ten_digit_stores_field(self) -> None:
        body = client.get("/addon/new?provider=payhip").text
        # STORES用の10桁必須欄が残っていると、Payhipの英数字Order IDでは送信できない。
        self.assertNotIn('name="order_code"', body)
        self.assertNotIn('pattern="[0-9]{10}"', body)

    def test_stores_provider_keeps_the_order_code_field(self) -> None:
        body = client.get("/addon/new?provider=stores").text
        self.assertIn('name="order_code"', body)
        self.assertIn('pattern="[0-9]{10}"', body)
        self.assertNotIn('name="payhip_order_id"', body)

    def test_coconala_provider_keeps_the_free_text_buyer_field(self) -> None:
        body = client.get("/addon/new?provider=coconala").text
        self.assertIn('name="order_code"', body)
        self.assertNotIn('pattern="[0-9]{10}"', body)


class AddonFormProviderLabelTest(unittest.TestCase):
    """購入元ごとのラベルが、購入者ガイドPDFの案内文と食い違わないこと。"""

    def test_etsy_label_does_not_say_stores(self) -> None:
        for lang, expected in (("en", "Etsy order number"), ("ja", "Etsyの注文番号")):
            with self.subTest(lang=lang):
                body = client.get(f"/addon/new?provider=etsy&lang={lang}").text
                self.assertIn(expected, body)
                self.assertNotIn("STORES order number", body)
                self.assertNotIn("STORESオーダー番号", body)

    def test_stores_label_still_says_stores(self) -> None:
        body = client.get("/addon/new?provider=stores&lang=en").text
        self.assertIn("STORES order number", body)
        self.assertNotIn("Etsy order number", body)

    def test_coconala_label_asks_for_username(self) -> None:
        body = client.get("/addon/new?provider=coconala&lang=en").text
        self.assertIn("Coconala username", body)
        self.assertNotIn("STORES order number", body)


# 購入者ガイドPDF（scripts/build_marketplace_product_guides.py）がEtsy購入者に
# 案内しているURL。ここに "STORES" が表示されると、購入元と食い違った指示になる。
ETSY_BUYER_URLS = [
    "/redeem/western-basic?lang=en&provider=etsy",
    "/redeem/western-full?lang=en&provider=etsy",
    "/redeem/western-transit?lang=en&provider=etsy",
    "/redeem/western-asteroids?lang=en&provider=etsy",
    "/redeem/acg-bundle?lang=en&provider=etsy",
    "/redeem/shichu?lang=en&provider=etsy",
    "/addon/new?lang=en&provider=etsy",
    "/addon/new?lang=ja&provider=etsy",
]

SCRIPT_BLOCK_RE = re.compile(r"<script.*?</script>", re.S)


class EtsyBuyerPagesMentionNoStoresTest(unittest.TestCase):
    """Etsy購入者に見える画面から、他社名（STORES）の指示が出ないこと。"""

    def test_no_visible_stores_wording_on_etsy_pages(self) -> None:
        for url in ETSY_BUYER_URLS:
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                # <script> の中身は画面に出ないので除外する。
                visible = SCRIPT_BLOCK_RE.sub("", response.text)
                self.assertNotIn("STORES", visible)

    def test_scripts_that_hardcode_a_stores_label_also_handle_etsy(self) -> None:
        # サーバー側で購入元別に出し分けても、読み込み時に走るJSが
        # textContent を上書きすれば表示は STORES に戻る。実際に
        # redeem_shichu.html がこれで「購入元: Etsy / STORESオーダー番号」に
        # なっていた。上のHTML走査は <script> を除外するので拾えない。
        stores_labels = ("STORESオーダー番号", "STORES order number")
        etsy_labels = ("Etsyの注文番号", "Etsy order number")
        for url in ETSY_BUYER_URLS:
            body = client.get(url).text
            for script in SCRIPT_BLOCK_RE.findall(body):
                if not any(label in script for label in stores_labels):
                    continue
                with self.subTest(url=url):
                    self.assertTrue(
                        any(label in script for label in etsy_labels),
                        f"{url}: JSが注文番号ラベルにSTORESを直書きしていますが、"
                        f"Etsy用の分岐がありません。読み込み時に表示が上書きされます。",
                    )


PATTERN_ATTR_RE = re.compile(r'pattern="([^"]+)"')
JS_PATTERN_RE = re.compile(r"\.pattern = '([^']+)'")
# v モード（現行ブラウザが pattern 属性のコンパイルに使う）では、文字クラス末尾の
# 素の '-' が構文エラーになる。壊れた pattern は例外ではなく「黙って無視」される
# ため、検証が丸ごと効かなくなっていても画面上は気づけない。
UNESCAPED_TRAILING_HYPHEN = re.compile(r"(?<!\\)-\]")


class PatternAttributeValidityTest(unittest.TestCase):
    """pattern 属性が v モードでコンパイルできること（できないと検証が無効化される）。"""

    def _assert_v_mode_safe(self, pattern: str, *, where: str) -> None:
        self.assertIsNone(
            UNESCAPED_TRAILING_HYPHEN.search(pattern),
            f"{where}: pattern {pattern!r} は v モードで無効になり、検証が無視されます。"
            r" 文字クラス末尾の '-' は '\-' とエスケープしてください。",
        )

    def test_rendered_pattern_attributes_compile_in_v_mode(self) -> None:
        for path in ORDER_FORM_PATHS + ["/redeem/western-full?provider=payhip"]:
            body = client.get(path).text
            for pattern in PATTERN_ATTR_RE.findall(body):
                with self.subTest(path=path, pattern=pattern):
                    self._assert_v_mode_safe(pattern, where=path)

    def test_no_template_ships_a_v_mode_hostile_pattern(self) -> None:
        # ルーティングされていない画面（管理者フォーム等）も取りこぼさない。
        templates_dir = pathlib.Path(__file__).resolve().parent.parent / "templates"
        checked = 0
        for template in sorted(templates_dir.rglob("*.html")):
            for pattern in PATTERN_ATTR_RE.findall(template.read_text(encoding="utf-8")):
                checked += 1
                with self.subTest(template=template.name, pattern=pattern):
                    self._assert_v_mode_safe(pattern, where=str(template.relative_to(templates_dir)))
        self.assertGreater(checked, 0, "pattern属性が1件も見つかりませんでした")

    def test_patterns_assigned_from_javascript_survive_string_unescaping(self) -> None:
        # JS文字列リテラル内の '\-' はエスケープ解除されて '-' に戻るため、
        # 属性値と同じ効果を得るには '\\-' と書く必要がある。
        for path in ORDER_FORM_PATHS:
            body = client.get(path).text
            for raw in JS_PATTERN_RE.findall(body):
                with self.subTest(path=path, pattern=raw):
                    unescaped = raw.replace("\\\\", "\\")
                    self._assert_v_mode_safe(unescaped, where=f"{path} (JS)")


if __name__ == "__main__":
    unittest.main()
