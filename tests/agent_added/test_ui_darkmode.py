from playwright.sync_api import sync_playwright

from tests.test_tasks_e2e import tasks_url as tasks_url


def test_ui(tasks_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(tasks_url)
        # Verify header has background color (navbar full)
        header_bg = page.evaluate("""() => {
            const style = getComputedStyle(document.querySelector('header'));
            return style.backgroundColor;
        }""")
        assert header_bg not in ("rgba(0, 0, 0, 0)", "transparent")
        # Toggle dark mode
        page.click("#theme-toggle")
        # Verify title color changes to light ink in dark mode
        title_color = page.evaluate("""() => {
            const h3 = document.querySelector('.task h3') || document.querySelector('h1');
            return getComputedStyle(h3).color;
        }""")
        # In dark mode ink should be light (e.g., rgb(224, 224, 224) or similar)
        r, g, b = map(int, title_color.replace("rgb(", "").replace(")", "").split(","))
        assert (r, g, b) >= (200, 200, 200)
        browser.close()
