import json

import pytest

from harness import code_proposer, gemini_proposer
from harness.engine import Validation, run_request
from harness.proposals import digest
from harness.provider_http import CheckError

BASE = {"taskapp/a.py": "value = 1\n"}


def groq_response(finish):
    return {
        "model": code_proposer.DEFAULT_MODEL,
        "choices": [{"finish_reason": finish, "message": {"content": '{"files": ['}}],
    }


def test_truncated_groq_is_discarded_and_complete_backup_must_validate(monkeypatch, capsys):
    monkeypatch.setattr(code_proposer, "request_json", lambda *_: groq_response("length"))
    change = {
        "action": "change",
        "summary": "Demo",
        "files": [
            {
                "path": "taskapp/a.py",
                "base_sha256": digest(BASE["taskapp/a.py"]),
                "content": "value = 2\n",
            }
        ],
    }
    response = {
        "modelVersion": gemini_proposer.DEFAULT_MODEL,
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(change)}]}}
        ],
    }
    monkeypatch.setattr(gemini_proposer, "request_json", lambda *_: response)
    provider = gemini_proposer.QuotaFallback(
        code_proposer.GroqProposer("primary-test"), gemini_proposer.GeminiProposer("backup-test")
    )
    validated = []

    def validate(candidate):
        validated.append(candidate)
        return Validation(True, "")

    outcome = run_request("Cambio", BASE, provider, validate)
    assert outcome.status == "validated"
    assert validated == [{"taskapp/a.py": "value = 2\n"}]
    assert json.loads(capsys.readouterr().out)["reason"] == "PROPOSAL_OUTPUT_LIMIT"


@pytest.mark.parametrize("finish", ["content_filter", "tool_calls", "unknown"])
def test_other_incomplete_responses_do_not_switch_model(monkeypatch, finish):
    monkeypatch.setattr(code_proposer, "request_json", lambda *_: groq_response(finish))
    backup = gemini_proposer.QuotaFallback(
        code_proposer.GroqProposer("test-only"), lambda *_: pytest.fail("No evadir rechazo")
    )
    with pytest.raises(CheckError, match="INCOMPLETE_PROPOSAL"):
        backup("Cambio", BASE, "")


def test_both_outputs_truncated_never_reach_validator(monkeypatch):
    monkeypatch.setattr(code_proposer, "request_json", lambda *_: groq_response("length"))
    monkeypatch.setattr(
        gemini_proposer,
        "request_json",
        lambda *_: {
            "modelVersion": gemini_proposer.DEFAULT_MODEL,
            "candidates": [{"finishReason": "MAX_TOKENS"}],
        },
    )
    provider = gemini_proposer.QuotaFallback(
        code_proposer.GroqProposer("primary-test"), gemini_proposer.GeminiProposer("backup-test")
    )
    result = run_request("Cambio", BASE, provider, lambda *_: pytest.fail("No aprobar parcial"))
    assert result.status == "failed"
    assert result.reason == "PROPOSAL_OUTPUT_LIMIT"
    assert result.candidate is None
    assert len(result.attempts) == 1
