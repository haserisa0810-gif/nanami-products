from __future__ import annotations

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test")

from fastapi.testclient import TestClient

from routes import app

client = TestClient(app)

EXPECTED = {"ok": True, "service": "nanami-products"}


class HealthEndpointTest(unittest.TestCase):
    """
    死活監視の窓口は /health。

    Google Front End は完全一致の `/healthz` を予約パスとして横取りし、
    コンテナへ転送しない。Cloud Run の外部URL（run.app・独自ドメインとも）では
    アプリに届く前に Google の 404 HTML が返るため、外部監視には使えない。
    実測では `/healthz` だけが遮断され、`/health` `/healthz2` `/livez` 等は
    アプリに到達した。
    """

    def test_health_is_served(self) -> None:
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), EXPECTED)

    def test_healthz_alias_is_kept_for_direct_container_access(self) -> None:
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), EXPECTED)

    def test_external_monitoring_path_is_not_the_reserved_one(self) -> None:
        # /health が消えて /healthz だけに戻ると、外部監視が再び全滅する。
        paths = {
            route.path for route in app.routes if getattr(route, "path", "") in {"/health", "/healthz"}
        }
        self.assertIn(
            "/health",
            paths,
            "外部監視用の /health がありません。/healthz は Google に横取りされるため単独では使えません。",
        )


if __name__ == "__main__":
    unittest.main()
