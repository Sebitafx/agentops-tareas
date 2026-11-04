import os

import pytest

from bootstrap.database import Database


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nunca conectar por accidente a una base personal desde las pruebas.
    for key in (
        "DATABASE_URL",
        "META_APP_SECRET",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_ALLOWED_SENDERS",
        "META_VERIFY_TOKEN",
        "WHATSAPP_TOKEN",
        "META_GRAPH_VERSION",
        "SERVICE_ROLE",
        "AGENT_APP_ID",
        "AGENT_APP_PRIVATE_KEY",
        "RENDER_TASKS_DEPLOY_HOOK",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def receiver_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setenv("WHATSAPP_ALLOWED_SENDERS", "51900000001")


@pytest.fixture
def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configurar TEST_DATABASE_URL para integracion PostgreSQL")
    database = Database(url)
    with database.connect() as conn:
        if conn.execute("SELECT current_database()").fetchone()[0] != "agentops_test":
            pytest.fail("Integracion requiere una base aislada llamada agentops_test")
    database.migrate()
    with database.connect() as conn:
        conn.execute(
            "TRUNCATE agentops_inbox, agentops_delivery_status, agentops_tasks, agentops_jobs, agentops_outbox"
        )
    yield database
