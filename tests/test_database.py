"""Integracion real; usar exclusivamente una base local llamada agentops_test."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient

from bootstrap.database import Database, DeliveryStatus, IncomingMessage, SchemaError
from bootstrap.main import app
from tests.test_receiver import delivery, signed_post


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
        conn.execute("TRUNCATE agentops_inbox, agentops_delivery_status")
    yield database


def example() -> IncomingMessage:
    return IncomingMessage("wamid.test", "12345", "51900000001", "test", datetime.now(UTC))


def test_migrations_repeat_and_concurrent(database) -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: database.migrate(), range(2)))
    database.check()
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM agentops_schema_versions").fetchone()[0] == 1


def test_duplicate_concurrent_messages(database) -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: database.save([example()], []), range(8)))
    assert database.summary() == {"messages": 1}


def test_batch_rollback_on_error(database) -> None:
    bad_status = DeliveryStatus("bad", None, datetime.now(UTC))
    with pytest.raises(psycopg.IntegrityError):
        database.save([example()], [bad_status])
    assert database.summary() == {"messages": 0}


def test_status_deduplication_and_sql_parameters(database) -> None:
    message = IncomingMessage(
        "wamid.sql", "12345", "51900000001", "'; DROP TABLE agentops_inbox; --", datetime.now(UTC)
    )
    status = DeliveryStatus("wamid.sql", "read", datetime.now(UTC))
    database.save([message], [status, status])
    with database.connect() as conn:
        assert conn.execute("SELECT body FROM agentops_inbox").fetchone()[0] == message.body
        assert conn.execute("SELECT count(*) FROM agentops_delivery_status").fetchone()[0] == 1


def test_schema_drift_detected(database) -> None:
    with database.connect() as conn:
        original = conn.execute("SELECT checksum FROM agentops_schema_versions").fetchone()[0]
        conn.execute("UPDATE agentops_schema_versions SET checksum = 'tampered'")
    try:
        with pytest.raises(SchemaError):
            database.migrate()
    finally:
        with database.connect() as conn:
            conn.execute("UPDATE agentops_schema_versions SET checksum = %s", (original,))


def test_http_restart_preserves_message(database, monkeypatch, receiver_env) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200
        assert signed_post(client, delivery()).status_code == 200
    with TestClient(app) as client:
        assert signed_post(client, delivery()).status_code == 200
        assert client.get("/ready").status_code == 200
    assert database.summary()["messages"] == 1
