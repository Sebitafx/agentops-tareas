import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nunca conectar por accidente a una base personal desde las pruebas.
    for key in (
        "DATABASE_URL",
        "META_APP_SECRET",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_ALLOWED_SENDERS",
        "META_VERIFY_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def receiver_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setenv("WHATSAPP_ALLOWED_SENDERS", "51900000001")
