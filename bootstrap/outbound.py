"""Salida limitada a Graph API y remitentes autorizados; sin claves en logs."""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request

import psycopg
from pydantic import BaseModel, Field, SecretStr, ValidationError
from starlette.concurrency import run_in_threadpool

from bootstrap.database import Database
from bootstrap.outbox import PendingReply, ReplyStore

logger = logging.getLogger("uvicorn.error.agentops")


class OutboundSettings(BaseModel):
    token: SecretStr = Field(min_length=1)
    phone_number_id: str = Field(pattern=r"^[0-9]+$")
    allowed_senders: frozenset[str] = Field(min_length=1)
    version: str = Field(default="v26.0", pattern=r"^v[0-9]{1,3}\.0$")

    @classmethod
    def from_environment(cls) -> "OutboundSettings":
        settings = cls(
            token=os.environ["WHATSAPP_TOKEN"],
            phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
            allowed_senders=frozenset(
                value.strip()
                for value in os.environ["WHATSAPP_ALLOWED_SENDERS"].split(",")
                if value.strip()
            ),
            version=os.getenv("META_GRAPH_VERSION", "v26.0"),
        )
        token = settings.token.get_secret_value()
        if not token.isascii() or any(character.isspace() for character in token):
            raise ValueError("INVALID_WHATSAPP_TOKEN_FORMAT")
        return settings


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SendError(Exception):
    def __init__(self, reason: str, retryable: bool = False, uncertain: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable
        self.uncertain = uncertain


def send_text(settings: OutboundSettings, reply: PendingReply) -> str:
    if (
        reply.sender not in settings.allowed_senders
        or reply.phone_number_id != settings.phone_number_id
    ):
        raise SendError("RECIPIENT_NOT_ALLOWED")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": reply.sender,
        "type": "text",
        "text": {"preview_url": False, "body": reply.body},
        "context": {"message_id": reply.message_id},
    }
    request = urllib.request.Request(
        f"https://graph.facebook.com/{settings.version}/{settings.phone_number_id}/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + settings.token.get_secret_value(),
            "Content-Type": "application/json",
            "User-Agent": "AgentOps-Tareas/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise SendError("INVALID_SEND_RESPONSE", uncertain=True)
        result = json.loads(raw)
        provider_id = result["messages"][0]["id"]
        if (
            not isinstance(provider_id, str)
            or not provider_id.startswith("wamid.")
            or len(provider_id) > 512
        ):
            raise SendError("INVALID_SEND_RESPONSE", uncertain=True)
        return provider_id
    except urllib.error.HTTPError as exc:
        status = exc.code
        # Solo se conserva el codigo numerico, nunca el mensaje crudo de Meta.
        try:
            details = json.loads(exc.read(65536)).get("error", {})
            error_code = details.get("code")
            subcode = details.get("error_subcode")
        except (ValueError, AttributeError, OSError):
            error_code = None
            subcode = None
        finally:
            exc.close()
        if type(error_code) is not int:
            error_code = None
        if error_code == 190 or status == 401:
            raise SendError("WHATSAPP_TOKEN_INVALID_OR_EXPIRED") from None
        if error_code == 131047:
            raise SendError("REPLY_WINDOW_CLOSED") from None
        if status == 429 or error_code in {4, 17, 32, 613, 130429, 131056}:
            raise SendError("WHATSAPP_RATE_LIMIT", retryable=True) from None
        reason = "WHATSAPP_HTTP_ERROR_" + str(status)
        if type(error_code) is int and 0 <= error_code <= 2147483647:
            reason += "_META_" + str(error_code)
        if type(subcode) is int and 0 <= subcode <= 2147483647:
            reason += "_SUB_" + str(subcode)
        raise SendError(reason, uncertain=status >= 500) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SendError("WHATSAPP_NETWORK_ERROR", uncertain=True) from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise SendError("INVALID_SEND_RESPONSE", uncertain=True) from None


def dispatch_one(store: ReplyStore, settings: OutboundSettings) -> bool:
    reply = store.claim()
    if reply is None:
        return False
    try:
        provider_id = send_text(settings, reply)
    except SendError as exc:
        store.failed(reply, exc.reason, exc.retryable, exc.uncertain)
        logger.warning(
            "whatsapp_reply id=%s result=%s reason=%s",
            reply.id,
            "uncertain" if exc.uncertain else "rejected",
            exc.reason,
        )
    else:
        store.sent(reply, provider_id)
        logger.info("whatsapp_reply id=%s result=accepted_by_meta", reply.id)
    return True


async def reply_worker(database: Database, stop: asyncio.Event) -> None:
    try:
        settings = OutboundSettings.from_environment()
    except (KeyError, ValidationError, ValueError):
        logger.warning("whatsapp_reply_worker result=not_configured")
        return
    store = ReplyStore(database)
    logger.info("whatsapp_reply_worker result=started")
    while not stop.is_set():
        try:
            worked = await run_in_threadpool(dispatch_one, store, settings)
        except psycopg.Error as exc:
            logger.warning(
                "whatsapp_reply_worker result=database_error error_type=%s", type(exc).__name__
            )
            worked = False
        try:
            await asyncio.wait_for(stop.wait(), timeout=1 if worked else 3)
        except TimeoutError:
            pass
