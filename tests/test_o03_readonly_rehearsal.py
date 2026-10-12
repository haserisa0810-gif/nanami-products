"""Local ASGI rehearsal of a proposed gate, NOT a production L7/ACL test."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import routes


class ProposedGate:
    """Rehearsal fixture only; this policy is not installed in the application."""

    def __init__(self, app):
        self.app = app
        self.readonly = False
        self.active = 0
        self.condition = threading.Condition()

    def enter_readonly(self):
        with self.condition:
            self.readonly = True

    def drained(self, timeout):
        with self.condition:
            return self.condition.wait_for(lambda: self.active == 0, timeout)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        host = dict(scope.get("headers", [])).get(b"host", b"")
        raw_path = scope.get("raw_path", scope["path"].encode())
        raw_read = (scope["method"] == "GET"
                    and re.fullmatch(r"/chart/[A-Za-z0-9_-]{5,128}\.yaml", scope["path"])
                    and b"%" not in raw_path)
        with self.condition:
            deny = host != b"chart.fixture.invalid" or (self.readonly and not raw_read)
            if not deny:
                self.active += 1
        if deny:
            await send({"type": "http.response.start", "status": 503,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                    (b"cache-control", b"no-store"), (b"retry-after", b"60")]})
            await send({"type": "http.response.body", "body": b"Maintenance: saved YAML remains available"})
            return
        try:
            await self.app(scope, receive, send)
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()


@pytest.mark.parametrize("original", [
    "systems:\n  shichusuimei:\n    engine_version: 0.3.0\n",
    "systems:\n  shichusuimei:\n    engine_version: 0.4.0\n",
    "systems:\n  shichusuimei:\n    engine_version: 0.5.0\n",
])
def test_raw_original_survives_proposed_readonly_gate(monkeypatch, original):
    chart = {"token": "fictional", "yaml_text": original,
             "prompt_text": "Stored original", "options": {"product_type": "shichu"},
             "expires_at": None}
    before = deepcopy(chart)
    monkeypatch.setattr(routes.pg_store, "get_chart", lambda *a, **kw: deepcopy(chart))
    monkeypatch.setattr(routes.pg_store, "save_chart", lambda **kw: pytest.fail("Unexpected chart write"))
    gate = ProposedGate(routes.app)
    gate.enter_readonly()
    client = TestClient(gate, base_url="https://chart.fixture.invalid")
    response = client.get("/chart/fictional.yaml")
    assert response.status_code == 200
    assert response.content == original.encode("utf-8")
    assert chart == before


@pytest.mark.parametrize("path", [
    "/redeem", "/redeem/shichu-full", "/admin/yaml/generate", "/addon/generate",
    "/internal/mail-sync", "/api/calc/shichu", "/personal-edition/activate",
    "/internal/orders/holds/stores/Fictional/approve", "/mcp",
])
def test_proposed_gate_denies_write_and_sync_entrances(path):
    gate = ProposedGate(routes.app)
    gate.enter_readonly()
    response = TestClient(gate, base_url="https://chart.fixture.invalid").post(path)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("host", [f"candidate-{i}.fixture.invalid" for i in range(6)])
def test_proposed_gate_denies_direct_old_tag_hosts(host):
    gate = ProposedGate(routes.app)
    gate.enter_readonly()
    assert TestClient(gate, base_url=f"https://{host}").post("/redeem").status_code == 503


@pytest.mark.parametrize("path", ["/chart/fictional", "/internal/orders/holds",
                                   "/chart/fictional%2Fother.yaml"])
def test_unreviewed_gets_are_not_implicitly_allowed(path):
    gate = ProposedGate(routes.app)
    gate.enter_readonly()
    assert TestClient(gate, base_url="https://chart.fixture.invalid").get(path).status_code == 503


def test_gate_drains_an_existing_request_and_does_not_resume_after_timeout():
    app = FastAPI()
    entered, finish = threading.Event(), threading.Event()
    saved = []

    @app.post("/write")
    def write():
        entered.set()
        assert finish.wait(5)
        saved.append("one synthetic result")
        return {"ok": True}

    gate = ProposedGate(app)
    client = TestClient(gate, base_url="https://chart.fixture.invalid")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, "/write")
        try:
            assert entered.wait(5)
            started = time.perf_counter()
            gate.enter_readonly()
            assert not gate.drained(0)
            assert client.post("/write").status_code == 503
            finish.set()
            assert future.result(timeout=5).status_code == 200
            assert gate.drained(5)
            elapsed = time.perf_counter() - started
            assert saved == ["one synthetic result"]
            assert gate.readonly  # Never restore writes automatically.
        finally:
            finish.set()
    output = os.environ.get("O03_LOCAL_REHEARSAL_METRICS")
    if output:
        Path(output).write_text(json.dumps({
            "local_gate_and_drain_seconds": elapsed,
            "scope": "One in-memory ASGI request with an artificial release event",
            "production_outage_estimate": None,
            "postgresql_acl_tested": False, "cloud_ingress_tested": False,
        }, indent=2) + "\n", encoding="utf-8")
