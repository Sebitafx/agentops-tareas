"""Publica una propuesta validada como PR; nunca actualiza main ni integra cambios."""

import re
from collections.abc import Callable
from uuid import UUID

from bootstrap.github_app import REPOSITORY, GitHubError
from harness.engine import Outcome
from harness.proposals import check_proposal


def publish_pr(
    outcome: Outcome,
    baseline: dict[str, str],
    base_sha: str,
    request_id: UUID,
    run_id: str,
    api: Callable,
) -> dict:
    # El coordinador confiable debe entregar el resultado del validador real.
    if outcome.status != "validated" or outcome.proposal is None or outcome.candidate is None:
        raise GitHubError("UNVALIDATED_PROPOSAL")
    if (
        not isinstance(request_id, UUID)
        or not re.fullmatch(r"[a-f0-9]{40}", base_sha)
        or not re.fullmatch(r"[0-9]{1,24}", run_id)
    ):
        raise GitHubError("INVALID_PUBLICATION_REFERENCE")
    proposal = outcome.proposal
    check_proposal(proposal, baseline)
    expected = {**baseline, **{change.path: change.content for change in proposal.files}}
    if dict(outcome.candidate) != expected:
        raise GitHubError("VALIDATED_CONTENT_CHANGED")
    root = "/repos/" + REPOSITORY

    def require_current_base():
        ref = api("GET", root + "/git/ref/heads/main")
        if ref.get("object", {}).get("sha") != base_sha:
            raise GitHubError("MAIN_CHANGED_REVALIDATION_REQUIRED")

    require_current_base()
    parent = api("GET", root + "/git/commits/" + base_sha)
    tree_sha = parent.get("tree", {}).get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", tree_sha):
        raise GitHubError("INVALID_BASE_TREE")
    entries = []
    for change in proposal.files:
        blob = api("POST", root + "/git/blobs", {"content": change.content, "encoding": "utf-8"})
        sha = blob.get("sha", "")
        if not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise GitHubError("INVALID_CREATED_BLOB")
        entries.append({"path": change.path, "mode": "100644", "type": "blob", "sha": sha})
    tree = api("POST", root + "/git/trees", {"base_tree": tree_sha, "tree": entries})
    sha = tree.get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise GitHubError("INVALID_CREATED_TREE")
    commit = api(
        "POST",
        root + "/git/commits",
        {
            "message": f"AgentOps: propuesta validada {request_id}",
            "tree": sha,
            "parents": [base_sha],
        },
    )
    head = commit.get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", head):
        raise GitHubError("INVALID_CREATED_COMMIT")
    require_current_base()
    branch = "agentops/requests/" + str(request_id)
    # Solo crea una referencia nueva. Si existe, falla; nunca la sobreescribe.
    api("POST", root + "/git/refs", {"ref": "refs/heads/" + branch, "sha": head})
    run_url = f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"
    pull = api(
        "POST",
        root + "/pulls",
        {
            "title": f"AgentOps: propuesta validada {str(request_id)[:8]}",
            "head": branch,
            "base": "main",
            "body": (
                "Cambio generado y validado en contenedor aislado.\n\n"
                f"Solicitud: `{request_id}`\nBase validada: `{base_sha}`\n"
                f"Validación: {run_url}\n\n"
                "La creación de este PR no confirma integración ni despliegue. "
                "Los controles del PR deben aprobar el contenido y su base actuales."
            ),
        },
    )
    number = pull.get("number")
    if type(number) is not int or number < 1:
        raise GitHubError("INVALID_CREATED_PULL_REQUEST")
    return {
        "number": number,
        "url": f"https://github.com/{REPOSITORY}/pull/{number}",
        "head_sha": head,
        "base_sha": base_sha,
        "branch": branch,
        "run_url": run_url,
    }
