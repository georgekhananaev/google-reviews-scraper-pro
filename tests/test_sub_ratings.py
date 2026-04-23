"""Tests for sub-rating capture (issue #18)."""

import pytest

from modules.sub_rating_labels import canonicalize_category


class TestCanonicalization:
    def test_english_known(self):
        assert canonicalize_category("Service") == "service"
        assert canonicalize_category("Food") == "food"
        assert canonicalize_category("Cleanliness") == "cleanliness"

    def test_case_and_whitespace(self):
        assert canonicalize_category("  SERVICE  ") == "service"

    def test_french(self):
        assert canonicalize_category("cuisine") == "food"
        assert canonicalize_category("propreté") == "cleanliness"

    def test_german(self):
        assert canonicalize_category("Sauberkeit") == "cleanliness"
        assert canonicalize_category("Zimmer") == "rooms"

    def test_spanish(self):
        assert canonicalize_category("limpieza") == "cleanliness"

    def test_hebrew(self):
        assert canonicalize_category("שירות") == "service"

    def test_partial_match(self):
        # "Room cleanliness" should map to cleanliness via substring match
        result = canonicalize_category("Room cleanliness")
        assert result in ("cleanliness", "rooms")  # either is acceptable

    def test_unknown_category_empty(self):
        assert canonicalize_category("") == ""
        assert canonicalize_category("totally unknown xyz") == ""


class TestSubRatingsPersistence:
    """Verify sub_ratings flows through the DB layer."""

    def test_insert_with_sub_ratings(self, tmp_path):
        from modules.review_db import ReviewDB
        db = ReviewDB(str(tmp_path / "t.db"))
        place_id = db.upsert_place("place_1", "Test Hotel", "https://maps.example/1", None)
        session_id = db.start_session(place_id)
        db.upsert_review(place_id, {
            "review_id": "rev_1",
            "author": "Alice",
            "rating": 5,
            "text": "Great",
            "lang": "en",
            "date": "1 day ago",
            "review_date": "2025-06-15T00:00:00+00:00",
            "photos": [],
            "sub_ratings": {"service": 5, "food": 4, "_other": {"drinks": 5}},
        }, session_id=session_id)

        review = db.get_review("rev_1", place_id)
        assert review is not None
        sub = review.get("sub_ratings")
        assert isinstance(sub, dict)
        assert sub.get("service") == 5
        assert sub.get("food") == 4
        assert sub.get("_other", {}).get("drinks") == 5
        db.close()

    def test_update_merges_sub_ratings(self, tmp_path):
        from modules.review_db import ReviewDB
        db = ReviewDB(str(tmp_path / "t.db"))
        place_id = db.upsert_place("place_1", "Test", "https://maps.example/1", None)
        session_id = db.start_session(place_id)

        # First insert
        db.upsert_review(place_id, {
            "review_id": "rev_1",
            "author": "Bob",
            "rating": 4,
            "text": "Good",
            "lang": "en",
            "date": "2 days ago",
            "review_date": "2025-06-14T00:00:00+00:00",
            "sub_ratings": {"service": 4},
        }, session_id=session_id)

        # Second scrape captures additional sub-rating
        db.upsert_review(place_id, {
            "review_id": "rev_1",
            "author": "Bob",
            "rating": 5,  # changed → triggers update
            "text": "Better now",
            "lang": "en",
            "date": "2 days ago",
            "review_date": "2025-06-14T00:00:00+00:00",
            "sub_ratings": {"food": 5},
        }, session_id=session_id)

        review = db.get_review("rev_1", place_id)
        sub = review.get("sub_ratings") or {}
        # Merge: both keys preserved
        assert sub.get("service") == 4
        assert sub.get("food") == 5
        db.close()
