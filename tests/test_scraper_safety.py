"""
Tests for the checks that keep the scraper on the right tab and button.

- verify_reviews_tab_clicked(): only the selected Reviews tab (or the
  reviews URL marker) counts; review snippets on Overview do not (issue #25).
- _is_sort_button(): only a control in the place panel that names sorting;
  the rating "info" button, review-card buttons and buttons outside the
  panel are rejected.
"""

import pytest

from modules.scraper import GoogleReviewsScraper


class FakeElement:
    def __init__(self, text="", aria="", cls="", selected=None, index="",
                 displayed=True, in_main=True, in_card=False,
                 popup=None, expanded=None, jsaction=""):
        self.text = text
        self._attrs = {"aria-label": aria, "class": cls, "aria-selected": selected,
                       "data-tab-index": index, "aria-haspopup": popup,
                       "aria-expanded": expanded, "jsaction": jsaction}
        self._displayed = displayed
        self._in_main = in_main
        self._in_card = in_card

    def get_attribute(self, name):
        return self._attrs.get(name)

    def is_displayed(self):
        return self._displayed

    def is_enabled(self):
        return True

    def find_elements(self, by, query):
        if "data-review-id" in query:
            return [self] if self._in_card else []
        if "role='main'" in query:
            return [self] if self._in_main else []
        return []


class FakeDriver:
    def __init__(self, url="https://www.google.com/maps/place/x", tabs=(), cards=0):
        self.current_url = url
        self._tabs = list(tabs)
        self._cards = cards

    def find_elements(self, by, query):
        if query == '[role="tab"]':
            return self._tabs
        if query == "div[data-review-id]":
            return [object()] * self._cards
        return []


@pytest.fixture
def scraper():
    s = GoogleReviewsScraper.__new__(GoogleReviewsScraper)
    s.config = {}
    return s


def overview(selected):
    return FakeElement(text="Overview", aria="Overview of Joe's Diner",
                       selected="true" if selected else "false", index="0")


def reviews(selected):
    return FakeElement(text="Reviews", aria="Reviews for Joe's Diner",
                       selected="true" if selected else "false", index="1")


class TestVerifyReviewsTab:

    def test_overview_selected_with_review_snippets_is_not_reviews(self, scraper):
        driver = FakeDriver(tabs=[overview(True), reviews(False)], cards=3)
        assert not scraper.verify_reviews_tab_clicked(driver)

    def test_reviews_selected(self, scraper):
        driver = FakeDriver(tabs=[overview(False), reviews(True)])
        assert scraper.verify_reviews_tab_clicked(driver)

    def test_reviews_url_marker(self, scraper):
        driver = FakeDriver(url="https://www.google.com/maps/place/x/data=!4m8!3m7!1s0x1:0x2!9m1!1b1",
                            tabs=[overview(True)])
        assert scraper.verify_reviews_tab_clicked(driver)

    def test_layout_without_tabs_uses_cards(self, scraper):
        assert scraper.verify_reviews_tab_clicked(FakeDriver(cards=5))
        assert not scraper.verify_reviews_tab_clicked(FakeDriver(cards=0))


class TestSortButton:

    @pytest.mark.parametrize("text, aria", [
        ("Sort", "Sort reviews"),
        ("Ordina", "Ordina recensioni"),
        ("Trier", "Trier les avis"),
        ("Ordenar", "Ordenar reseñas"),
        ("", "จัดเรียงรีวิว"),
    ])
    def test_sort_chip_in_any_language(self, scraper, text, aria):
        assert scraper._is_sort_button(FakeElement(text=text, aria=aria))

    def test_dropdown_class_accepted(self, scraper):
        assert scraper._is_sort_button(FakeElement(text="Most relevant", cls="HQzyZ"))

    def test_current_order_dropdown_accepted(self, scraper):
        """Thai UI, captured live: the dropdown shows "Most relevant"."""
        assert scraper._is_sort_button(FakeElement(
            text="เกี่ยวข้องที่สุด", aria="เกี่ยวข้องที่สุด", cls="FNe70d",
            popup="true", expanded="false", jsaction="pane.wfvdle83; keydown:pane.wfvdle83"))

    @pytest.mark.parametrize("aria", ["Informazioni", "ข้อมูล", "Information"])
    def test_info_button_with_popup_rejected(self, scraper, aria):
        """Master picked this one in the Italian UI and lost the review list."""
        assert not scraper._is_sort_button(FakeElement(
            aria=aria, cls="oGrB9e", popup="true",
            jsaction="pane.wfvdle19.reviewlegaldisclosure.toggle; focus:pane.focus"))

    def test_disclosure_toggle_rejected_even_with_text(self, scraper):
        assert not scraper._is_sort_button(FakeElement(
            text="Info", popup="true", expanded="false",
            jsaction="pane.wfvdle19.reviewlegaldisclosure.toggle"))

    def test_button_inside_review_card_rejected(self, scraper):
        assert not scraper._is_sort_button(FakeElement(aria="Sort", in_card=True))

    def test_button_outside_place_panel_rejected(self, scraper):
        assert not scraper._is_sort_button(FakeElement(aria="Sort", in_main=False))

    def test_hidden_button_rejected(self, scraper):
        assert not scraper._is_sort_button(FakeElement(aria="Sort reviews", displayed=False))

    def test_place_name_does_not_count(self, scraper):
        scraper._place_name = "Sunset Beach Resort"
        assert not scraper._is_sort_button(FakeElement(aria="Share Sunset Beach Resort"))
