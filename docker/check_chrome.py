"""Check that Chrome starts inside the image, the same way a scrape starts it.

Loads a page from memory, so it needs no network and never contacts Google:

    docker run --rm --entrypoint python google-reviews-scraper-pro /app/docker/check_chrome.py
"""

import copy
import sys
import tempfile
from pathlib import Path

from selenium.webdriver.common.by import By

from modules.config import DEFAULT_CONFIG
from modules.scraper import GoogleReviewsScraper

PAGE = "data:text/html,<title>check</title><h1 id='status'>chrome works</h1>"


def main() -> int:
    config = copy.deepcopy(DEFAULT_CONFIG)
    with tempfile.TemporaryDirectory() as tmp:
        config["db_path"] = str(Path(tmp) / "check.db")
        driver = GoogleReviewsScraper(config).setup_driver(headless=True)
        try:
            driver.get(PAGE)
            text = driver.find_element(By.ID, "status").text
            version = driver.capabilities.get("browserVersion", "unknown")
        finally:
            driver.quit()

    if text != "chrome works":
        print(f"Check failed: the page showed {text!r}", file=sys.stderr)
        return 1
    print(f"Check passed: Chrome {version} started and rendered a page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
