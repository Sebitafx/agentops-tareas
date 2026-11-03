"""Receptor de Meta con bandeja duradera; agentes aun pendientes de implementar."""

import hmac
import logging
import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from bootstrap.database import SCHEMA_VERSION, Database, SchemaError
from bootstrap.whatsapp import MAX_BODY_BYTES, Event, ReceiverSettings, extract, valid_signature

logger = logging.getLogger(__name__)


def receiver_settings() -> ReceiverSettings:
    try:
        return ReceiverSettings(
            secret=os.environ["META_APP_SECRET"],
            phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
            allowed_senders=frozenset(
                part.strip()
                for part in os.environ["WHATSAPP_ALLOWED_SENDERS"].split(",")
                if part.strip()
            ),
        )
    except (KeyError, ValidationError) as exc:
        raise HTTPException(503, "Receptor sin configurar") from exc


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.database = None
    url = os.getenv("DATABASE_URL", "")
    if url:
        database = Database(url)
        try:
            await run_in_threadpool(database.migrate)
            application.state.database = database
            logger.info("Migraciones PostgreSQL aplicadas")
        except (psycopg.Error, SchemaError, ValueError, OSError) as exc:
            logger.error("Inicializacion de PostgreSQL fallida (%s)", type(exc).__name__)
    yield


app = FastAPI(title="AgentOps Tareas — receptor WhatsApp", lifespan=lifespan)


def storage(request: Request) -> Database:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(503, "PostgreSQL no inicializado; revisar configuracion y reiniciar")
    return database


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "receiver"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"commit": os.getenv("RENDER_GIT_COMMIT", os.getenv("APP_COMMIT", "local"))}


@app.get("/ready")
def ready(request: Request) -> dict:
    database = storage(request)
    try:
        database.check()
    except (psycopg.Error, SchemaError) as exc:
        logger.warning("PostgreSQL no disponible (%s)", type(exc).__name__)
        raise HTTPException(503, "PostgreSQL o esquema no disponible") from exc
    configured = True
    try:
        receiver_settings()
    except HTTPException:
        configured = False
    return {
        "status": "ok",
        "database": "ok",
        "schema_version": SCHEMA_VERSION,
        "receiver_configured": configured,
        "agents": "pending",
    }


@app.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge", max_length=1024),
) -> str:
    expected = os.getenv("META_VERIFY_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Verificacion de Meta sin configurar")
    if mode != "subscribe" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(403, "Verificacion rechazada")
    return challenge


@app.post("/webhooks/whatsapp")
async def receive_whatsapp(request: Request) -> dict[str, str]:
    settings = receiver_settings()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(413, "Entrega demasiado grande")
    if not valid_signature(
        bytes(body), request.headers.get("x-hub-signature-256", ""), settings.secret
    ):
        raise HTTPException(403, "Firma de Meta rechazada")
    try:
        event = Event.model_validate_json(bytes(body))
        messages, statuses = extract(event, settings)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(400, "Evento de Meta invalido") from exc
    database = storage(request)
    try:
        await run_in_threadpool(database.save, messages, statuses)
    except psycopg.Error as exc:
        logger.warning("Entrega sin confirmar: fallo PostgreSQL (%s)", type(exc).__name__)
        raise HTTPException(503, "No se pudo guardar la entrega; reintentar") from exc
    return {"status": "accepted"}
