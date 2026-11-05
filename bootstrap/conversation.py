"""Procesa mensajes ya confirmados en el webhook; una decisión por turno."""

import asyncio
import logging
import re
import unicodedata
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from bootstrap.budget import reserve
from bootstrap.outbox import resume_job
from harness.model_tools import SESSION, ProviderSession, choose
from harness.provider_http import CheckError

logger = logging.getLogger("uvicorn.error.agentops")
SYSTEM = """Hablas en español como desarrollador del gestor de tareas. Interpreta lenguaje natural.
Un saludo, pregunta hipotética o charla recibe answer. Ayuda con el software y sus cambios.
Si pide un cambio claro usa change y especifica el resultado esperado en text. Decide detalles técnicos.
Si falta la función del botón pregunta brevemente con answer. Usa el historial para entender la respuesta.
Usa resume si contesta a un trabajo needs_input. Usa status para consultar el avance.
Si hay varias solicitudes plausibles pregunta cuál. Nunca inventes avances, enlaces o despliegues.
Solo la aplicación puede cambiar. No solicites ni repitas secretos ni números de teléfono."""


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["answer", "change", "resume", "status"]
    text: str = Field(min_length=1, max_length=1500)
    job_id: UUID | None = None


def process(database) -> bool:
    with database.connect() as conn:
        row = conn.execute("""SELECT t.message_id,i.sender,i.body,i.sent_at FROM agentops_turns t
            JOIN agentops_inbox i USING(message_id) WHERE t.answer IS NULL
            AND (t.claimed_at IS NULL OR t.claimed_at < now()-interval '10 minutes')
            AND NOT EXISTS (SELECT 1 FROM agentops_turns earlier
                JOIN agentops_inbox prev USING(message_id) WHERE prev.sender=i.sender
                AND earlier.seq<t.seq AND earlier.answer IS NULL)
            ORDER BY t.seq LIMIT 1 FOR UPDATE OF t SKIP LOCKED""").fetchone()
        if not row:
            return False
        mid, sender, body, sent = row
        lease = uuid4()
        conn.execute(
            "UPDATE agentops_turns SET claimed_at=now(),lease=%s WHERE message_id=%s", (lease, mid)
        )
        history = conn.execute(
            """SELECT left(i.body,1000),left(t.answer,1000) FROM agentops_turns t
            JOIN agentops_inbox i USING(message_id) WHERE i.sender=%s AND t.answer IS NOT NULL
            ORDER BY t.seq DESC LIMIT 6""",
            (sender,),
        ).fetchall()
        rows = conn.execute(
            """SELECT j.id,j.state,left(j.summary,1500),left(coalesce(j.request_text,i.body),300)
            FROM agentops_jobs j JOIN agentops_inbox i USING(message_id)
            WHERE i.sender=%s ORDER BY j.updated_at DESC LIMIT 6""",
            (sender,),
        ).fetchall()
    jobs = {str(r[0]): r for r in rows}
    providers = []
    session = ProviderSession()
    token = SESSION.set(session)
    try:
        decision = Decision.model_validate(
            choose(
                SYSTEM,
                {"history": history[::-1], "jobs": rows, "message": body},
                Decision.model_json_schema(),
                lambda n: reserve(database, n),
                1200,
                providers.append,
            )
        )
    except (CheckError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("conversation_failed reason=%s", getattr(exc, "reason", type(exc).__name__))
        decision = None
    finally:
        SESSION.reset(token)
    with database.connect() as conn:
        if not conn.execute(
            """SELECT 1 FROM agentops_turns WHERE message_id=%s AND lease=%s
                            AND answer IS NULL FOR UPDATE""",
            (mid, lease),
        ).fetchone():
            return False
        reply = (
            act(conn, mid, sender, decision, jobs, body, session.selected)
            if decision
            else "No pude interpretar tu mensaje ahora. Puedes volver a enviarlo."
        )
        if providers:
            reply += f"\nProveedor de respaldo: {providers[-1]}."
        conn.execute("UPDATE agentops_turns SET answer=%s WHERE message_id=%s", (reply, mid))
        conn.execute(
            """INSERT INTO agentops_outbox(id,message_id,body,expires_at,event_key)
            VALUES (%s,%s,%s,%s,%s)""",
            (uuid4(), mid, reply, sent + timedelta(hours=23), "chat:" + mid),
        )
        return True


def act(conn, mid, sender, decision, jobs, original="", provider=None):
    if decision.action == "answer":
        return decision.text
    if decision.action == "change":
        job = uuid4()
        plain = "".join(
            c
            for c in unicodedata.normalize("NFKD", original.casefold())
            if not unicodedata.combining(c)
        )
        keep = bool(re.search(r"no\s+cambi\w*\s+(?:de\s+)?modelo", plain))
        conn.execute(
            """INSERT INTO agentops_jobs(id,message_id,request_text,preferred_provider,keep_provider)
               VALUES (%s,%s,%s,%s,%s)""",
            (job, mid, decision.text, provider if keep else None, keep),
        )
        policy = (
            f"\nImplementaré con {provider}, sin cambiar de proveedor." if keep and provider else ""
        )
        return (
            f"Registré el cambio: {decision.text}\nTe avisaré del avance. Solicitud {job}." + policy
        )
    row = jobs.get(str(decision.job_id))
    if not row and not decision.job_id and len(jobs) == 1:
        row = next(iter(jobs.values()))
    if not row:
        return "¿A qué cambio te refieres? Puedes indicarme su descripción o su id."
    if decision.action == "status":
        return f"Solicitud {row[0]} · {row[1]}\n{row[2] or 'Pendiente de la siguiente fase.'}"
    return resume_job(conn, sender, row[0], decision.text)


async def worker(database, stop):
    while not stop.is_set():
        try:
            if await run_in_threadpool(process, database):
                continue
        except psycopg.Error:
            logger.warning("conversation_database_unavailable")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except TimeoutError:
            pass
