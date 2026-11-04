from contextlib import contextmanager
from uuid import uuid4

import pytest

from harness import request_worker as worker
from harness.engine import Outcome
from harness.proposals import Proposal
from harness.provider_http import CheckError


def prepare(monkeypatch, outcome):
    calls = []
    monkeypatch.setattr(worker.AppSettings, "from_environment", lambda: object())

    def control(settings, job_id, action, body):
        calls.append((action, body))
        return (
            {"lease": str(uuid4()), "request": "Cambia el boton Crear por Agregar"}
            if action == "claim"
            else {}
        )

    monkeypatch.setattr(worker, "control", control)

    class Validator:
        baseline = {"taskapp/static/index.html": "original"}

    monkeypatch.setattr(worker, "DockerValidator", lambda *_: Validator())
    monkeypatch.setattr(worker, "GroqProposer", lambda *_, **__: object())
    monkeypatch.setattr(worker, "run_request", lambda *_: outcome)
    return calls


def test_worker_clarifies_without_creating_pr(monkeypatch):
    proposal = Proposal(action="clarify", summary="Falta requisito", question="¿Que boton?")
    calls = prepare(monkeypatch, Outcome("clarify", "NEEDS_INPUT", (), proposal))
    monkeypatch.setattr(worker, "publish_pr", lambda *_: pytest.fail("No publicar aclaracion"))
    assert worker.execute(uuid4(), "image", "123") == 0
    assert calls[-1][1]["state"] == "needs_input" and calls[-1][1]["summary"] == proposal.question


def test_worker_failed_validation_reports_failure(monkeypatch):
    calls = prepare(monkeypatch, Outcome("failed", "ATTEMPTS_EXHAUSTED", ()))
    assert worker.execute(uuid4(), "image", "123") == 1
    assert calls[-1][1]["state"] == "failed"


def test_worker_validated_change_publishes_pr_and_reports_links(monkeypatch):
    calls = prepare(monkeypatch, Outcome("validated", "VALIDATION_PASSED", ()))

    @contextmanager
    def token(*_):
        yield "fake-private-token"

    monkeypatch.setattr(worker, "installation_token", token)

    class Commit:
        stdout = "a" * 40

    monkeypatch.setattr(worker.subprocess, "run", lambda *_, **__: Commit())
    monkeypatch.setattr(
        worker,
        "publish_pr",
        lambda *_: {
            "url": "https://github.com/Sebitafx/agentops-tareas/pull/1",
            "run_url": "https://github.com/Sebitafx/agentops-tareas/actions/runs/123",
        },
    )
    assert worker.execute(uuid4(), "image", "123") == 0
    assert calls[-1][1]["state"] == "pr_open"
    assert "/pull/1" in calls[-1][1]["summary"]
    assert "fake-private-token" not in str(calls)


def test_duplicate_workflow_does_not_execute(monkeypatch):
    monkeypatch.setattr(worker.AppSettings, "from_environment", lambda: object())

    def conflict(*_):
        raise worker.ControlError(409)

    monkeypatch.setattr(worker, "control", conflict)
    monkeypatch.setattr(worker, "DockerValidator", lambda *_: pytest.fail("No validar duplicado"))
    assert worker.execute(uuid4(), "image", "123") == 0


def test_provider_outage_records_failure(monkeypatch):
    calls = prepare(monkeypatch, None)

    def unavailable(*_, **__):
        raise CheckError("QUOTA_OR_RATE_LIMIT")

    monkeypatch.setattr(worker, "GroqProposer", unavailable)
    assert worker.execute(uuid4(), "image", "123") == 1
    assert calls[-1][1]["state"] == "failed"


def test_context_selection_does_not_include_private_tests():
    base = {
        "taskapp/main.py": "code",
        "tests/test_main.py": "private-test",
        "taskapp/static/app.js": "code",
    }
    assert worker.visible_files("Cambia taskapp/main.py", base) == frozenset({"taskapp/main.py"})
    assert "tests/test_main.py" not in worker.visible_files("Cambia validacion", base)
    assert "taskapp/static/index.html" in worker.visible_files("Cambia el boton", base)
    assert "taskapp/static/style.css" in worker.visible_files("Cambia el color", base)
    assert "taskapp/static/style.css" in worker.visible_files(
        'Cambia el color de "Una cosa a la vez"',
        {
            **base,
            "taskapp/static/index.html": "Una cosa a la vez",
        },
    )


@pytest.mark.parametrize(
    "request_text",
    [
        'cambiar el encabezado "Una cosa a la vez" por "Mis tareas"',
        'cambiar "Una cosa a la vez" por "Mis tareas"',
        "cambia la cabecera del formulario",
        "change the heading",
    ],
)
def test_visible_heading_request_receives_html_and_reset_logic(request_text):
    base = {
        "taskapp/main.py": "server",
        "taskapp/static/index.html": '<h2 id="form-heading">Una cosa a la vez</h2>',
        "taskapp/static/app.js": 'heading.textContent = "Una cosa a la vez";',
        "tests/test_secret.py": "not-for-model",
    }
    assert worker.visible_files(request_text, base) == frozenset(
        {
            "taskapp/static/index.html",
            "taskapp/static/app.js",
        }
    )


def test_worker_deploy_success_requires_confirmation(monkeypatch):
    calls = prepare(monkeypatch, Outcome("validated", "VALIDATION_PASSED", ()))

    @contextmanager
    def token(*_):
        yield "fake-token"

    monkeypatch.setattr(worker, "installation_token", token)

    class Commit:
        stdout = "a" * 40

    monkeypatch.setattr(worker.subprocess, "run", lambda *_, **__: Commit())
    monkeypatch.setattr(
        worker,
        "publish_pr",
        lambda *_: {
            "url": "https://github.com/Sebitafx/agentops-tareas/pull/1",
            "run_url": "https://github.com/Sebitafx/agentops-tareas/actions/runs/123",
        },
    )
    monkeypatch.setenv(
        "RENDER_TASKS_DEPLOY_HOOK", "https://api.render.com/deploy/srv-test?key=fake"
    )
    monkeypatch.setattr(worker, "integrate_pr", lambda *_: "b" * 40)

    class Deployment:
        succeeded = True

    monkeypatch.setattr(worker, "deploy_commit", lambda *_: Deployment())
    assert worker.execute(uuid4(), "image", "123") == 0
    assert [body["state"] for action, body in calls if action == "progress"] == [
        "pr_open",
        "merged",
        "deploying",
        "succeeded",
    ]
