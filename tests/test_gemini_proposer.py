import io
import json

import pytest

from harness import gemini_proposer as gemini
from harness import provider_http, review_push
from harness.engine import Validation, run_request
from harness.proposals import Proposal, digest
from harness.provider_http import CheckError

BASE = {"taskapp/sample.py": "value = 1\n"}


def test_provider_timeouts_remain_bounded_and_network_is_not_retried(monkeypatch):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(timeout)
            if len(calls) == 3:
                raise TimeoutError("private")
            return io.BytesIO(b"{}")

    monkeypatch.setenv("GROQ_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(provider_http.urllib.request, "build_opener", lambda *_: Opener())
    google = "https://generativelanguage.googleapis.com/v1beta/models/demo"
    provider_http.request_json(google, {})
    provider_http.request_json("https://api.groq.com/openai/v1/models", {})
    with pytest.raises(CheckError, match="NETWORK_ERROR"):
        provider_http.request_json(google, {})
    assert calls == [90, 30, 90]


def proposal():
    return Proposal.model_validate(
        {
            "action": "change",
            "summary": "Valor ficticio",
            "files": [
                {
                    "path": "taskapp/sample.py",
                    "base_sha256": digest(BASE["taskapp/sample.py"]),
                    "content": "value = 2\n",
                }
            ],
        }
    )


def response(text=None):
    return {
        "modelVersion": gemini.DEFAULT_MODEL,
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": text or proposal().model_dump_json()}]},
            }
        ],
    }


def test_gemini_preserves_contract_context_and_secret_boundary(monkeypatch):
    calls = []

    def transport(key, model, payload):
        assert key == "test-only"
        assert model == gemini.DEFAULT_MODEL
        assert "test-only" not in json.dumps(payload)
        calls.append(payload)
        return response()

    monkeypatch.setattr(gemini, "request_json", transport)
    base = {**BASE, "tests/private.py": "not-shared"}
    generated = gemini.GeminiProposer("test-only", frozenset(BASE))("Cambio", base, "Fallo previo")
    assert generated == proposal()
    context = json.loads(calls[0]["contents"][0]["parts"][0]["text"])
    assert set(context["files"]) == set(BASE)
    assert context["files"]["taskapp/sample.py"]["content"] == BASE["taskapp/sample.py"]
    assert context["validation_feedback"] == "Fallo previo"
    assert calls[0]["generationConfig"]["responseMimeType"] == "application/json"
    assert calls[0]["generationConfig"]["maxOutputTokens"] == 4096


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"modelVersion": "other"},
        {**response(), "candidates": []},
        {**response(), "candidates": [{"finishReason": "MAX_TOKENS"}]},
        {**response(), "candidates": [{"finishReason": "SAFETY"}]},
        {**response(), "candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
        {
            **response(),
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"functionCall": {}}]}}],
        },
    ],
)
def test_incomplete_or_unexpected_gemini_responses_are_rejected(monkeypatch, bad):
    monkeypatch.setattr(gemini, "request_json", lambda *_: bad)
    proposer = gemini.GeminiProposer("test-only")
    with pytest.raises(CheckError):
        proposer("Cambio", BASE, "")


def test_gemini_invalid_context_never_calls_network(monkeypatch):
    monkeypatch.setattr(
        gemini, "request_json", lambda *_: pytest.fail("No enviar contexto excesivo")
    )
    proposer = gemini.GeminiProposer("test-only")
    with pytest.raises(CheckError, match="CONTEXT_TOO_LARGE"):
        proposer("Cambio", {"taskapp/a.py": "x" * 16000}, "")


def test_fallback_stays_on_gemini_during_repair_and_still_validates(capsys):
    primary_calls, secondary_calls, validations = [], [], []

    def primary(*args):
        primary_calls.append(args)
        raise CheckError("QUOTA_OR_RATE_LIMIT", 429)

    def secondary(*args):
        secondary_calls.append(args)
        return proposal()

    def validate(candidate):
        validations.append(candidate)
        return Validation(len(validations) == 2, "Fallo real de prueba")

    outcome = run_request("Cambio", BASE, gemini.QuotaFallback(primary, secondary), validate)
    assert outcome.status == "validated"
    assert len(primary_calls) == 1
    assert len(secondary_calls) == len(validations) == 2
    assert secondary_calls[1][2] == "Fallo real de prueba"
    event = json.loads(capsys.readouterr().out)
    assert event["from"] == "groq"
    assert event["to"] == "gemini"


@pytest.mark.parametrize(
    "reason",
    ["AUTHENTICATION_FAILED", "NETWORK_ERROR", "INVALID_RESPONSE", "CONTEXT_TOO_LARGE"],
)
def test_other_errors_never_switch_provider(reason):
    def primary(*_):
        raise CheckError(reason)

    backup = gemini.QuotaFallback(primary, lambda *_: pytest.fail("No ocultar otros fallos"))
    with pytest.raises(CheckError, match=reason):
        backup("Cambio", BASE, "")


def test_both_providers_limited_stop_without_approving():
    def limited(*_):
        raise CheckError("QUOTA_OR_RATE_LIMIT", 429)

    result = run_request(
        "Cambio", BASE, gemini.QuotaFallback(limited, limited), lambda *_: pytest.fail("No validar")
    )
    assert result.status == "failed"
    assert result.candidate is None
    assert len(result.attempts) == 1


def test_available_groq_does_not_call_backup():
    backup = gemini.QuotaFallback(lambda *_: proposal(), lambda *_: pytest.fail("No gastar Gemini"))
    assert backup("Cambio", BASE, "") == proposal()


def test_unconfigured_backup_keeps_original_provider(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    primary = lambda *_: proposal()  # noqa: E731
    assert gemini.with_gemini_fallback(primary, frozenset(BASE)) is primary


def test_contextual_review_fallback_keeps_line_validation(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")

    def limited(*_):
        raise CheckError("QUOTA_OR_RATE_LIMIT", 429)

    monkeypatch.setattr(review_push, "request_json", limited)
    recommendation = {"rule": "NAME", "path": "taskapp/sample.py", "line": 1, "message": "Nombre"}
    monkeypatch.setattr(
        review_push,
        "generate_json",
        lambda *_: json.dumps({"recommendations": [recommendation]}),
    )
    assert review_push.contextual_review("primary-test", BASE, list(BASE)) == [recommendation]
    recommendation["line"] = 999
    with pytest.raises(CheckError, match="INVALID_CONTEXTUAL_REVIEW"):
        review_push.contextual_review("primary-test", BASE, list(BASE))
