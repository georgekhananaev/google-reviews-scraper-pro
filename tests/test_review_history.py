"""Tests for audit trail and review history."""

import pytest

from modules.review_db import ReviewDB


@pytest.fixture
def db(tmp_path):
    """Fresh temp-file database for each test."""
    db_instance = ReviewDB(str(tmp_path / "test.db"))
    yield db_instance
    db_instance.close()


def _make_review(review_id="r1", text="Great place!", rating=5.0, likes=2,
                 lang="en", date="3 months ago", review_date="2025-06-15",
                 author="Test User", profile="http://profile", avatar="http://avatar",
                 owner_text="", photos=None):
    return {
        "review_id": review_id,
        "text": text,
        "rating": rating,
        "likes": likes,
        "lang": lang,
        "date": date,
        "review_date": review_date,
        "author": author,
        "profile": profile,
        "avatar": avatar,
        "owner_text": owner_text,
        "photos": photos or [],
    }


class TestReviewHistory:
    """Tests for the audit trail system."""

    def test_insert_logs_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        history = db.get_review_history("r1", "place1")
        assert len(history) >= 1
        assert history[0]["action"] == "insert"

    def test_update_logs_changed_fields(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        db.upsert_review("place1", _make_review(text="Updated text"))
        history = db.get_review_history("r1", "place1")
        update_entries = [h for h in history if h["action"] == "update"]
        assert len(update_entries) >= 1
        # changed_fields should contain hash changes
        entry = update_entries[0]
        assert entry["old_content_hash"] is not None
        assert entry["new_content_hash"] is not None
        assert entry["old_content_hash"] != entry["new_content_hash"]

    def test_soft_delete_logs_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        db.hide_review("r1", "place1")
        history = db.get_review_history("r1", "place1")
        actions = [h["action"] for h in history]
        assert "soft_delete" in actions

    def test_restore_logs_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        db.hide_review("r1", "place1")
        db.restore_review("r1", "place1")
        history = db.get_review_history("r1", "place1")
        actions = [h["action"] for h in history]
        assert "restore" in actions

    def test_get_review_history_ordered(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        db.upsert_review("place1", _make_review(text="Update 1"))
        db.upsert_review("place1", _make_review(text="Update 2"))
        history = db.get_review_history("r1", "place1")
        assert len(history) >= 3
        # Timestamps should be in ascending order
        timestamps = [h["timestamp"] for h in history]
        assert timestamps == sorted(timestamps)

    def test_get_session_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        session_id = db.start_session("place1")
        db.upsert_review("place1", _make_review("r1"), session_id)
        db.upsert_review("place1", _make_review("r2"), session_id)
        history = db.get_session_history(session_id)
        assert len(history) >= 2

    def test_history_preserves_old_and_new_hashes(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        db.upsert_review("place1", _make_review(text="Changed", rating=3.0))
        history = db.get_review_history("r1", "place1")
        update = [h for h in history if h["action"] == "update"]
        assert len(update) >= 1
        assert update[0]["old_content_hash"] is not None
        assert update[0]["new_content_hash"] is not None

    def test_actor_tracked(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        db.hide_review("r1", "place1")
        db.restore_review("r1", "place1")
        history = db.get_review_history("r1", "place1")
        actors = {h["actor"] for h in history}
        assert "scraper" in actors
        assert "cli_hide" in actors
        assert "cli_restore" in actors
