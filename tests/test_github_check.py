import json
import subprocess

import pytest

from harness import github_check as check


def test_exact_repository_scope():
    result = check.validate_scope(
        {"total_count": 1, "repositories": [{"full_name": check.REPOSITORY}]}
    )
    assert result["installation_repository_count"] == 1


@pytest.mark.parametrize(
    "data",
    [
        [],
        {},
        {"total_count": True},
        {"total_count": 0, "repositories": []},
        {"total_count": 2, "repositories": [{"full_name": check.REPOSITORY}]},
        {"total_count": 1, "repositories": [{"full_name": "private/repo"}]},
        {"total_count": 1, "repositories": [None]},
    ],
)
def test_scope_fails_closed(data):
    with pytest.raises(check.ScopeError) as error:
        check.validate_scope(data)
    assert "private/repo" not in str(error.value)


def test_reads_are_authenticated_and_never_mutate(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "private-token")

    def run(args, **kwargs):
        assert args[:3] == ["gh", "api", "/installation/repositories"]
        assert args[3:5] == ["--method", "GET"]
        assert "private-token" not in " ".join(args)
        assert kwargs["timeout"] == 30
        return subprocess.CompletedProcess(args, 0, stdout='{"total_count": 1}')

    monkeypatch.setattr(check.subprocess, "run", run)
    assert check.github_get("/installation/repositories")["total_count"] == 1


def test_no_fallback_to_personal_credentials(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def fail(*args, **kwargs):
        pytest.fail("No debe llamar a gh sin token explicito")

    monkeypatch.setattr(check.subprocess, "run", fail)
    with pytest.raises(check.ScopeError, match="MISSING_APP_TOKEN"):
        check.github_get("/installation/repositories")


@pytest.mark.parametrize(
    "failure",
    [
        OSError("private-token"),
        subprocess.TimeoutExpired("private-token", 30),
    ],
)
def test_connection_errors_redacted(monkeypatch, failure):
    monkeypatch.setenv("GH_TOKEN", "private-token")

    def run(*args, **kwargs):
        raise failure

    monkeypatch.setattr(check.subprocess, "run", run)
    with pytest.raises(check.ScopeError, match="GITHUB_CONNECTION_ERROR") as error:
        check.github_get("/installation/repositories")
    assert "private-token" not in str(error.value)


@pytest.mark.parametrize(
    ("code", "stdout", "reason"),
    [
        (1, "", "GITHUB_API_REJECTED"),
        (0, "private-invalid-json", "INVALID_GITHUB_RESPONSE"),
    ],
)
def test_invalid_github_response_redacted(monkeypatch, code, stdout, reason):
    monkeypatch.setenv("GH_TOKEN", "private-token")
    monkeypatch.setattr(
        check.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, code, stdout=stdout, stderr="private-token"
        ),
    )
    with pytest.raises(check.ScopeError, match=reason):
        check.github_get("/installation/repositories")


def responses():
    return [
        {"full_name": check.REPOSITORY},
        {"ref": "refs/heads/main"},
        [],
        {"workflows": []},
    ]


def test_repository_reads_without_write_claim(monkeypatch):
    replies = iter(responses())
    calls = []

    def get(path):
        calls.append(path)
        return next(replies)

    monkeypatch.setattr(check, "github_get", get)
    summary = check.check_repository()
    assert len(calls) == 4
    assert summary["actions_read"] is True
    assert summary["write_operations_tested"] is False


@pytest.mark.parametrize(("index", "value"), [(0, {}), (1, {}), (2, {}), (3, {})])
def test_repository_checks_fail_closed(monkeypatch, index, value):
    replies = responses()
    replies[index] = value
    iterator = iter(replies)
    monkeypatch.setattr(check, "github_get", lambda _: next(iterator))
    with pytest.raises(check.ScopeError):
        check.check_repository()


def test_main_rejects_wrong_app(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check", "installation"])
    monkeypatch.setenv("AGENT_APP_SLUG", "wrong-app")
    assert check.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "UNEXPECTED_APP"


@pytest.mark.parametrize("mode", ["installation", "repository"])
def test_main_returns_safe_summary(monkeypatch, capsys, mode):
    monkeypatch.setattr("sys.argv", ["check", mode])
    monkeypatch.setenv("AGENT_APP_SLUG", check.APP_SLUG)
    if mode == "installation":
        reply = {"total_count": 1, "repositories": [{"full_name": check.REPOSITORY}]}
        monkeypatch.setattr(check, "github_get", lambda _: reply)
    else:
        monkeypatch.setattr(check, "check_repository", lambda: {"status": "ok"})
    assert check.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_protection_preflight_uses_actual_branch_settings(monkeypatch):
    from tests.test_delivery_pipeline import protection

    calls = []
    monkeypatch.setattr(check, "github_get", lambda path: calls.append(path) or protection())
    assert check.check_main_protection()["main_protection_verified"] is True
    assert calls == [f"/repos/{check.REPOSITORY}/branches/main/protection"]
    monkeypatch.setattr(check, "github_get", lambda _: {})
    with pytest.raises(check.ScopeError, match="MAIN_PROTECTION_REQUIRED"):
        check.check_main_protection()
