"""Valida tokens de la App mediante consultas GET, sin cambios en el repositorio."""

import argparse
import json
import os
import subprocess

REPOSITORY = "Sebitafx/agentops-tareas"
APP_SLUG = "agentops-tareas-sebitafx"


class ScopeError(Exception):
    pass


def github_get(path: str):
    # GH_TOKEN viene exclusivamente del token efimero creado por la accion oficial.
    if not os.getenv("GH_TOKEN"):
        raise ScopeError("MISSING_APP_TOKEN")
    try:
        result = subprocess.run(
            ["gh", "api", path, "--method", "GET", "-H", "Accept: application/vnd.github+json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ScopeError("GITHUB_CONNECTION_ERROR") from None
    if result.returncode:
        # stderr de gh puede contener detalles privados. No imprimirlo.
        raise ScopeError("GITHUB_API_REJECTED")
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise ScopeError("INVALID_GITHUB_RESPONSE") from None


def validate_scope(data) -> dict:
    if not isinstance(data, dict) or type(data.get("total_count")) is not int:
        raise ScopeError("INVALID_INSTALLATION_RESPONSE")
    repos = data.get("repositories")
    if data["total_count"] != 1 or not isinstance(repos, list) or len(repos) != 1:
        raise ScopeError("INSTALLATION_MUST_HAVE_EXACTLY_ONE_REPOSITORY")
    repo = repos[0]
    if (
        not isinstance(repo, dict)
        or str(repo.get("full_name", "")).casefold() != REPOSITORY.casefold()
    ):
        raise ScopeError("UNEXPECTED_REPOSITORY")
    return {"status": "ok", "installation_repository_count": 1, "repository": REPOSITORY}


def check_repository() -> dict:
    base = f"/repos/{REPOSITORY}"
    metadata = github_get(base)
    if (
        not isinstance(metadata, dict)
        or metadata.get("full_name", "").casefold() != REPOSITORY.casefold()
    ):
        raise ScopeError("UNEXPECTED_REPOSITORY")
    ref = github_get(base + "/git/ref/heads/main")
    if not isinstance(ref, dict) or ref.get("ref") != "refs/heads/main":
        raise ScopeError("MAIN_REF_NOT_ACCESSIBLE")
    pulls = github_get(base + "/pulls?state=open&per_page=1")
    if not isinstance(pulls, list):
        raise ScopeError("PULL_REQUESTS_NOT_ACCESSIBLE")
    workflows = github_get(base + "/actions/workflows?per_page=1")
    if not isinstance(workflows, dict) or not isinstance(workflows.get("workflows"), list):
        raise ScopeError("ACTIONS_NOT_ACCESSIBLE")
    return {
        "status": "ok",
        "repository": REPOSITORY,
        "contents_read": True,
        "pull_requests_read": True,
        "actions_read": True,
        "write_operations_tested": False,
    }


def check_main_protection() -> dict:
    from harness.integrate import IntegrationError, check_protection

    try:
        check_protection(github_get(f"/repos/{REPOSITORY}/branches/main/protection"))
    except IntegrationError as exc:
        raise ScopeError(str(exc)) from None
    return {"status": "ok", "main_protection_verified": True, "administration_read": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["installation", "repository", "protection"])
    args = parser.parse_args()
    try:
        if os.getenv("AGENT_APP_SLUG") != APP_SLUG:
            raise ScopeError("UNEXPECTED_APP")
        if args.mode == "installation":
            summary = validate_scope(github_get("/installation/repositories?per_page=100"))
        elif args.mode == "repository":
            summary = check_repository()
        else:
            summary = check_main_protection()
    except ScopeError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
