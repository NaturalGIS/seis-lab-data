import re

import pytest
from playwright.sync_api import expect

# This module deals with playwright tracing options manually because some
# tests need the `authenticated_context` fixture, which creates a new
# browser context different from the default one.
_TRACING_VALUES = ("on", "retain-on-failure")


def pytest_addoption(parser):
    parser.addoption(
        "--user-email",
        default=None,
        help="Email address of the user to authenticate with",
    )
    parser.addoption(
        "--user-password",
        default=None,
        help="Password of the user to authenticate with",
    )


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="session")
def auth_credentials(request):
    email = request.config.getoption("--user-email")
    password = request.config.getoption("--user-password")
    if not email or not password:
        pytest.skip(
            "Authentication credentials not provided. Pass the --user-email "
            "and --user-password CLI options."
        )
    return email, password


@pytest.fixture(scope="session")
def authenticated_context(browser, auth_credentials, base_url, request):
    context = browser.new_context(base_url=base_url)

    if (tracing_value := request.config.getoption("--tracing")) in _TRACING_VALUES:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

    page = context.new_page()

    try:
        page.goto("/")
        page.get_by_test_id("login-nav").click()
        email, password = auth_credentials
        page.get_by_placeholder(re.compile("email", re.IGNORECASE)).fill(email)
        page.get_by_placeholder(
            re.compile("please enter your password", re.IGNORECASE)
        ).fill(password)
        page.get_by_text(re.compile("log in", re.IGNORECASE)).click()
        expect(page.get_by_test_id("user-menu")).to_be_visible()
        storage_state = context.storage_state()

        if tracing_value in _TRACING_VALUES:
            context.tracing.stop()

    except:
        if tracing_value in _TRACING_VALUES:
            trace_path = "test-results/auth-setup-trace.zip"
            context.tracing.stop(path=trace_path)
        raise
    finally:
        page.close()
        context.close()

    yield storage_state


@pytest.fixture(scope="function")
def authenticated_page(browser, authenticated_context, base_url, request):
    context = browser.new_context(
        storage_state=authenticated_context, base_url=base_url
    )

    if (tracing_value := request.config.getoption("--tracing")) in _TRACING_VALUES:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

    page = context.new_page()
    yield page

    if tracing_value in _TRACING_VALUES:
        if tracing_value == "on" or (
            tracing_value == "retain-on-failure" and request.node.rep_call.failed
        ):
            trace_path = f"test-results/{request.node.name}-trace.zip"
            context.tracing.stop(path=trace_path)
        else:
            context.tracing.stop()
    context.close()


@pytest.fixture(scope="function")
def fresh_authenticated_page(browser, auth_credentials, base_url):
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    page.goto("/")
    page.get_by_test_id("login-nav").click()
    email, password = auth_credentials
    page.get_by_placeholder(re.compile("email", re.IGNORECASE)).fill(email)
    page.get_by_placeholder(
        re.compile("please enter your password", re.IGNORECASE)
    ).fill(password)
    page.get_by_text(re.compile("log in", re.IGNORECASE)).click()
    expect(page.get_by_test_id("user-menu")).to_be_visible()
    yield page
    context.close()
