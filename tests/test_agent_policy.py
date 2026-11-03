import pytest
from pydantic import ValidationError

from harness.engine import Validation, run_request
from harness.proposals import (
    PolicyError,
    Proposal,
    apply_to_snapshot,
    check_proposal,
    digest,
)
from harness.provider_http import CheckError

BASE = {"taskapp/sample.py": "value = 1\n", "tests/test_original.py": "assert True\n"}


def change(path="taskapp/sample.py", content="value = 2\n", sha=None):
    return Proposal.model_validate(
        {
            "action": "change",
            "summary": "Ajustar valor ficticio",
            "files": [{"path": path, "base_sha256": sha, "content": content}],
        }
    )


def valid_change():
    return change(sha=digest(BASE["taskapp/sample.py"]))


@pytest.mark.parametrize(
    "path",
    [
        "../taskapp/sample.py",
        "/taskapp/sample.py",
        "taskapp/../harness/engine.py",
        "taskapp//sample.py",
        "taskapp/./sample.py",
        "taskapp/.hidden.py",
        ".",
        "C:/taskapp/sample.py",
        "taskapp\\sample.py",
        "taskapp/sample.py:stream",
        "taskapp/%2e%2e/code.py",
        "taskapp/code.py\n",
        "taskapp/ñ.py",
    ],
)
def test_noncanonical_paths_rejected(path):
    with pytest.raises(PolicyError, match="INVALID_PATH"):
        check_proposal(change(path), BASE)


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        "requirements.txt",
        "pyproject.toml",
        "bootstrap/migrations/001_inbox.sql",
        "harness/engine.py",
        "Dockerfile",
        "docs/convenciones-python.md",
        "tests/test_original.py",
        "tests/conftest.py",
        "tests/agent_added/conftest.py",
        "tests/agent_added/test_x/config.py",
        "taskapp/settings.env",
        "taskapp/blob.bin",
        "tests/agent_added/__init__.py",
    ],
)
def test_protected_files_rejected(path):
    with pytest.raises(PolicyError):
        check_proposal(change(path), BASE)


def test_cannot_overwrite_even_an_existing_agent_test():
    path = "tests/agent_added/test_prior.py"
    base = {**BASE, path: "assert True\n"}
    with pytest.raises(PolicyError, match="PROTECTED_PATH"):
        check_proposal(change(path, sha=digest(base[path])), base)


def test_existing_file_requires_exact_base_and_new_file_requires_null():
    for proposal in [change(), change(sha="0" * 64), change("taskapp/new.py", sha="0" * 64)]:
        with pytest.raises(PolicyError, match="STALE_BASE"):
            check_proposal(proposal, BASE)


def test_snapshot_is_independent_and_preserves_protected_files():
    proposal = valid_change()
    proposal.files.extend(change("tests/agent_added/test_behavior.py", "assert 1 == 1\n").files)
    candidate = apply_to_snapshot(proposal, BASE)
    assert BASE["taskapp/sample.py"] == "value = 1\n"
    assert candidate["taskapp/sample.py"] == "value = 2\n"
    assert candidate["tests/test_original.py"] == BASE["tests/test_original.py"]
    assert "tests/agent_added/test_behavior.py" in candidate


@pytest.mark.parametrize("content, reason", [("\x00", "BINARY_CONTENT"), ("  \n", "EMPTY_FILE")])
def test_empty_or_binary_files_rejected(content, reason):
    with pytest.raises(PolicyError, match=reason):
        check_proposal(change(content=content, sha=digest(BASE["taskapp/sample.py"])), BASE)


def test_duplicate_and_large_changes_rejected():
    proposal = valid_change()
    proposal.files *= 2
    with pytest.raises(PolicyError, match="DUPLICATE_PATH"):
        check_proposal(proposal, BASE)
    proposal = change("taskapp/a.py", "a" * 32768)
    proposal.files.extend(change("taskapp/b.py", "b" * 32768).files)
    proposal.files.extend(change("taskapp/c.py", "c").files)
    with pytest.raises(PolicyError, match="CHANGE_TOO_LARGE"):
        check_proposal(proposal, BASE)


def test_unchanged_files_are_not_a_correction():
    with pytest.raises(PolicyError, match="NO_CHANGE"):
        check_proposal(
            change(content=BASE["taskapp/sample.py"], sha=digest(BASE["taskapp/sample.py"])), BASE
        )


@pytest.mark.parametrize(
    "data",
    [
        {"action": "change", "summary": "x"},
        {"action": "clarify", "summary": "x"},
        {"action": "clarify", "summary": "x", "question": " "},
        {"action": "refuse", "summary": "x", "command": "rm"},
        {"action": "execute", "summary": "x"},
        {"action": "change", "summary": "x", "files": [{"path": "taskapp/x.py", "content": "x"}]},
    ],
)
def test_closed_protocol(data):
    with pytest.raises(ValidationError):
        Proposal.model_validate(data)


def test_bad_policy_never_reaches_validator_and_stops_at_three_attempts():
    calls = []

    def proposer(request, base, feedback):
        calls.append(feedback)
        base.clear()
        return change("harness/engine.py")

    def validator(candidate):
        pytest.fail("La propuesta prohibida no debe ejecutarse")

    result = run_request("Peticion ficticia", BASE, proposer, validator)
    assert result.status == "failed" and result.reason == "ATTEMPTS_EXHAUSTED"
    assert calls == ["", "PROTECTED_PATH", "PROTECTED_PATH"]
    assert len(result.attempts) == 3 and result.candidate is None
    assert BASE["taskapp/sample.py"] == "value = 1\n"


def test_validation_failure_is_repaired_from_same_base():
    contexts = []

    def propose(request, base, feedback):
        contexts.append((base, feedback))
        return valid_change()

    def validate(candidate):
        assert candidate["taskapp/sample.py"] == "value = 2\n"
        candidate.clear()
        return Validation(len(contexts) == 2, "prueba de comportamiento fallida")

    result = run_request("Peticion ficticia", BASE, propose, validate)
    assert result.status == "validated" and len(result.attempts) == 2
    assert contexts[0] == (BASE, "")
    assert contexts[1] == (BASE, "prueba de comportamiento fallida")
    assert result.candidate["taskapp/sample.py"] == "value = 2\n"


@pytest.mark.parametrize("action", ["clarify", "refuse"])
def test_clarification_and_refusal_stop_without_execution(action):
    proposal = Proposal(
        action=action,
        summary="Requiere aclaracion",
        question="¿Que filtro?" if action == "clarify" else None,
    )
    result = run_request(
        "Peticion ficticia", BASE, lambda *_: proposal, lambda _: pytest.fail("No ejecutar")
    )
    assert result.status == ("clarify" if action == "clarify" else "refused")
    assert result.proposal == proposal and len(result.attempts) == 1


def test_quota_stops_immediately_without_fallback():
    def propose(*_):
        raise CheckError("QUOTA_OR_RATE_LIMIT", 429)

    result = run_request("Peticion ficticia", BASE, propose, lambda _: pytest.fail("No ejecutar"))
    assert result.reason == "QUOTA_OR_RATE_LIMIT" and len(result.attempts) == 1


def test_invalid_json_is_bounded_and_validator_outage_never_passes():
    def propose(*_):
        raise ValueError("JSON invalido")

    result = run_request("Peticion ficticia", BASE, propose, lambda _: pytest.fail("No ejecutar"))
    assert result.reason == "ATTEMPTS_EXHAUSTED" and len(result.attempts) == 3

    def validate(_):
        raise TimeoutError()

    result = run_request("Peticion ficticia", BASE, lambda *_: valid_change(), validate)
    assert result.reason == "VALIDATOR_UNAVAILABLE" and result.status == "failed"


def test_failed_validations_cannot_publish_candidate():
    result = run_request(
        "Peticion ficticia",
        BASE,
        lambda *_: valid_change(),
        lambda _: Validation(False, "x" * 10000),
    )
    assert result.status == "failed" and result.candidate is None


@pytest.mark.parametrize("task_request", ["", " ", "x" * 3001])
def test_invalid_request_never_calls_provider(task_request):
    result = run_request(
        task_request,
        BASE,
        lambda *_: pytest.fail("No llamar IA"),
        lambda _: pytest.fail("No validar"),
    )
    assert result.reason == "INVALID_REQUEST" and not result.attempts
