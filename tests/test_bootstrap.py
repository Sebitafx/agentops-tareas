"""No confundir handshake, disponibilidad y procesamiento de mensajes."""

import pytest
from fastapi.testclient import TestClient

from bootstrap.main import app

client = TestClient(app)


def test_health_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert client.get("/health").json() == {"status": "ok", "stage": "receiver"}
    assert client.get("/version").json() == {"commit": "abc123"}


def test_local_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("APP_COMMIT", raising=False)
    assert client.get("/version").json() == {"commit": "local"}


def test_not_ready_or_accepting_messages() -> None:
    assert client.get("/ready").status_code == 503
    assert client.post("/webhooks/whatsapp", json={}).status_code == 503


@pytest.mark.parametrize(
    ("configured", "token", "mode", "status"),
    [
        ("", "x", "subscribe", 503),
        ("secret", "bad", "subscribe", 403),
        ("secret", "secret", "wrong", 403),
        ("secret", "secret", "subscribe", 200),
    ],
)
def test_handshake(
    monkeypatch: pytest.MonkeyPatch, configured: str, token: str, mode: str, status: int
) -> None:
    monkeypatch.setenv("META_VERIFY_TOKEN", configured)
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": mode,
            "hub.verify_token": token,
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == status
    if status == 200:
        assert response.text == "12345"
        assert response.headers["content-type"].startswith("text/plain")


def test_missing_parameters_rejected() -> None:
    assert client.get("/webhooks/whatsapp").status_code == 422
