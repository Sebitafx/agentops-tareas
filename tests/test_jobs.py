from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from bootstrap import jobs
from bootstrap.database import IncomingMessage
from bootstrap.github_app import GitHubError
from bootstrap.jobs import Progress, claim_job, update_job
from bootstrap.main import app
from bootstrap.outbox import is_help


def seed(database):
    message = IncomingMessage(
        "wamid." + uuid4().hex,
        "12345",
        "51900000001",
        "Cambia el boton Crear por Agregar",
        datetime.now(UTC),
    )
    database.save([message], [])
    with database.connect() as conn:
        return conn.execute(
            "SELECT id FROM agentops_jobs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]


@pytest.mark.parametrize(
    "text",
    [
        "¿Qué puedes hacer?",
        "qué eres capaz de hacer?",
        "AYUDA",
        "hola",
        "¿Cómo funciona?",
        "ver estos comandos",
        "Ver comandos",
        "Muéstrame los comandos",
        "menú",
        "/ayuda",
        "¿Qué puedo hacer?",
    ],
)
def test_natural_help_does_not_create_request(database, text):
    assert is_help(text)
    database.save(
        [IncomingMessage("wamid." + uuid4().hex, "12345", "51900000001", text, datetime.now(UTC))],
        [],
    )
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM agentops_jobs").fetchone()[0] == 0
    assert not is_help("Cambia el texto de ayuda")


def test_one_workflow_claims_job_and_callbacks_are_idempotent(database):
    job_id = seed(database)

    def claim(number):
        try:
            return claim_job(database, job_id, str(number))
        except HTTPException as exc:
            assert exc.status_code == 409
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(claim, range(1, 5)))
    claimed = [result for result in results if result]
    assert len(claimed) == 1 and "sender" not in claimed[0]
    progress = Progress(
        lease=claimed[0]["lease"],
        state="pr_open",
        summary="PR validado https://github.com/Sebitafx/agentops-tareas/pull/1",
    )
    update_job(database, job_id, progress)
    update_job(database, job_id, progress)
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM agentops_outbox").fetchone()[0] == 2
    with pytest.raises(HTTPException) as error:
        update_job(database, job_id, Progress(lease=uuid4(), state="failed", summary="obsoleto"))
    assert error.value.status_code == 409


def test_clarification_resumes_original_job_and_invalidates_old_lease(database):
    job_id = seed(database)
    first = claim_job(database, job_id, "1")
    update_job(
        database, job_id, Progress(lease=first["lease"], state="needs_input", summary="¿Qué boton?")
    )
    database.save(
        [
            IncomingMessage(
                "wamid.answer",
                "12345",
                "51900000001",
                f"responder {job_id} El boton del formulario",
                datetime.now(UTC),
            )
        ],
        [],
    )
    second = claim_job(database, job_id, "2")
    assert "El boton del formulario" in second["request"]
    assert first["lease"] != second["lease"]
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM agentops_jobs").fetchone()[0] == 1
    with pytest.raises(HTTPException):
        update_job(database, job_id, Progress(lease=first["lease"], state="failed", summary="old"))


def test_another_sender_does_not_answer_private_question(database):
    job_id = seed(database)
    first = claim_job(database, job_id, "1")
    update_job(
        database, job_id, Progress(lease=first["lease"], state="needs_input", summary="¿Que boton?")
    )
    database.save(
        [
            IncomingMessage(
                "wamid.other", "12345", "51900000002", "agregar otro filtro", datetime.now(UTC)
            )
        ],
        [],
    )
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM agentops_jobs").fetchone()[0] == 2


def test_unprefixed_text_and_wrong_sender_cannot_resume_question(database):
    job_id = seed(database)
    first = claim_job(database, job_id, "1")
    update_job(
        database, job_id, Progress(lease=first["lease"], state="needs_input", summary="¿Qué texto?")
    )
    for number, text, sender in [
        (1, "El titulo nuevo", "51900000001"),
        (2, f"responder {job_id} otro titulo", "51900000002"),
        (3, "responder incorrecto texto", "51900000001"),
        (4, "responder", "51900000001"),
    ]:
        database.save(
            [IncomingMessage(f"wamid.invalid{number}", "12345", sender, text, datetime.now(UTC))],
            [],
        )
    with database.connect() as conn:
        assert conn.execute(
            "SELECT state,lease FROM agentops_jobs WHERE id=%s", (job_id,)
        ).fetchone() == ("needs_input", UUID(first["lease"]))
        assert conn.execute("SELECT count(*) FROM agentops_jobs").fetchone()[0] == 1


def test_control_api_rejects_bad_auth_and_missing_jobs(monkeypatch):
    class Settings:
        def control_token(self):
            return "test-only-control"

    monkeypatch.setattr(jobs.AppSettings, "from_environment", lambda: Settings())
    with TestClient(app) as client:
        url = f"/internal/jobs/{uuid4()}/claim"
        assert client.post(url, json={"run_id": "1"}).status_code == 403
        assert (
            client.post(
                url, json={"run_id": "1"}, headers={"Authorization": "Bearer test-only-control"}
            ).status_code
            == 503
        )


def test_dispatch_sends_only_uuid_and_serializes(database, monkeypatch):
    first = seed(database)
    seed(database)
    calls = []

    @contextmanager
    def token(*_):
        yield "test-only-token"

    monkeypatch.setattr(jobs, "installation_token", token)
    monkeypatch.setattr(jobs, "github_json", lambda *args: calls.append(args) or {})
    assert jobs.dispatch_one(database, object())
    assert not jobs.dispatch_one(database, object())
    assert calls[0][3] == {"ref": "main", "inputs": {"job_id": str(first)}}
    claim_job(database, first, "1")
    assert not jobs.dispatch_one(database, object())


def test_dispatch_errors_stop_after_three_attempts(database, monkeypatch):
    job_id = seed(database)

    @contextmanager
    def token(*_):
        raise GitHubError("GITHUB_HTTP_403")
        yield

    monkeypatch.setattr(jobs, "installation_token", token)
    for _ in range(3):
        assert jobs.dispatch_one(database, object())
        with database.connect() as conn:
            conn.execute("UPDATE agentops_jobs SET next_dispatch_at=now() WHERE id=%s", (job_id,))
    assert not jobs.dispatch_one(database, object())
    with database.connect() as conn:
        assert conn.execute("SELECT state,dispatch_attempts FROM agentops_jobs").fetchone() == (
            "failed",
            3,
        )


def test_unknown_job_cannot_be_claimed(database):
    with pytest.raises(HTTPException) as error:
        claim_job(database, UUID(int=0), "1")
    assert error.value.status_code == 404
