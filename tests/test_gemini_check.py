import io
import json
import urllib.error

import pytest

from harness import gemini_check as check
from harness import provider_http


def metadata():
    return {
        "name": "models/" + check.DEFAULT_MODEL,
        "supportedGenerationMethods": ["generateContent"],
    }


def generation():
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "OK"}]}}]}


def mock_api(monkeypatch, replies):
    calls = []

    def open_request(request, timeout):
        calls.append(request)
        reply = replies[len(calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply if isinstance(reply, bytes) else json.dumps(reply).encode())

    class Opener:
        open = staticmethod(open_request)

    monkeypatch.setattr(provider_http.urllib.request, "build_opener", lambda *args: Opener())
    return calls


def test_success_bounded_requests_and_no_private_data(monkeypatch):
    calls = mock_api(monkeypatch, [metadata(), generation()])
    result = check.run_check("private-key", check.DEFAULT_MODEL)
    assert result["generation_confirmed"] is True
    assert result["remaining_quota"] == "unknown"
    assert result["billing_verified"] is False
    assert len(calls) == 2
    assert calls[0].method == "GET"
    assert calls[1].method == "POST"
    assert calls[0].get_header("X-goog-api-key") == "private-key"
    assert "private-key" not in calls[0].full_url
    payload = json.loads(calls[1].data)
    assert payload["contents"][0]["parts"] == [{"text": "Reply with exactly OK."}]
    assert payload["generationConfig"]["maxOutputTokens"] == 1024
    assert "private-key" not in json.dumps(result)


@pytest.mark.parametrize(
    ("key", "model", "reason"),
    [
        ("", check.DEFAULT_MODEL, "MISSING_OR_INVALID_API_KEY"),
        ("bad key", check.DEFAULT_MODEL, "MISSING_OR_INVALID_API_KEY"),
        ("key", "../../other-host", "MODEL_NOT_ALLOWED"),
    ],
)
def test_invalid_config_never_calls_provider(monkeypatch, key, model, reason):
    calls = mock_api(monkeypatch, [])
    with pytest.raises(check.CheckError, match=reason):
        check.run_check(key, model)
    assert calls == []


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (400, "INVALID_REQUEST"),
        (401, "AUTHENTICATION_FAILED"),
        (403, "PERMISSION_DENIED"),
        (404, "MODEL_UNAVAILABLE"),
        (429, "QUOTA_OR_RATE_LIMIT"),
        (503, "PROVIDER_UNAVAILABLE"),
        (302, "HTTP_ERROR"),
    ],
)
def test_http_errors_sanitized_and_not_retried(monkeypatch, capsys, status, reason):
    error = urllib.error.HTTPError("https://private-key", status, "private-key", {}, io.BytesIO())
    calls = mock_api(monkeypatch, [error])
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    assert check.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == reason
    assert result["http_status"] == status
    assert "private-key" not in json.dumps(result)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "reply",
    [b"not-json", b"[]", b"\xff", b"x" * (provider_http.MAX_RESPONSE_BYTES + 1)],
    ids=["bad-json", "non-object", "invalid-encoding", "oversized"],
)
def test_invalid_responses_not_exposed(monkeypatch, reply):
    mock_api(monkeypatch, [reply])
    with pytest.raises(check.CheckError):
        check.run_check("key", check.DEFAULT_MODEL)


@pytest.mark.parametrize(
    "error", [urllib.error.URLError("private-key"), TimeoutError("private-key")]
)
def test_network_failure_sanitized(monkeypatch, error):
    calls = mock_api(monkeypatch, [error])
    with pytest.raises(check.CheckError, match="NETWORK_ERROR"):
        check.run_check("key", check.DEFAULT_MODEL)
    assert len(calls) == 1


@pytest.mark.parametrize("reply", [{}, {"name": "models/" + check.DEFAULT_MODEL}])
def test_metadata_checked_before_generation(monkeypatch, reply):
    calls = mock_api(monkeypatch, [reply])
    with pytest.raises(check.CheckError):
        check.run_check("key", check.DEFAULT_MODEL)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"candidates": "wrong"},
        {"candidates": [None]},
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "OK"}]}}]},
        {
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": "private-response"}]}}
            ]
        },
    ],
)
def test_generation_must_be_confirmed(monkeypatch, reply):
    mock_api(monkeypatch, [metadata(), reply])
    with pytest.raises(check.CheckError):
        check.run_check("key", check.DEFAULT_MODEL)


def test_main_safe_output(monkeypatch, capsys):
    mock_api(monkeypatch, [metadata(), generation()])
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    assert check.main() == 0
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "ok"
    assert "private-key" not in output
    assert "Reply with exactly" not in output


def test_redirects_do_not_forward_key():
    assert (
        provider_http.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other-host")
        is None
    )
