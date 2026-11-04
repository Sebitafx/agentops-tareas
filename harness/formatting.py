"""Ruff determinista sobre stdin. Analiza texto; no importa ni ejecuta la aplicacion."""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from harness.proposals import Proposal, check_proposal
from harness.provider_http import CheckError


def normalize_proposal(root: Path, proposal: Proposal, base: Mapping[str, str]) -> Proposal:
    check_proposal(proposal, base)
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
            "HOME",
            "USERPROFILE",
        }
    }
    files = []
    for change in proposal.files:
        content = change.content
        if change.path.endswith(".py"):
            config = str(root / "pyproject.toml")
            commands = [
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--config",
                    config,
                    "--select",
                    "I",
                    "--fix",
                    "--stdin-filename",
                    change.path,
                    "-",
                ],
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "format",
                    "--config",
                    config,
                    "--stdin-filename",
                    change.path,
                    "-",
                ],
            ]
            for command in commands:
                try:
                    result = subprocess.run(
                        command,
                        input=content.encode("utf-8"),
                        capture_output=True,
                        env=env,
                        cwd=root,
                        timeout=10,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    raise CheckError("FORMATTER_UNAVAILABLE") from None
                if result.returncode != 0:
                    # Un error sintactico se entrega al validador para que informe al
                    # modelo. No se oculta ni se transforma en una aprobacion.
                    break
                content = result.stdout.decode("utf-8")
        files.append(change.model_copy(update={"content": content}))
    normalized = proposal.model_copy(update={"files": files})
    check_proposal(normalized, base)
    return normalized
