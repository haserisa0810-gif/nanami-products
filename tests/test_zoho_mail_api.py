from __future__ import annotations

from email.message import EmailMessage

import pytest

from services.zoho_mail_api import ZohoMailApiError, ZohoMailClient, ZohoMailConfig


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *, post_responses, get_responses):
        self.post_responses = list(post_responses)
        self.get_responses = list(get_responses)
        self.posts = []
        self.gets = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.post_responses.pop(0)

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.get_responses.pop(0)


def config(**overrides):
    values = {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
        "account_id": "12345",
        "username": "support@nanami-astro.com",
        "accounts_base_url": "https://accounts.zoho.jp",
        "mail_api_base_url": "https://mail.zoho.jp/api",
        "timeout_seconds": 15,
    }
    values.update(overrides)
    return ZohoMailConfig(**values)


def test_fetch_original_messages_uses_read_only_api_and_returns_mime_bytes():
    mime = EmailMessage()
    mime["From"] = "hello@stores.jp"
    mime["Subject"] = "order"
    mime.set_content("body")
    session = FakeSession(
        post_responses=[FakeResponse({"access_token": "access-token"})],
        get_responses=[
            FakeResponse(
                {
                    "status": {"code": 200},
                    "data": [
                        {"messageId": "2", "receivedtime": 200},
                        {"messageId": "1", "receivedtime": 100},
                    ],
                }
            ),
            FakeResponse({"status": {"code": 200}, "data": {"content": mime.as_string()}}),
            FakeResponse({"status": {"code": 200}, "data": {"content": mime.as_string()}}),
        ],
    )

    messages = ZohoMailClient(config(), session=session).fetch_original_messages(
        senders=["hello@stores.jp", "emails@mail.etsy.com"],
        limit=2,
    )

    assert len(messages) == 2
    assert b"Subject: order" in messages[0]
    token_request = session.posts[0]
    assert token_request[0] == "https://accounts.zoho.jp/oauth/v2/token"
    assert token_request[1]["data"]["grant_type"] == "refresh_token"
    search_request = session.gets[0]
    assert search_request[0].endswith("/accounts/12345/messages/search")
    assert search_request[1]["params"]["searchKey"] == (
        "sender:hello@stores.jp::or:sender:emails@mail.etsy.com"
    )
    assert search_request[1]["params"]["limit"] == 2
    assert all(call[1].get("params") is None for call in session.gets[1:])


def test_account_id_can_be_resolved_from_username():
    session = FakeSession(
        post_responses=[FakeResponse({"access_token": "access-token"})],
        get_responses=[
            FakeResponse(
                {
                    "status": {"code": 200},
                    "data": [
                        {
                            "accountId": "67890",
                            "mailboxAddress": "support@nanami-astro.com",
                        }
                    ],
                }
            )
        ],
    )
    client = ZohoMailClient(config(account_id=""), session=session)

    assert client.account_id() == "67890"
    assert session.gets[0][0].endswith("/accounts")


def test_missing_oauth_configuration_fails_without_exposing_values(monkeypatch):
    monkeypatch.delenv("ZOHO_MAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_MAIL_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ZOHO_MAIL_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("STORES_MAIL_USERNAME", "support@nanami-astro.com")

    with pytest.raises(ZohoMailApiError, match="ZOHO_MAIL_CLIENT_ID"):
        ZohoMailConfig.from_env()


def test_refresh_failure_does_not_include_secret_values():
    session = FakeSession(
        post_responses=[FakeResponse({"error": "invalid_client"}, status_code=400)],
        get_responses=[],
    )
    client = ZohoMailClient(config(), session=session)

    with pytest.raises(ZohoMailApiError) as exc_info:
        client.fetch_original_messages(senders=["hello@stores.jp"], limit=1)

    message = str(exc_info.value)
    assert "invalid_client" in message
    assert "client-secret" not in message
    assert "refresh-token" not in message
