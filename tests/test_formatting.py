from pathlib import Path

import pytest

from harness import formatting
from harness.formatting import normalize_proposal
from harness.proposals import PolicyError, Proposal, digest

ROOT = Path(formatting.__file__).resolve().parents[1]


def test_normalizer_sorts_imports_without_modifying_existing_test_file():
    path = "tests/agent_added/test_title.py"
    proposal = Proposal.model_validate(
        {
            "action": "change",
            "summary": "Prueba ficticia",
            "files": [
                {
                    "path": path,
                    "base_sha256": None,
                    "content": "import pytest\nfrom pydantic import ValidationError\nfrom taskapp.schemas import TaskCreate\n\ndef test_title():\n with pytest.raises(ValidationError):\n  TaskCreate(title='')\n",
                }
            ],
        }
    )
    base = {"tests/test_protected.py": "assert 1 == 1\n"}
    normalized = normalize_proposal(ROOT, proposal, base)
    assert "from pydantic import ValidationError\n\nfrom taskapp" in normalized.files[0].content
    assert base == {"tests/test_protected.py": "assert 1 == 1\n"}
    assert normalized.files[0].base_sha256 is None
    assert not Path(path).exists()


def test_normalizer_does_not_execute_python_and_preserves_base_hash():
    base = {"taskapp/a.py": "a = 1\n"}
    proposal = Proposal.model_validate(
        {
            "action": "change",
            "summary": "Demo",
            "files": [
                {
                    "path": "taskapp/a.py",
                    "base_sha256": digest(base["taskapp/a.py"]),
                    "content": "raise RuntimeError('THIS_CODE_MUST_NOT_EXECUTE')\n",
                }
            ],
        }
    )
    normalized = normalize_proposal(ROOT, proposal, base)
    assert "THIS_CODE_MUST_NOT_EXECUTE" in normalized.files[0].content
    assert normalized.files[0].base_sha256 == proposal.files[0].base_sha256


def test_normalizer_rejects_protected_files():
    proposal = Proposal.model_validate(
        {
            "action": "change",
            "summary": "Demo",
            "files": [
                {
                    "path": "harness/engine.py",
                    "base_sha256": None,
                    "content": "pass\n",
                }
            ],
        }
    )
    with pytest.raises(PolicyError, match="PROTECTED_PATH"):
        normalize_proposal(ROOT, proposal, {})
