import json

import pytest

from bootstrap import conversation
from harness import model_tools
from harness.interactive_proposer import InteractiveProposer
from harness.proposals import apply_to_snapshot
from harness.provider_http import CheckError
from tests.test_replies import incoming


@pytest.mark.parametrize("reason", [None, "QUOTA_OR_RATE_LIMIT", "BILLING_UNAVAILABLE"])
def test_gemini_continues_from_clarification_to_patch(database, monkeypatch, reason):
    if reason:
        monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")

    def exhausted(*args):
        if not reason:
            pytest.fail("Sol sin clave")
        raise CheckError(reason)

    monkeypatch.setattr(model_tools, "request_json", exhausted)

    def gemini(key, system, user, max_tokens):
        ctx = json.loads(user)
        if "paths" in ctx:
            assert "tema oscuro" in ctx["request"]
            return json.dumps(
                {
                    "action": "change",
                    "detail": "Tema actualizado",
                    "edits": [{"path": "taskapp/style.css", "before": "white", "after": "black"}],
                }
            )
        if ctx["history"]:
            assert ctx["history"][0][0] == "Pon un botón"
            return '{"action":"change","text":"Agregar selector de tema oscuro"}'
        return '{"action":"answer","text":"¿Para qué sirve el botón?"}'

    monkeypatch.setattr(model_tools, "generate_json", gemini)
    for message in ["Pon un botón", "Para alternar el tema"]:
        database.save([incoming(message)], [])
        assert conversation.process(database)
    with database.connect() as c:
        [(request,)] = c.execute("SELECT request_text FROM agentops_jobs").fetchall()
        assert (
            c.execute(
                "SELECT count(*) FROM agentops_turns WHERE answer LIKE '%Gemini%'"
            ).fetchone()[0]
            == 2
        )
    base = {"taskapp/style.css": "body { background: white; }"}
    proposal = InteractiveProposer(lambda _: True, lambda _: None)(request, base, "")
    assert "black" in apply_to_snapshot(proposal, base)["taskapp/style.css"]
