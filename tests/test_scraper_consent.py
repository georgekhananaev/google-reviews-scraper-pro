"""
Tests for the full-page Google consent redirect (PR #28).

EU visitors can land on consent.google.com instead of Google Maps. The
scraper has to notice that page by its hostname, click through it and wait
until the browser has left it. No browser is launched: the driver and its
buttons are small stand-ins.
"""

import pytest

from modules import scraper as scraper_module
from modules.scraper import (
    CONSENT_ACCEPT_BTN,
    CONSENT_FALLBACK_BTN,
    GoogleReviewsScraper,
    _is_google_consent_url,
)

CONSENT_URL = (
    "https://consent.google.com/m?continue="
    "https://www.google.com/maps/place/Some+Place&gl=IT&hl=it"
)
MAPS_URL = "https://www.google.com/maps/place/Some+Place/@41.9,12.5,17z"


class MockButton:
    """A button that can send the driver on to Maps when clicked."""

    def __init__(self, driver=None, displayed=True):
        self._driver = driver
        self._displayed = displayed
        self.clicked = False

    def is_displayed(self):
        return self._displayed

    def click(self):
        self.clicked = True
        if self._driver is not None:
            self._driver.current_url = MAPS_URL


class MockDriver:
    """Serves buttons per CSS selector and records the selectors asked for."""

    def __init__(self, url, consent_on=None):
        self.current_url = url
        self.buttons = {}
        self.lookups = []
        self._consent_on = consent_on

    def get(self, url):
        redirected = self._consent_on is not None and self._consent_on in url
        self.current_url = CONSENT_URL if redirected else url

    def find_elements(self, by, value):
        self.lookups.append(value)
        return self.buttons.get(value, [])


class ImmediateWait:
    """Stand-in for WebDriverWait in navigate_to_place: checks once."""

    def __init__(self, driver):
        self._driver = driver

    def until(self, method):
        return method(self._driver)


@pytest.fixture
def scraper(monkeypatch):
    """Minimal scraper instance without launching Chrome, and without waits."""
    monkeypatch.setattr(scraper_module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper_module, "CONSENT_WAIT_SECONDS", 0.2)
    s = GoogleReviewsScraper.__new__(GoogleReviewsScraper)
    s.config = {}
    return s


class TestConsentUrl:
    def test_consent_page(self):
        assert _is_google_consent_url(CONSENT_URL)

    def test_hostname_is_case_insensitive(self):
        assert _is_google_consent_url("https://CONSENT.Google.com/m?hl=it")

    def test_maps_page(self):
        assert not _is_google_consent_url(MAPS_URL)

    def test_consent_host_only_in_query_string(self):
        url = "https://www.google.com/maps?continue=https://consent.google.com/m"
        assert not _is_google_consent_url(url)

    def test_lookalike_host(self):
        assert not _is_google_consent_url("https://consent.google.com.example.org/m")

    @pytest.mark.parametrize("url", ["", None, "not a url", "http://[bad"])
    def test_unusable_url(self, url):
        assert not _is_google_consent_url(url)


class TestHandleGoogleConsent:
    def test_does_nothing_on_maps_page(self, scraper):
        driver = MockDriver(MAPS_URL)
        driver.buttons[CONSENT_ACCEPT_BTN] = [MockButton(driver)]
        assert scraper.handle_google_consent(driver) is False
        assert driver.lookups == []

    def test_clicks_accept_button_and_waits_to_leave(self, scraper):
        driver = MockDriver(CONSENT_URL)
        hidden, accept = MockButton(driver, displayed=False), MockButton(driver)
        driver.buttons[CONSENT_ACCEPT_BTN] = [hidden, accept]
        assert scraper.handle_google_consent(driver) is True
        assert accept.clicked
        assert not hidden.clicked
        assert driver.lookups == [CONSENT_ACCEPT_BTN]
        assert driver.current_url == MAPS_URL

    def test_falls_back_to_consent_form_button(self, scraper):
        driver = MockDriver(CONSENT_URL)
        form_button = MockButton(driver)
        driver.buttons[CONSENT_FALLBACK_BTN] = [form_button]
        assert scraper.handle_google_consent(driver) is True
        assert form_button.clicked
        assert driver.lookups == [CONSENT_ACCEPT_BTN, CONSENT_FALLBACK_BTN]

    def test_reports_failure_when_no_button_is_found(self, scraper):
        driver = MockDriver(CONSENT_URL)
        assert scraper.handle_google_consent(driver) is False

    def test_reports_failure_when_the_page_does_not_change(self, scraper):
        driver = MockDriver(CONSENT_URL)
        stuck = MockButton(driver=None)
        driver.buttons[CONSENT_ACCEPT_BTN] = [stuck]
        assert scraper.handle_google_consent(driver) is False
        assert stuck.clicked

    def test_dismiss_cookies_handles_consent_page(self, scraper):
        driver = MockDriver(CONSENT_URL)
        accept = MockButton(driver)
        driver.buttons[CONSENT_ACCEPT_BTN] = [accept]
        assert scraper.dismiss_cookies(driver) is True
        assert accept.clicked


class TestNavigateToPlace:
    def test_consent_after_the_search_url_is_handled(self, scraper, monkeypatch):
        """Long /maps/place/ URLs load no page before the search URL (PR #28)."""
        driver = MockDriver(MAPS_URL, consent_on="/maps/search/")
        accept = MockButton(driver)
        driver.buttons[CONSENT_ACCEPT_BTN] = [accept]
        monkeypatch.setattr(scraper, "dismiss_cookies", lambda d: False)
        monkeypatch.setattr(scraper, "_is_limited_view", lambda d: False)

        assert scraper.navigate_to_place(driver, MAPS_URL, ImmediateWait(driver))
        assert accept.clicked
