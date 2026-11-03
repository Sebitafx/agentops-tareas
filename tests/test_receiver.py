import hashlib
import hmac
import json
import logging

import psycopg
import pytest
from fastapi.testclient import TestClient

from bootstrap.main import app
from bootstrap.whatsapp import MAX_BODY_BYTES, valid_signature


def delivery(text: str = "Hola AgentOps") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "12345"},
                            "messages": [
                                {
                                    "id": "wamid.test",
                                    "from": "51900000001",
                                    "timestamp": "1793392350",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }


def signed_post(client: TestClient, event: dict | bytes, signature: str | None = None):
    body = event if isinstance(event, bytes) else json.dumps(event).encode()
    actual_signature = "sha256=" + hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"x-hub-signature-256": signature if signature is not None else actual_signature},
    )


class FakeDatabase:
    def __init__(self) -> None:
        self.messages = []
        self.statuses = []

    def check(self) -> None:
        pass

    def save(self, messages, statuses) -> None:
        self.messages.extend(messages)
        self.statuses.extend(statuses)


@pytest.fixture
def client(receiver_env):
    with TestClient(app) as client:
        app.state.database = FakeDatabase()
        yield client


def test_authenticated_text_persisted_before_ack(client) -> None:
    response = signed_post(client, delivery("acción ' ; DROP TABLE prueba; --"))
    assert response.status_code == 200
    assert app.state.database.messages[0].body == "acción ' ; DROP TABLE prueba; --"
    assert app.state.database.messages[0].sender == "51900000001"
    assert app.state.database.messages[0].sent_at.tzinfo is not None


@pytest.mark.parametrize("signature", ["", "sha256=bad", "sha256=" + "0" * 64, "invalid"])
def test_invalid_signatures_rejected(client, signature) -> None:
    assert signed_post(client, delivery(), signature).status_code == 403
    assert app.state.database.messages == []


def test_tampering_invalidates_signature() -> None:
    signature = "sha256=" + hmac.new(b"secret", b"original", hashlib.sha256).hexdigest()
    assert valid_signature(b"original", signature, "secret")
    assert not valid_signature(b"modified", signature, "secret")
    assert not valid_signature(b"original", signature, "")
    assert not valid_signature(b"original", "💥", "secret")


@pytest.mark.parametrize("kind", ["sender", "phone", "media", "unrelated"])
def test_out_of_scope_ignored(client, kind) -> None:
    event = delivery()
    change = event["entry"][0]["changes"][0]
    value = change["value"]
    if kind == "sender":
        value["messages"][0]["from"] = "51900000002"
    elif kind == "phone":
        value["metadata"]["phone_number_id"] = "54321"
    elif kind == "media":
        value["messages"][0]["type"] = "image"
        del value["messages"][0]["text"]
    else:
        change["field"] = "account_alerts"
        change["value"] = {}
    assert signed_post(client, event).status_code == 200
    assert app.state.database.messages == []


def test_status_not_converted_to_task(client) -> None:
    event = delivery()
    value = event["entry"][0]["changes"][0]["value"]
    value.pop("messages")
    value["statuses"] = [{"id": "wamid.sent", "status": "delivered", "timestamp": "1793392350"}]
    assert signed_post(client, event).status_code == 200
    assert app.state.database.messages == []
    assert app.state.database.statuses[0].status == "delivered"


@pytest.mark.parametrize("event", [b"invalid json", b"[]", b"{}", b'{"object":"other","entry":[]}'])
def test_invalid_event_rejected(client, event) -> None:
    assert signed_post(client, event).status_code == 400
    assert app.state.database.messages == []


def test_missing_text_rejected(client) -> None:
    event = delivery()
    del event["entry"][0]["changes"][0]["value"]["messages"][0]["text"]
    assert signed_post(client, event).status_code == 400


def test_body_limit(client) -> None:
    assert signed_post(client, b"x" * (MAX_BODY_BYTES + 1)).status_code == 413


def test_database_failure_not_acknowledged(client, monkeypatch, caplog) -> None:
    def failing_save(*args):
        raise psycopg.OperationalError("postgresql://private-password@private-host")

    monkeypatch.setattr(app.state.database, "save", failing_save)
    response = signed_post(client, delivery())
    assert response.status_code == 503
    assert "private-password" not in response.text + caplog.text
    assert "private-host" not in response.text + caplog.text


def test_readiness_reports_database_and_pending_agents(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["receiver_configured"] is True
    assert response.json()["agents"] == "pending"


def test_readiness_failure(client, monkeypatch) -> None:
    def failing_check():
        raise psycopg.OperationalError("unavailable")

    monkeypatch.setattr(app.state.database, "check", failing_check)
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_missing_storage_no_ack(receiver_env) -> None:
    with TestClient(app) as client:
        assert signed_post(client, delivery()).status_code == 503


@pytest.mark.parametrize("value", ["", "+51900000001", "wrong"])
def test_bad_allowlist_fails_closed(client, monkeypatch, value) -> None:
    monkeypatch.setenv("WHATSAPP_ALLOWED_SENDERS", value)
    assert signed_post(client, delivery()).status_code == 503
    assert app.state.database.messages == []


def test_startup_migration_failure_sanitized(monkeypatch, caplog) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://private-password@private-host")

    def fail_migration(self):
        raise psycopg.OperationalError("private-password at private-host")

    monkeypatch.setattr("bootstrap.database.Database.migrate", fail_migration)
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503
        assert client.get("/health").status_code == 200
    assert "private-password" not in caplog.text
    assert "private-host" not in caplog.text


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("allowed", "messages=1"),
        ("phone", "ignored_phone_changes=1"),
        ("sender", "ignored_senders=1"),
        ("media", "ignored_types=1"),
        ("unrelated", "ignored_fields=1"),
    ],
)
def test_diagnostic_counts_without_personal_data(client, caplog, kind, expected) -> None:
    caplog.set_level(logging.INFO, logger="uvicorn.error.agentops")
    event = delivery("private-body-should-never-be-logged")
    change = event["entry"][0]["changes"][0]
    if kind == "phone":
        change["value"]["metadata"]["phone_number_id"] = "54321"
    elif kind == "sender":
        change["value"]["messages"][0]["from"] = "51900000002"
    elif kind == "media":
        change["value"]["messages"][0]["type"] = "image"
    elif kind == "unrelated":
        change["field"] = "account_alerts"
    assert signed_post(client, event).status_code == 200
    assert "stage=received" in caplog.text
    assert "stage=accepted" in caplog.text
    assert expected in caplog.text
    for private in (
        "51900000001",
        "51900000002",
        "12345",
        "54321",
        "wamid.test",
        "private-body-should-never-be-logged",
        "test-app-secret",
    ):
        assert private not in caplog.text
    if kind != "allowed":
        assert "messages=0" in caplog.text


def test_diagnostic_signature_rejection_without_credentials(client, caplog) -> None:
    assert signed_post(client, delivery(), "sha256=" + "0" * 64).status_code == 403
    assert "reason=signature" in caplog.text
    assert "stage=accepted" not in caplog.text
    assert "test-app-secret" not in caplog.text


def test_diagnostic_database_failure_never_claims_acceptance(client, monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="uvicorn.error.agentops")

    def fail(*args):
        raise psycopg.OperationalError("private-host private-password")

    monkeypatch.setattr(app.state.database, "save", fail)
    assert signed_post(client, delivery()).status_code == 503
    assert "reason=database" in caplog.text
    assert "stage=accepted" not in caplog.text
    assert "private-password" not in caplog.text
