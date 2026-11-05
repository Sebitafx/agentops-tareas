from concurrent.futures import ThreadPoolExecutor

import pytest

from bootstrap import conversation
from bootstrap.budget import reserve
from harness import interactive_proposer as coding
from harness import model_tools
from harness.proposals import apply_to_snapshot
from tests.test_replies import counts, incoming


def test_turns_survive_between_messages_without_duplicate_job(database, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    def decide(system, context, *args):
        if not context["history"]:
            return {"action": "answer", "text": "¿Qué debe hacer el botón?"}
        if context["jobs"]:
            return {"action": "status", "text": "Consultar"}
        assert "botón" in context["history"][0][1]
        return {"action": "change", "text": "Alternar modo oscuro y claro."}

    monkeypatch.setattr(conversation, "choose", decide)
    for text in ["Pon un botón", "Que alterne el modo oscuro", "¿Cómo va?"]:
        m = incoming(text)
        database.save([m, m], [])
        assert conversation.process(database)
        assert not conversation.process(database)
    assert counts(database) == (3, 3, 1)
    with database.connect() as c:
        assert (
            "received"
            in c.execute("SELECT answer FROM agentops_turns ORDER BY seq DESC LIMIT 1").fetchone()[
                0
            ]
        )


def test_concurrent_budget_preserves_demo_reserve(database, monkeypatch):
    monkeypatch.delenv("AGENTOPS_DEMO", raising=False)
    with database.connect() as c:
        c.execute("UPDATE agentops_ai_budget SET reserved=4900000")
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(lambda _: reserve(database, 100000), range(4))) == 1
        monkeypatch.setenv("AGENTOPS_DEMO", "1")
        assert reserve(database, 100000)
    finally:
        with database.connect() as c:
            c.execute("UPDATE agentops_ai_budget SET reserved=0")


def test_budget_denial_switches_before_openai_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(model_tools, "request_json", lambda *_: pytest.fail("Paid request"))
    monkeypatch.setattr(model_tools, "generate_json", lambda *_: '{"action":"answer"}')
    notices = []
    assert model_tools.choose("chat", {}, {}, lambda _: False, 1000, notices.append) == {
        "action": "answer"
    }
    assert notices == ["Gemini"]


def test_sol_responses_contract(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    def transport(url, headers, payload):
        assert url == "https://api.openai.com/v1/responses"
        assert payload["model"] == "gpt-6.1-sol" and payload["reasoning"] == {"effort": "medium"}
        return {
            "status": "completed",
            "output": [
                {"type": "reasoning"},
                {
                    "type": "function_call",
                    "name": "next_action",
                    "arguments": '{"action":"answer"}',
                },
            ],
        }

    monkeypatch.setattr(model_tools, "request_json", transport)
    assert model_tools.choose("chat", {}, {}, lambda n: n > 10000, 1200)["action"] == "answer"


def test_model_search_and_patch_keep_rest_of_file(monkeypatch):
    base = {"taskapp/x.js": "head\nlight\nend", "tests/private.py": "do not expose"}

    def decide(system, context, *args):
        assert "tests/private.py" not in str(context)
        if "matches" not in context:
            return {"action": "search", "detail": "light"}
        return {
            "action": "change",
            "detail": "Tema actualizado",
            "edits": [{"path": "taskapp/x.js", "before": "light", "after": "dark"}],
        }

    monkeypatch.setattr(coding, "choose", decide)
    result = coding.InteractiveProposer(lambda _: True, lambda _: None)("oscuro", base, "")
    assert apply_to_snapshot(result, base)["taskapp/x.js"] == "head\ndark\nend"


def test_ambiguous_patch_rejected():
    step = coding.Step(
        action="change",
        detail="tema",
        edits=[coding.Edit(path="taskapp/x.js", before="a", after="b")],
    )
    with pytest.raises(ValueError, match="PATCH_MISMATCH"):
        coding.materialize(step, {"taskapp/x.js": "aaa"})


def test_patch_mismatch_names_file_reason_and_fragment():
    step = coding.Step(
        action="change",
        detail="tema",
        edits=[coding.Edit(path="taskapp/x.js", before="clase vieja", after="clase nueva")],
    )
    with pytest.raises(
        ValueError,
        match=r"PATCH_MISMATCH en taskapp/x\.js: fragmento no encontrado \(0 coincidencias\).*clase vieja",
    ):
        coding.materialize(step, {"taskapp/x.js": "a"})


def test_patch_mismatch_distinguishes_duplicate_from_missing():
    duplicado = coding.Step(
        action="change",
        detail="tema",
        edits=[coding.Edit(path="taskapp/x.js", before="a", after="b")],
    )
    with pytest.raises(ValueError, match=r"duplicado \(2 coincidencias\)"):
        coding.materialize(duplicado, {"taskapp/x.js": "a\nb\na"})
    inexistente = coding.Step(
        action="change",
        detail="tema",
        edits=[coding.Edit(path="taskapp/nuevo.js", before="a", after="b")],
    )
    with pytest.raises(ValueError, match="el archivo no existe en el snapshot"):
        coding.materialize(inexistente, {"taskapp/x.js": "a"})


def test_engine_feedback_carries_patch_diagnosis_to_next_attempt():
    from harness.engine import Validation, run_request

    contexts = []

    def propose(request, base, feedback):
        contexts.append(feedback)
        if len(contexts) == 1:
            raise ValueError("PATCH_MISMATCH en taskapp/x.js: fragmento no encontrado")
        from harness.proposals import Proposal, digest

        return Proposal.model_validate(
            {
                "action": "change",
                "summary": "Reparacion informada",
                "files": [
                    {
                        "path": "taskapp/x.js",
                        "base_sha256": digest(base["taskapp/x.js"]),
                        "content": base["taskapp/x.js"] + "\n// aplicado\n",
                    }
                ],
            }
        )

    base = {"taskapp/x.js": "head\nend"}
    result = run_request("Peticion ficticia", base, propose, lambda _: Validation(True, "ok"))
    assert result.status == "validated"
    assert contexts[1].startswith("INVALID_PROPOSAL: PATCH_MISMATCH en taskapp/x.js")
