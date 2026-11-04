"""Cola duradera y API privada para el workflow confiable; nunca ejecuta propuestas."""

import asyncio
import hashlib
import hmac
import logging
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, Header, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from bootstrap.database import Database
from bootstrap.github_app import (
    REPOSITORY,
    AppSettings,
    GitHubError,
    github_json,
    installation_token,
)
from bootstrap.outbox import help_text, is_help

logger = logging.getLogger("uvicorn.error.agentops")
router = APIRouter(prefix="/internal/jobs", include_in_schema=False)


def authenticate(authorization: str) -> None:
    try:
        expected = "Bearer " + AppSettings.from_environment().control_token()
    except (KeyError, ValidationError, GitHubError):
        raise HTTPException(503, "Control del agente sin configurar") from None
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(403, "Acceso rechazado")


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=r"^[0-9]{1,24}$")


class Progress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease: UUID
    state: Literal["needs_input", "failed", "pr_open", "merged", "deploying", "succeeded"]
    summary: str = Field(min_length=1, max_length=2500)


def claim_job(database: Database, job_id: UUID, run_id: str) -> dict:
    with database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """SELECT j.*, i.body, i.sent_at FROM agentops_jobs j
            JOIN agentops_inbox i ON i.message_id = j.message_id
            WHERE j.id = %s FOR UPDATE OF j""",
            (job_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Solicitud no encontrada")
        if row["state"] != "received" or row["worker_run_id"]:
            raise HTTPException(409, "Solicitud ya reclamada")
        lease = uuid4()
        cursor.execute(
            """UPDATE agentops_jobs SET state='running', worker_run_id=%s,
            lease=%s, updated_at=now() WHERE id=%s""",
            (run_id, lease, job_id),
        )
        return {
            "id": str(job_id),
            "lease": str(lease),
            "request": row["request_text"] or row["body"],
        }


def update_job(database: Database, job_id: UUID, progress: Progress) -> None:
    with database.connect() as conn, conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """SELECT j.*, i.sent_at FROM agentops_jobs j
            JOIN agentops_inbox i ON i.message_id=j.message_id
            WHERE j.id=%s FOR UPDATE OF j""",
            (job_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Solicitud no encontrada")
        if row["lease"] != progress.lease:
            raise HTTPException(409, "Ejecucion obsoleta")
        if row["state"] == progress.state and row["summary"] == progress.summary:
            return
        transitions = {
            "running": {"needs_input", "failed", "pr_open"},
            "pr_open": {"pr_open", "merged", "failed"},
            "merged": {"deploying", "failed"},
            "deploying": {"succeeded", "failed"},
        }
        if progress.state not in transitions.get(row["state"], set()):
            raise HTTPException(409, "Transicion rechazada")
        cursor.execute(
            "UPDATE agentops_jobs SET state=%s, summary=%s, updated_at=now() WHERE id=%s",
            (progress.state, progress.summary, job_id),
        )
        cursor.execute(
            """INSERT INTO agentops_outbox (id,message_id,body,expires_at,event_key)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(event_key) DO NOTHING""",
            (
                uuid4(),
                row["message_id"],
                f"Solicitud {job_id}\n{progress.summary}",
                row["sent_at"] + timedelta(hours=23),
                f"job:{job_id}:{progress.lease}:{progress.state}:"
                + hashlib.sha256(progress.summary.encode()).hexdigest()[:16],
            ),
        )


@router.post("/{job_id}/claim")
def claim_endpoint(
    job_id: UUID, data: Claim, request: Request, authorization: str = Header(default="")
):
    authenticate(authorization)
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(503, "Almacenamiento no disponible")
    return claim_job(database, job_id, data.run_id)


@router.post("/{job_id}/progress")
def progress_endpoint(
    job_id: UUID, data: Progress, request: Request, authorization: str = Header(default="")
):
    authenticate(authorization)
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(503, "Almacenamiento no disponible")
    update_job(database, job_id, data)
    return {"status": "ok"}


def dispatch_one(database: Database, settings: AppSettings) -> bool:
    with database.connect() as conn:
        conn.execute("SET LOCAL statement_timeout = '5s'")
        conn.execute("SELECT pg_advisory_xact_lock(19771104)")
        conn.execute("""UPDATE agentops_jobs SET state='failed',
            summary='El agente no confirmo el inicio o la finalizacion. Requiere revision.', updated_at=now()
            WHERE (state='received' AND dispatch_attempts>=3 AND next_dispatch_at<now())
            OR (state IN ('running','pr_open','merged','deploying') AND updated_at<now()-interval '45 minutes')""")
        if conn.execute(
            "SELECT 1 FROM agentops_jobs WHERE state IN ('running','pr_open','merged','deploying') LIMIT 1"
        ).fetchone():
            return False
        row = conn.execute("""SELECT j.id,j.dispatch_attempts,j.next_dispatch_at<=now(),
                COALESCE(j.request_text,i.body),i.sent_at,j.message_id FROM agentops_jobs j
            JOIN agentops_inbox i ON i.message_id=j.message_id
            WHERE j.state='received' AND j.worker_run_id IS NULL AND j.dispatch_attempts < 3
            ORDER BY j.created_at FOR UPDATE OF j LIMIT 1""").fetchone()
        if row is None:
            return False
        job_id, attempts, due, text, sent_at, message_id = row
        if not due:
            return False
        if is_help(text):
            conn.execute(
                "UPDATE agentops_jobs SET state='blocked',summary='Consulta de ayuda, sin cambio de codigo.',updated_at=now() WHERE id=%s",
                (job_id,),
            )
            conn.execute(
                """INSERT INTO agentops_outbox(id,message_id,body,expires_at,event_key)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT(event_key) DO NOTHING""",
                (uuid4(), message_id, help_text(), sent_at + timedelta(hours=23), f"help:{job_id}"),
            )
            return True
        conn.execute(
            """UPDATE agentops_jobs SET dispatch_attempts=dispatch_attempts+1,
            next_dispatch_at=now()+interval '5 minutes', updated_at=now() WHERE id=%s""",
            (job_id,),
        )
    try:
        with installation_token(settings, {"actions": "write"}) as token:
            github_json(
                "POST",
                f"/repos/{REPOSITORY}/actions/workflows/whatsapp-agent.yml/dispatches",
                token,
                {"ref": "main", "inputs": {"job_id": str(job_id)}},
            )
    except GitHubError as exc:
        with database.connect() as conn:
            conn.execute(
                """UPDATE agentops_jobs SET last_error=%s,
                next_dispatch_at=now()+interval '60 seconds',
                state=CASE WHEN dispatch_attempts>=3 THEN 'failed' ELSE state END,
                summary=CASE WHEN dispatch_attempts>=3 THEN 'No pude iniciar el agente; revisar el despacho.' ELSE summary END
                WHERE id=%s AND state='received'""",
                (exc.reason, job_id),
            )
        logger.warning("agent_dispatch id=%s result=failed reason=%s", job_id, exc.reason)
    else:
        logger.info("agent_dispatch id=%s result=accepted", job_id)
    return True


async def dispatch_worker(database: Database, stop: asyncio.Event) -> None:
    try:
        settings = AppSettings.from_environment()
    except (KeyError, ValidationError, GitHubError):
        logger.warning("agent_dispatch result=not_configured")
        return
    while not stop.is_set():
        try:
            await run_in_threadpool(dispatch_one, database, settings)
        except psycopg.Error as exc:
            logger.warning("agent_dispatch result=database_error error_type=%s", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except TimeoutError:
            pass
