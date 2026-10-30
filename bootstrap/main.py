"""Servicio inicial: salud y handshake de Meta, sin aceptar trabajos todavia."""

import hmac
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

app = FastAPI(title="AgentOps Tareas — verificacion inicial")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "bootstrap"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"commit": os.getenv("RENDER_GIT_COMMIT", os.getenv("APP_COMMIT", "local"))}


@app.get("/ready")
def ready() -> None:
    # No confundir un servidor activo con un sistema completo y conectado.
    raise HTTPException(
        503, "Verificacion inicial pendiente: agentes y almacenamiento no habilitados"
    )


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
def receive_whatsapp() -> None:
    # No responder 200 ni descartar mensajes antes de tener persistencia duradera.
    raise HTTPException(503, "Recepcion pendiente de conectar PostgreSQL")
