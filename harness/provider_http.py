"""Transporte JSON acotado para los proveedores revisados. Sin reintentos ni redirects."""

import json
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE_BYTES = 1048576
ALLOWED_HOSTS = frozenset({"generativelanguage.googleapis.com", "api.groq.com"})


class CheckError(Exception):
    def __init__(self, reason: str, http_status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url: str, headers: dict[str, str], payload: dict | None = None) -> dict:
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.netloc not in ALLOWED_HOSTS
        or parts.query
        or parts.fragment
    ):
        raise CheckError("ENDPOINT_NOT_ALLOWED")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={**headers, "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise CheckError("RESPONSE_TOO_LARGE")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise CheckError("INVALID_RESPONSE")
        return result
    except urllib.error.HTTPError as exc:
        reasons = {
            400: "INVALID_REQUEST",
            401: "AUTHENTICATION_FAILED",
            403: "PERMISSION_DENIED",
            404: "MODEL_UNAVAILABLE",
            429: "QUOTA_OR_RATE_LIMIT",
        }
        reason = reasons.get(exc.code, "PROVIDER_UNAVAILABLE" if exc.code >= 500 else "HTTP_ERROR")
        exc.close()
        raise CheckError(reason, exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CheckError("NETWORK_ERROR") from None
    except (ValueError, UnicodeError):
        raise CheckError("INVALID_RESPONSE") from None


def validate_key(key: str) -> None:
    if not key or not key.isascii() or any(character.isspace() for character in key):
        raise CheckError("MISSING_OR_INVALID_API_KEY")
