"""Webhook -> DB -> claim -> Docker real -> callbacks. APIs externas simuladas."""

import io
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from bootstrap.github_app import AppSettings
from bootstrap.main import app
from harness import request_worker as worker
from harness.proposals import Proposal, digest
from tests.test_receiver import delivery, signed_post


@pytest.mark.skipif(
    os.getenv("BROKER_E2E") != "1", reason="Requiere Docker en el host y BROKER_E2E=1"
)
def test_webhook_to_validated_change_and_completion(database, monkeypatch, receiver_env):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("SERVICE_ROLE", "tasks")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    settings = AppSettings(app_id="123", private_key=pem)
    monkeypatch.setattr(worker.AppSettings, "from_environment", lambda: settings)
    proposal_paths = ("taskapp/static/index.html", "taskapp/static/app.js")

    def propose(request, base, feedback):
        return Proposal.model_validate(
            {
                "action": "change",
                "summary": "Renombrar boton conservando CRUD",
                "files": [
                    {
                        "path": path,
                        "base_sha256": digest(base[path]),
                        "content": base[path].replace("Crear tarea", "Agregar tarea"),
                    }
                    for path in proposal_paths
                ],
            }
        )

    monkeypatch.setattr(worker, "GroqProposer", lambda *_, **__: propose)

    @contextmanager
    def token(*_):
        yield "fake-only-installation-token"

    monkeypatch.setattr(worker, "installation_token", token)
    monkeypatch.setattr(
        worker,
        "publish_pr",
        lambda *_: {
            "url": "https://github.com/Sebitafx/agentops-tareas/pull/1",
            "run_url": "https://github.com/Sebitafx/agentops-tareas/actions/runs/123",
        },
    )
    monkeypatch.setattr(worker, "integrate_pr", lambda *_: "b" * 40)

    class Deployment:
        succeeded = True

    monkeypatch.setattr(worker, "deploy_commit", lambda *_: Deployment())
    monkeypatch.setenv(
        "RENDER_TASKS_DEPLOY_HOOK", "https://api.render.com/deploy/srv-test?key=fake-only"
    )
    with TestClient(app) as client:
        event = delivery("Cambia el boton Crear tarea por Agregar tarea")
        event["entry"][0]["changes"][0]["value"]["messages"][0]["timestamp"] = str(
            int(datetime.now(UTC).timestamp())
        )
        assert signed_post(client, event).status_code == 200
        with database.connect() as conn:
            job_id = conn.execute("SELECT id FROM agentops_jobs").fetchone()[0]

        class Opener:
            def open(self, request, timeout):
                assert request.full_url.startswith(worker.RECEIVER + "/internal/jobs/")
                response = client.post(
                    urlsplit(request.full_url).path,
                    content=request.data,
                    headers=dict(request.header_items()),
                )
                assert response.status_code == 200, response.text
                return io.BytesIO(json.dumps(response.json()).encode())

        monkeypatch.setattr(worker.urllib.request, "build_opener", lambda *_: Opener())
        image = os.environ["BROKER_VALIDATOR_IMAGE"]
        assert worker.execute(job_id, image, "123") == 0
        with database.connect() as conn:
            assert (
                conn.execute("SELECT state FROM agentops_jobs WHERE id=%s", (job_id,)).fetchone()[0]
                == "succeeded"
            )
            replies = conn.execute(
                "SELECT body FROM agentops_outbox ORDER BY created_at"
            ).fetchall()
        assert len(replies) == 5
        assert "Versión confirmada" in replies[-1][0]
