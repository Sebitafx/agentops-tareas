import ast
import json
from pathlib import Path

from harness.code_proposer import SYSTEM, GroqProposer
from harness.request_worker import visible_files


def test_theme_request_has_complete_styles_markup_and_behavior_within_budget():
    root = Path(__file__).resolve().parents[1]
    paths = {
        "taskapp/static/index.html",
        "taskapp/static/app.js",
        "taskapp/static/style.css",
    }
    base = {name: (root / name).read_text(encoding="utf-8") for name in paths}
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
