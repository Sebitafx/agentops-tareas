"""Validador de imagen de referencia: PostgreSQL, controles y Chromium sin red externa."""

import json
import os
import resource
import subprocess
import sys
from pathlib import Path

REFERENCE = Path("/opt/reference")
CANDIDATE = Path("/candidate")
SCRATCH = Path("/tmp/agentops-validation")


def boundaries() -> dict[str, bool]:
    return {
        "non_root": os.getuid() != 0,
        "readonly_root": bool(os.statvfs("/").f_flag & os.ST_RDONLY),
        "network_none": {p.name for p in Path("/sys/class/net").iterdir()} == {"lo"},
    }


def verify_reference() -> None:
    # Las pruebas de referencia vienen de la imagen confiable y son inmutables.
    # No se permiten symlinks ni reemplazar tests/configuracion con el candidato.
    for path in CANDIDATE.rglob("*"):
        if path.is_symlink():
            raise ValueError("SYMLINK_NOT_ALLOWED")
    for original in (REFERENCE / "tests").rglob("*.py"):
        relative = original.relative_to(REFERENCE)
        staged = CANDIDATE / relative
        if not staged.is_file() or staged.read_bytes() != original.read_bytes():
            raise ValueError("REFERENCE_TEST_CHANGED")
    for staged in (CANDIDATE / "tests").rglob("*"):
        if staged.is_file() and not (REFERENCE / staged.relative_to(CANDIDATE)).exists():
            if (
                staged.name == "conftest.py"
                or not staged.name.startswith("test_")
                or staged.suffix != ".py"
            ):
                raise ValueError("INVALID_ADDED_TEST")


def command(name: str, argv: list[str], env: dict[str, str], timeout: int = 120) -> dict:
    log = SCRATCH / (name + ".log")
    try:
        with log.open("wb") as output:
            process = subprocess.run(
                argv,
                env=env,
                cwd=SCRATCH,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        code = process.returncode
    except subprocess.TimeoutExpired:
        code = 124
    # Nunca devolver salida ilimitada al modelo o al proceso coordinador.
    diagnostics = log.read_bytes()[-6000:].decode("utf-8", errors="replace")
    return {"name": name, "exit_code": code, "diagnostics": diagnostics}


def main() -> int:
    report = {"passed": False, "boundaries": boundaries(), "stages": []}
    if not all(report["boundaries"].values()):
        report["reason"] = "ISOLATION_REQUIRED"
        print(json.dumps(report))
        return 1
    try:
        verify_reference()
    except (OSError, ValueError):
        report["reason"] = "INVALID_CANDIDATE_REFERENCE"
        print(json.dumps(report))
        return 1
    SCRATCH.mkdir()
    pg_bin = next(Path("/usr/lib/postgresql").glob("*/bin"))
    pg_data = SCRATCH / "pgdata"
    pg_socket = SCRATCH / "pgsocket"
    pg_socket.mkdir(mode=0o700)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CANDIDATE) + ":" + str(REFERENCE)
    env["MYPYPATH"] = env["PYTHONPATH"]
    env["E2E_ENABLED"] = "1"
    env["RUFF_CACHE_DIR"] = str(SCRATCH / "ruff")
    env["TEST_DATABASE_URL"] = "postgresql://agentops_test@/agentops_test?host=" + str(pg_socket)
    # No se acepta inyectar secretos en el entorno del contenedor.
    if any(
        key.startswith(
            ("GH_", "GITHUB_", "GROQ_", "GEMINI_", "META_", "WHATSAPP_", "AGENT_APP_", "RENDER_")
        )
        for key in env
    ):
        report["reason"] = "SECRETS_ENV_NOT_ALLOWED"
        print(json.dumps(report))
        return 1
    started = False
    try:
        setup = [
            (
                "initdb",
                [
                    str(pg_bin / "initdb"),
                    "-D",
                    str(pg_data),
                    "-A",
                    "trust",
                    "-U",
                    "agentops_test",
                    "--encoding=UTF8",
                    "--locale=C",
                ],
            ),
            (
                "startdb",
                [
                    str(pg_bin / "pg_ctl"),
                    "-D",
                    str(pg_data),
                    "-l",
                    str(SCRATCH / "postgres.log"),
                    "-o",
                    f"-k {pg_socket} -h '' -F",
                    "-w",
                    "start",
                ],
            ),
            (
                "createdb",
                [
                    str(pg_bin / "createdb"),
                    "-h",
                    str(pg_socket),
                    "-U",
                    "agentops_test",
                    "agentops_test",
                ],
            ),
        ]
        for name, argv in setup:
            stage = command(name, argv, env, timeout=30)
            report["stages"].append(stage)
            if stage["exit_code"]:
                report["reason"] = "TEST_DATABASE_SETUP_FAILED"
                return 1
            if name == "startdb":
                started = True
        # Los hijos de prueba no pueden generar logs infinitos en /tmp.
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
        config = str(REFERENCE / "pyproject.toml")
        checks = [
            (
                "lint",
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--config",
                    config,
                    str(CANDIDATE / "taskapp"),
                    str(CANDIDATE / "tests"),
                ],
            ),
            (
                "format",
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "format",
                    "--check",
                    "--config",
                    config,
                    str(CANDIDATE / "taskapp"),
                    str(CANDIDATE / "tests"),
                ],
            ),
            (
                "types",
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    "--config-file",
                    config,
                    "--cache-dir",
                    str(SCRATCH / "mypy"),
                    str(CANDIDATE / "taskapp"),
                ],
            ),
            (
                "tests",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-c",
                    config,
                    "-o",
                    f"pythonpath={CANDIDATE} {REFERENCE}",
                    "-p",
                    "no:cacheprovider",
                    str(CANDIDATE / "tests"),
                    "--cov=bootstrap",
                    "--cov=harness",
                    "--cov=taskapp",
                    "--cov-branch",
                    "--cov-fail-under=80",
                    "--tb=short",
                ],
            ),
        ]
        for name, argv in checks:
            stage = command(name, argv, env)
            report["stages"].append(stage)
            if stage["exit_code"]:
                report["reason"] = "VALIDATION_FAILED"
                return 1
        report["passed"] = True
        report["reason"] = "VALIDATION_PASSED"
        return 0
    except (OSError, StopIteration, ValueError):
        report["reason"] = "VALIDATOR_RUNTIME_ERROR"
        return 1
    finally:
        if started:
            subprocess.run(
                [str(pg_bin / "pg_ctl"), "-D", str(pg_data), "-m", "immediate", "stop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        print(json.dumps(report))


if __name__ == "__main__":
    raise SystemExit(main())
