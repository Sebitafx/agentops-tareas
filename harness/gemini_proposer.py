"""Respaldo explicito Gemini: mismo contrato, contexto y validacion aislada."""

import json
import os
from collections.abc import Mapping

from harness.code_proposer import SYSTEM, GroqProposer
from harness.engine import Proposer
from harness.gemini_check import ALLOWED_MODELS, DEFAULT_MODEL, request_json
from harness.proposals import Proposal
from harness.provider_http import (
    ROTATE_STATUSES,
    CheckError,
    ProposalOutputLimit,
    split_keys,
    validate_key,
)


def generate_json(key: str, system: str, context: str, max_tokens: int = 4096) -> str:
    validate_key(key)
    result = request_json(
        key,
        DEFAULT_MODEL,
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": context}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "thinkingConfig": {"thinkingLevel": "low"},
                "responseMimeType": "application/json",
            },
        },
    )
    if result.get("modelVersion") != DEFAULT_MODEL:
        raise CheckError("UNEXPECTED_GENERATION_MODEL")
    try:
        candidates = result["candidates"]
        if len(candidates) == 1 and candidates[0]["finishReason"] == "MAX_TOKENS":
            raise ProposalOutputLimit()
        if len(candidates) != 1 or candidates[0]["finishReason"] != "STOP":
            raise CheckError("INCOMPLETE_PROPOSAL")
        parts = candidates[0]["content"]["parts"]
        if not isinstance(parts, list) or not parts:
            raise CheckError("INVALID_RESPONSE")
        text = "".join(visible_part(part) for part in parts)
        if not text.strip():
            raise CheckError("INVALID_RESPONSE")
    except (KeyError, IndexError, TypeError, AttributeError):
        raise CheckError("INVALID_RESPONSE") from None
    return text


def visible_part(part: dict) -> str:
    if not isinstance(part, dict) or set(part) - {"text", "thought", "thoughtSignature"}:
        raise CheckError("INVALID_RESPONSE")
    if part.get("thought", False):
        return ""
    if not isinstance(part.get("text"), str):
        raise CheckError("INVALID_RESPONSE")
    return part["text"]


class GeminiProposer(GroqProposer):
    def __init__(self, key: str, visible_paths: frozenset[str] | None = None) -> None:
        # Solo se comparte el constructor de contexto, no el transporte Groq.
        # El env puede traer un pool separado por comas; cada tanque se valida.
        self.keys = split_keys(key)
        if not self.keys:
            raise CheckError("MISSING_OR_INVALID_API_KEY")
        for entry in self.keys:
            validate_key(entry)
        if DEFAULT_MODEL not in ALLOWED_MODELS:
            raise CheckError("MODEL_NOT_ALLOWED")
        self.key = self.keys[0]
        self.model = DEFAULT_MODEL
        self.visible_paths = visible_paths

    def __call__(self, request: str, base: Mapping[str, str], feedback: str) -> Proposal:
        context = self.context(request, base, feedback)
        total = len(self.keys)
        text: str | None = None
        last: CheckError | None = None
        for step in range(total):
            try:
                text = generate_json(self.keys[step], SYSTEM, context, 8192)
                break
            except CheckError as exc:
                last = exc
                if exc.http_status in ROTATE_STATUSES and step + 1 < total:
                    print(
                        json.dumps(
                            {
                                "event": "key_rotated",
                                "provider": "gemini",
                                "index": (step + 1) % total,
                            }
                        ),
                        flush=True,
                    )
                    continue
                raise
        if text is None:
            if last is not None:
                raise last
            raise CheckError("PROVIDER_UNAVAILABLE")
        return Proposal.model_validate_json(text)


class QuotaFallback:
    def __init__(self, primary: Proposer, secondary: Proposer) -> None:
        self.primary = primary
        self.secondary = secondary
        self.using_secondary = False

    def __call__(self, request: str, base: Mapping[str, str], feedback: str) -> Proposal:
        if not self.using_secondary:
            try:
                return self.primary(request, base, feedback)
            except CheckError as exc:
                if exc.reason != "QUOTA_OR_RATE_LIMIT" and not isinstance(exc, ProposalOutputLimit):
                    raise
                self.using_secondary = True
                print(
                    json.dumps(
                        {
                            "event": "provider_fallback",
                            "from": "groq",
                            "to": "gemini",
                            "reason": exc.reason,
                            "model": DEFAULT_MODEL,
                        }
                    ),
                    flush=True,
                )
        return self.secondary(request, base, feedback)


def with_gemini_fallback(primary: Proposer, paths: frozenset[str]) -> Proposer:
    # El pool vive en el env separado por comas; el proposer rota entre tanques.
    keys = split_keys(os.getenv("GEMINI_API_KEY", ""))
    if not keys:
        return primary
    theme_files = {
        "taskapp/static/index.html",
        "taskapp/static/app.js",
        "taskapp/static/style.css",
    }
    if theme_files.issubset(paths):
        print(
            json.dumps(
                {
                    "event": "provider_selected",
                    "provider": "gemini",
                    "model": DEFAULT_MODEL,
                    "reason": "MULTIFILE_UI_CONTEXT",
                }
            ),
            flush=True,
        )
        return GeminiProposer(",".join(keys), paths)
    return QuotaFallback(primary, GeminiProposer(",".join(keys), paths))
