"""Una propuesta sintetica real. Se guarda como artefacto; no se aplica ni ejecuta."""

import json
import os
from pathlib import Path

from pydantic import ValidationError

from harness.code_proposer import GroqProposer
from harness.proposals import PolicyError, check_proposal
from harness.provider_http import CheckError


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    name = "taskapp/schemas.py"
    base = {name: (root / name).read_text(encoding="utf-8")}
    try:
        proposer = GroqProposer(os.getenv("GROQ_API_KEY", ""))
        proposal = proposer(
            "En la demo, limita el titulo a 180 caracteres tanto al crear como al editar. "
            "El limite actual es 200. Conserva el resto. Agrega una prueba nueva que "
            "acepte 180 caracteres y rechace 181 en ambos modelos Pydantic.",
            base,
            "",
        )
        if proposal.action != "change":
            raise CheckError("NO_CODE_PROPOSED")
        check_proposal(proposal, base)
    except (CheckError, PolicyError, ValidationError) as exc:
        reason = (
            exc.reason
            if isinstance(exc, CheckError)
            else str(exc)
            if isinstance(exc, PolicyError)
            else "INVALID_PROPOSAL"
        )
        print(json.dumps({"status": "failed", "reason": reason}))
        return 1
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "synthetic-proposal.json").write_text(
        proposal.model_dump_json(indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "proposed",
                "scope_checked": True,
                "files": [change.path for change in proposal.files],
                "code_executed": False,
                "tests_executed": False,
                "checkout_modified": False,
                "pr_created": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
