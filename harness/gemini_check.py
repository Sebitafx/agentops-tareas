"""Preflight limitado de Gemini. No imprime claves, prompts ni respuestas del proveedor."""

import json
import os
import urllib.error
import urllib.request

DEFAULT_MODEL = "gemini-3.8-flash"
# Revisar precios y compatibilidad antes de autorizar otro modelo.
ALLOWED_MODELS = frozenset({DEFAULT_MODEL})
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_RESPONSE_BYTES = 1048576


class CheckError(Exception):
    def __init__(self, reason: str, http_status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # No reenviar el header de autenticacion a otra URL.
        return None


def request_json(key: str, model: str, payload: dict | None = None) -> dict:
    url = API_ROOT + model + (":generateContent" if payload is not None else "")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise CheckError("RESPONSE_TOO_LARGE")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise CheckError("INVALID_RESPONSE")
        return result
    except urllib.error.HTTPError as exc:
        reasons = {
            400: "INVALID_REQUEST",
            401: "AUTHENTICATION_FAILED",
            403: "PERMISSION_DENIED",
            404: "MODEL_UNAVAILABLE",
            429: "QUOTA_OR_RATE_LIMIT",
        }
        reason = reasons.get(exc.code, "PROVIDER_UNAVAILABLE" if exc.code >= 500 else "HTTP_ERROR")
        exc.close()
        raise CheckError(reason, exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CheckError("NETWORK_ERROR") from None
    except (ValueError, UnicodeError):
        raise CheckError("INVALID_RESPONSE") from None


def run_check(key: str, model: str) -> dict:
    if not key or not key.isascii() or any(character.isspace() for character in key):
        raise CheckError("MISSING_OR_INVALID_API_KEY")
    if model not in ALLOWED_MODELS:
        raise CheckError("MODEL_NOT_ALLOWED")
    metadata = request_json(key, model)
    if metadata.get("name") != "models/" + model:
        raise CheckError("UNEXPECTED_MODEL_METADATA")
    methods = metadata.get("supportedGenerationMethods")
    if not isinstance(methods, list) or "generateContent" not in methods:
        raise CheckError("GENERATION_NOT_SUPPORTED")
    result = request_json(
        key,
        model,
        {
            "contents": [{"role": "user", "parts": [{"text": "Reply with exactly OK."}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 1024,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        },
    )
    candidates = result.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        raise CheckError("NO_GENERATED_CANDIDATE")
    try:
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if not part.get("thought", False))
        confirmed = candidate.get("finishReason") == "STOP" and text.strip() == "OK"
    except (AttributeError, TypeError):
        raise CheckError("INVALID_RESPONSE") from None
    if not confirmed:
        raise CheckError("GENERATION_NOT_CONFIRMED")
    # Nunca inferir plan de facturacion ni cuota restante de una peticion exitosa.
    return {
        "status": "ok",
        "model": model,
        "model_access": True,
        "generation_confirmed": True,
        "billing_verified": False,
        "remaining_quota": "unknown",
    }


def main() -> int:
    try:
        result = run_check(
            os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        )
    except CheckError as exc:
        print(
            json.dumps({"status": "failed", "reason": exc.reason, "http_status": exc.http_status})
        )
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
