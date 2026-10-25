from pathlib import Path
import shutil

import pytest
from playwright.sync_api import sync_playwright


def pytest_addoption(parser):
    parser.addoption("--headed", action="store_true", help="Run browser checks on a graphical display")


@pytest.fixture(scope="session")
def browser(request):
    with sync_playwright() as p:
        # Reuse the orb's installed Chrome; elsewhere use playwright install chromium.
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        instance = p.chromium.launch(executable_path=chrome, headless=not request.config.getoption("--headed"), args=["--no-sandbox"])
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(locale="en-US", timezone_id="America/New_York")
    context.route("**/*", lambda route: route.abort())
    page = context.new_page()
    page.set_default_timeout(1000)
    yield page
    context.close()


@pytest.fixture
def fixture_html():
    return lambda name: (Path(__file__).parent / "fixtures" / (name + ".html")).read_text()
