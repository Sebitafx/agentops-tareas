import io
import json
import time
import urllib.error

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from bootstrap import github_app
from bootstrap.github_app import AppSettings, GitHubError, github_json, installation_token


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def pem(key, fmt=serialization.PrivateFormat.PKCS8):
    return key.private_bytes(serialization.Encoding.PEM, fmt, serialization.NoEncryption()).decode()


def test_jwt_signature_expiry_and_normalized_control_secret(rsa_key):
    settings = AppSettings(app_id="123", private_key=pem(rsa_key))
    payload = jwt.decode(settings.jwt(), rsa_key.public_key(), algorithms=["RS256"])
    assert payload["iss"] == "123" and payload["iat"] < time.time() < payload["exp"]
    assert payload["exp"] - payload["iat"] <= 600
    alternate = AppSettings(
        app_id="123",
        private_key=pem(rsa_key, serialization.PrivateFormat.TraditionalOpenSSL).replace(
            "\n", "\r\n"
        ),
    )
    assert alternate.control_token() == settings.control_token()
    assert len(settings.control_token()) == 64
    assert "BEGIN" not in repr(settings)
    assert settings.control_token() not in settings.jwt()


@pytest.mark.parametrize("value", ["", "invalid", "x" * 16385, "ñ"])
def test_bad_private_key_never_leaks_raw_input(value):
    settings = AppSettings(app_id="123", private_key=value)
    with pytest.raises(GitHubError, match="INVALID_APP_PRIVATE_KEY"):
        settings.rsa_key()


def test_only_named_app_and_repository_can_issue_token(monkeypatch, rsa_key):
    calls = []

    def api(method, path, token, payload=None):
        calls.append((method, path, payload))
        if path == "/app":
            return {"slug": github_app.APP_SLUG}
        if path.endswith("/installation"):
            return {"id": 42}
        if path.endswith("/access_tokens"):
            assert payload["repositories"] == ["agentops-tareas"]
            assert payload["permissions"] == {"actions": "write"}
            return {"token": "temporary-test-token"}
        assert path == "/installation/token" and token == "temporary-test-token"
        return {}

    monkeypatch.setattr(github_app, "github_json", api)
    with installation_token(
        AppSettings(app_id="123", private_key=pem(rsa_key)), {"actions": "write"}
    ) as token:
        assert token == "temporary-test-token"
    assert calls[-1][:2] == ("DELETE", "/installation/token")


def test_wrong_app_does_not_request_installation_token(monkeypatch, rsa_key):
    calls = []

    def api(*args):
        calls.append(args)
        return {"slug": "another-app"}

    monkeypatch.setattr(github_app, "github_json", api)
    with (
        pytest.raises(GitHubError, match="UNEXPECTED_GITHUB_APP"),
        installation_token(AppSettings(app_id="123", private_key=pem(rsa_key)), {}),
    ):
        pytest.fail("No emitir token de otra app")
    assert len(calls) == 1


def test_revoke_failure_does_not_repeat_completed_operation(monkeypatch, rsa_key, caplog):
    def api(method, path, *_):
        if path == "/app":
            return {"slug": github_app.APP_SLUG}
        if path.endswith("/installation"):
            return {"id": 42}
        if path.endswith("/access_tokens"):
            return {"token": "temporary-test-token"}
        raise GitHubError("GITHUB_NETWORK_ERROR")

    monkeypatch.setattr(github_app, "github_json", api)
    with installation_token(AppSettings(app_id="123", private_key=pem(rsa_key)), {}):
        pass
    assert "revoke_failed" in caplog.text and "temporary-test-token" not in caplog.text


@pytest.mark.parametrize(
    "path", ["https://evil.invalid", "//evil.invalid", "/../app", "/app#fragment"]
)
def test_github_destination_is_fixed(path):
    with pytest.raises(GitHubError, match="PATH_NOT_ALLOWED"):
        github_json("GET", path, "test-token")


def test_transport_limits_and_safe_errors(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://api.github.com/app"
            assert timeout == 15 and request.get_header("Authorization") == "Bearer test-token"
            return Response(b'{"slug":"demo"}')

    monkeypatch.setattr(github_app.urllib.request, "build_opener", lambda *_: Opener())
    assert github_json("GET", "/app", "test-token") == {"slug": "demo"}

    class FailingOpener:
        def open(self, *_args, **_kwargs):
            raise urllib.error.HTTPError(
                "https://api.github.com",
                401,
                "private-secret",
                {},
                io.BytesIO(json.dumps({"private": "secret"}).encode()),
            )

    monkeypatch.setattr(github_app.urllib.request, "build_opener", lambda *_: FailingOpener())
    with pytest.raises(GitHubError, match="GITHUB_HTTP_401") as exc:
        github_json("GET", "/app", "test-token")
    assert "secret" not in str(exc.value)
