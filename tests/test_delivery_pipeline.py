import pytest

from bootstrap.github_app import REPOSITORY
from harness.deploy import DeploymentError, confirm, deploy_commit, hook_for_commit
from harness.integrate import IntegrationError, check_protection, integrate_pr

BASE, HEAD, MERGED, TREE = (letter * 40 for letter in "abcd")
HOOK = "https://api.render.com/deploy/srv-test123?key=fake-only-key"
PUBLICATION = {"number": 1, "head_sha": HEAD, "base_sha": BASE}


def protection():
    return {
        "required_status_checks": {"strict": True, "contexts": ["bootstrap-quality"]},
        "required_pull_request_reviews": {},
        "enforce_admins": {"enabled": True},
    }


@pytest.mark.parametrize(
    "kind", ["loose", "no_check", "no_pr", "admins_bypass", "force_push", "delete"]
)
def test_main_must_be_strictly_protected(kind):
    value = protection()
    if kind == "loose":
        value["required_status_checks"]["strict"] = False
    if kind == "no_check":
        value["required_status_checks"]["contexts"] = []
    if kind == "no_pr":
        value.pop("required_pull_request_reviews")
    if kind == "admins_bypass":
        value["enforce_admins"]["enabled"] = False
    if kind == "force_push":
        value["allow_force_pushes"] = {"enabled": True}
    if kind == "delete":
        value["allow_deletions"] = {"enabled": True}
    with pytest.raises(IntegrationError):
        check_protection(value)


def api_fixture(problem=None):
    calls = []

    def api(method, path, body=None):
        calls.append((method, path, body))
        if path.endswith("/protection"):
            return protection()
        if path.endswith("/pulls/1"):
            return {
                "state": "open",
                "draft": False,
                "head": {
                    "sha": "f" * 40 if problem == "head" else HEAD,
                    "repo": {"full_name": REPOSITORY},
                },
                "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
            }
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "f" * 40 if problem == "base" else BASE}}
        if "/actions/runs?" in path:
            return {
                "workflow_runs": [
                    {
                        "id": 1,
                        "name": "Bootstrap CI",
                        "head_sha": HEAD,
                        "status": "completed",
                        "conclusion": "failure" if problem == "checks" else "success",
                    }
                ]
            }
        if path.endswith("/merge"):
            assert body == {"sha": HEAD, "merge_method": "merge"}
            return {"merged": True, "sha": MERGED}
        if path.endswith("/git/commits/" + MERGED):
            return {
                "parents": [{"sha": BASE}, {"sha": HEAD}],
                "tree": {"sha": "f" * 40 if problem == "tree" else TREE},
            }
        if path.endswith("/git/commits/" + HEAD):
            return {"tree": {"sha": TREE}}
        pytest.fail("Ruta inesperada")

    return api, calls


def test_merge_confirms_exact_validated_tree_and_parents():
    api, calls = api_fixture()
    assert integrate_pr(PUBLICATION, api) == MERGED
    assert len([c for c in calls if c[0] == "PUT"]) == 1


@pytest.mark.parametrize("problem", ["head", "base", "checks", "tree"])
def test_changed_content_or_failed_checks_never_approves(problem):
    api, calls = api_fixture(problem)
    with pytest.raises(IntegrationError):
        integrate_pr(PUBLICATION, api)
    if problem != "tree":
        assert not any(c[0] == "PUT" for c in calls)


def test_hook_accepts_only_fixed_destination_and_sha():
    assert "ref=" + MERGED in hook_for_commit(HOOK, MERGED)
    for invalid in [
        "http://api.render.com/deploy/srv-test123?key=x",
        "https://evil.invalid/deploy/srv-test123?key=x",
        HOOK + "&ref=main",
        HOOK + "#frag",
        "not-a-url",
    ]:
        with pytest.raises(DeploymentError):
            hook_for_commit(invalid, MERGED)


def test_deploy_success_and_postdeploy_failure_rollback():
    posts = []
    version = BASE

    def read(url, method="GET"):
        nonlocal version
        if method == "POST":
            posts.append(url)
            version = MERGED if "ref=" + MERGED in url else BASE
            return {"deploy": {"id": "dep-test"}}
        if url.endswith("/version"):
            return {"commit": version}
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/ready"):
            return {"database": "ok"}
        return []

    assert deploy_commit(HOOK, MERGED, read, timeout=0).succeeded
    version = BASE

    def broken(url, method="GET"):
        if url.endswith("/health") and version == MERGED:
            return {"status": "error"}
        return read(url, method)

    result = deploy_commit(HOOK, MERGED, broken, timeout=0)
    assert not result.succeeded and result.rollback == "confirmed"
    assert "ref=" + BASE in posts[-1]


def test_wrong_version_cannot_announce_success():
    with pytest.raises(DeploymentError):
        confirm(MERGED, lambda _: {"commit": BASE}, timeout=0)
