"""UI checks: a real browser drives the static UI that compose serves on :8080 (ADR-9).

The UI is plain JavaScript with no build step, so the only way to know it still works
with both services is to load it the way a user does. Each test fails on any uncaught
JavaScript error in the page, not only on its own assertions.
"""
import pytest
from conftest import UI_URL, prompts_down
from playwright.sync_api import Page, expect, sync_playwright


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(15_000)
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    yield page
    context.close()
    assert not errors, f"JavaScript errors in the UI: {errors}"


def open_prompt(page: Page, prompt_version: dict) -> None:
    page.goto(f"{UI_URL}/#/p/{prompt_version['prompt_id']}")
    expect(page.locator("#p-title")).to_have_text(prompt_version["prompt_name"])


def test_the_manifest_lists_a_prompt_created_in_the_prompts_service(page, prompt_version):
    page.goto(UI_URL)
    link = page.get_by_role("link", name=prompt_version["prompt_name"])
    expect(link).to_be_visible()

    link.click()
    # the prompt page is built from prompts (versions, test cases) and evals (runs)
    expect(page.locator("#p-title")).to_have_text(prompt_version["prompt_name"])
    expect(page.locator("#cases")).to_contain_text("greets the person")
    expect(page.locator("#runs")).to_contain_text("Nothing has gone through the dock")


def test_a_run_started_from_the_ui_completes_in_evals(page, evals, prompt_version):
    open_prompt(page, prompt_version)
    page.get_by_role("button", name="Run v1").click()

    # the runs list polls evals until the run finishes
    row = page.locator("#runs .run-row").first
    expect(row).to_contain_text("completed", timeout=30_000)

    [run] = evals.get("/runs", params={"prompt_id": prompt_version["prompt_id"]}).json()
    assert run["prompt_version_id"] == prompt_version["id"]

    row.get_by_role("link", name=f"#{run['id']}").click()
    expect(page.locator("#run-title")).to_have_text(f"Run #{run['id']}")
    expect(page.locator(".fields")).to_contain_text("1 / 0 / 0")


def test_with_prompts_down_starting_a_run_shows_the_503_message(page, evals, prompt_version):
    open_prompt(page, prompt_version)
    run_button = page.get_by_role("button", name="Run v1")
    expect(run_button).to_be_enabled()

    with prompts_down():
        run_button.click()
        # evals answers 503 with a detail, and the UI shows it instead of failing silently
        expect(page.locator("#ticker")).to_contain_text("prompts service is unavailable")

    assert evals.get("/runs", params={"prompt_id": prompt_version["prompt_id"]}).json() == []
