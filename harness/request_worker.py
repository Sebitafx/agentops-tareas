"""Controlador confiable de una solicitud: consulta, IA, Docker, PR y callback."""

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

from bootstrap.github_app import AppSettings, GitHubError, github_json, installation_token
from harness.code_proposer import GroqProposer
from harness.deploy import APP, DeploymentError, deploy_commit, hook_for_commit
from harness.engine import run_request
from harness.formatting import normalize_proposal
from harness.gemini_proposer import with_gemini_fallback
from harness.integrate import IntegrationError, integrate_pr
from harness.provider_http import CheckError
from harness.publish import publish_pr
from harness.sandbox import DockerValidator

RECEIVER = "https://agentops-receiver.onrender.com"


class ControlError(Exception):
    def __init__(self, status):
        super().__init__("CONTROL_HTTP_" + str(status))
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def control(settings: AppSettings, job_id: UUID, action: str, body: dict) -> dict:
    if action not in {"claim", "progress"} or not isinstance(job_id, UUID):
        raise ControlError(400)
    request = urllib.request.Request(
        f"{RECEIVER}/internal/jobs/{job_id}/{action}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + settings.control_token(),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ControlError(502)
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ControlError(502)
        return result
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise ControlError(code) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise ControlError(503) from None


def visible_files(request: str, baseline: dict[str, str]) -> frozenset[str]:
    text = request.casefold()
    explicit = [path for path in baseline if path.startswith("taskapp/") and path in request]
    if explicit:
        return frozenset(explicit)
    if any(word in text for word in ("modo oscuro", "modo claro", "dark mode", "tema oscuro")):
        return frozenset(
            {"taskapp/static/index.html", "taskapp/static/app.js", "taskapp/static/style.css"}
        )
    if any(word in text for word in ("color", "estilo", "css")):
        return frozenset({"taskapp/static/style.css", "taskapp/static/index.html"})
    # Un texto visible citado identifica archivos aunque el usuario no diga "texto".
    literals = re.findall(r"""["“”']([^"“”'\n]{3,200})["“”']""", request)
    matched = {
        path
        for path, content in baseline.items()
        if path.startswith("taskapp/static/")
        and path.endswith((".html", ".js"))
        and any(literal.casefold() in content.casefold() for literal in literals)
    }
    if matched:
        return frozenset({"taskapp/static/index.html", "taskapp/static/app.js"})
    if any(
        word in text
        for word in (
            "botón",
            "encabezado",
            "cabecera",
            "heading",
            "boton",
            "interfaz",
            "color",
            "pantalla",
            "texto",
            "estilo",
            "button",
            "css",
            "html",
        )
    ):
        # El indice permite citar otros archivos; evita exceder el presupuesto del modelo.
        if any(word in text for word in ("color", "estilo", "css")):
            return frozenset({"taskapp/static/style.css", "taskapp/static/index.html"})
        return frozenset({"taskapp/static/index.html", "taskapp/static/app.js"})
    return frozenset(
        path for path in baseline if path.startswith("taskapp/") and path.endswith(".py")
    )


def execute(job_id: UUID, image: str, run_id: str) -> int:
    settings = AppSettings.from_environment()
    try:
        claimed = control(settings, job_id, "claim", {"run_id": run_id})
    except ControlError as exc:
        if exc.status == 409:
            print(json.dumps({"status": "already_claimed", "job_id": str(job_id)}))
            return 0
        raise
    lease = str(UUID(claimed["lease"]))

    def progress(state, summary):
        control(settings, job_id, "progress", {"lease": lease, "state": state, "summary": summary})

    try:
        root = Path.cwd()
        validator = DockerValidator(root, image)
        request = claimed["request"]
        proposer = GroqProposer(
            os.getenv("GROQ_API_KEY", ""), visible_paths=visible_files(request, validator.baseline)
        )
        proposer = with_gemini_fallback(proposer, visible_files(request, validator.baseline))
        outcome = run_request(
            request,
            validator.baseline,
            proposer,
            validator,
            lambda proposal, base: normalize_proposal(root, proposal, base),
        )
        # Solo etiquetas del controlador, nunca propuesta, prompt ni diagnostico crudo.
        print(
            json.dumps(
                {
                    "status": outcome.status,
                    "reason": outcome.reason,
                    "attempts": [
                        {"number": item.number, "result": item.result} for item in outcome.attempts
                    ],
                }
            ),
            flush=True,
        )
        if outcome.status == "clarify":
            progress("needs_input", outcome.proposal.question)
            return 0
        if outcome.status != "validated":
            progress(
                "failed",
                "No pude aprobar el cambio. Motivo: "
                + outcome.reason
                + ". No he integrado ni desplegado cambios.\n"
                + "Intentos: "
                + (
                    ", ".join(f"{item.number}: {item.result}" for item in outcome.attempts)
                    or "sin propuesta"
                )
                + f"\nEjecución: https://github.com/Sebitafx/agentops-tareas/actions/runs/{run_id}",
            )
            return 1
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip()
        with installation_token(settings, {"contents": "write", "pull_requests": "write"}) as token:

            def api(method, path, payload=None):
                return github_json(method, path, token, payload)

            result = publish_pr(outcome, validator.baseline, base_sha, job_id, run_id, api)
        progress(
            "pr_open",
            f"Cambio validado y PR creado: {result['url']}\nPruebas: {result['run_url']}\nComprobaré los controles y la protección antes de integrar.",
        )
        if os.getenv("RENDER_TASKS_DEPLOY_HOOK"):
            hook_for_commit(os.environ["RENDER_TASKS_DEPLOY_HOOK"], base_sha)
            with installation_token(
                settings,
                {
                    "contents": "write",
                    "pull_requests": "write",
                    "actions": "read",
                    "administration": "read",
                },
            ) as token:

                def merge_api(method, path, payload=None):
                    return github_json(method, path, token, payload)

                merged_sha = integrate_pr(result, merge_api)
            progress(
                "merged",
                f"PR integrado: {result['url']}\nCommit validado: {merged_sha}\nEl despliegue aún no está confirmado.",
            )
            progress("deploying", f"Desplegando el commit {merged_sha}. Aún no se anuncia éxito.")
            deployment = deploy_commit(os.environ["RENDER_TASKS_DEPLOY_HOOK"], merged_sha)
            if not deployment.succeeded:
                progress(
                    "failed",
                    f"PR: {result['url']}\nFalló la comprobación del despliegue: {deployment.reason}. Restauración del código anterior: {deployment.rollback}. No se revierten datos.",
                )
                return 1
            progress(
                "succeeded",
                f"Cambio publicado ✅\nPR: {result['url']}\nPruebas: {result['run_url']}\nWeb: {APP}\nVersión confirmada: {merged_sha}",
            )
        print(
            json.dumps(
                {
                    "status": "succeeded" if os.getenv("RENDER_TASKS_DEPLOY_HOOK") else "pr_open",
                    "job_id": str(job_id),
                    "pr": result["url"],
                }
            )
        )
        return 0
    except (
        GitHubError,
        CheckError,
        IntegrationError,
        DeploymentError,
        OSError,
        TimeoutError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        reason = (
            exc.reason
            if isinstance(exc, (GitHubError, CheckError))
            else str(exc)
            if isinstance(exc, (IntegrationError, DeploymentError))
            else type(exc).__name__
        )
        progress(
            "failed",
            "La ejecución se detuvo. Motivo: "
            + reason
            + ". No se confirma integración ni despliegue.",
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True, type=UUID)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    try:
        return execute(args.job_id, args.image, os.environ["GITHUB_RUN_ID"])
    except (ControlError, GitHubError, KeyError, ValueError) as exc:
        print(json.dumps({"status": "failed", "reason": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
