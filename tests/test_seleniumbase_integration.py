"""
Tests for SeleniumBase UC Mode integration.
Verifies that the driver setup works correctly with the new library.
"""

import pytest
from modules.scraper import GoogleReviewsScraper


def test_seleniumbase_driver_creation():
    """Test that SeleniumBase driver can be created successfully"""
    config = {
        "url": "https://maps.app.goo.gl/test",
        "headless": True,
        "use_mongodb": False,
        "backup_to_json": False
    }

    scraper = GoogleReviewsScraper(config)

    # Test driver creation
    driver = None
    try:
        driver = scraper.setup_driver(headless=True)
        assert driver is not None
        assert driver.name == "chrome"

        # Verify driver can navigate
        driver.get("https://www.google.com")
        assert "google" in driver.current_url.lower()

    finally:
        if driver:
            driver.quit()


def test_seleniumbase_driver_headless_mode():
    """Test that headless mode works correctly"""
    config = {
        "url": "https://maps.app.goo.gl/test",
        "headless": True,
        "use_mongodb": False,
        "backup_to_json": False
    }

    scraper = GoogleReviewsScraper(config)
    driver = None

    try:
        driver = scraper.setup_driver(headless=True)
        assert driver is not None

        # In headless mode, window size should still be set
        size = driver.get_window_size()
        assert size['width'] == 1400
        assert size['height'] == 900

    finally:
        if driver:
            driver.quit()


def test_seleniumbase_driver_nonheadless_mode():
    """Test that non-headless mode works correctly"""
    config = {
        "url": "https://maps.app.goo.gl/test",
        "headless": False,
        "use_mongodb": False,
        "backup_to_json": False
    }

    scraper = GoogleReviewsScraper(config)
    driver = None

    try:
        driver = scraper.setup_driver(headless=False)
        assert driver is not None
        assert driver.name == "chrome"

    finally:
        if driver:
            driver.quit()


@pytest.mark.skip(reason="Integration test - requires network access")
def test_seleniumbase_google_maps_access():
    """Test that driver can access Google Maps (integration test)"""
    config = {
        "url": "https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9",
        "headless": True,
        "use_mongodb": False,
        "backup_to_json": False
    }

    scraper = GoogleReviewsScraper(config)
    driver = None

    try:
        driver = scraper.setup_driver(headless=True)
        driver.get(config["url"])

        # Wait for redirect to Google Maps
        import time
        time.sleep(3)

        assert "google.com/maps" in driver.current_url

    finally:
        if driver:
            driver.quit()
