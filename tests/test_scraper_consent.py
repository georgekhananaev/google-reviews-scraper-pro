"""
Tests for the full-page Google consent redirect (PR #28).

EU visitors can land on consent.google.com instead of Google Maps. The
scraper has to notice that page by its hostname and click through it.
No browser is launched: the driver and its buttons are small stand-ins.
"""

import pytest

from modules import scraper as scraper_module
from modules.scraper import GoogleReviewsScraper, _is_google_consent_url

CONSENT_URL = (
    "https://consent.google.com/m?continue="
    "https://www.google.com/maps/place/Some+Place&gl=IT&hl=it"
)
MAPS_URL = "https://www.google.com/maps/place/Some+Place/@41.9,12.5,17z"


class MockButton:
    def __init__(self, displayed=True):
        self._displayed = displayed
        self.clicked = False

    def is_displayed(self):
        return self._displayed

    def click(self):
        self.clicked = True


class MockDriver:
    """Returns the given buttons for every lookup and counts the lookups."""

    def __init__(self, url, buttons=()):
        self.current_url = url
        self._buttons = list(buttons)
        self.lookups = 0

    def find_elements(self, by, value):
        self.lookups += 1
        return self._buttons


@pytest.fixture
def scraper(monkeypatch):
    """Minimal scraper instance without launching Chrome, and without waits."""
    monkeypatch.setattr(scraper_module.time, "sleep", lambda seconds: None)
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
        driver = MockDriver(MAPS_URL, [MockButton()])
        assert scraper.handle_google_consent(driver) is False
        assert driver.lookups == 0

    def test_clicks_visible_button_on_consent_page(self, scraper):
        hidden, visible = MockButton(displayed=False), MockButton()
        driver = MockDriver(CONSENT_URL, [hidden, visible])
        assert scraper.handle_google_consent(driver) is True
        assert visible.clicked
        assert not hidden.clicked

    def test_reports_failure_when_no_button_is_found(self, scraper):
        driver = MockDriver(CONSENT_URL, [])
        assert scraper.handle_google_consent(driver) is False
        assert driver.lookups > 0

    def test_dismiss_cookies_handles_consent_page(self, scraper):
        button = MockButton()
        driver = MockDriver(CONSENT_URL, [button])
        assert scraper.dismiss_cookies(driver) is True
        assert button.clicked
