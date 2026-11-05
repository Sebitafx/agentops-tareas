"""Generacion y validacion aislada sinteticas; no cambia el checkout ni crea PR."""

import argparse
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from harness.code_proposer import GroqProposer
from harness.engine import run_request
from harness.formatting import normalize_proposal
from harness.gemini_proposer import GeminiProposer
from harness.provider_http import CheckError
from harness.sandbox import DockerValidator

REQUEST = (
    "En la demo, limita el titulo a 180 caracteres tanto al crear como al editar. "
    "El limite actual es 200. Conserva el resto. Agrega una prueba nueva que "
    "acepte 180 caracteres y rechace 181 en ambos modelos Pydantic."
)
SCENARIOS = {
    "task-theme": (
        "Agrega un boton despues de la marca en la cabecera para alternar toda la interfaz "
        "entre modo oscuro y claro. Texto inicial Modo oscuro; activado debe decir Modo claro. "
        "Elige las clases y una paleta oscura legible. Conserva la seleccion al recargar, "
        "el CRUD y los filtros. Agrega prueba de navegador. Sin nuevas dependencias ni migraciones.",
        frozenset(
            {"taskapp/static/index.html", "taskapp/static/app.js", "taskapp/static/style.css"}
        ),
    ),
    "title-limit": (REQUEST, frozenset({"taskapp/schemas.py"})),
    "button-label": (
        'Cambia el texto del boton de crear de "Crear tarea" a "Agregar tarea". '
        "Debe conservar ese texto despues de guardar. Conserva Guardar cambios al editar.",
        frozenset({"taskapp/static/index.html", "taskapp/static/app.js"}),
    ),
    "task-search": (
        "Agrega un buscador local de tareas por titulo, ignorando mayusculas. "
        'Usa un input id="task-search" con label "Buscar tareas". '
        "Filtra mientras se escribe y al vaciar muestra todas las tareas del filtro actual. "
        "Sin dependencias nuevas, sin cambiar API ni esquema. Conserva el CRUD.",
        frozenset({"taskapp/static/index.html", "taskapp/static/app.js"}),
    ),
    "ambiguous": (
        "Cambia un boton.",
        frozenset({"taskapp/static/index.html", "taskapp/static/app.js"}),
    ),
}


def evaluate(
    root: Path, image: str, key: str, scenario: str = "title-limit", provider: str = "groq"
) -> dict:
    request, paths = SCENARIOS[scenario]
    try:
        if provider not in {"groq", "gemini"}:
            raise CheckError("PROVIDER_NOT_ALLOWED")
        proposer = (GeminiProposer if provider == "gemini" else GroqProposer)(
            key, visible_paths=paths
        )
        validator = DockerValidator(root, image)
        validator.scenario = "" if scenario == "ambiguous" else scenario
        outcome = run_request(
            request,
            validator.baseline,
            proposer,
            validator,
            lambda proposal, base: normalize_proposal(root, proposal, base),
        )
    except CheckError as exc:
        return {"status": "failed", "reason": exc.reason, "attempts": []}
    summary = {
        "scenario": scenario,
        "provider": provider,
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
    parser.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="title-limit")
    parser.add_argument("--provider", choices=["groq", "gemini"], default="groq")
    args = parser.parse_args()
    root = Path.cwd()
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    summaries = []
    for scenario in SCENARIOS if args.scenario == "all" else [args.scenario]:
        for name in ("synthetic-proposal.json", "latest-validation.json"):
            (artifacts / name).unlink(missing_ok=True)
        key_name = "GEMINI_API_KEY" if args.provider == "gemini" else "GROQ_API_KEY"
        summary = evaluate(root, args.image, os.getenv(key_name, ""), scenario, args.provider)
        summaries.append(summary)
        target = artifacts / "evaluations" / scenario
        target.mkdir(parents=True, exist_ok=True)
        for name in ("synthetic-proposal.json", "latest-validation.json"):
            if (artifacts / name).exists():
                shutil.copyfile(artifacts / name, target / name)
        (target / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary), flush=True)
    summary = {"scenarios": summaries}
    (artifacts / "evaluation-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return (
        0
        if all(
            item["status"] == ("clarify" if item.get("scenario") == "ambiguous" else "validated")
            for item in summaries
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
