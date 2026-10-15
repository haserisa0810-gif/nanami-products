"""Buyer waiting-copy regression checks; no app import or DB connection."""
import ast
from pathlib import Path
import unittest

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


class RedeemWaitNoticeTest(unittest.TestCase):
    def test_every_redeem_form_has_notice_before_submission(self):
        env = Environment(loader=FileSystemLoader(ROOT / "templates"))
        for name in ("redeem.html", "redeem_western_basic.html", "redeem_western_full.html", "redeem_shichu.html", "redeem_shichu_full.html", "redeem_transit_yaml.html"):
            with self.subTest(template=name):
                source = (ROOT / "templates" / name).read_text(encoding="utf-8")
                env.get_template(name)
                self.assertLess(source.index('id="generation-wait-notice"'), source.index('<button type="submit" class="submit-button">'))
                self.assertIn("{{ t.submit_loading_desc }}", source)
                self.assertIn("submitGuardActive", source)

    def test_localized_copy_explains_estimate_and_waiting(self):
        copies = []
        for filename in ("routes.py", "services/site_locales.py"):
            tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if isinstance(key, ast.Constant) and key.value == "submit_loading_desc":
                            copies.append(ast.literal_eval(value))
        self.assertEqual(len(copies), 4)
        for copy in copies:
            self.assertRegex(copy, r"10[〜–]60")
        self.assertIn("目安", copies[0])
        self.assertIn("さらに時間がかかる", copies[0])

    def test_modal_forms_reuse_visible_waiting_copy(self):
        for name in ("redeem_western_basic.html", "redeem_western_full.html", "redeem_shichu.html", "redeem_shichu_full.html"):
            with self.subTest(template=name):
                source = (ROOT / "templates" / name).read_text(encoding="utf-8")
                self.assertIn("desc: {{ t.submit_loading_desc | tojson }}", source)
                self.assertIn("aria-live", source)


def test_four_pillars_full_renders_wait_notice(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:1/unused")
    from fastapi.testclient import TestClient
    from routes import app
    response = TestClient(app).get("/redeem/shichu-full")
    assert response.status_code == 200
    assert 'id="generation-wait-notice"' in response.text
    assert "10〜60秒" in response.text
    assert "四柱推命FULL" in response.text
