from tests.test_tasks_e2e import tasks_url as tasks_url


def test_ui(tasks_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(tasks_url)
        # Verify theme toggle is visible and has correct aria attributes
        toggle = page.locator("#theme-toggle")
        assert toggle.is_visible()
        # Initial state should be light (aria-pressed false)
        assert toggle.get_attribute("aria-pressed") == "false"
        # Click to switch to dark mode
        toggle.click()
        # After click, aria-pressed should be true and dark theme applied
        assert toggle.get_attribute("aria-pressed") == "true"
        assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
        # Verify contrast: input background should be dark
        bg = page.evaluate("getComputedStyle(document.querySelector('input')).backgroundColor")
        # Expect a dark rgb value (e.g., rgb(42, 42, 42))
        assert "rgb(42" in bg or "rgb(34" in bg
        browser.close()
