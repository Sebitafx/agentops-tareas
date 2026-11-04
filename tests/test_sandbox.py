import json
import subprocess
from pathlib import Path

import pytest

from harness import sandbox
from harness.proposals import PolicyError

IMAGE = "agentops-validator:" + "a" * 40
BASE = {"taskapp/a.py": "a = 1\n", "tests/test_base.py": "assert True\n"}


def test_no_deletion_or_existing_test_changes_before_docker():
    with pytest.raises(PolicyError, match="FILE_DELETION"):
        sandbox.check_candidate({"taskapp/a.py": "a=2"}, BASE)
    with pytest.raises(PolicyError, match="PROTECTED_PATH"):
        sandbox.check_candidate({**BASE, "tests/test_base.py": "assert False"}, BASE)
    sandbox.check_candidate({**BASE, "taskapp/a.py": "a = 2\n"}, BASE)


def test_fixed_container_isolation_and_no_host_secret_forwarding(tmp_path):
    name = "agentops-validation-" + "b" * 32
    args = sandbox.container_command(IMAGE, tmp_path, name)
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args and "--pull=never" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--user") + 1] == "10001:10001"
    assert args[args.index("--security-opt") + 1] == "no-new-privileges"
    assert args[-1] == IMAGE and args[-2].endswith("target=/candidate,readonly")
    assert "--env" not in args and "docker.sock" not in " ".join(args)
    with pytest.raises(ValueError):
        sandbox.container_command("untrusted:latest", tmp_path, name)
    with pytest.raises(ValueError):
        sandbox.container_command(IMAGE, tmp_path, "--privileged")
    with pytest.raises(ValueError, match="INVALID_VALIDATION_SCENARIO"):
        sandbox.container_command(IMAGE, tmp_path, name, "GROQ_API_KEY=private")
    sample = sandbox.container_command(IMAGE, tmp_path, name, "button-label")
    assert sample[sample.index("--env") + 1] == "VALIDATION_SCENARIO=button-label"


def test_snapshot_loads_only_tracked_files_and_preserves_bytes(monkeypatch, tmp_path):
    (tmp_path / "taskapp").mkdir()
    (tmp_path / "taskapp/a.py").write_bytes(b"a = 1\r\n")
    (tmp_path / "private.env").write_text("not-for-agent", encoding="utf-8")
    monkeypatch.setattr(
        sandbox.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout=b"taskapp/a.py\x00"),
    )
    assert sandbox.load_snapshot(tmp_path) == {"taskapp/a.py": "a = 1\r\n"}
    (tmp_path / "taskapp/a.py").write_bytes(b"x" * 131073)
    with pytest.raises(PolicyError, match="SNAPSHOT_FILE_TOO_LARGE"):
        sandbox.load_snapshot(tmp_path)


def report(passed=True):
    return {
        "passed": passed,
        "boundaries": {"non_root": True, "readonly_root": True, "network_none": True},
        "stages": [
            {"name": name, "exit_code": 0, "diagnostics": "ok"}
            for name in ["initdb", "startdb", "createdb", "lint", "format", "types", "tests"]
        ],
    }


def fake_docker(monkeypatch, raw, code=0, running=False):
    calls = []

    class Process:
        returncode = code

        def __init__(self, command, **kwargs):
            calls.append(command)
            assert "GROQ_API_KEY" not in kwargs["env"]
            assert "AGENT_APP_PRIVATE_KEY" not in kwargs["env"]
            kwargs["stdout"].write(raw)
            kwargs["stdout"].flush()
            self.stopped = False

        def poll(self):
            return None if running and not self.stopped else self.returncode

        def terminate(self):
            self.stopped = True

        def wait(self, timeout):
            return self.returncode

    monkeypatch.setenv("GROQ_API_KEY", "fake-private-key")
    monkeypatch.setenv("AGENT_APP_PRIVATE_KEY", "fake-private-pem")
    monkeypatch.setattr(sandbox.subprocess, "Popen", Process)
    monkeypatch.setattr(sandbox.subprocess, "run", lambda command, **kwargs: calls.append(command))
    monkeypatch.setattr(sandbox, "load_snapshot", lambda _: dict(BASE))
    return calls


def test_validator_stages_readonly_copy_and_requires_complete_success(monkeypatch, tmp_path):
    calls = fake_docker(monkeypatch, json.dumps(report()).encode())
    validator = sandbox.DockerValidator(tmp_path, IMAGE)
    assert validator({**BASE, "taskapp/a.py": "a = 2\n"}).passed
    assert calls[-1][:3] == ["docker", "rm", "--force"]
    assert not list((tmp_path / "artifacts").glob("validation-*"))
    assert json.loads((tmp_path / "artifacts/latest-validation.json").read_text())["passed"]


@pytest.mark.parametrize(
    "variant",
    [
        "invalid_json",
        "failed",
        "no_network_boundary",
        "missing_stage",
        "failed_stage",
        "nonzero_exit",
    ],
)
def test_partial_or_invalid_report_never_approves(monkeypatch, tmp_path, variant):
    result = report()
    if variant == "failed":
        result["passed"] = False
    if variant == "no_network_boundary":
        result["boundaries"]["network_none"] = False
    if variant == "missing_stage":
        result["stages"].pop()
    if variant == "failed_stage":
        result["stages"][-1].update(exit_code=1, diagnostics="test failed")
    raw = b"not-json" if variant == "invalid_json" else json.dumps(result).encode()
    fake_docker(monkeypatch, raw, code=1 if variant == "nonzero_exit" else 0)
    assert not sandbox.DockerValidator(tmp_path, IMAGE)(BASE).passed


def test_timeout_stops_container_and_client(monkeypatch, tmp_path):
    calls = fake_docker(monkeypatch, b"", running=True)
    with pytest.raises(TimeoutError):
        sandbox.DockerValidator(tmp_path, IMAGE, timeout=0)(BASE)
    assert calls[-1][:3] == ["docker", "rm", "--force"]


def test_mount_injection_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="INVALID_MOUNT_PATH"):
        sandbox.container_command(
            IMAGE, Path(str(tmp_path) + ",target=/etc"), "agentops-validation-" + "b" * 32
        )
