"""Adaptadores de una decisión de herramienta. Solo el controlador ejecuta la acción."""

import json
import os
from collections.abc import Callable

from harness.gemini_proposer import generate_json
from harness.groq_check import API_ROOT, DEFAULT_MODEL
from harness.provider_http import CheckError, request_json

SOL = "gpt-6.1-sol"
RECOVERABLE = {
    "BUDGET_LIMIT",
    "QUOTA_OR_RATE_LIMIT",
    "BILLING_UNAVAILABLE",
    "MODEL_UNAVAILABLE",
    "PROVIDER_UNAVAILABLE",
    "NETWORK_ERROR",
    "PROPOSAL_OUTPUT_LIMIT",
}


def conversation_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))


def reservation(payload: dict, output_tokens: int) -> int:
    # UTF-8 bytes bound text tokens conservatively, plus protocol overhead.
    size = len(json.dumps(payload, ensure_ascii=False).encode()) + 4096
    if size > 120000:
        raise CheckError("CONTEXT_TOO_LARGE")
    return size * 2 + output_tokens * 10


def choose(
    system: str,
    context: dict,
    schema: dict,
    reserve: Callable[[int], bool],
    output_tokens: int,
    notice=lambda provider: None,
) -> dict:
    user = json.dumps(context, ensure_ascii=False, default=str)
    function = {
        "type": "function",
        "name": "next_action",
        "description": "Indicar el siguiente paso.",
        "parameters": schema,
        "strict": False,
    }
    payload = {
        "model": SOL,
        "reasoning": {"effort": "medium"},
        "store": False,
        "instructions": system,
        "input": user,
        "tools": [function],
        "tool_choice": {"type": "function", "name": "next_action"},
        "parallel_tool_calls": False,
        "max_output_tokens": output_tokens,
    }
    key = os.getenv("OPENAI_API_KEY")
    if key:
        try:
            if not reserve(reservation(payload, output_tokens)):
                raise CheckError("BUDGET_LIMIT")
            response = request_json(
                "https://api.openai.com/v1/responses", {"Authorization": "Bearer " + key}, payload
            )
            if response.get("status") == "incomplete":
                raise CheckError("PROPOSAL_OUTPUT_LIMIT")
            calls = [
                item for item in response.get("output", []) if item.get("type") == "function_call"
            ]
            if (
                response.get("status") != "completed"
                or len(calls) != 1
                or calls[0].get("name") != "next_action"
            ):
                raise ValueError("INVALID_TOOL_RESPONSE")
            return json.loads(calls[0]["arguments"])
        except CheckError as exc:
            print(
                json.dumps(
                    {
                        "event": "provider_attempt_failed",
                        "provider": "openai",
                        "reason": exc.reason,
                        "http_status": exc.http_status,
                    }
                ),
                flush=True,
            )
            if exc.reason not in RECOVERABLE:
                raise
    instruction = system + " Devuelve solo JSON con este esquema: " + json.dumps(schema)
    if gemini := os.getenv("GEMINI_API_KEY"):
        notice("Gemini")
        try:
            return json.loads(generate_json(gemini, instruction, user, output_tokens))
        except CheckError as exc:
            print(
                json.dumps(
                    {
                        "event": "provider_attempt_failed",
                        "provider": "gemini",
                        "reason": exc.reason,
                        "http_status": exc.http_status,
                    }
                ),
                flush=True,
            )
            if exc.reason not in RECOVERABLE:
                raise
    if groq := os.getenv("GROQ_API_KEY"):
        notice("Groq")
        response = request_json(
            API_ROOT + "/chat/completions",
            {"Authorization": "Bearer " + groq},
            {
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "reasoning_effort": "low",
                "max_completion_tokens": output_tokens,
            },
        )
        choice = response["choices"][0]
        if choice["finish_reason"] != "stop":
            raise CheckError("INCOMPLETE_PROPOSAL")
        return json.loads(choice["message"]["content"])
    raise CheckError("NO_AVAILABLE_PROVIDER")
