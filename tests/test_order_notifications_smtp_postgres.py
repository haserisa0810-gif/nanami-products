"""Real TLS SMTP + isolated PostgreSQL integration; no external email delivery.

Opt in with TEST_ORDER_SMTP_INTEGRATION=1 and TEST_ORDER_DATABASE_URL.
Requires aiosmtpd and openssl in the isolated test environment only.
"""
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
import os
import socket
import ssl
import subprocess
import threading

import pytest

from test_purchase_notifications_postgres import database, ingest, scalar
from services import order_holds


class MailSink:
    def __init__(self):
        self.messages = []
        self.reject = False

    async def handle_DATA(self, server, session, envelope):
        if self.reject:
            return '451 Temporary failure for integration test'
        self.messages.append(envelope.content)
        return '250 Accepted into isolated test sink'


@pytest.fixture(params=['ssl', 'starttls'])
def smtp_sink(request, tmp_path, monkeypatch):
    if os.getenv('TEST_ORDER_SMTP_INTEGRATION') != '1':
        pytest.skip('未実施: isolated TLS SMTP integration not enabled')
    smtp = pytest.importorskip('aiosmtpd.smtp')
    controller_module = pytest.importorskip('aiosmtpd.controller')
    cert, key = tmp_path / 'server.pem', tmp_path / 'server.key'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-subj', '/CN=localhost', '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost',
                    '-keyout', str(key), '-out', str(cert)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    monkeypatch.setenv('SSL_CERT_FILE', str(cert))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    sink = MailSink()
    def authenticate(server, session, envelope, mechanism, auth_data):
        # Implicit SSL is encrypted even though aiosmtpd's STARTTLS flag is false.
        assert server.transport.get_extra_info('ssl_object') is not None
        return smtp.AuthResult(success=(auth_data.login == b'fixture' and auth_data.password == b'fixture-secret'),
                               handled=False)
    kwargs = {'ssl_context': context, 'auth_require_tls': False} if request.param == 'ssl' else {
        'tls_context': context, 'require_starttls': True, 'auth_require_tls': True}
    controller = controller_module.Controller(sink, hostname='127.0.0.1', port=port,
        authenticator=authenticate, auth_required=True, ready_timeout=5, **kwargs)
    values = {'ORDER_HOLD_NOTIFY_TO': 'operator@example.invalid', 'ORDER_HOLD_NOTIFY_FROM': 'sender@example.invalid',
              'ORDER_HOLD_SMTP_HOST': '127.0.0.1', 'ORDER_HOLD_SMTP_PORT': str(port),
              'ORDER_HOLD_SMTP_USERNAME': 'fixture', 'ORDER_HOLD_SMTP_PASSWORD': 'fixture-secret',
              'ORDER_HOLD_SMTP_SECURITY': request.param}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    controller.start()
    try:
        yield sink
    finally:
        controller.stop()


def dispatch(database):
    with database[0]() as con:
        return order_holds.dispatch_pending_notices(con)


def test_actual_smtp_failure_retry_and_notice_state_persist(database, smtp_sink):
    ingest(database, 'Order ID: SmtpRetry\nProduct: [NP-SFULL]\nBuyer: private@example.invalid')
    smtp_sink.reject = True
    assert dispatch(database) == {'status': 'configured', 'sent': 0, 'failed': 1}
    assert scalar(database, "SELECT notification_status FROM {schema}.marketplace_order_holds") == 'pending'
    assert scalar(database, "SELECT notification_attempts FROM {schema}.marketplace_order_holds") == 1
    # Immediate retry must respect the existing five-minute backoff.
    assert dispatch(database) == {'status': 'configured', 'sent': 0, 'failed': 0}
    with database[0]() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE {database[1]}.marketplace_order_holds "
                        "SET last_notification_at = NOW() - INTERVAL '6 minutes'")
    smtp_sink.reject = False
    assert dispatch(database) == {'status': 'configured', 'sent': 1, 'failed': 0}
    assert scalar(database, "SELECT notification_status FROM {schema}.marketplace_order_holds") == 'sent'
    assert scalar(database, "SELECT notification_attempts FROM {schema}.marketplace_order_holds") == 2
    assert dispatch(database)['sent'] == 0
    assert len(smtp_sink.messages) == 1
    message = BytesParser(policy=policy.default).parsebytes(smtp_sink.messages[0])
    body = message.get_content()
    assert message['To'] == 'operator@example.invalid'
    assert 'payhip' in body and 'SmtpRetry' in body and 'unknown_product_code' in body
    assert 'private@example.invalid' not in body and 'fixture-secret' not in body
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.order_entitlements") == 0
    assert scalar(database, "SELECT COUNT(*) FROM {schema}.charts") == 0


def test_parallel_actual_smtp_dispatch_sends_one_notice(database, smtp_sink):
    ingest(database, 'Order ID: SmtpRace\nProduct: [NP-SFULL]')
    barrier = threading.Barrier(4)
    def worker(_):
        barrier.wait(timeout=5)
        return dispatch(database)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, range(4)))
    assert sum(row['sent'] for row in results) == 1
    assert len(smtp_sink.messages) == 1
    assert scalar(database, "SELECT notification_attempts FROM {schema}.marketplace_order_holds") == 1
