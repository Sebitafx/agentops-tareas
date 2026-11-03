import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


@pytest.fixture
def tasks_url(database):
    if os.getenv("E2E_ENABLED") != "1":
        pytest.skip("Configurar E2E_ENABLED=1 e instalar Chromium para E2E")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("META_", "WHATSAPP_", "AGENT_APP_", "GROQ_", "GEMINI_"))
    }
    env["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "taskapp.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                if httpx.get(url + "/ready", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if process.poll() is not None or time.monotonic() >= deadline:
                pytest.fail("No arranco la aplicacion E2E en la base de prueba")
            time.sleep(0.2)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_browser_crud_filters_and_mobile(tasks_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(tasks_url)
        page.get_by_label("Título de la tarea").fill("Preparar la demostración")
        page.get_by_label("Descripción").fill("Recorrer WhatsApp, revisión y despliegue.")
        page.get_by_role("button", name="Crear tarea").click()
        expect(page.get_by_test_id("task-card")).to_have_count(1)
        page.get_by_role("button", name="Editar", exact=True).click()
        page.get_by_label("Título de la tarea").fill("Demostración preparada")
        page.get_by_role("button", name="Guardar cambios").click()
        expect(page.get_by_role("heading", name="Demostración preparada")).to_be_visible()
        page.get_by_role("checkbox", name="Completar Demostración preparada").check()
        page.get_by_role("button", name="Pendientes", exact=True).click()
        expect(page.get_by_test_id("task-card")).to_have_count(0)
        page.get_by_role("button", name="Completadas", exact=True).click()
        expect(page.get_by_test_id("task-card")).to_have_count(1)
        artifacts = Path("artifacts")
        artifacts.mkdir(exist_ok=True)
        page.screenshot(path=str(artifacts / "tasks-desktop.png"), full_page=True)
        page.reload()
        expect(page.get_by_role("heading", name="Demostración preparada")).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(artifacts / "tasks-mobile.png"), full_page=True)
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Eliminar", exact=True).click()
        expect(page.get_by_test_id("task-card")).to_have_count(0)
        # Un titulo con HTML debe mostrarse como texto, sin ejecutarse.
        page.get_by_label("Título de la tarea").fill("<img src=x onerror=alert('xss')>")
        page.get_by_role("button", name="Crear tarea").click()
        expect(page.get_by_test_id("task-card")).to_have_count(1)
        assert page.locator("#task-list img").count() == 0
        browser.close()
