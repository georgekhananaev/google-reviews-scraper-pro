"""
Tests for detecting a capped review list (Google's limited view).

Signed-out browsers can get only the first few reviews followed by a
"See more reviews (N)" button. _capped_list() must find that button after
the last card and read N, and must ignore other buttons with counts (topic
chips above the list, photo counters inside cards).

Runs the detection script in a real headless Chrome on a local page.
"""

from urllib.parse import quote

import pytest
from selenium.webdriver.common.by import By

from modules.scraper import GoogleReviewsScraper

CARD = '<div class="jftiEf" data-review-id="{i}"><button>Like</button><button>+3</button></div>'


def page(before="", after="", cards=5):
    body = "".join(CARD.format(i=i) for i in range(cards))
    return f'<div id="pane">{before}{body}{after}</div>'


@pytest.fixture(scope="module")
def driver():
    from seleniumbase import Driver

    d = Driver(headless=True)
    yield d
    d.quit()


@pytest.fixture
def scraper():
    s = GoogleReviewsScraper.__new__(GoogleReviewsScraper)
    s.config = {}
    return s


def load(driver, html):
    driver.get("data:text/html;charset=utf-8," + quote(html))
    return driver.find_element(By.ID, "pane")


def test_see_more_button_after_list(driver, scraper):
    pane = load(driver, page(after='<button aria-label="See more reviews (741)">See more reviews (741)</button>'))
    button, held_back = scraper._capped_list(driver, pane)
    assert held_back == 741
    assert "See more" in button.text


def test_thousands_separator(driver, scraper):
    pane = load(driver, page(after="<button>ดูรีวิวเพิ่มเติม (5,113)</button>"))
    assert scraper._capped_list(driver, pane)[1] == 5113


def test_full_list_without_button(driver, scraper):
    assert scraper._capped_list(driver, load(driver, page())) is None


def test_topic_chips_before_list_ignored(driver, scraper):
    pane = load(driver, page(before="<button>service (29)</button><button>price (12)</button>"))
    assert scraper._capped_list(driver, pane) is None


def test_count_inside_card_ignored(driver, scraper):
    pane = load(driver, page(after='<div data-review-id="x"><button>Photos (3)</button></div>'))
    assert scraper._capped_list(driver, pane) is None
