import json

import pytest

from harness import interactive_proposer as coding
from harness import model_tools as models
from harness.engine import Validation, run_request
from harness.provider_http import CheckError


def test_patch_repair_keeps_provider_and_bounded_context(monkeypatch):
    for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.setenv(key, "fake-only")
    monkeypatch.setattr(models.time, "sleep", lambda _: None)
    calls = []
    outputs = iter(
        [
            {"action": "read", "detail": "taskapp/style.css"},
            {
                "action": "change",
                "detail": "tema",
                "edits": [{"path": "taskapp/style.css", "before": "missing", "after": "black"}],
            },
            {
                "action": "change",
                "detail": "tema",
                "edits": [{"path": "taskapp/style.css", "before": "white", "after": "black"}],
            },
        ]
    )

    def transport(url, headers, payload):
        calls.append(url)
        if "openai.com" in url:
            raise CheckError("QUOTA_OR_RATE_LIMIT", 429)
        assert len(payload["messages"][1]["content"]) < 10000
        assert payload["max_completion_tokens"] == 3072
        return {
            "choices": [
                {"finish_reason": "stop", "message": {"content": json.dumps(next(outputs))}}
            ]
        }

    monkeypatch.setattr(models, "request_json", transport)
    gemini = []

    def unavailable(*_):
        gemini.append(1)
        raise CheckError("PROVIDER_UNAVAILABLE", 503)

    monkeypatch.setattr(models, "generate_json", unavailable)
    p = coding.InteractiveProposer(lambda _: True, lambda _: None)
    base = {
        "taskapp/style.css": "body {color:white;}\n/*" + "x" * 8000 + "*/",
        "taskapp/app.js": "//" + "x" * 33000,
    }
    outcome = run_request("Oscuro", base, p, lambda _: Validation(True, "ok"))
    assert outcome.status == "validated"
    assert sum("openai.com" in u for u in calls) == 1
    assert len(gemini) == 2
    assert p.session.selected == "groq"


def test_locked_provider_failure_does_not_switch(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-only")
    monkeypatch.setenv("GROQ_API_KEY", "fake-only")
    monkeypatch.setattr(models.time, "sleep", lambda _: None)
    monkeypatch.setattr(models, "request_json", lambda *_: pytest.fail("No cambiar a Groq"))

    def unavailable(*_):
        raise CheckError("PROVIDER_UNAVAILABLE", 503)

    monkeypatch.setattr(models, "generate_json", unavailable)
    p = coding.InteractiveProposer(lambda _: True, lambda _: None, preferred="gemini", locked=True)
    with pytest.raises(CheckError, match="PROVIDER_UNAVAILABLE"):
        p("Tema", {}, "")


def test_user_provider_preference_survives_normalized_request(database, monkeypatch):
    from bootstrap import conversation
    from bootstrap.jobs import claim_job
    from tests.test_replies import incoming

    monkeypatch.setenv("GEMINI_API_KEY", "fake-only")
    monkeypatch.setattr(
        models, "generate_json", lambda *_: '{"action":"change","text":"Mejorar tema"}'
    )
    database.save(
        [incoming("Mejora el tema. Y no cambies de modelo durante la implementación")], []
    )
    assert conversation.process(database)
    with database.connect() as c:
        job = c.execute("SELECT id FROM agentops_jobs").fetchone()[0]
    claimed = claim_job(database, job, "123")
    assert claimed["preferred_provider"] == "gemini" and claimed["keep_provider"]
    assert claimed["request"] == "Mejorar tema"
