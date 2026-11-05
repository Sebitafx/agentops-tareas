import io
import json
import urllib.error

import pytest

from harness import gemini_proposer as gemini
from harness import provider_http as transport
from harness.provider_http import CheckError

THEME_FILES = frozenset(
    {"taskapp/static/index.html", "taskapp/static/app.js", "taskapp/static/style.css"}
)


def test_full_theme_context_selects_gemini_without_calling_groq(monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "backup-test-only")
    captured = []

    def gemini_factory(key, paths):
        captured.append((key, paths))
        return lambda *_: "complete-backup-proposal"

    monkeypatch.setattr(gemini, "GeminiProposer", gemini_factory)
    provider = gemini.with_gemini_fallback(lambda *_: pytest.fail("No llamar Groq"), THEME_FILES)
    assert provider("Tema", {}, "") == "complete-backup-proposal"
    assert captured == [("backup-test-only", THEME_FILES)]
    event = json.loads(capsys.readouterr().out)
    assert event["reason"] == "MULTIFILE_UI_CONTEXT"
    assert "backup-test-only" not in json.dumps(event)


def test_small_context_still_prefers_groq(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "backup-test-only")
    monkeypatch.setattr(gemini, "GeminiProposer", lambda *_: lambda *_: pytest.fail("No backup"))
    provider = gemini.with_gemini_fallback(lambda *_: "primary", frozenset({"taskapp/a.py"}))
    assert provider("Cambio", {}, "") == "primary"


def test_missing_gemini_key_does_not_change_primary(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def primary(*_):
        return "primary"

    assert gemini.with_gemini_fallback(primary, THEME_FILES) is primary


@pytest.mark.parametrize("code", ["json_validate_failed", "unknown-private-code"])
def test_only_known_provider_code_is_reported_without_external_message(monkeypatch, code):
    error = urllib.error.HTTPError(
        "https://api.groq.com/openai/v1/chat/completions",
        400,
        "private",
        {},
        io.BytesIO(
            json.dumps(
                {
                    "error": {
                        "code": code,
                        "message": "private-key-and-prompt",
                        "failed_generation": "private-source",
                    }
                }
            ).encode()
        ),
    )

    class Opener:
        def open(self, *_, **__):
            raise error

    monkeypatch.setenv("GROQ_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(transport.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(CheckError) as result:
        transport.request_json(error.url, {}, {})
    expected = (
        "PROVIDER_JSON_GENERATION_FAILED" if code == "json_validate_failed" else "INVALID_REQUEST"
    )
    assert result.value.reason == expected
    assert "private" not in str(result.value)
