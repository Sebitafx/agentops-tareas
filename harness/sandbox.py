"""Solo ejecuta el validador predefinido en Docker; no acepta comandos del modelo."""

import argparse
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from harness.engine import Validation
from harness.proposals import (
    FileChange,
    PolicyError,
    Proposal,
    canonical_path,
    check_proposal,
    digest,
)


def load_snapshot(root: Path) -> dict[str, str]:
    root = root.resolve()
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z", "--", "taskapp", "tests"],
            cwd=root,
            capture_output=True,
            check=True,
            timeout=10,
        )
        .stdout.decode("utf-8")
        .split("\x00")
    )
    result = {}
    for name in filter(None, tracked):
        canonical_path(name)
        path = root / name
        if not stat.S_ISREG(path.lstat().st_mode) or not path.resolve().is_relative_to(root):
            raise PolicyError("SYMLINK_NOT_ALLOWED")
        if path.suffix not in {".py", ".html", ".css", ".js"}:
            raise PolicyError("UNSUPPORTED_SNAPSHOT_FILE")
        data = path.read_bytes()
        if len(data) > 131072:
            raise PolicyError("SNAPSHOT_FILE_TOO_LARGE")
        result[name] = data.decode("utf-8")
    return result


def check_candidate(candidate: dict[str, str], baseline: dict[str, str]) -> None:
    if not baseline.keys() <= candidate.keys():
        raise PolicyError("FILE_DELETION_NOT_ALLOWED")
    changes = [
        FileChange(
            path=name,
            base_sha256=digest(baseline[name]) if name in baseline else None,
            content=content,
        )
        for name, content in candidate.items()
        if baseline.get(name) != content
    ]
    if changes:
        check_proposal(
            Proposal(action="change", summary="Validar candidato", files=changes), baseline
        )


def container_command(image: str, folder: Path, name: str, scenario: str = "") -> list[str]:
    if not re.fullmatch(r"agentops-validator:[a-f0-9]{40}", image):
        raise ValueError("INVALID_VALIDATOR_IMAGE")
    if not re.fullmatch(r"agentops-validation-[a-f0-9]{32}", name):
        raise ValueError("INVALID_CONTAINER_NAME")
    if "," in str(folder):
        raise ValueError("INVALID_MOUNT_PATH")
    if scenario not in {"", "title-limit", "button-label", "task-search"}:
        raise ValueError("INVALID_VALIDATION_SCENARIO")
    return [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "10001:10001",
        "--pids-limit",
        "256",
        "--memory",
        "1536m",
        "--cpus",
        "2",
        "--shm-size",
        "128m",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=768m,mode=1777",
        *(["--env", "VALIDATION_SCENARIO=" + scenario] if scenario else []),
        "--mount",
        f"type=bind,source={folder.resolve()},target=/candidate,readonly",
        image,
    ]


class DockerValidator:
    def __init__(self, root: Path, image: str, timeout: int = 240, scenario: str = "") -> None:
        self.root = root.resolve()
        self.baseline = load_snapshot(self.root)
        self.image = image
        self.timeout = timeout
        self.scenario = scenario
        self.last_report: dict = {}

    def __call__(self, candidate: dict[str, str]) -> Validation:
        check_candidate(candidate, self.baseline)
        artifacts = self.root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="validation-", dir=artifacts) as temp:
            stage = Path(temp) / "candidate"
            stage.mkdir()
            for name, content in candidate.items():
                canonical_path(name)
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content.encode("utf-8"))
            name = "agentops-validation-" + uuid4().hex
            command = container_command(self.image, stage, name, self.scenario)
            # El cliente Docker tampoco necesita las claves del proceso coordinador.
            env = {
                key: value
                for key, value in os.environ.items()
                if key.upper()
                in {
                    "PATH",
                    "SYSTEMROOT",
                    "WINDIR",
                    "TEMP",
                    "TMP",
                    "USERPROFILE",
                    "HOME",
                    "DOCKER_HOST",
                    "DOCKER_CONTEXT",
                    "DOCKER_CONFIG",
                    "DOCKER_TLS_VERIFY",
                    "DOCKER_CERT_PATH",
                }
            }
            output_path = Path(temp) / "result.log"
            process = None
            deadline = time.monotonic() + self.timeout
            try:
                with output_path.open("wb") as output:
                    process = subprocess.Popen(
                        command, env=env, stdout=output, stderr=subprocess.STDOUT
                    )
                    while process.poll() is None:
                        if time.monotonic() > deadline or output_path.stat().st_size > 1048576:
                            raise TimeoutError("VALIDATOR_LIMIT_REACHED")
                        time.sleep(0.1)
                text = output_path.read_bytes().decode("utf-8", errors="replace")
                try:
                    report = json.loads(text)
                except ValueError:
                    return Validation(False, "VALIDATOR_INVALID_REPORT")
                required = {"initdb", "startdb", "createdb", "lint", "format", "types", "tests"}
                stages = report.get("stages", [])
                passed = (
                    process.returncode == 0
                    and report.get("passed") is True
                    and report.get("boundaries")
                    == {"non_root": True, "readonly_root": True, "network_none": True}
                    and {stage.get("name") for stage in stages} == required
                    and all(stage.get("exit_code") == 0 for stage in stages)
                )
                self.last_report = report
                (artifacts / "latest-validation.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                feedback = "\n".join(
                    stage.get("name", "") + ": " + stage.get("diagnostics", "")
                    for stage in stages
                    if stage.get("exit_code")
                )
                return Validation(
                    passed,
                    "VALIDATION_PASSED" if passed else feedback[-4000:] or "VALIDATION_FAILED",
                )
            finally:
                subprocess.run(
                    ["docker", "rm", "--force", name],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    validator = DockerValidator(Path.cwd(), args.image)
    result = validator(dict(validator.baseline))
    print(json.dumps({"passed": result.passed, "feedback": result.feedback}))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
