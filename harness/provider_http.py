"""Transporte acotado; solo reintenta 429 de Groq con Retry-After breve."""

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE_BYTES = 1048576
MAX_RATE_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 60
GROQ_HOST = "api.groq.com"
ALLOWED_HOSTS = frozenset({"generativelanguage.googleapis.com", GROQ_HOST})
USER_AGENT = "AgentOps-Tareas/0.1 (+https://github.com/Sebitafx/agentops-tareas)"
_last_groq_started: float | None = None


class CheckError(Exception):
    def __init__(self, reason: str, http_status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ProposalOutputLimit(CheckError):
    """El proveedor confirma que corto la generacion por limite de salida."""

    def __init__(self) -> None:
        super().__init__("PROPOSAL_OUTPUT_LIMIT")


def pace_groq() -> None:
    global _last_groq_started
    try:
        interval = int(os.getenv("GROQ_MIN_INTERVAL_SECONDS", "0"))
        if not 0 <= interval <= 120:
            raise ValueError()
    except ValueError:
        raise CheckError("INVALID_PROVIDER_PACING") from None
    if interval and _last_groq_started is not None:
        wait = interval - (time.monotonic() - _last_groq_started)
        if wait > 0:
            time.sleep(wait)
    _last_groq_started = time.monotonic()


def request_json(url: str, headers: dict[str, str], payload: dict | None = None) -> dict:
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.netloc not in ALLOWED_HOSTS
        or parts.query
        or parts.fragment
    ):
        raise CheckError("ENDPOINT_NOT_ALLOWED")
    groq_generation = parts.netloc == GROQ_HOST and parts.path.endswith("/chat/completions")
    if groq_generation:
        pace_groq()
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={**headers, "Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST" if payload is not None else "GET",
    )
    return request_with_retries(request, groq_generation)


def request_with_retries(request: urllib.request.Request, groq_generation: bool) -> dict:
    for attempt in range(MAX_RATE_RETRIES + 1):
        try:
            return send_json(request)
        except urllib.error.HTTPError as exc:
            # Solo un rechazo explicito garantiza que no hubo una generacion aceptada.
            # No se interpreta ni registra el cuerpo externo (puede contener secretos).
            delay = retry_delay((exc.headers or {}).get("Retry-After", ""))
            retry = (
                groq_generation
                and exc.code == 429
                and delay is not None
                and attempt < MAX_RATE_RETRIES
            )
            code = exc.code
            exc.close()
            if retry:
                time.sleep(delay)
                continue
            reasons = {
                400: "INVALID_REQUEST",
                401: "AUTHENTICATION_FAILED",
                403: "PERMISSION_DENIED",
                404: "MODEL_UNAVAILABLE",
                429: "QUOTA_OR_RATE_LIMIT",
            }
            reason = reasons.get(code, "PROVIDER_UNAVAILABLE" if code >= 500 else "HTTP_ERROR")
            raise CheckError(reason, code) from None
    raise CheckError("QUOTA_OR_RATE_LIMIT", 429)


def retry_delay(value: str) -> float | None:
    try:
        delay = float(value)
    except (TypeError, ValueError):
        return None
    return delay if math.isfinite(delay) and 0 < delay <= MAX_RETRY_AFTER_SECONDS else None


def send_json(request: urllib.request.Request) -> dict:
    try:
        opener = urllib.request.build_opener(NoRedirect())
        # Gemini puede tardar mas en generar con razonamiento. Sigue siendo una
        # unica llamada acotada: un timeout de red no se reintenta automaticamente.
        timeout = 90 if request.host == "generativelanguage.googleapis.com" else 30
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise CheckError("RESPONSE_TOO_LARGE")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise CheckError("INVALID_RESPONSE")
        return result
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CheckError("NETWORK_ERROR") from None
    except (ValueError, UnicodeError):
        raise CheckError("INVALID_RESPONSE") from None


def validate_key(key: str) -> None:
    if not key or not key.isascii() or any(character.isspace() for character in key):
        raise CheckError("MISSING_OR_INVALID_API_KEY")
