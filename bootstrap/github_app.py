"""GitHub App dedicada al repo; sin credenciales personales ni secretos en URL/logs."""

import hashlib
import hmac
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from pydantic import BaseModel, Field, SecretStr

REPOSITORY = "Sebitafx/agentops-tareas"
APP_SLUG = "agentops-tareas-sebitafx"
logger = logging.getLogger("uvicorn.error.agentops")


class GitHubError(Exception):
    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class AppSettings(BaseModel):
    app_id: str = Field(pattern=r"^[0-9]+$")
    private_key: SecretStr

    @classmethod
    def from_environment(cls) -> "AppSettings":
        settings = cls(
            app_id=os.environ["AGENT_APP_ID"], private_key=os.environ["AGENT_APP_PRIVATE_KEY"]
        )
        settings.rsa_key()
        return settings

    def rsa_key(self) -> RSAPrivateKey:
        try:
            raw = self.private_key.get_secret_value().encode("ascii")
            if len(raw) > 16384:
                raise ValueError()
            key = serialization.load_pem_private_key(raw, password=None)
            if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
                raise ValueError()
            return key
        except (ValueError, TypeError, UnicodeError, UnsupportedAlgorithm):
            raise GitHubError("INVALID_APP_PRIVATE_KEY") from None

    def jwt(self) -> str:
        now = int(time.time())
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self.app_id},
            self.rsa_key(),
            algorithm="RS256",
        )

    def control_token(self) -> str:
        # Clave de control separada por dominio, derivada del mismo PEM privado ya
        # configurado en Render y Actions. No requiere otro secreto que copiar.
        private = self.rsa_key().private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return hmac.new(private, b"AgentOps-Tareas/control-api/v1", hashlib.sha256).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github_json(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
        raise GitHubError("METHOD_NOT_ALLOWED")
    if (
        not path.startswith("/")
        or path.startswith("//")
        or ".." in path
        or not re.fullmatch(r"/[A-Za-z0-9_./?=&-]+", path)
    ):
        raise GitHubError("PATH_NOT_ALLOWED")
    request = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "AgentOps-Tareas/0.1",
        },
        method=method,
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise GitHubError("RESPONSE_TOO_LARGE")
        result = json.loads(raw) if raw else {}
        if not isinstance(result, dict):
            raise GitHubError("INVALID_GITHUB_RESPONSE")
        return result
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise GitHubError("GITHUB_HTTP_" + str(status), status) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GitHubError("GITHUB_NETWORK_ERROR") from None
    except (ValueError, UnicodeError):
        raise GitHubError("INVALID_GITHUB_RESPONSE") from None


@contextmanager
def installation_token(settings: AppSettings, permissions: dict[str, str]):
    app_jwt = settings.jwt()
    app = github_json("GET", "/app", app_jwt)
    if app.get("slug") != APP_SLUG:
        raise GitHubError("UNEXPECTED_GITHUB_APP")
    installation = github_json("GET", f"/repos/{REPOSITORY}/installation", app_jwt)
    installation_id = installation.get("id")
    if type(installation_id) is not int or installation_id <= 0:
        raise GitHubError("INVALID_INSTALLATION")
    result = github_json(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        app_jwt,
        {
            "repositories": ["agentops-tareas"],
            "permissions": permissions,
        },
    )
    token = result.get("token")
    if (
        not isinstance(token, str)
        or not token
        or not token.isascii()
        or any(c.isspace() for c in token)
    ):
        raise GitHubError("INVALID_INSTALLATION_TOKEN")
    try:
        yield token
    finally:
        # El token tambien caduca en GitHub. Un fallo al revocarlo no debe repetir
        # un dispatch o una escritura que ya pudieron haberse completado.
        try:
            github_json("DELETE", "/installation/token", token)
        except GitHubError as exc:
            logger.warning("github_app_token result=revoke_failed reason=%s", exc.reason)
