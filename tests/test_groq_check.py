import json
import urllib.error

import pytest

from harness import groq_check as check
from harness import provider_http
from tests.test_gemini_check import mock_api


def catalog():
    return {"data": [{"id": check.DEFAULT_MODEL, "active": True}]}


def generation():
    return {
        "model": check.DEFAULT_MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "OK"},
            }
        ],
    }


def test_groq_success_no_secret_or_private_input(monkeypatch, capsys):
    calls = mock_api(monkeypatch, [catalog(), generation()])
    monkeypatch.setenv("GROQ_API_KEY", "private-groq-key")
    assert check.main() == 0
    output = capsys.readouterr().out
    assert json.loads(output)["provider"] == "groq"
    assert json.loads(output)["generation_confirmed"] is True
    assert json.loads(output)["billing_verified"] is False
    assert "private-groq-key" not in output
    assert len(calls) == 2
    assert calls[0].get_header("Authorization") == "Bearer private-groq-key"
    assert calls[0].get_header("User-agent") == provider_http.USER_AGENT
    assert calls[1].get_header("User-agent") == provider_http.USER_AGENT
    assert calls[0].full_url == "https://api.groq.com/openai/v1/models"
    assert calls[1].full_url == "https://api.groq.com/openai/v1/chat/completions"
    payload = json.loads(calls[1].data)
    assert payload["messages"] == [{"role": "user", "content": "Reply with exactly OK."}]
    assert payload["max_completion_tokens"] == 1024
    assert "tools" not in payload


@pytest.mark.parametrize(
    ("key", "model"),
    [
        ("", check.DEFAULT_MODEL),
        ("bad key", check.DEFAULT_MODEL),
        ("key", "model-not-reviewed"),
    ],
)
def test_groq_invalid_configuration_never_calls_provider(monkeypatch, key, model):
    calls = mock_api(monkeypatch, [])
    with pytest.raises(check.CheckError):
        check.run_check(key, model)
    assert calls == []


@pytest.mark.parametrize(
    "reply",
    [{}, {"data": []}, {"data": [None]}, {"data": [{"id": check.DEFAULT_MODEL, "active": False}]}],
)
def test_groq_catalog_checked_before_generation(monkeypatch, reply):
    calls = mock_api(monkeypatch, [reply])
    with pytest.raises(check.CheckError):
        check.run_check("key", check.DEFAULT_MODEL)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "choices",
    [
        [],
        [None],
        [{"message": None}],
        [{"finish_reason": "length", "message": {"content": "OK"}}],
        [{"finish_reason": "stop", "message": {"content": "private-response"}}],
        [{"finish_reason": "stop", "message": {"content": "OK", "tool_calls": [{"id": "x"}]}}],
    ],
)
def test_groq_requires_final_confirmation(monkeypatch, choices):
    mock_api(monkeypatch, [catalog(), {"model": check.DEFAULT_MODEL, "choices": choices}])
    with pytest.raises(check.CheckError):
        check.run_check("key", check.DEFAULT_MODEL)


def test_groq_no_silent_model_change(monkeypatch):
    reply = generation()
    reply["model"] = "other-model"
    mock_api(monkeypatch, [catalog(), reply])
    with pytest.raises(check.CheckError, match="UNEXPECTED_GENERATION_MODEL"):
        check.run_check("key", check.DEFAULT_MODEL)


def test_groq_rate_limit_stops_without_fallback(monkeypatch, capsys):
    mock_api(monkeypatch, [urllib.error.HTTPError("", 429, "private-groq-key", {}, None)])
    monkeypatch.setenv("GROQ_API_KEY", "private-groq-key")
    assert check.main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["reason"] == "QUOTA_OR_RATE_LIMIT"
    assert "private-groq-key" not in output


@pytest.mark.parametrize(
    "url",
    [
        "http://api.groq.com/openai/v1/models",
        "https://other-host/models",
        "https://api.groq.com@other-host/models",
        "https://api.groq.com/models?secret=key",
        "https://api.groq.com/models#fragment",
    ],
)
def test_transport_rejects_unreviewed_destinations(monkeypatch, url):
    calls = mock_api(monkeypatch, [])
    with pytest.raises(check.CheckError, match="ENDPOINT_NOT_ALLOWED"):
        provider_http.request_json(url, {"Authorization": "Bearer secret"})
    assert calls == []
