"""Adaptadores de una decisión de herramienta. Solo el controlador ejecuta la acción."""

import json
import os
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

from harness.gemini_proposer import generate_json
from harness.groq_check import API_ROOT, DEFAULT_MODEL
from harness.provider_http import ROTATE_STATUSES, CheckError, pool_keys, request_json

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
    key_cursor: dict[str, int] = field(default_factory=dict)

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
    gemini_keys = pool_keys("GEMINI_API_KEY")
    if gemini_keys and session.eligible("gemini"):
        notice("Gemini")
        try:
            decision = json.loads(
                _gemini_text(session, gemini_keys, instruction, user, output_tokens)
            )
            session.success("gemini")
            return decision
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
    groq_keys = pool_keys("GROQ_API_KEY")
    if groq_keys and session.eligible("groq"):
        notice("Groq")
        total = len(groq_keys)
        last: CheckError | None = None
        for step in range(total):
            index = (session.key_cursor.get("groq", 0) + step) % total
            try:
                decision = _groq_decision(
                    groq_keys[index], instruction, user, schema, output_tokens
                )
                session.success("groq")
                session.key_cursor["groq"] = index
                return decision
            except CheckError as exc:
                last = exc
                if exc.http_status not in ROTATE_STATUSES or step + 1 >= total:
                    break
                print(
                    json.dumps(
                        {
                            "event": "key_rotated",
                            "provider": "groq",
                            "index": (index + 1) % total,
                        }
                    ),
                    flush=True,
                )
        print(
            json.dumps(
                {
                    "event": "provider_attempt_failed",
                    "provider": "groq",
                    "reason": last.reason if last else "PROVIDER_UNAVAILABLE",
                    "http_status": last.http_status if last else None,
                }
            ),
            flush=True,
        )
        if last is None:
            raise CheckError("NO_AVAILABLE_PROVIDER")
        session.failed("groq")
        raise last
    raise CheckError("NO_AVAILABLE_PROVIDER")


def _gemini_text(
    session: ProviderSession, keys: list[str], instruction: str, user: str, output_tokens: int
) -> str:
    """Primer tanque vivo del pool Gemini; gira al siguiente cuando un 429 lo seca."""
    total = len(keys)
    last: CheckError | None = None
    for step in range(total):
        index = (session.key_cursor.get("gemini", 0) + step) % total
        try:
            for attempt in range(2):
                try:
                    text = generate_json(keys[index], instruction, user, output_tokens)
                    session.key_cursor["gemini"] = index
                    return text
                except CheckError as exc:
                    if exc.http_status != 503 or attempt:
                        raise
                    time.sleep(2)
        except CheckError as exc:
            last = exc
            if exc.http_status in ROTATE_STATUSES and step + 1 < total:
                print(
                    json.dumps(
                        {
                            "event": "key_rotated",
                            "provider": "gemini",
                            "index": (index + 1) % total,
                        }
                    ),
                    flush=True,
                )
                continue
            raise
    if last is not None:
        raise last
    raise CheckError("PROVIDER_UNAVAILABLE")


def _groq_decision(key: str, instruction: str, user: str, schema: dict, output_tokens: int) -> dict:
    response = request_json(
        API_ROOT + "/chat/completions",
        {"Authorization": "Bearer " + key},
        {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": user},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "next_action",
                        "description": "Leer, buscar, editar o responder usando el contrato.",
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "next_action"}},
            "parallel_tool_calls": False,
            "reasoning_effort": "low",
            "max_completion_tokens": min(output_tokens, 3072),
        },
    )
    try:
        choice = response["choices"][0]
        calls = choice["message"].get("tool_calls", [])
        if choice["finish_reason"] != "tool_calls" or len(calls) != 1:
            raise CheckError("INVALID_TOOL_RESPONSE")
        call = calls[0]["function"]
        if call["name"] != "next_action":
            raise CheckError("INVALID_TOOL_RESPONSE")
        decision = json.loads(call["arguments"])
    except (KeyError, IndexError, TypeError):
        raise CheckError("INVALID_TOOL_RESPONSE") from None
    return decision
