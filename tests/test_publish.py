from uuid import UUID

import pytest

from bootstrap.github_app import GitHubError
from harness.engine import Outcome
from harness.proposals import Proposal, digest
from harness.publish import publish_pr

BASE = {"taskapp/a.py": "value = 1\n"}
BASE_SHA = "a" * 40
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000001")


def validated():
    proposal = Proposal.model_validate(
        {
            "action": "change",
            "summary": "Private input must not be published",
            "files": [
                {
                    "path": "taskapp/a.py",
                    "base_sha256": digest(BASE["taskapp/a.py"]),
                    "content": "value = 2\n",
                }
            ],
        }
    )
    return Outcome("validated", "VALIDATION_PASSED", (), proposal, {"taskapp/a.py": "value = 2\n"})


def fake_api(changed=False):
    calls = []

    def api(method, path, payload=None):
        calls.append((method, path, payload))
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "b" * 40 if changed and len(calls) > 1 else BASE_SHA}}
        if "/git/commits/" in path:
            return {"tree": {"sha": "b" * 40}}
        if path.endswith("/pulls"):
            assert "Private input" not in payload["body"] + payload["title"]
            return {"number": 12}
        return {"sha": "c" * 40}

    return api, calls


def test_validated_change_creates_only_new_branch_and_pr():
    api, calls = fake_api()
    result = publish_pr(validated(), BASE, BASE_SHA, REQUEST_ID, "1234", api)
    assert result["number"] == 12 and result["head_sha"] == "c" * 40
    refs = [payload for method, path, payload in calls if path.endswith("/git/refs")]
    assert refs == [{"ref": "refs/heads/agentops/requests/" + str(REQUEST_ID), "sha": "c" * 40}]
    assert all(method in {"GET", "POST"} for method, _, _ in calls)
    assert not any("/merge" in path for _, path, _ in calls)


def test_failed_or_modified_candidate_cannot_publish():
    def api(*_):
        pytest.fail("No llamar GitHub sin validacion")

    with pytest.raises(GitHubError, match="UNVALIDATED_PROPOSAL"):
        publish_pr(Outcome("failed", "FAILED", ()), BASE, BASE_SHA, REQUEST_ID, "1234", api)
    outcome = validated()
    outcome.candidate["taskapp/a.py"] = "tampered"
    with pytest.raises(GitHubError, match="VALIDATED_CONTENT_CHANGED"):
        publish_pr(outcome, BASE, BASE_SHA, REQUEST_ID, "1234", api)


def test_base_movement_prevents_branch_creation():
    api, calls = fake_api(changed=True)
    with pytest.raises(GitHubError, match="MAIN_CHANGED_REVALIDATION_REQUIRED"):
        publish_pr(validated(), BASE, BASE_SHA, REQUEST_ID, "1234", api)
    assert not any(path.endswith("/git/refs") for _, path, _ in calls)
