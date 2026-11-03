"""Receptor de Meta con bandeja duradera; agentes aun pendientes de implementar."""

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from bootstrap.database import SCHEMA_VERSION, Database, SchemaError
from bootstrap.whatsapp import MAX_BODY_BYTES, Event, ReceiverSettings, extract, valid_signature

# Hereda los handlers de Uvicorn: INFO debe ser visible en Render, sin access logs.
logger = logging.getLogger("uvicorn.error.agentops")


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
    application.state.reply_worker = None
    url = os.getenv("DATABASE_URL", "")
    if url:
        database = Database(url)
        try:
            await run_in_threadpool(database.migrate)
            application.state.database = database
            logger.info("Migraciones PostgreSQL aplicadas")
        except (psycopg.Error, SchemaError, ValueError, OSError) as exc:
            logger.error("Inicializacion de PostgreSQL fallida (%s)", type(exc).__name__)
    stop = asyncio.Event()
    worker = None
    if (
        application.state.database is not None
        and os.getenv("SERVICE_ROLE", "receiver") == "receiver"
        and os.getenv("WHATSAPP_TOKEN")
    ):
        from bootstrap.outbound import reply_worker

        worker = asyncio.create_task(reply_worker(application.state.database, stop))
        application.state.reply_worker = worker
    try:
        yield
    finally:
        stop.set()
        if worker:
            try:
                await asyncio.wait_for(worker, timeout=20)
            except (TimeoutError, asyncio.CancelledError):
                worker.cancel()
        application.state.reply_worker = None
        application.state.database = None


app = FastAPI(title="AgentOps Tareas — receptor WhatsApp", lifespan=lifespan)


@app.get("/privacy", response_class=FileResponse, include_in_schema=False)
def privacy() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "privacy.html", media_type="text/html")


@app.get("/data-deletion", response_class=FileResponse, include_in_schema=False)
def data_deletion() -> FileResponse:
    return FileResponse(
        Path(__file__).parent / "static" / "data-deletion.html", media_type="text/html"
    )


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
    from bootstrap.outbound import OutboundSettings

    try:
        OutboundSettings.from_environment()
        reply_configured = True
    except (KeyError, ValidationError, ValueError):
        reply_configured = False
    worker = getattr(request.app.state, "reply_worker", None)
    return {
        "status": "ok",
        "database": "ok",
        "schema_version": SCHEMA_VERSION,
        "receiver_configured": configured,
        "reply_sender_configured": reply_configured,
        "reply_worker_running": worker is not None and not worker.done(),
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
    delivery_id = uuid4().hex[:12]
    logger.info("whatsapp_delivery id=%s stage=received", delivery_id)
    try:
        settings = receiver_settings()
    except HTTPException:
        logger.warning("whatsapp_delivery id=%s stage=rejected reason=configuration", delivery_id)
        raise
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            logger.warning("whatsapp_delivery id=%s stage=rejected reason=body_limit", delivery_id)
            raise HTTPException(413, "Entrega demasiado grande")
    if not valid_signature(
        bytes(body), request.headers.get("x-hub-signature-256", ""), settings.secret
    ):
        logger.warning("whatsapp_delivery id=%s stage=rejected reason=signature", delivery_id)
        raise HTTPException(403, "Firma de Meta rechazada")
    try:
        event = Event.model_validate_json(bytes(body))
        delivery = extract(event, settings)
    except (ValidationError, ValueError) as exc:
        logger.warning("whatsapp_delivery id=%s stage=rejected reason=payload", delivery_id)
        raise HTTPException(400, "Evento de Meta invalido") from exc
    try:
        database = storage(request)
    except HTTPException:
        logger.warning(
            "whatsapp_delivery id=%s stage=rejected reason=storage_not_ready", delivery_id
        )
        raise
    try:
        await run_in_threadpool(database.save, delivery.messages, delivery.statuses)
    except psycopg.Error as exc:
        logger.warning(
            "whatsapp_delivery id=%s stage=rejected reason=database error_type=%s",
            delivery_id,
            type(exc).__name__,
        )
        raise HTTPException(503, "No se pudo guardar la entrega; reintentar") from exc
    logger.info(
        "whatsapp_delivery id=%s stage=accepted messages=%d statuses=%d "
        "ignored_phone_changes=%d ignored_senders=%d ignored_types=%d ignored_fields=%d",
        delivery_id,
        len(delivery.messages),
        len(delivery.statuses),
        delivery.ignored_phone_changes,
        delivery.ignored_senders,
        delivery.ignored_types,
        delivery.ignored_fields,
    )
    return {"status": "accepted"}
