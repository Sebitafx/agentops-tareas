"""Generacion y validacion aislada sinteticas; no cambia el checkout ni crea PR."""

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from harness.code_proposer import GroqProposer
from harness.engine import run_request
from harness.provider_http import CheckError
from harness.sandbox import DockerValidator

REQUEST = (
    "En la demo, limita el titulo a 180 caracteres tanto al crear como al editar. "
    "El limite actual es 200. Conserva el resto. Agrega una prueba nueva que "
    "acepte 180 caracteres y rechace 181 en ambos modelos Pydantic."
)


def evaluate(root: Path, image: str, key: str) -> dict:
    validator = DockerValidator(root, image)
    try:
        proposer = GroqProposer(key, visible_paths=frozenset({"taskapp/schemas.py"}))
        outcome = run_request(REQUEST, validator.baseline, proposer, validator)
    except CheckError as exc:
        return {"status": "failed", "reason": exc.reason, "attempts": []}
    summary = {
        "status": outcome.status,
        "reason": outcome.reason,
        "attempts": [asdict(attempt) for attempt in outcome.attempts],
        "isolated_validation_passed": outcome.status == "validated",
        "checkout_modified": False,
        "pr_created": False,
        "deployed": False,
    }
    if outcome.proposal:
        artifacts = root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "synthetic-proposal.json").write_text(
            outcome.proposal.model_dump_json(indent=2), encoding="utf-8"
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    summary = evaluate(root, args.image, os.getenv("GROQ_API_KEY", ""))
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "evaluation-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))
    return 0 if summary["status"] == "validated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
