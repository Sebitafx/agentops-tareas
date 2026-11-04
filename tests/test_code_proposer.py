import json

import pytest
from pydantic import ValidationError

from harness import code_proposer, proposal_check
from harness.code_proposer import GroqProposer
from harness.proposals import Proposal, digest
from harness.provider_http import CheckError


def generated(text, finish="stop", **message):
    return {
        "model": code_proposer.DEFAULT_MODEL,
        "choices": [{"finish_reason": finish, "message": {"content": text, **message}}],
    }


def test_structured_proposal_sends_hashes_and_keeps_key_out_of_prompt(monkeypatch):
    calls = []
    response = {
        "action": "change",
        "summary": "Cambio ficticio",
        "files": [{"path": "taskapp/a.py", "base_sha256": digest("a=1"), "content": "a=2"}],
    }

    def transport(url, headers, payload):
        calls.append(payload)
        assert headers["Authorization"] == "Bearer test-only"
        assert "test-only" not in json.dumps(payload)
        assert payload["response_format"] == {"type": "json_object"}
        context = json.loads(payload["messages"][1]["content"])
        assert context["files"]["taskapp/a.py"]["sha256"] == digest("a=1")
        assert context["validation_feedback"] == "Fallo de prueba ficticia"
        return generated(json.dumps(response))

    monkeypatch.setattr(code_proposer, "request_json", transport)
    proposal = GroqProposer("test-only")(
        "Ajusta valor", {"taskapp/a.py": "a=1"}, "Fallo de prueba ficticia"
    )
    assert proposal.files[0].content == "a=2" and len(calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"model": "otro"},
        {"model": code_proposer.DEFAULT_MODEL, "choices": []},
        {"model": code_proposer.DEFAULT_MODEL, "choices": [None]},
        generated(None),
        generated("{}", finish="length"),
        generated("{}", tool_calls=[{"name": "shell"}]),
    ],
)
def test_malformed_or_incomplete_generation_not_accepted(monkeypatch, response):
    monkeypatch.setattr(code_proposer, "request_json", lambda *_: response)
    with pytest.raises(CheckError):
        GroqProposer("test-only")("Demo", {}, "")


def test_invalid_json_contract_is_rejected(monkeypatch):
    monkeypatch.setattr(code_proposer, "request_json", lambda *_: generated('{"action":"execute"}'))
    with pytest.raises(ValidationError):
        GroqProposer("test-only")("Demo", {}, "")


def test_context_and_credentials_checked_before_network(monkeypatch):
    monkeypatch.setattr(code_proposer, "request_json", lambda *_: pytest.fail("No llamar red"))
    for key, model in [("", code_proposer.DEFAULT_MODEL), ("test-only", "inventado")]:
        with pytest.raises(CheckError):
            GroqProposer(key, model)
    with pytest.raises(CheckError, match="CONTEXT_TOO_LARGE"):
        GroqProposer("test-only")("Demo", {"taskapp/a.py": "x" * 16000}, "")
    # El codigo no se recorta: aun con diagnostico presente, exceder sigue fallando.
    with pytest.raises(CheckError, match="CONTEXT_TOO_LARGE"):
        GroqProposer("test-only")("Demo", {"taskapp/a.py": "x" * 16000}, "Fallo real")


def test_oversized_diagnostic_trimmed_but_request_and_code_complete(monkeypatch):
    calls = []

    def transport(_url, _headers, payload):
        calls.append(payload)
        return generated(json.dumps({"action": "clarify", "summary": "Demo", "question": "Demo?"}))

    monkeypatch.setattr(code_proposer, "request_json", transport)
    source = "a = 1\n"
    feedback = "CAUSA " + "x" * 20000 + " RESUMEN"
    GroqProposer("test-only")("Requisito completo", {"taskapp/a.py": source}, feedback)
    context = json.loads(calls[0]["messages"][1]["content"])
    sent = context["validation_feedback"]
    assert len(calls) == 1
    assert len(sent) < len(feedback) and "[diagnostico acotado]" in sent
    assert sent.startswith("CAUSA") and sent.endswith("RESUMEN")
    assert context["files"]["taskapp/a.py"]["content"] == source
    assert context["request"] == "Requisito completo"
    assert (
        len(code_proposer.SYSTEM) + len(calls[0]["messages"][1]["content"])
        <= code_proposer.MAX_CONTEXT_CHARS
    )


def test_diagnostic_is_not_trimmed_when_context_fits(monkeypatch):
    captured = {}

    def transport(_url, _headers, payload):
        captured.update(payload)
        return generated(json.dumps({"action": "clarify", "summary": "Demo", "question": "Demo?"}))

    monkeypatch.setattr(code_proposer, "request_json", transport)
    feedback = "Causa corta " * 50
    GroqProposer("test-only")("Demo", {"taskapp/a.py": "a = 1\n"}, feedback)
    sent = json.loads(captured["messages"][1]["content"])["validation_feedback"]
    assert sent == feedback and "[diagnostico acotado]" not in sent


def test_provider_quota_has_no_automatic_retry(monkeypatch):
    calls = []

    def transport(*_):
        calls.append(1)
        raise CheckError("QUOTA_OR_RATE_LIMIT", 429)

    monkeypatch.setattr(code_proposer, "request_json", transport)
    with pytest.raises(CheckError, match="QUOTA_OR_RATE_LIMIT"):
        GroqProposer("test-only")("Demo", {}, "")
    assert len(calls) == 1


def test_preflight_missing_key_reports_safe_failure(monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert proposal_check.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "reason": "MISSING_OR_INVALID_API_KEY",
    }


def test_preflight_proposal_is_artifact_only(monkeypatch, tmp_path, capsys):
    (tmp_path / "taskapp").mkdir()
    source = tmp_path / "taskapp" / "schemas.py"
    source.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(proposal_check, "__file__", str(tmp_path / "harness" / "proposal_check.py"))
    proposal = Proposal.model_validate(
        {
            "action": "change",
            "summary": "Demo",
            "files": [
                {
                    "path": "taskapp/schemas.py",
                    "content": "value = 2\n",
                    "base_sha256": digest("value = 1\n"),
                }
            ],
        }
    )
    monkeypatch.setattr(proposal_check, "GroqProposer", lambda _: lambda *_: proposal)
    assert proposal_check.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "proposed" and not result["code_executed"]
    assert source.read_text(encoding="utf-8") == "value = 1\n"
    artifact = tmp_path / "artifacts" / "synthetic-proposal.json"
    assert Proposal.model_validate_json(artifact.read_text(encoding="utf-8")) == proposal


def test_preflight_clarification_is_not_a_code_generation_success(monkeypatch, capsys):
    proposal = Proposal(action="clarify", summary="Falta requisito", question="¿Cual?")
    monkeypatch.setattr(proposal_check, "GroqProposer", lambda _: lambda *_: proposal)
    assert proposal_check.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "NO_CODE_PROPOSED"
