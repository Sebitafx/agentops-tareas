"""Oraculos independientes para los benchmarks; el agente no puede editarlos."""

import os
import re

import pytest
from pydantic import ValidationError

from taskapp.schemas import TaskCreate, TaskPatch
from tests.test_tasks_e2e import tasks_url as tasks_url


def sample(name):
    return pytest.mark.skipif(os.getenv("VALIDATION_SCENARIO") != name, reason="Otro escenario")


@sample("title-limit")
def test_requested_title_boundary():
    for model in (TaskCreate, TaskPatch):
        assert model(title="x" * 180).title == "x" * 180
        with pytest.raises(ValidationError):
            model(title="x" * 181)


@sample("button-label")
def test_requested_create_label_survives_submission(tasks_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(tasks_url)
        label = re.compile(r"^Agregar tarea(?:\s*↗)?$")
        expect(page.locator("#submit")).to_have_text(label)
        page.get_by_label("Título de la tarea").fill("Prueba del texto nuevo")
        page.locator("#submit").click()
        expect(page.get_by_test_id("task-card")).to_have_count(1)
        expect(page.locator("#submit")).to_have_text(label)
        browser.close()


@sample("task-search")
def test_requested_search_is_case_insensitive_and_clearable(tasks_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(tasks_url)
        for title in ("Tarea Alfa", "Tarea Beta"):
            page.get_by_label("Título de la tarea").fill(title)
            page.locator("#submit").click()
            expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
        search = page.get_by_role("textbox", name="Buscar tareas", exact=True)
        expect(search).to_have_attribute("id", "task-search")
        search.fill("ALFA")
        expect(page.get_by_test_id("task-card")).to_have_count(1)
        expect(page.get_by_role("heading", name="Tarea Alfa", exact=True)).to_be_visible()
        search.fill("beTA")
        expect(page.get_by_test_id("task-card")).to_have_count(1)
        expect(page.get_by_role("heading", name="Tarea Beta", exact=True)).to_be_visible()
        search.fill("")
        expect(page.get_by_test_id("task-card")).to_have_count(2)
        browser.close()
