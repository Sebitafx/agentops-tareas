import os
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from taskapp.main import app


@pytest.fixture
def tasks(database, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(app) as client:
        yield client


def create(client, title="Preparar demo"):
    response = client.post(
        "/api/tasks", json={"title": title, "description": "Solo datos ficticios"}
    )
    assert response.status_code == 201
    return response.json()


def test_tasks_crud(tasks):
    task = create(tasks, "  Preparar demo  ")
    assert task["title"] == "Preparar demo"
    assert task["completed"] is False
    assert tasks.get(f"/api/tasks/{task['id']}").json() == task
    changed = tasks.patch(
        f"/api/tasks/{task['id']}", json={"title": "Demo lista", "completed": True}
    )
    assert changed.status_code == 200
    assert changed.json()["title"] == "Demo lista"
    assert changed.json()["completed"] is True
    assert changed.json()["created_at"] == task["created_at"]
    assert changed.json()["updated_at"] >= task["updated_at"]
    assert tasks.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert tasks.get(f"/api/tasks/{task['id']}").status_code == 404


def test_task_filters_and_reopening(tasks):
    pending = create(tasks, "Pendiente")
    done = create(tasks, "Terminada")
    tasks.patch(f"/api/tasks/{done['id']}", json={"completed": True})
    assert len(tasks.get("/api/tasks").json()) == 2
    assert [t["id"] for t in tasks.get("/api/tasks?status=pending").json()] == [pending["id"]]
    assert [t["id"] for t in tasks.get("/api/tasks?status=completed").json()] == [done["id"]]
    tasks.patch(f"/api/tasks/{done['id']}", json={"completed": False})
    assert tasks.get("/api/tasks?status=completed").json() == []
    assert len(tasks.get("/api/tasks?status=pending").json()) == 2
    assert tasks.get("/api/tasks?status=unknown").status_code == 422


@pytest.mark.parametrize(
    "data",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "ok", "description": "x" * 4001},
        {"title": "ok", "completed": True},
    ],
)
def test_invalid_task_creation(tasks, data):
    assert tasks.post("/api/tasks", json=data).status_code == 422
    assert tasks.get("/api/tasks").json() == []


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"title": None},
        {"completed": None},
        {"title": " "},
        {"id": "overwrite"},
        {"created_at": "override"},
    ],
)
def test_invalid_patch(tasks, data):
    task = create(tasks)
    assert tasks.patch(f"/api/tasks/{task['id']}", json=data).status_code == 422
    assert tasks.get(f"/api/tasks/{task['id']}").json() == task


def test_unknown_task_and_bad_uuid(tasks):
    missing = str(uuid4())
    assert tasks.get(f"/api/tasks/{missing}").status_code == 404
    assert tasks.patch(f"/api/tasks/{missing}", json={"completed": True}).status_code == 404
    assert tasks.delete(f"/api/tasks/{missing}").status_code == 404
    assert tasks.get("/api/tasks/bad-id").status_code == 422


def test_text_not_sql_and_description_can_clear(tasks):
    task = create(tasks, "'; DROP TABLE agentops_tasks; --")
    response = tasks.patch(f"/api/tasks/{task['id']}", json={"description": ""})
    assert response.json()["description"] == ""
    assert len(tasks.get("/api/tasks").json()) == 1


def test_task_survives_restart(database, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(app) as client:
        task = create(client)
    with TestClient(app) as client:
        assert client.get(f"/api/tasks/{task['id']}").json()["title"] == task["title"]
        assert client.get("/ready").status_code == 200


def test_unavailable_database_returns_safe_error(tasks, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError("private-password private-host")

    monkeypatch.setattr("taskapp.repository.TaskRepository.list", fail)
    response = tasks.get("/api/tasks")
    assert response.status_code == 503
    assert "private-password" not in response.text + caplog.text
    assert "private-host" not in response.text + caplog.text


def test_static_content_and_health_without_database():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/style.css").status_code == 200
        assert client.get("/privacy").status_code == 200
        assert client.get("/data-deletion").status_code == 200
        assert client.get("/version").status_code == 200
        assert client.get("/health").json()["service"] == "tasks"
        assert client.get("/ready").status_code == 503
        assert client.get("/api/tasks").status_code == 503
