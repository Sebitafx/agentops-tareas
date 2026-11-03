import json

import pytest


@pytest.fixture
def runner():
    pytest.importorskip("resource", reason="El ejecutor aislado solo corre en Linux")
    from harness import offline_runner

    return offline_runner


def test_missing_isolation_rejects_before_running_commands(runner, monkeypatch, capsys):
    monkeypatch.setattr(runner, "boundaries", lambda: {"network_none": False})
    monkeypatch.setattr(runner, "command", lambda *_: pytest.fail("No ejecutar sin aislamiento"))
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "ISOLATION_REQUIRED"


def staged_reference(tmp_path, runner, monkeypatch):
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    for folder in [reference, candidate]:
        (folder / "tests").mkdir(parents=True)
        (folder / "tests/test_existing.py").write_text("assert 1 == 1\n", encoding="utf-8")
    monkeypatch.setattr(runner, "REFERENCE", reference)
    monkeypatch.setattr(runner, "CANDIDATE", candidate)
    return reference, candidate


@pytest.mark.parametrize("kind", ["changed", "deleted", "conftest", "symlink"])
def test_tampered_test_reference_is_rejected(runner, monkeypatch, tmp_path, kind):
    _, candidate = staged_reference(tmp_path, runner, monkeypatch)
    existing = candidate / "tests/test_existing.py"
    if kind == "changed":
        existing.write_text("pass\n", encoding="utf-8")
    elif kind == "deleted":
        existing.unlink()
    elif kind == "conftest":
        (candidate / "tests/conftest.py").write_text("pass\n", encoding="utf-8")
    else:
        (candidate / "tests/test_link.py").symlink_to(existing)
    with pytest.raises(ValueError):
        runner.verify_reference()


def test_unchanged_reference_and_new_behavior_test_are_allowed(runner, monkeypatch, tmp_path):
    _, candidate = staged_reference(tmp_path, runner, monkeypatch)
    (candidate / "tests/test_additional.py").write_text("assert 2 == 2\n", encoding="utf-8")
    runner.verify_reference()
