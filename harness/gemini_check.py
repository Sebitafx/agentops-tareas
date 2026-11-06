"""Preflight limitado de Gemini. No imprime claves, prompts ni respuestas del proveedor."""

import json
import os

from harness.provider_http import CheckError, split_keys, validate_key
from harness.provider_http import request_json as provider_request_json

DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Revisar precios y compatibilidad antes de autorizar otro modelo.
ALLOWED_MODELS = frozenset({DEFAULT_MODEL, "gemini-3.8-flash"})
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"


def request_json(key: str, model: str, payload: dict | None = None) -> dict:
    url = API_ROOT + model + (":generateContent" if payload is not None else "")
    return provider_request_json(url, {"x-goog-api-key": key}, payload)


def run_check(key: str, model: str) -> dict:
    validate_key(key)
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
    keys = split_keys(os.getenv("GEMINI_API_KEY", ""))
    try:
        if not keys:
            raise CheckError("MISSING_OR_INVALID_API_KEY")
        result: dict | None = None
        # Cada tanque del pool se comprueba en vivo: una llave muerta es error de config.
        for index, key in enumerate(keys):
            if index:
                print(
                    json.dumps({"event": "key_rotated", "provider": "gemini", "index": index}),
                    flush=True,
                )
            result = run_check(key, os.getenv("GEMINI_MODEL", DEFAULT_MODEL))
    except CheckError as exc:
        print(
            json.dumps({"status": "failed", "reason": exc.reason, "http_status": exc.http_status})
        )
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
