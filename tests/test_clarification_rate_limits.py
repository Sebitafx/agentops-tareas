import io
import urllib.error
from email.message import Message

import pytest

from harness import provider_http as transport
from harness.engine import Validation, run_request
from harness.proposals import Proposal, digest

URL = "https://api.groq.com/openai/v1/chat/completions"


@pytest.mark.parametrize(
    "task_request",
    ["Agregar un boton", "AGREGA UN BOTÓN.", "añadir un botón", "agregar una función por favor"],
)
def test_vague_addition_asks_before_any_generation_or_validation(task_request):
    result = run_request(
        task_request,
        {},
        lambda *_: pytest.fail("No gastar cuota inventando requisitos"),
        lambda *_: pytest.fail("No ejecutar cambios ambiguos"),
    )
    assert result.status == "clarify"
    assert result.attempts == ()
    assert result.proposal.question
    assert "pulsarlo" in result.proposal.question
    assert result.candidate is None


def test_concrete_theme_request_reaches_proposer():
    base = {"taskapp/static/app.js": "const theme = 'light';"}
    calls = []

    def propose(request, snapshot, feedback):
        calls.append(request)
        return Proposal.model_validate(
            {
                "action": "change",
                "summary": "Tema ficticio",
                "files": [
                    {
                        "path": "taskapp/static/app.js",
                        "base_sha256": digest(base["taskapp/static/app.js"]),
                        "content": "const theme = 'dark';",
                    }
                ],
            }
        )

    result = run_request(
        "Agregar un boton de modo oscuro y claro funcional, realizar las pruebas correspondientes",
        base,
        propose,
        lambda _: Validation(True, ""),
    )
    assert result.status == "validated"
    assert len(calls) == 1


def install_responses(monkeypatch, codes, retry_after="2", url=URL):
    calls, waits, bodies = [], [], []
    monkeypatch.setenv("GROQ_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(transport.time, "sleep", waits.append)

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            code = codes[len(calls) - 1]
            if code:
                headers = Message()
                if retry_after is not None:
                    headers["Retry-After"] = retry_after
                body = io.BytesIO(b"private-provider-body")
                bodies.append(body)
                raise urllib.error.HTTPError(url, code, "private", headers, body)
            return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(transport.urllib.request, "build_opener", lambda *_: Opener())
    return calls, waits, bodies


def test_explicit_short_rate_limit_recovers_with_identical_request(monkeypatch):
    calls, waits, bodies = install_responses(monkeypatch, [429, 429, 0], "1.5")
    assert transport.request_json(URL, {"Authorization": "Bearer test-only"}, {"demo": 1}) == {
        "ok": True
    }
    assert waits == [1.5, 1.5]
    assert len(calls) == 3
    assert calls[0] is calls[1] is calls[2]
    assert all(body.closed for body in bodies)


@pytest.mark.parametrize("delay", [None, "", "bad", "NaN", "inf", "-1", "0", "86400"])
def test_unknown_or_long_quota_does_not_retry(monkeypatch, delay):
    calls, waits, _ = install_responses(monkeypatch, [429], delay)
    with pytest.raises(transport.CheckError, match="^QUOTA_OR_RATE_LIMIT$"):
        transport.request_json(URL, {}, {})
    assert len(calls) == 1
    assert waits == []


def test_repeated_rate_limit_stops_after_two_waits(monkeypatch):
    calls, waits, _ = install_responses(monkeypatch, [429, 429, 429], "60")
    with pytest.raises(transport.CheckError, match="^QUOTA_OR_RATE_LIMIT$"):
        transport.request_json(URL, {}, {})
    assert len(calls) == 3
    assert sum(waits) == 120


@pytest.mark.parametrize("code", [400, 401, 403, 404, 500])
def test_other_http_errors_are_never_retried(monkeypatch, code):
    calls, waits, _ = install_responses(monkeypatch, [code])
    with pytest.raises(transport.CheckError) as error:
        transport.request_json(URL, {}, {})
    assert error.value.http_status == code
    assert "private" not in str(error.value)
    assert len(calls) == 1
    assert waits == []


def test_gemini_rate_limit_is_not_retried(monkeypatch):
    url = "https://generativelanguage.googleapis.com/v1beta/models/demo:generateContent"
    calls, waits, _ = install_responses(monkeypatch, [429], url=url)
    with pytest.raises(transport.CheckError, match="QUOTA_OR_RATE_LIMIT"):
        transport.request_json(url, {}, {})
    assert len(calls) == 1
    assert waits == []
