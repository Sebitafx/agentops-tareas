"""Integracion serializada con proteccion estricta y contenido/base comprobados."""

import re
import time

from bootstrap.github_app import APP_SLUG, REPOSITORY


class IntegrationError(Exception):
    pass


def check_protection(data: dict) -> None:
    checks = data.get("required_status_checks") or {}
    contexts = set(checks.get("contexts", [])) | {
        item.get("context") for item in checks.get("checks", [])
    }
    reviews = data.get("required_pull_request_reviews")
    if (
        checks.get("strict") is not True
        or "bootstrap-quality" not in contexts
        or not isinstance(reviews, dict)
        or data.get("enforce_admins", {}).get("enabled") is not True
        or data.get("allow_force_pushes", {}).get("enabled") is True
        or data.get("allow_deletions", {}).get("enabled") is True
    ):
        raise IntegrationError("MAIN_PROTECTION_REQUIRED")
    allowances = reviews.get("bypass_pull_request_allowances", {})
    if (
        reviews.get("required_approving_review_count", 0) > 0
        or reviews.get("require_code_owner_reviews")
        or reviews.get("require_last_push_approval")
    ):
        raise IntegrationError("HUMAN_REVIEW_REQUIRED_BY_MAIN")
    if any(item.get("slug") == APP_SLUG for item in allowances.get("apps", [])):
        raise IntegrationError("BOT_MUST_NOT_BYPASS_PROTECTION")


def integrate_pr(
    publication: dict, api, timeout: int = 600, sleep=time.sleep, now=time.monotonic
) -> str:
    root = "/repos/" + REPOSITORY
    number, head, base = publication["number"], publication["head_sha"], publication["base_sha"]
    if (
        type(number) is not int
        or number < 1
        or not all(re.fullmatch(r"[a-f0-9]{40}", sha) for sha in (head, base))
    ):
        raise IntegrationError("INVALID_PUBLICATION")
    check_protection(api("GET", root + "/branches/main/protection"))
    deadline = now() + timeout

    def current():
        pr = api("GET", root + f"/pulls/{number}")
        if pr.get("state") != "open" or pr.get("draft") or pr.get("head", {}).get("sha") != head:
            raise IntegrationError("PR_CHANGED_REVALIDATION_REQUIRED")
        if (
            pr.get("base", {}).get("ref") != "main"
            or pr.get("base", {}).get("repo", {}).get("full_name") != REPOSITORY
        ):
            raise IntegrationError("UNEXPECTED_PR_TARGET")
        if pr.get("head", {}).get("repo", {}).get("full_name") != REPOSITORY:
            raise IntegrationError("FORK_NOT_ALLOWED")
        if api("GET", root + "/git/ref/heads/main").get("object", {}).get("sha") != base:
            raise IntegrationError("MAIN_CHANGED_REVALIDATION_REQUIRED")

    while True:
        current()
        data = api("GET", root + f"/actions/runs?head_sha={head}&event=push&per_page=30")
        runs = [
            run
            for run in data.get("workflow_runs", [])
            if run.get("name") == "Bootstrap CI" and run.get("head_sha") == head
        ]
        if runs:
            latest = max(runs, key=lambda item: item.get("id", 0))
            if latest.get("status") == "completed":
                if latest.get("conclusion") != "success":
                    raise IntegrationError("PR_CHECKS_FAILED")
                break
        if now() >= deadline:
            raise IntegrationError("PR_CHECKS_TIMEOUT")
        sleep(15)
    check_protection(api("GET", root + "/branches/main/protection"))
    current()
    result = api("PUT", root + f"/pulls/{number}/merge", {"sha": head, "merge_method": "merge"})
    sha = result.get("sha", "")
    if result.get("merged") is not True or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise IntegrationError("MERGE_NOT_CONFIRMED")
    # La integracion es un merge de dos padres: debe preservar exactamente el
    # arbol del head validado y los padres base/head que acabamos de comprobar.
    merged = api("GET", root + "/git/commits/" + sha)
    expected = api("GET", root + "/git/commits/" + head)
    parents = [item.get("sha") for item in merged.get("parents", [])]
    tree = merged.get("tree", {}).get("sha", "")
    if (
        parents != [base, head]
        or not re.fullmatch(r"[a-f0-9]{40}", tree)
        or tree != expected.get("tree", {}).get("sha")
    ):
        raise IntegrationError("MERGED_CONTENT_NOT_VALIDATED")
    return sha
