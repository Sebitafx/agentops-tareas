"""Oraculo de tema: comportamiento visible y persistencia, independiente de clases."""

import os
import re

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.test_tasks_e2e import tasks_url as tasks_url


@pytest.mark.skipif(os.getenv("VALIDATION_SCENARIO") != "task-theme", reason="Otro escenario")
def test_theme_toggle_changes_interface_and_survives_reload(tasks_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(tasks_url)
        toggle = page.get_by_role("button", name=re.compile(r"^Modo oscuro$", re.I))
        expect(toggle).to_be_visible()
        original = page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor")
        toggle.click()
        dark_toggle = page.get_by_role("button", name=re.compile(r"^Modo claro$", re.I))
        expect(dark_toggle).to_be_visible()
        dark = page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor")
        assert dark != original
        # Una etiqueta o un atributo sin cambio visual no cumplen la funcion.
        channels = [float(value) for value in re.findall(r"[\d.]+", dark)[:3]]
        assert len(channels) == 3
        assert max(channels) < 128
        page.reload()
        expect(page.get_by_role("button", name=re.compile(r"^Modo claro$", re.I))).to_be_visible()
        assert page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == dark
        page.get_by_role("button", name=re.compile(r"^Modo claro$", re.I)).click()
        expect(page.get_by_role("button", name=re.compile(r"^Modo oscuro$", re.I))).to_be_visible()
        assert page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == original
        browser.close()
