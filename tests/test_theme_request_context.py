import ast
import json
from pathlib import Path

from harness.code_proposer import SYSTEM, GroqProposer
from harness.interactive_proposer import InteractiveProposer
from harness.request_worker import visible_files


def test_theme_request_has_complete_styles_markup_and_behavior_within_budget():
    paths = {
        "taskapp/static/index.html",
        "taskapp/static/app.js",
        "taskapp/static/style.css",
    }
    # Este contrato comprueba el adaptador con entradas fijas. Un cambio de UI
    # no debe convertirse en una exigencia de tamaño sobre toda la aplicación.
    base = {
        "taskapp/static/index.html": '<button id="theme-toggle">Modo oscuro</button>',
        "taskapp/static/app.js": 'localStorage.setItem("theme", "dark");',
        "taskapp/static/style.css": '[data-theme="dark"] { color: white; background: black; }',
    }
    base["bootstrap/private.py"] = "never-for-model"
    request = (
        "Agregar un boton. Pregunta: que debe hacer? Respuesta: en la cabecera, "
        "alternar modo oscuro y modo claro conservando la seleccion al recargar. "
        "Agregar prueba de navegador, conservar CRUD y no agregar dependencias."
    )
    visible = visible_files(request, base)
    context = json.loads(
        GroqProposer("test-only", visible_paths=visible).context(request, base, "")
    )
    assert set(context["files"]) == paths
    for name in paths:
        assert context["files"][name]["content"] == base[name]


def test_ui_example_registers_fixture_in_same_complete_example():
    example = SYSTEM.split("Ejemplo válido", 1)[1].split("Si solo cambias", 1)[0]
    example = example.split("\n", 1)[1]
    module = ast.parse(example)
    imports = [node for node in module.body if isinstance(node, ast.ImportFrom)]
    assert any(
        node.module == "tests.test_tasks_e2e"
        and any(alias.name == "tasks_url" and alias.asname == "tasks_url" for alias in node.names)
        for node in imports
    )


def test_interactive_theme_reads_growing_application_without_groq_context_limit(monkeypatch):
    from harness import interactive_proposer
    from harness.proposals import apply_to_snapshot

    root = Path(__file__).resolve().parents[1]
    paths = ["taskapp/static/index.html", "taskapp/static/app.js", "taskapp/static/style.css"]
    base = {p: (root / p).read_text(encoding="utf-8") for p in paths}
    base[paths[2]] += "\n/*" + "theme regression " * 2500 + "*/"
    base["taskapp/theme_probe.js"] = "const themeProbe = false;"
    calls = []

    def decide(system, context, *_):
        calls.append(context.copy())
        if paths[2] not in context["files"]:
            return {"action": "read", "detail": paths[2]}
        assert context["files"][paths[2]].startswith(base[paths[2]][:100])
        return {
            "action": "change",
            "detail": "Estilos ficticios",
            "edits": [
                {
                    "path": "taskapp/theme_probe.js",
                    "before": "const themeProbe = false;",
                    "after": "const themeProbe = true;",
                }
            ],
        }

    monkeypatch.setattr(interactive_proposer, "choose", decide)
    proposal = InteractiveProposer(lambda _: True, lambda _: None)("Mejora el tema", base, "")
    candidate = apply_to_snapshot(proposal, base)
    assert candidate[paths[2]] == base[paths[2]]
    assert candidate["taskapp/theme_probe.js"] == "const themeProbe = true;"
    assert len(calls) == 2
