"""Preflight de Groq: catalogo y una generacion sintetica; no procesa datos de la demo."""

import json
import os

from harness.provider_http import CheckError, request_json, split_keys, validate_key

DEFAULT_MODEL = "openai/gpt-oss-120b"
ALLOWED_MODELS = frozenset({DEFAULT_MODEL})
API_ROOT = "https://api.groq.com/openai/v1"


def run_check(key: str, model: str) -> dict:
    validate_key(key)
    if model not in ALLOWED_MODELS:
        raise CheckError("MODEL_NOT_ALLOWED")
    headers = {"Authorization": "Bearer " + key}
    catalog = request_json(API_ROOT + "/models", headers)
    models = catalog.get("data")
    if not isinstance(models, list):
        raise CheckError("INVALID_MODEL_CATALOG")
    available = any(
        isinstance(item, dict) and item.get("id") == model and item.get("active", True) is True
        for item in models
    )
    if not available:
        raise CheckError("MODEL_UNAVAILABLE")
    result = request_json(
        API_ROOT + "/chat/completions",
        headers,
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly OK."}],
            "temperature": 0,
            "max_completion_tokens": 1024,
            "reasoning_effort": "low",
            "stream": False,
        },
    )
    if result.get("model") != model:
        raise CheckError("UNEXPECTED_GENERATION_MODEL")
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise CheckError("NO_GENERATED_CANDIDATE")
    try:
        choice = choices[0]
        message = choice.get("message", {})
        text = message.get("content")
        confirmed = (
            choice.get("finish_reason") == "stop"
            and isinstance(text, str)
            and text.strip() == "OK"
            and not message.get("tool_calls")
        )
    except AttributeError:
        raise CheckError("INVALID_RESPONSE") from None
    if not confirmed:
        raise CheckError("GENERATION_NOT_CONFIRMED")
    return {
        "status": "ok",
        "provider": "groq",
        "model": model,
        "model_access": True,
        "generation_confirmed": True,
        "billing_verified": False,
        "remaining_quota": "unknown",
    }


def main() -> int:
    keys = split_keys(os.getenv("GROQ_API_KEY", ""))
    try:
        if not keys:
            raise CheckError("MISSING_OR_INVALID_API_KEY")
        result: dict | None = None
        # Cada tanque del pool se comprueba en vivo: una llave muerta es error de config.
        for index, key in enumerate(keys):
            if index:
                print(
                    json.dumps({"event": "key_rotated", "provider": "groq", "index": index}),
                    flush=True,
                )
            result = run_check(key, os.getenv("GROQ_MODEL", DEFAULT_MODEL))
    except CheckError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "provider": "groq",
                    "reason": exc.reason,
                    "http_status": exc.http_status,
                }
            )
        )
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
