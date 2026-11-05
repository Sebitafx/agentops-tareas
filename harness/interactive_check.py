"""Ensayo real sin PR ni despliegues. Usa el mismo generador y validador de Actions."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from harness.engine import run_request
from harness.formatting import normalize_proposal
from harness.interactive_proposer import InteractiveProposer
from harness.sandbox import DockerValidator

REQUEST = (
    "Reemplaza el selector de tema por un switch tipo palanquita con iconos SVG sol/luna. "
    "Conserva #theme-toggle visible y pulsable. Corrige el contraste de texto en campos "
    "y tarjetas en modo oscuro. Conserva CRUD, filtros y persistencia. Añade pruebas de navegador."
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    validator = DockerValidator(root, args.image)
    proposer = InteractiveProposer(lambda _: False, lambda _: None, preferred="groq", locked=True)
    outcome = run_request(
        REQUEST,
        validator.baseline,
        proposer,
        validator,
        lambda p, b: normalize_proposal(root, p, b),
    )
    result = {
        "status": outcome.status,
        "reason": outcome.reason,
        "attempts": [asdict(a) for a in outcome.attempts],
        "provider": proposer.session.selected,
        "pr_created": False,
        "deployed": False,
    }
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "interactive-summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    if outcome.proposal:
        (artifacts / "interactive-proposal.json").write_text(
            outcome.proposal.model_dump_json(indent=2), encoding="utf-8"
        )
    print(json.dumps(result), flush=True)
    return 0 if outcome.status == "validated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
