"""
Tests for the count fields:

- max_reviews limits how many reviews a run looks at, stored ones included
  ("check the newest N"), instead of counting everything already in the DB.
- places.total_reviews follows the visible reviews of a place.
- images_count reports the images on disk for the reviews a run handled.
"""

import pytest
from selenium.common.exceptions import StaleElementReferenceException

from modules.image_handler import ImageHandler
from modules.pipeline import PostScrapeRunner
from modules.review_db import ReviewDB
from modules.scraper import GoogleReviewsScraper


class Card:
    def __init__(self, review_id, stale=False):
        self.review_id = review_id
        self.stale = stale

    def get_attribute(self, name):
        if self.stale:
            raise StaleElementReferenceException()
        return self.review_id


collect = GoogleReviewsScraper._collect_fresh_cards


class TestMaxReviews:

    def test_counts_reviews_looked_at_not_reviews_stored(self):
        """571 stored, max 40: check the newest 40 (old behaviour stopped after 1 new)."""
        stored = {f"old{i}" for i in range(571)}
        cards = [Card("new0")] + [Card(f"old{i}") for i in range(60)]
        processed = set()
        fresh, already = collect(cards, processed, stored, max_reviews=40)
        assert len(processed) == 40
        assert [c.review_id for c in fresh] == ["new0"]
        assert already == 39

    def test_limit_spans_batches(self):
        processed = set()
        collect([Card(f"r{i}") for i in range(30)], processed, set(), max_reviews=40)
        fresh, _ = collect([Card(f"r{i}") for i in range(60)], processed, set(), max_reviews=40)
        assert len(processed) == 40
        assert len(fresh) == 10

    def test_zero_means_unlimited(self):
        processed = set()
        fresh, _ = collect([Card(f"r{i}") for i in range(100)], processed, set(), max_reviews=0)
        assert len(fresh) == 100

    def test_nested_duplicates_and_stale_cards_are_skipped(self):
        processed = set()
        cards = [Card("a"), Card("a"), Card("b", stale=True), Card("c"), Card(None)]
        fresh, already = collect(cards, processed, set(), max_reviews=0)
        assert [c.review_id for c in fresh] == ["a", "c"]
        assert already == 0


def review(i):
    return {"review_id": f"r{i}", "author": "A", "rating": 5, "text": f"t{i}", "lang": "en",
            "date": "1 day ago", "review_date": "2026-10-01T00:00:00+00:00"}


class TestPlaceTotal:

    @pytest.fixture
    def db(self, tmp_path):
        review_db = ReviewDB(str(tmp_path / "reviews.db"))
        review_db.upsert_place("p1", "Place", "https://maps.example/p1", "")
        yield review_db
        review_db.close()

    def total(self, db):
        return db.get_place("p1")["total_reviews"]

    def test_refresh_counts_visible_reviews(self, db):
        session_id = db.start_session("p1")
        for i in range(4):
            db.upsert_review("p1", review(i), session_id=session_id)
        assert self.total(db) == 0  # per-review upserts don't touch the counter
        assert db.refresh_place_total("p1") == 4
        assert self.total(db) == 4

    def test_hide_and_restore_update_total(self, db):
        for i in range(3):
            db.upsert_review("p1", review(i))
        db.refresh_place_total("p1")
        db.hide_review("r1", "p1")
        assert self.total(db) == 2
        db.restore_review("r1", "p1")
        assert self.total(db) == 3


class TestImageCount:

    PROFILE = "https://lh3.googleusercontent.com/a-/ALV-UjWe6IOUf5rVy4N7i=s120-c"

    def test_images_on_disk_are_counted_without_downloading(self, tmp_path):
        handler = ImageHandler({"image_dir": str(tmp_path), "download_images": True})
        handler.set_place_id("p1")
        handler.ensure_directories()
        (handler.profile_dir / handler.get_filename_from_url(self.PROFILE, True)).write_bytes(b"x")

        handler.download_all_images({"r1": {"review_id": "r1", "profile_picture": self.PROFILE}})
        assert handler.last_image_count == 1

    def test_runner_reports_none_when_downloads_are_off(self, tmp_path):
        runner = PostScrapeRunner({"image_dir": str(tmp_path), "download_images": False,
                                   "backup_to_json": False, "use_mongodb": False})
        try:
            assert runner.image_count() is None
        finally:
            runner.close()

    def test_runner_reports_zero_before_any_download(self, tmp_path):
        runner = PostScrapeRunner({"image_dir": str(tmp_path), "download_images": True,
                                   "backup_to_json": False, "use_mongodb": False})
        try:
            assert runner.image_count() == 0
        finally:
            runner.close()
