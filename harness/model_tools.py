"""Adaptadores de una decisión de herramienta. Solo el controlador ejecuta la acción."""

import json
import os
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

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


@dataclass
class ProviderSession:
    selected: str | None = None
    locked: bool = False
    unavailable: set[str] = field(default_factory=set)

    def eligible(self, provider):
        return provider not in self.unavailable and (
            not self.selected or not self.locked or provider == self.selected
        )

    def success(self, provider):
        self.selected = provider

    def failed(self, provider):
        if self.locked and self.selected == provider:
            return False
        self.unavailable.add(provider)
        return True


SESSION: ContextVar[ProviderSession | None] = ContextVar("provider_session", default=None)


def strict_schema(schema):
    """Subset compartido: el validador local conserva todas las restricciones."""
    if isinstance(schema, list):
        return [strict_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    omitted = {
        "default",
        "title",
        "format",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "maxItems",
    }
    result = {key: strict_schema(value) for key, value in schema.items() if key not in omitted}
    if result.get("type") == "object":
        result["additionalProperties"] = False
        result["required"] = list(result.get("properties", {}))
    return result


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
    session = SESSION.get() or ProviderSession()
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
    if key and session.eligible("openai"):
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
            decision = json.loads(calls[0]["arguments"])
            session.success("openai")
            return decision
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
            if exc.reason not in RECOVERABLE or not session.failed("openai"):
                raise
    instruction = system + " Devuelve solo JSON con este esquema: " + json.dumps(schema)
    gemini = os.getenv("GEMINI_API_KEY")
    if gemini and session.eligible("gemini"):
        notice("Gemini")
        try:
            for attempt in range(2):
                try:
                    decision = json.loads(generate_json(gemini, instruction, user, output_tokens))
                    session.success("gemini")
                    return decision
                except CheckError as exc:
                    if exc.http_status != 503 or attempt:
                        raise
                    time.sleep(2)
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
            if exc.reason not in RECOVERABLE or not session.failed("gemini"):
                raise
    groq = os.getenv("GROQ_API_KEY")
    if groq and session.eligible("groq"):
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
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "next_action",
                        "strict": True,
                        "schema": strict_schema(schema),
                    },
                },
                "reasoning_effort": "low",
                "max_completion_tokens": min(output_tokens, 3072),
            },
        )
        choice = response["choices"][0]
        if choice["finish_reason"] != "stop":
            raise CheckError("INCOMPLETE_PROPOSAL")
        decision = json.loads(choice["message"]["content"])
        session.success("groq")
        return decision
    raise CheckError("NO_AVAILABLE_PROVIDER")
