import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from harness import review_push as review
from harness.engine import Outcome, Validation
from harness.provider_http import CheckError


def test_review_findings_have_real_rule_file_and_line():
    text = "I001 Imports incorrectos\n --> /candidate/taskapp/main.py:7:1\n"
    assert review.deterministic_findings(text, ["taskapp/main.py"])[0] == {
        "rule": "I001",
        "file": "taskapp/main.py",
        "line": 7,
        "explanation": "I001 Imports incorrectos",
    }
    assert (
        review.deterministic_findings("/candidate/taskapp/main.py:3: error: falta tipo", [])[0][
            "line"
        ]
        == 3
    )


def test_contextual_advice_is_bounded_and_line_validated(monkeypatch):
    response = {
        "model": review.DEFAULT_MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "recommendations": [
                                {
                                    "rule": "NAMES",
                                    "path": "taskapp/a.py",
                                    "line": 1,
                                    "message": "Nombre mas claro",
                                }
                            ]
                        }
                    )
                },
            }
        ],
    }
    monkeypatch.setattr(review, "request_json", lambda *_: response)
    assert (
        review.contextual_review("fake-key", {"taskapp/a.py": "x=1"}, ["taskapp/a.py"])[0]["rule"]
        == "NAMES"
    )
    response["choices"][0]["message"]["content"] = json.dumps(
        {
            "recommendations": [
                {"rule": "NAMES", "path": "taskapp/a.py", "line": 20, "message": "Invalid"}
            ]
        }
    )
    with pytest.raises(CheckError):
        review.contextual_review("fake-key", {"taskapp/a.py": "x=1"}, ["taskapp/a.py"])


def prepare(monkeypatch, valid=True):
    baseline = {"taskapp/a.py": "value = 1\n"}
    candidate = {"taskapp/a.py": "value = 2\n"}

    class Validator:
        def __init__(self, *_):
            self.baseline = baseline

        def __call__(self, *_):
            return Validation(valid, "lint failed")

    monkeypatch.setattr(review, "DockerValidator", Validator)
    monkeypatch.setattr(review, "source_candidate", lambda *_: (candidate, ["taskapp/a.py"]))
    return baseline, candidate


def test_valid_push_creates_pr_with_advisories_nonblocking(monkeypatch, tmp_path):
    prepare(monkeypatch)
    monkeypatch.setattr(
        review,
        "contextual_review",
        lambda *_: [{"rule": "NAMES", "path": "taskapp/a.py", "line": 1, "message": "Consejo"}],
    )
    monkeypatch.setattr(review.AppSettings, "from_environment", lambda: object())

    @contextmanager
    def token(*_):
        yield "fake-private-token"

    monkeypatch.setattr(review, "installation_token", token)

    class Commit:
        stdout = "a" * 40

    monkeypatch.setattr(review.subprocess, "run", lambda *_, **__: Commit())
    monkeypatch.setattr(
        review,
        "publish_pr",
        lambda *_: {"url": "https://github.com/Sebitafx/agentops-tareas/pull/1", "number": 1},
    )
    calls = []
    monkeypatch.setattr(review, "github_json", lambda *args: calls.append(args) or {})
    report = review.execute(tmp_path, "image", "b" * 40, "123")
    assert report["status"] == "pr_open" and report["initial_validation_passed"]
    assert "Recomendacion" in calls[0][3]["body"]


def test_unrepairable_push_does_not_publish(monkeypatch, tmp_path):
    prepare(monkeypatch, False)
    monkeypatch.setattr(review, "GroqProposer", lambda *_, **__: object())
    monkeypatch.setattr(
        review, "run_request", lambda *_: Outcome("failed", "ATTEMPTS_EXHAUSTED", ())
    )
    monkeypatch.setattr(review, "publish_pr", lambda *_: pytest.fail("No publicar sin validacion"))
    result = review.execute(tmp_path, "image", "b" * 40, "123")
    assert result["status"] == "blocked" and result["deterministic_findings"]


def test_repair_equal_to_main_does_not_create_empty_pr(monkeypatch, tmp_path):
    baseline, _ = prepare(monkeypatch, False)
    monkeypatch.setattr(review, "GroqProposer", lambda *_, **__: object())
    monkeypatch.setattr(
        review,
        "run_request",
        lambda *_: Outcome("validated", "VALIDATION_PASSED", (), candidate=baseline),
    )
    assert review.execute(tmp_path, "image", "b" * 40, "123")["status"] == "already_satisfied"


def test_source_sha_rejects_command_injection():
    with pytest.raises(ValueError):
        review.source_candidate(Path.cwd(), {}, "--upload-pack=evil")
