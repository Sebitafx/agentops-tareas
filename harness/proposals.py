"""Contrato cerrado de propuestas. Recibir texto de IA nunca ejecuta codigo."""

import hashlib
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_CHANGED_BYTES = 65536
APP_EXTENSIONS = frozenset({".py", ".html", ".css", ".js"})


class PolicyError(Exception):
    """Motivo publico y estable; no incluye contenido de archivos ni secretos."""


class FileChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=180)
    # null significa archivo nuevo; para existentes debe coincidir el hash de la base.
    base_sha256: str | None
    content: str = Field(max_length=32768)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["change", "clarify", "refuse"]
    summary: str = Field(min_length=1, max_length=1000)
    question: str | None = Field(default=None, max_length=600)
    files: list[FileChange] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def consistent_action(self) -> "Proposal":
        if self.action == "change":
            if not self.files or self.question is not None:
                raise ValueError("Un cambio necesita archivos y no una pregunta")
        elif self.files:
            raise ValueError("Una aclaracion o rechazo no modifica archivos")
        if (self.action == "clarify") != bool(self.question and self.question.strip()):
            raise ValueError("Solo una aclaracion necesita una pregunta no vacia")
        return self


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def canonical_path(name: str) -> PurePosixPath:
    # Un formato unico tambien evita rutas Windows, ADS, escapes y nombres ocultos.
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", name):
        raise PolicyError("INVALID_PATH")
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or path.as_posix() != name
        or any(part in {".", ".."} or part.startswith(".") for part in path.parts)
    ):
        raise PolicyError("INVALID_PATH")
    return path


def check_proposal(proposal: Proposal, base: Mapping[str, str]) -> None:
    """Revisa alcance y base antes de entregar la propuesta al validador aislado."""
    seen: set[str] = set()
    total_bytes = 0
    meaningful = False
    for change in proposal.files:
        path = canonical_path(change.path)
        if change.path in seen:
            raise PolicyError("DUPLICATE_PATH")
        seen.add(change.path)
        app_file = path.parts[0] == "taskapp" and path.suffix in APP_EXTENSIONS
        # Se agregan pruebas en un directorio propio, sin reemplazar ninguna existente.
        new_test = (
            len(path.parts) == 3
            and path.parts[:2] == ("tests", "agent_added")
            and re.fullmatch(r"test_[a-z0-9_]+\.py", path.name)
            and change.path not in base
        )
        if not app_file and not new_test:
            raise PolicyError("PROTECTED_PATH")
        original = base.get(change.path)
        expected_hash = digest(original) if original is not None else None
        if change.base_sha256 != expected_hash:
            raise PolicyError("STALE_BASE")
        if "\x00" in change.content:
            raise PolicyError("BINARY_CONTENT")
        if not change.content.strip():
            raise PolicyError("EMPTY_FILE")
        total_bytes += len(change.content.encode("utf-8"))
        meaningful |= original != change.content
    if total_bytes > MAX_CHANGED_BYTES:
        raise PolicyError("CHANGE_TOO_LARGE")
    if proposal.action == "change" and not meaningful:
        raise PolicyError("NO_CHANGE")


def apply_to_snapshot(proposal: Proposal, base: Mapping[str, str]) -> dict[str, str]:
    """Crea una copia en memoria; nunca escribe el checkout ni toca el filesystem."""
    check_proposal(proposal, base)
    return {**base, **{change.path: change.content for change in proposal.files}}
