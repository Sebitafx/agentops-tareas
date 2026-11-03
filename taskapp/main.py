import logging
from pathlib import Path
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bootstrap.database import SCHEMA_VERSION, SchemaError
from bootstrap.main import data_deletion, lifespan, privacy, storage, version
from taskapp.repository import TaskRepository
from taskapp.schemas import Task, TaskCreate, TaskFilter, TaskPatch

logger = logging.getLogger("uvicorn.error.agentops")
app = FastAPI(title="AgentOps Tareas", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.add_api_route("/version", version)
app.add_api_route("/privacy", privacy, response_class=FileResponse, include_in_schema=False)
app.add_api_route(
    "/data-deletion", data_deletion, response_class=FileResponse, include_in_schema=False
)


def repository(request: Request) -> TaskRepository:
    return TaskRepository(storage(request))


@app.exception_handler(psycopg.Error)
@app.exception_handler(SchemaError)
async def database_error(request: Request, exc: psycopg.Error | SchemaError) -> JSONResponse:
    logger.warning("tasks_database_unavailable error_type=%s", type(exc).__name__)
    return JSONResponse(
        status_code=503, content={"detail": "Base de datos temporalmente no disponible"}
    )


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tasks"}


@app.get("/ready")
def ready(request: Request) -> dict[str, str]:
    storage(request).check()
    return {"status": "ok", "database": "ok", "schema_version": SCHEMA_VERSION}


@app.get("/api/tasks", response_model=list[Task])
def list_tasks(request: Request, status: TaskFilter = "all") -> list[Task]:
    return repository(request).list(status)


@app.post("/api/tasks", response_model=Task, status_code=201)
def create_task(data: TaskCreate, request: Request) -> Task:
    return repository(request).create(data)


@app.get("/api/tasks/{task_id}", response_model=Task)
def get_task(task_id: UUID, request: Request) -> Task:
    task = repository(request).get(task_id)
    if task is None:
        raise HTTPException(404, "Tarea no encontrada")
    return task


@app.patch("/api/tasks/{task_id}", response_model=Task)
def update_task(task_id: UUID, data: TaskPatch, request: Request) -> Task:
    task = repository(request).update(task_id, data)
    if task is None:
        raise HTTPException(404, "Tarea no encontrada")
    return task


@app.delete("/api/tasks/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: UUID, request: Request) -> Response:
    if not repository(request).delete(task_id):
        raise HTTPException(404, "Tarea no encontrada")
    return Response(status_code=204)
