"""
Regression tests for Reviews tab detection (issues #21, #17, #15).

Tests the scoring-based `is_reviews_tab()` directly against mock WebElements.
The crucial scenarios:

- Menu at data-tab-index="1": must NOT be accepted (previous bug)
- Reviews at any index with matching aria-label: accepted
- French/German/Hebrew review keywords: accepted
- Empty tab: rejected
"""

import pytest

from modules.scraper import (
    GoogleReviewsScraper,
    NON_REVIEW_TAB_WORDS,
    REVIEW_WORDS,
    _text_contains_any,
)


class MockTab:
    """Minimal WebElement stand-in for is_reviews_tab scoring tests."""

    def __init__(self, aria_label="", text="", data_tab_index="",
                 href="", cls="", data_href=""):
        self._attrs = {
            "aria-label": aria_label,
            "data-tab-index": data_tab_index,
            "href": href,
            "data-href": data_href,
            "data-url": "",
            "data-target": "",
            "class": cls,
        }
        self.text = text

    def get_attribute(self, name):
        return self._attrs.get(name, "")


@pytest.fixture
def scraper():
    """Minimal scraper instance without launching Chrome."""
    s = GoogleReviewsScraper.__new__(GoogleReviewsScraper)
    s.config = {}
    return s


# ---------------------------------------------------------------------------
# _text_contains_any primitive
# ---------------------------------------------------------------------------

class TestKeywordMatching:
    def test_review_english(self):
        assert _text_contains_any("reviews for starbucks", REVIEW_WORDS)

    def test_review_french(self):
        assert _text_contains_any("avis de la boulangerie", REVIEW_WORDS)

    def test_review_german(self):
        assert _text_contains_any("bewertungen", REVIEW_WORDS)

    def test_review_hebrew(self):
        assert _text_contains_any("ביקורות על העסק", REVIEW_WORDS)

    def test_menu_matches_non_review(self):
        assert _text_contains_any("menu", NON_REVIEW_TAB_WORDS)
        assert not _text_contains_any("menu", REVIEW_WORDS)

    def test_photos_matches_non_review(self):
        assert _text_contains_any("photos", NON_REVIEW_TAB_WORDS)

    def test_empty_matches_neither(self):
        assert not _text_contains_any("", REVIEW_WORDS)
        assert not _text_contains_any("", NON_REVIEW_TAB_WORDS)


# ---------------------------------------------------------------------------
# is_reviews_tab scoring (regression for #21)
# ---------------------------------------------------------------------------

class TestTabDetection:

    def test_menu_at_index_1_rejected(self, scraper):
        """The bug from issue #21: Menu tab sits at data-tab-index=1."""
        tab = MockTab(aria_label="Menu", text="Menu", data_tab_index="1")
        assert not scraper.is_reviews_tab(tab)

    def test_reviews_at_index_1_accepted(self, scraper):
        tab = MockTab(
            aria_label="Reviews for Starbucks",
            text="Reviews",
            data_tab_index="1",
        )
        assert scraper.is_reviews_tab(tab)

    def test_reviews_at_index_2_accepted(self, scraper):
        tab = MockTab(
            aria_label="Reviews for Bakery",
            text="Reviews",
            data_tab_index="2",
        )
        assert scraper.is_reviews_tab(tab)

    def test_french_avis_accepted(self, scraper):
        tab = MockTab(aria_label="Avis sur la boulangerie", text="Avis",
                      data_tab_index="1")
        assert scraper.is_reviews_tab(tab)

    def test_german_bewertungen_accepted(self, scraper):
        tab = MockTab(aria_label="Bewertungen zum Restaurant", text="Bewertungen")
        assert scraper.is_reviews_tab(tab)

    def test_hebrew_reviews_accepted(self, scraper):
        tab = MockTab(aria_label="ביקורות על Starbucks", text="ביקורות")
        assert scraper.is_reviews_tab(tab)

    def test_photos_at_index_1_rejected(self, scraper):
        tab = MockTab(aria_label="Photos", text="Photos", data_tab_index="1")
        assert not scraper.is_reviews_tab(tab)

    def test_overview_rejected(self, scraper):
        tab = MockTab(aria_label="Overview", text="Overview", data_tab_index="1")
        assert not scraper.is_reviews_tab(tab)

    def test_empty_tab_rejected(self, scraper):
        tab = MockTab()
        assert not scraper.is_reviews_tab(tab)

    def test_href_with_review_keyword_accepted(self, scraper):
        tab = MockTab(data_href="/place/reviews/")
        assert scraper.is_reviews_tab(tab)

    def test_bare_index_insufficient(self, scraper):
        """data-tab-index='1' alone without any keyword must NOT match."""
        tab = MockTab(data_tab_index="1")
        assert not scraper.is_reviews_tab(tab)

    def test_threshold_config_override(self, scraper):
        """Low threshold accepts even bare index (for operators who want
        old behavior — configurable, not default)."""
        scraper.config = {"adaptive": {"tab_detection_threshold": 0.0}}
        # Empty tab still scores 0, stays rejected.
        tab = MockTab(data_tab_index="1", cls="review")
        assert scraper.is_reviews_tab(tab)
