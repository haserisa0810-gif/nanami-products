"""Safe defaults for pytest; production application configuration is untouched."""
from contextlib import ExitStack
import os
import socket
import threading
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn
import pytest


# setdefault would preserve an existing empty string and skip order checks.
# This is deliberately a test-only, unconditional replacement, before collection.
os.environ["DATABASE_URL"] = "postgresql://fictional.invalid:5432/never"


def pytest_addoption(parser):
    parser.addoption(
        "--local-fixture-services", action="store_true", default=False,
        help="Permit opt-in loopback fixture services only; never a remote database.",
    )


def pytest_configure(config):
    allow_local = config.getoption("--local-fixture-services")
    fixture_dsn = os.environ.get("TEST_ORDER_DATABASE_URL", "")
    if allow_local:
        settings = parse_dsn(fixture_dsn) if fixture_dsn else {}
        if (settings.get("host") not in {"127.0.0.1", "::1"}
                or not settings.get("dbname", "").startswith("np_o03_")
                or settings.get("hostaddr") or settings.get("service")):
            raise pytest.UsageError(
                "Local fixtures require a literal loopback host and np_o03_ database."
            )

    state = threading.local()
    original_pair = socket.socketpair
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_lookup = socket.getaddrinfo
    original_db_connect = psycopg2.connect

    def blocked(*args, **kwargs):
        raise RuntimeError("pytest offline guard: external network/DB connection blocked")

    def local_address(address):
        return (allow_local and isinstance(address, tuple)
                and address[0] in {"127.0.0.1", "::1"})

    def pair(*args, **kwargs):
        # Windows implements asyncio's socketpair using internal loopback IPC.
        state.in_socketpair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            state.in_socketpair = False

    def connect(sock, address):
        if getattr(state, "in_socketpair", False) or local_address(address):
            return original_connect(sock, address)
        return blocked()

    def connect_ex(sock, address):
        if getattr(state, "in_socketpair", False) or local_address(address):
            return original_connect_ex(sock, address)
        return blocked()

    def lookup(host, *args, **kwargs):
        if allow_local and host in {"127.0.0.1", "::1"}:
            return original_lookup(host, *args, **kwargs)
        return blocked()

    def db_connect(dsn=None, *args, **kwargs):
        if (allow_local and dsn == fixture_dsn and not args
                and set(kwargs) <= {"cursor_factory", "connect_timeout"}):
            return original_db_connect(dsn, **kwargs)
        return blocked()

    stack = ExitStack()
    config._nanami_offline_guard = stack
    stack.enter_context(patch("socket.socketpair", pair))
    stack.enter_context(patch("socket.socket.connect", connect))
    stack.enter_context(patch("socket.socket.connect_ex", connect_ex))
    stack.enter_context(patch("socket.getaddrinfo", lookup))
    stack.enter_context(patch("psycopg2.connect", db_connect))


def pytest_unconfigure(config):
    stack = getattr(config, "_nanami_offline_guard", None)
    if stack is not None:
        stack.close()
