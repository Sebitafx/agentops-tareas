from harness import evaluation_check
from harness.engine import Attempt, Outcome
from harness.proposals import Proposal
from harness.provider_http import CheckError


def test_evaluation_records_proposal_without_touching_checkout(monkeypatch, tmp_path):
    proposal = Proposal(action="clarify", summary="Pregunta", question="¿Cual?")

    class Validator:
        baseline = {"taskapp/schemas.py": "original"}

    monkeypatch.setattr(evaluation_check, "DockerValidator", lambda *_: Validator())
    monkeypatch.setattr(evaluation_check, "GroqProposer", lambda *_, **__: object())
    monkeypatch.setattr(
        evaluation_check,
        "run_request",
        lambda *_: Outcome("clarify", "NEEDS_INPUT", (Attempt(1, "clarify"),), proposal),
    )
    summary = evaluation_check.evaluate(tmp_path, "image", "key")
    assert summary["status"] == "clarify"
    assert not summary["checkout_modified"] and not summary["deployed"]
    assert not summary["isolated_validation_passed"]
    assert (tmp_path / "artifacts/synthetic-proposal.json").is_file()
    assert not (tmp_path / "taskapp").exists()


def test_evaluation_missing_key_does_not_run_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation_check, "DockerValidator", lambda *_: object())

    def unavailable(*_, **__):
        raise CheckError("MISSING_OR_INVALID_API_KEY")

    monkeypatch.setattr(evaluation_check, "GroqProposer", unavailable)
    assert (
        evaluation_check.evaluate(tmp_path, "image", "")["reason"] == "MISSING_OR_INVALID_API_KEY"
    )
