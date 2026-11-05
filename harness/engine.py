"""Bucle acotado de correccion con proveedor y validacion separados."""

import json
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError

from harness.proposals import PolicyError, Proposal, apply_to_snapshot
from harness.provider_http import CheckError

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Validation:
    passed: bool
    # Solo diagnosticos del contenedor aislado, sin credenciales ni respuestas externas.
    feedback: str


@dataclass(frozen=True)
class Attempt:
    number: int
    result: str


@dataclass(frozen=True)
class Outcome:
    status: Literal["validated", "clarify", "refused", "failed"]
    reason: str
    attempts: tuple[Attempt, ...]
    proposal: Proposal | None = None
    candidate: Mapping[str, str] | None = field(default=None, repr=False)


# La validacion es obligatoria. Este modulo no contiene una opcion para omitirla.
Proposer = Callable[[str, Mapping[str, str], str], Proposal]
Validator = Callable[[Mapping[str, str]], Validation]
Normalizer = Callable[[Proposal, Mapping[str, str]], Proposal]


def missing_requirement(request: str) -> str | None:
    plain = "".join(
        char
        for char in unicodedata.normalize("NFKD", request.casefold())
        if not unicodedata.combining(char)
    )
    plain = " ".join(re.sub(r"[^a-z0-9 ]", " ", plain).split())
    if re.fullmatch(
        r"(?:agrega|agregar|anade|anadir|crea|crear) "
        r"(?:(?:el|la|un|una|los|las) )?"
        r"(?:boton|botones|funcion|funcionalidad|algo)"
        r"(?: por favor)?",
        plain,
    ):
        return (
            "¿Qué debe hacer lo que quieres agregar y dónde debe aparecer? "
            "Si es un botón, indica su texto y qué debe ocurrir al pulsarlo."
        )
    if re.fullmatch(
        r"(?:cambia|cambiar|modifica|modificar|mejora|mejorar) "
        r"(?:(?:el|la|un|una|los|las) )?"
        r"(?:boton|botones|color|colores|texto|interfaz|sistema|aplicacion)",
        plain,
    ) or re.fullmatch(r"agrega(?:r)? (?:algo|una funcion|una funcionalidad)", plain):
        return "¿Qué elemento quieres cambiar y cuál es el resultado concreto que debe tener?"
    return None


def run_request(
    request: str,
    base: Mapping[str, str],
    propose: Proposer,
    validate: Validator,
    normalize: Normalizer | None = None,
) -> Outcome:
    if not request.strip() or len(request) > 3000:
        return Outcome("failed", "INVALID_REQUEST", ())
    if question := missing_requirement(request):
        return Outcome(
            "clarify",
            "NEEDS_INPUT",
            (),
            Proposal(action="clarify", summary="Falta un requisito concreto", question=question),
        )
    # Cada intento parte de la misma base. Un fallo no acumula modificaciones.
    baseline = dict(base)
    history: list[Attempt] = []
    feedback = ""
    last_validation_feedback = ""
    for number in range(1, MAX_ATTEMPTS + 1):
        try:
            proposal = propose(request, dict(baseline), feedback)
        except CheckError as exc:
            history.append(Attempt(number, exc.reason))
            return Outcome("failed", exc.reason, tuple(history))
        except (ValidationError, ValueError) as exc:
            # Tipos y ubicaciones, sin input, cuerpo externo ni fragmentos de código.
            if isinstance(exc, ValidationError):
                errors = [
                    {"type": e["type"], "loc": list(e["loc"])}
                    for e in exc.errors(include_input=False)
                ]
                detail = {"kind": "schema", "errors": errors[:6]}
            else:
                known = str(exc).split(";", 1)[0]
                detail = {
                    "kind": known
                    if known.startswith(
                        (
                            "PATCH_MISMATCH",
                            "REPAIR_REQUIRES_IMPLEMENTATION",
                            "TOOL_LIMIT",
                            "INVALID_TOOL_RESPONSE",
                        )
                    )
                    else "ValueError"
                }
            print(
                json.dumps({"event": "invalid_proposal", "attempt": number, **detail}), flush=True
            )
            # Diagnostico primero y acotado; la causa previa no debe desplazarlo.
            diagnosis = f"INVALID_PROPOSAL: {exc}"
            feedback = (diagnosis + "\n" + last_validation_feedback)[:4000]
            history.append(Attempt(number, "INVALID_PROPOSAL"))
            continue
        if proposal.action != "change":
            status = "clarify" if proposal.action == "clarify" else "refused"
            history.append(Attempt(number, status))
            return Outcome(
                status,
                "NEEDS_INPUT" if status == "clarify" else "OUT_OF_SCOPE",
                tuple(history),
                proposal,
            )
        try:
            if normalize:
                # El normalizador tambien comprueba el alcance antes de tocar el texto.
                proposal = normalize(proposal, baseline)
            candidate = apply_to_snapshot(proposal, baseline)
        except PolicyError as exc:
            feedback = str(exc)
            history.append(Attempt(number, feedback))
            if last_validation_feedback:
                feedback = (
                    feedback
                    + "\nNo cambies pruebas de referencia. Corrige la aplicación o tu prueba nueva."
                    + "\nÚltimo fallo de validación:\n"
                    + last_validation_feedback
                )[:4000]
            continue
        except CheckError as exc:
            history.append(Attempt(number, exc.reason))
            return Outcome("failed", exc.reason, tuple(history))
        # Fallos del validador son fallos de infraestructura, no una aprobacion.
        try:
            validation = validate(dict(candidate))
        except (OSError, TimeoutError):
            history.append(Attempt(number, "VALIDATOR_UNAVAILABLE"))
            return Outcome("failed", "VALIDATOR_UNAVAILABLE", tuple(history))
        if validation.passed:
            history.append(Attempt(number, "VALIDATION_PASSED"))
            return Outcome("validated", "VALIDATION_PASSED", tuple(history), proposal, candidate)
        last_validation_feedback = validation.feedback[:4000]
        feedback = last_validation_feedback
        history.append(Attempt(number, "VALIDATION_FAILED"))
    return Outcome("failed", "ATTEMPTS_EXHAUSTED", tuple(history))
