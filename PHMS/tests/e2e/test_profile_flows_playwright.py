import os

import pytest


pytestmark = pytest.mark.e2e


def _env_or_skip(name):
    value = os.getenv(name)
    if not value:
        pytest.skip(f'Missing {name}; skipping e2e profile test')
    return value


def _login(page, base_url, email, password):
    page.goto(f'{base_url}/login', wait_until='domcontentloaded')
    page.fill('#email', email)
    page.fill('#password', password)
    page.click('#loginBtn')
    page.wait_for_url('**/dashboard', timeout=20000)


@pytest.fixture(scope='module')
def sync_playwright_api():
    return pytest.importorskip('playwright.sync_api')


@pytest.fixture(scope='module')
def e2e_profile_page(sync_playwright_api):
    base_url = _env_or_skip('PHMS_E2E_BASE_URL')
    email = _env_or_skip('PHMS_E2E_EMAIL')
    password = _env_or_skip('PHMS_E2E_PASSWORD')

    with sync_playwright_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(base_url=base_url)
        page = context.new_page()

        _login(page, base_url, email, password)
        page.goto(f'{base_url}/profile', wait_until='networkidle')
        page.wait_for_selector('#openUpdateBtn', timeout=15000)

        yield page

        context.close()
        browser.close()


def test_profile_modal_open_and_escape_close(e2e_profile_page):
    page = e2e_profile_page

    page.click('#openUpdateBtn')
    page.wait_for_selector('#updateModal[aria-hidden="false"]', timeout=8000)

    page.keyboard.press('Escape')
    page.wait_for_selector('#updateModal[aria-hidden="true"]', timeout=8000)


def test_profile_update_flow_with_mocked_api(e2e_profile_page):
    page = e2e_profile_page

    page.route(
        '**/update-profile',
        lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body='{"success":true,"message":"Profile updated successfully","updated":{"username":"qa-user","gender":"Other","age":29,"height":172.1,"weight":73.4,"bmi":24.8},"completion":100}',
        ),
    )

    page.click('#openUpdateBtn')
    page.wait_for_selector('#updateModal[aria-hidden="false"]', timeout=8000)

    page.fill('#edit_username', 'qa-user')
    page.select_option('#edit_gender', 'Other')
    page.fill('#edit_age', '29')
    page.fill('#edit_height', '172.1')
    page.fill('#edit_weight', '73.4')

    page.click('[data-action="submit-profile-update"]')

    page.wait_for_selector('#updateModal[aria-hidden="true"]', timeout=8000)
    assert page.locator('#display_username').inner_text() == 'qa-user'
    assert '29 years' in page.locator('#info_age').inner_text()


def test_password_change_flow_shows_server_error_message(e2e_profile_page):
    page = e2e_profile_page

    page.route(
        '**/change-password',
        lambda route: route.fulfill(
            status=400,
            content_type='application/json',
            body='{"success":false,"message":"Current password is incorrect"}',
        ),
    )

    page.click('#openPasswordBtn')
    page.wait_for_selector('#passwordModal[aria-hidden="false"]', timeout=8000)

    page.fill('#current_password', 'wrong-password')
    page.fill('#new_password', 'Password123')
    page.fill('#confirm_password', 'Password123')

    page.click('[data-action="submit-password-change"]')

    page.wait_for_timeout(500)
    assert page.locator('#passwordModal').get_attribute('aria-hidden') == 'false'
