from __future__ import annotations

import ast
import os
import pathlib
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")

from services import pg_store, stores_mail_sync

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# routes.py から呼ばれるサービス関数が実在すること。
#
# 存在しない関数の呼び出しは、到達しない分岐や except で握りつぶされた箇所に
# 潜むと本番まで気づけない。実際に pg_store の *_relaxed 系4関数と
# update_chart_svgs が、それぞれ「gumroadを手前で弾くので到達しない分岐」と
# 「try/except pass の内側」に隠れていた。
MODULES = {
    "pg_store": pg_store,
    "stores_mail_sync": stores_mail_sync,
}


def _referenced_attributes(source: str, module_name: str) -> set[str]:
    """`module_name.attr` の属性アクセスだけを集める。

    正規表現だと文字列リテラル内のファイルパス（"services/pg_store.py" など）まで
    拾ってしまうため、ASTで実際の属性参照だけを見る。
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == module_name
        ):
            found.add(node.attr)
    return found


class ServiceCallTargetsExistTest(unittest.TestCase):
    def test_every_service_attribute_referenced_by_routes_exists(self) -> None:
        source = (REPO_ROOT / "routes.py").read_text(encoding="utf-8")
        for module_name, module in MODULES.items():
            referenced = sorted(_referenced_attributes(source, module_name))
            self.assertTrue(referenced, f"{module_name} の参照が1件も見つかりませんでした")
            for attribute in referenced:
                with self.subTest(module=module_name, attribute=attribute):
                    self.assertTrue(
                        hasattr(module, attribute),
                        f"routes.py が {module_name}.{attribute} を呼んでいますが、"
                        f"services/{module_name}.py に存在しません。",
                    )

    def test_guard_ignores_module_names_inside_strings(self) -> None:
        # ログ文面などに "services/stores_mail_sync.py" と書いても誤検知しないこと。
        source = 'logger.warning("see services/stores_mail_sync.py for details")\n'
        self.assertEqual(_referenced_attributes(source, "stores_mail_sync"), set())

    def test_guard_still_detects_a_real_attribute_access(self) -> None:
        source = "pg_store.some_function(order_code=1)\n"
        self.assertEqual(_referenced_attributes(source, "pg_store"), {"some_function"})


if __name__ == "__main__":
    unittest.main()
