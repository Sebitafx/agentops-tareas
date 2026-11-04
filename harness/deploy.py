"""Despliegue por SHA con hook limitado, salud/version y restauracion de codigo."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

APP = "https://agentops-tasks.onrender.com"


class DeploymentError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url: str, method: str = "GET"):
    request = urllib.request.Request(
        url, method=method, headers={"User-Agent": "AgentOps-Tareas/0.1"}
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise DeploymentError("DEPLOY_RESPONSE_TOO_LARGE")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise DeploymentError("DEPLOY_NETWORK_OR_RESPONSE_ERROR") from None
    except (urllib.error.URLError, OSError, ValueError):
        # Nunca incluir la URL del hook en excepciones, registros o respuestas.
        raise DeploymentError("DEPLOY_NETWORK_OR_RESPONSE_ERROR") from None


def hook_for_commit(hook: str, sha: str) -> str:
    try:
        if len(hook) > 2048:
            raise ValueError()
        parts = urllib.parse.urlsplit(hook)
        values = urllib.parse.parse_qs(parts.query, strict_parsing=True)
    except ValueError:
        raise DeploymentError("INVALID_DEPLOY_HOOK_OR_COMMIT") from None
    if (
        parts.scheme != "https"
        or parts.netloc != "api.render.com"
        or not re.fullmatch(r"/deploy/srv-[a-z0-9]+", parts.path)
        or set(values) != {"key"}
        or len(values["key"]) != 1
        or not values["key"][0]
        or parts.fragment
        or not re.fullmatch(r"[a-f0-9]{40}", sha)
    ):
        raise DeploymentError("INVALID_DEPLOY_HOOK_OR_COMMIT")
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urllib.parse.urlencode({"key": values["key"][0], "ref": sha}),
            "",
        )
    )


def confirm(sha: str, read=request_json, timeout=480, sleep=time.sleep, now=time.monotonic) -> None:
    deadline = now() + timeout
    while True:
        try:
            if read(APP + "/version").get("commit") == sha:
                health, ready = read(APP + "/health"), read(APP + "/ready")
                tasks = read(APP + "/api/tasks?status=pending")
                if (
                    health.get("status") == "ok"
                    and ready.get("database") == "ok"
                    and isinstance(tasks, list)
                ):
                    return
        except (DeploymentError, AttributeError, TypeError):
            pass
        if now() >= deadline:
            raise DeploymentError("DEPLOY_HEALTH_OR_VERSION_NOT_CONFIRMED")
        sleep(15)


@dataclass(frozen=True)
class DeploymentResult:
    succeeded: bool
    commit: str
    previous_commit: str
    rollback: str
    reason: str


def deploy_commit(
    hook: str, sha: str, read=request_json, sleep=time.sleep, now=time.monotonic, timeout=480
) -> DeploymentResult:
    target = hook_for_commit(hook, sha)
    previous = read(APP + "/version").get("commit", "")
    if not re.fullmatch(r"[a-f0-9]{40}", previous):
        raise DeploymentError("PREVIOUS_VERSION_UNKNOWN")
    try:
        result = read(target, "POST")
        # Render 202 puede poner el despliegue en cola sin devolver un id.
        # Solo la comprobacion posterior de SHA y salud permite anunciar exito.
        if not isinstance(result, dict):
            raise DeploymentError("DEPLOY_NOT_ACCEPTED")
        confirm(sha, read, timeout, sleep, now)
        return DeploymentResult(True, sha, previous, "not_needed", "DEPLOY_CONFIRMED")
    except DeploymentError as exc:
        reason = str(exc)
        rollback = "failed"
        try:
            read(hook_for_commit(hook, previous), "POST")
            confirm(previous, read, timeout, sleep, now)
            rollback = "confirmed"
        except DeploymentError:
            pass
        return DeploymentResult(False, sha, previous, rollback, reason)
