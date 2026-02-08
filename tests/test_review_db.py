"""Tests for ReviewDB — SQLite storage layer."""

import json
import os
import threading

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
    """Helper to build a raw review dict."""
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


class TestPlaceOperations:
    """Place management tests."""

    def test_upsert_place_insert(self, db):
        pid = db.upsert_place("place1", "Test Place", "http://original")
        assert pid == "place1"
        place = db.get_place("place1")
        assert place["place_name"] == "Test Place"

    def test_upsert_place_update(self, db):
        db.upsert_place("place1", "Test Place", "http://original")
        db.upsert_place("place1", "Updated Place", "http://original")
        place = db.get_place("place1")
        assert place["place_name"] == "Updated Place"

    def test_upsert_place_alias_resolution(self, db):
        db.upsert_place("place1", "Place One", "http://orig1",
                         resolved_url="https://google.com/maps/place/test")
        canonical = db.upsert_place("place2", "Place Two", "http://orig2",
                                     resolved_url="https://google.com/maps/place/test")
        assert canonical == "place1"

    def test_get_place_by_alias(self, db):
        db.upsert_place("place1", "Place One", "http://orig1",
                         resolved_url="https://google.com/maps/place/test")
        db.upsert_place("place2", "Place Two", "http://orig2",
                         resolved_url="https://google.com/maps/place/test")
        place = db.get_place("place2")
        assert place["place_id"] == "place1"

    def test_get_place_not_found(self, db):
        assert db.get_place("nonexistent") is None

    def test_list_places_empty(self, db):
        assert db.list_places() == []

    def test_list_places_multiple(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        places = db.list_places()
        assert len(places) == 2


class TestReviewOperations:
    """Review CRUD and dedup tests."""

    def test_upsert_review_new(self, db):
        db.upsert_place("place1", "Test", "http://test")
        result = db.upsert_review("place1", _make_review())
        assert result == "new"
        review = db.get_review("r1", "place1")
        assert review is not None
        assert review["rating"] == 5.0

    def test_upsert_review_update_changed(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        result = db.upsert_review("place1", _make_review(text="Updated text"))
        assert result == "updated"

    def test_upsert_review_unchanged(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        session_id = db.start_session("place1")
        result = db.upsert_review("place1", _make_review(), session_id=session_id)
        assert result == "unchanged"

    def test_upsert_review_merge_preserves_languages(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review(lang="en", text="English text"))
        db.upsert_review("place1", _make_review(lang="he", text="טקסט בעברית"))
        review = db.get_review("r1", "place1")
        assert "en" in review["review_text"]
        assert "he" in review["review_text"]

    def test_get_review_ids_empty(self, db):
        db.upsert_place("place1", "Test", "http://test")
        assert db.get_review_ids("place1") == set()

    def test_get_review_ids_populated(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.upsert_review("place1", _make_review("r2"))
        ids = db.get_review_ids("place1")
        assert ids == {"r1", "r2"}

    def test_get_review_ids_excludes_deleted(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.upsert_review("place1", _make_review("r2"))
        db.hide_review("r1", "place1")
        ids = db.get_review_ids("place1")
        assert ids == {"r2"}

    def test_get_review_ids_isolated_by_place(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        db.upsert_review("p1", _make_review("r1"))
        db.upsert_review("p2", _make_review("r2"))
        assert db.get_review_ids("p1") == {"r1"}
        assert db.get_review_ids("p2") == {"r2"}

    def test_flush_batch_mixed(self, db):
        db.upsert_place("place1", "Test", "http://test")
        # Insert first review
        db.upsert_review("place1", _make_review("r1"))
        session_id = db.start_session("place1")
        # Batch with one existing unchanged, one new, one updated
        batch = [
            _make_review("r1"),  # unchanged
            _make_review("r2"),  # new
        ]
        stats = db.flush_batch("place1", batch, session_id)
        assert stats["new"] == 1
        assert stats["unchanged"] == 1

    def test_flush_batch_empty(self, db):
        db.upsert_place("place1", "Test", "http://test")
        session_id = db.start_session("place1")
        stats = db.flush_batch("place1", [], session_id)
        assert stats["new"] == 0


class TestDualHash:
    """Tests for content and engagement hash behavior in DB context."""

    def test_content_change_detected(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        new_hash = ReviewDB.compute_content_hash("Different text", 5.0, "3 months ago")
        assert db.review_changed("r1", "place1", new_hash)

    def test_likes_only_change_not_content_change(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        same_hash = ReviewDB.compute_content_hash("Great place!", 5.0, "3 months ago")
        assert not db.review_changed("r1", "place1", same_hash)

    def test_review_changed_not_found(self, db):
        db.upsert_place("place1", "Test", "http://test")
        assert db.review_changed("nonexistent", "place1", "somehash")


class TestStopOnMatch:
    """Tests for N-consecutive-unchanged stop logic."""

    def test_should_stop_after_threshold(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        h = ReviewDB.compute_content_hash("Great place!", 5.0, "3 months ago")
        assert db.should_stop("r1", "place1", h, consecutive_unchanged=2, threshold=3)

    def test_should_not_stop_before_threshold(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        h = ReviewDB.compute_content_hash("Great place!", 5.0, "3 months ago")
        assert not db.should_stop("r1", "place1", h, consecutive_unchanged=0, threshold=3)

    def test_should_not_stop_on_changed_review(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review())
        h = ReviewDB.compute_content_hash("Different text", 5.0, "3 months ago")
        assert not db.should_stop("r1", "place1", h, consecutive_unchanged=5, threshold=3)

    def test_should_not_stop_new_review(self, db):
        db.upsert_place("place1", "Test", "http://test")
        h = ReviewDB.compute_content_hash("New text", 5.0, "3 months ago")
        # New review = changed, should not stop
        assert not db.should_stop("new_review", "place1", h, consecutive_unchanged=5, threshold=3)


class TestStaleDetection:
    """Tests for stale review detection."""

    def test_mark_stale_flags_missing_reviews(self, db):
        db.upsert_place("place1", "Test", "http://test")
        session_id = db.start_session("place1")
        db.upsert_review("place1", _make_review("r1"), session_id)
        db.upsert_review("place1", _make_review("r2"), session_id)
        db.upsert_review("place1", _make_review("r3"), session_id)
        # Simulate scrape that only found r1 and r2
        stale = db.mark_stale("place1", session_id, {"r1", "r2"})
        assert stale == 1
        review = db.get_review("r3", "place1")
        assert review["is_deleted"] == 1

    def test_mark_stale_preserves_recent_reviews(self, db):
        db.upsert_place("place1", "Test", "http://test")
        session_id = db.start_session("place1")
        db.upsert_review("place1", _make_review("r1"), session_id)
        stale = db.mark_stale("place1", session_id, {"r1"})
        assert stale == 0

    def test_export_excludes_deleted(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.upsert_review("place1", _make_review("r2"))
        db.hide_review("r1", "place1")
        exported = db.export_reviews_json("place1")
        assert len(exported) == 1
        assert exported[0]["review_id"] == "r2"


class TestSessionTracking:
    """Tests for scrape session management."""

    def test_start_session(self, db):
        db.upsert_place("place1", "Test", "http://test")
        sid = db.start_session("place1", sort_by="newest")
        assert sid > 0

    def test_end_session_completed(self, db):
        db.upsert_place("place1", "Test", "http://test")
        sid = db.start_session("place1")
        db.end_session(sid, "completed", reviews_found=50, reviews_new=10)
        session = db.backend.fetchone(
            "SELECT * FROM scrape_sessions WHERE session_id = ?", (sid,)
        )
        assert session["status"] == "completed"
        assert session["reviews_new"] == 10

    def test_end_session_failed(self, db):
        db.upsert_place("place1", "Test", "http://test")
        sid = db.start_session("place1")
        db.end_session(sid, "failed", error="Connection timeout")
        session = db.backend.fetchone(
            "SELECT * FROM scrape_sessions WHERE session_id = ?", (sid,)
        )
        assert session["status"] == "failed"
        assert session["error_message"] == "Connection timeout"


class TestExport:
    """Tests for data export functionality."""

    def test_export_reviews_json(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.upsert_review("place1", _make_review("r2"))
        exported = db.export_reviews_json("place1")
        assert len(exported) == 2

    def test_export_reviews_json_empty(self, db):
        db.upsert_place("place1", "Test", "http://test")
        assert db.export_reviews_json("place1") == []

    def test_export_all_json_multiple_places(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        db.upsert_review("p1", _make_review("r1"))
        db.upsert_review("p2", _make_review("r2"))
        exported = db.export_all_json()
        assert "p1" in exported
        assert "p2" in exported
        assert len(exported["p1"]) == 1
        assert len(exported["p2"]) == 1

    def test_export_csv(self, db, tmp_path):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1", text="Hello"))
        path = str(tmp_path / "output.csv")
        count = db.export_reviews_csv("place1", path)
        assert count == 1
        assert os.path.exists(path)


class TestSyncCheckpoints:
    """Tests for sync checkpoint management."""

    def test_get_sync_checkpoint_none(self, db):
        assert db.get_sync_checkpoint("place1", "mongodb") is None

    def test_update_sync_checkpoint(self, db):
        db.upsert_place("place1", "Test", "http://test")
        sid = db.start_session("place1", action="sync_mongodb")
        db.update_sync_checkpoint("place1", "mongodb", sid)
        cp = db.get_sync_checkpoint("place1", "mongodb")
        assert cp is not None
        assert cp["status"] == "ok"

    def test_reset_sync_checkpoint(self, db):
        db.upsert_place("place1", "Test", "http://test")
        sid = db.start_session("place1", action="sync_mongodb")
        db.update_sync_checkpoint("place1", "mongodb", sid)
        db.reset_sync_checkpoint("place1", "mongodb")
        assert db.get_sync_checkpoint("place1", "mongodb") is None

    def test_sync_partial_failure_recorded(self, db):
        db.upsert_place("place1", "Test", "http://test")
        sid = db.start_session("place1", action="sync_mongodb")
        db.update_sync_checkpoint(
            "place1", "mongodb", sid, status="partial",
            error="Timeout after 50 reviews"
        )
        cp = db.get_sync_checkpoint("place1", "mongodb")
        assert cp["status"] == "partial"
        assert cp["attempt_count"] == 1


class TestURLCanonicalization:
    """Tests for URL canonicalization in DB context."""

    def test_alias_resolved_via_canonical_url(self, db):
        db.upsert_place("p1", "Place", "http://orig1",
                         resolved_url="https://Google.COM/maps/place/Test/")
        canonical = db.upsert_place("p2", "Same Place", "http://orig2",
                                     resolved_url="https://google.com/maps/place/Test")
        assert canonical == "p1"


class TestSchemaVersioning:
    """Tests for schema management."""

    def test_schema_version_on_init(self, db):
        assert db.get_schema_version() == 1

    def test_schema_migration_idempotent(self, tmp_path):
        db1 = ReviewDB(str(tmp_path / "test.db"))
        v1 = db1.get_schema_version()
        db1.close()
        db2 = ReviewDB(str(tmp_path / "test.db"))
        v2 = db2.get_schema_version()
        db2.close()
        assert v1 == v2


class TestResurrection:
    """Tests for stale review resurrection."""

    def test_stale_review_reappears_restored(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        assert db.get_review("r1", "place1")["is_deleted"] == 1
        result = db.upsert_review("place1", _make_review("r1"))
        assert result == "restored"
        assert db.get_review("r1", "place1")["is_deleted"] == 0

    def test_restored_review_logs_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        db.upsert_review("place1", _make_review("r1"))
        history = db.get_review_history("r1", "place1")
        actions = [h["action"] for h in history]
        assert "restore" in actions


class TestOptimisticLocking:
    """Tests for row_version-based optimistic locking."""

    def test_row_version_incremented_on_write(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        review = db.get_review("r1", "place1")
        assert review["row_version"] == 1
        db.upsert_review("place1", _make_review("r1", text="Updated"))
        review = db.get_review("r1", "place1")
        assert review["row_version"] == 2

    def test_concurrent_upsert_same_review_no_lost_update(self, tmp_path):
        """Two threads updating the same review shouldn't lose updates."""
        db_path = str(tmp_path / "concurrent.db")
        db1 = ReviewDB(db_path)
        db1.upsert_place("place1", "Test", "http://test")
        db1.upsert_review("place1", _make_review("r1"))
        db1.close()

        results = []

        def updater(text):
            db = ReviewDB(db_path)
            result = db.upsert_review("place1", _make_review("r1", text=text))
            results.append(result)
            db.close()

        t1 = threading.Thread(target=updater, args=("Text from thread 1",))
        t2 = threading.Thread(target=updater, args=("Text from thread 2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both should complete without error
        assert len(results) == 2
        # Final review should exist
        db_check = ReviewDB(db_path)
        review = db_check.get_review("r1", "place1")
        assert review is not None
        assert review["row_version"] >= 2
        db_check.close()


class TestConcurrency:
    """Tests for concurrent access patterns."""

    def test_wal_mode_enabled(self, db):
        row = db.backend.fetchone("PRAGMA journal_mode")
        assert row["journal_mode"] == "wal"


class TestPlaceIsolation:
    """Multi-business data isolation."""

    def test_reviews_isolated_between_places(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        db.upsert_review("p1", _make_review("r1"))
        db.upsert_review("p2", _make_review("r2"))
        assert db.get_review_ids("p1") == {"r1"}
        assert db.get_review_ids("p2") == {"r2"}

    def test_same_review_id_different_places(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        db.upsert_review("p1", _make_review("r1", text="Place 1 review"))
        db.upsert_review("p2", _make_review("r1", text="Place 2 review"))
        r1 = db.get_review("r1", "p1")
        r2 = db.get_review("r1", "p2")
        assert r1["review_text"]["en"] == "Place 1 review"
        assert r2["review_text"]["en"] == "Place 2 review"

    def test_overwrite_only_affects_target_place(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        db.upsert_review("p1", _make_review("r1"))
        db.upsert_review("p2", _make_review("r2"))
        db.clear_place("p1")
        assert db.get_review_ids("p1") == set()
        assert db.get_review_ids("p2") == {"r2"}

    def test_session_tracking_per_place(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        s1 = db.start_session("p1")
        s2 = db.start_session("p2")
        assert s1 != s2

    def test_stale_detection_scoped_to_place(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        sid = db.start_session("p1")
        db.upsert_review("p1", _make_review("r1"), sid)
        db.upsert_review("p1", _make_review("r2"), sid)
        db.upsert_review("p2", _make_review("r3"), sid)
        stale = db.mark_stale("p1", sid, {"r1"})
        assert stale == 1
        # p2 review unaffected
        assert db.get_review("r3", "p2")["is_deleted"] == 0


class TestReviewManagement:
    """Tests for hide/restore CLI commands."""

    def test_hide_review(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        assert db.hide_review("r1", "place1")
        assert db.get_review("r1", "place1")["is_deleted"] == 1

    def test_hide_review_already_deleted(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        assert not db.hide_review("r1", "place1")

    def test_restore_review(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        assert db.restore_review("r1", "place1")
        assert db.get_review("r1", "place1")["is_deleted"] == 0

    def test_restore_review_not_deleted(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        assert not db.restore_review("r1", "place1")

    def test_hide_logs_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        history = db.get_review_history("r1", "place1")
        actors = [h["actor"] for h in history]
        assert "cli_hide" in actors

    def test_restore_logs_history(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        db.restore_review("r1", "place1")
        history = db.get_review_history("r1", "place1")
        actors = [h["actor"] for h in history]
        assert "cli_restore" in actors


class TestDatabaseManagement:
    """Tests for DB management operations."""

    def test_clear_place(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        counts = db.clear_place("place1")
        assert counts["places"] == 1
        assert db.get_place("place1") is None

    def test_clear_all(self, db):
        db.upsert_place("p1", "Place 1", "http://1")
        db.upsert_place("p2", "Place 2", "http://2")
        db.upsert_review("p1", _make_review("r1"))
        db.upsert_review("p2", _make_review("r2"))
        counts = db.clear_all()
        assert counts["places"] == 2
        assert counts["reviews"] == 2

    def test_get_stats(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        stats = db.get_stats()
        assert stats["places_count"] == 1
        assert stats["reviews_count"] == 1
        assert stats["db_size_bytes"] > 0

    def test_vacuum(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.clear_all()
        db.vacuum()  # should not raise


class TestHistoryManagement:
    """Tests for history pruning."""

    def test_prune_history_dry_run(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        count = db.prune_history(older_than_days=0, dry_run=True)
        # Just-created history should be included in dry run
        assert count >= 1
        # Verify nothing was actually deleted
        history = db.get_review_history("r1", "place1")
        assert len(history) >= 1

    def test_prune_history_deletes_old(self, db):
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        deleted = db.prune_history(older_than_days=0)
        assert deleted >= 1


class TestScrapeMode:
    """Tests for scrape_mode parameter in upsert_review."""

    def test_new_only_skips_existing(self, db):
        """Existing unchanged review returns 'unchanged' without hash comparison."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        result = db.upsert_review(
            "place1", _make_review("r1"), scrape_mode="new_only"
        )
        assert result == "unchanged"

    def test_new_only_inserts_new(self, db):
        """New review returns 'new' in new_only mode."""
        db.upsert_place("place1", "Test", "http://test")
        result = db.upsert_review(
            "place1", _make_review("r1"), scrape_mode="new_only"
        )
        assert result == "new"

    def test_new_only_resurrects_deleted(self, db):
        """Deleted review returns 'restored' in new_only mode."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        db.hide_review("r1", "place1")
        result = db.upsert_review(
            "place1", _make_review("r1"), scrape_mode="new_only"
        )
        assert result == "restored"
        assert db.get_review("r1", "place1")["is_deleted"] == 0

    def test_new_only_skips_content_update(self, db):
        """In new_only mode, content changes are NOT applied to existing reviews."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1", text="Original"))
        db.upsert_review(
            "place1", _make_review("r1", text="Updated"),
            scrape_mode="new_only",
        )
        review = db.get_review("r1", "place1")
        assert "Original" in str(review["review_text"])

    def test_update_mode_updates_content(self, db):
        """Content change in update mode → 'updated'."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1", text="Original"))
        result = db.upsert_review(
            "place1", _make_review("r1", text="Changed"),
            scrape_mode="update",
        )
        assert result == "updated"

    def test_update_mode_updates_engagement(self, db):
        """Engagement change in update mode → 'updated'."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1", likes=1))
        result = db.upsert_review(
            "place1", _make_review("r1", likes=100),
            scrape_mode="update",
        )
        assert result == "updated"

    def test_full_mode_same_as_update(self, db):
        """Full mode upsert behavior matches update for content changes."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1", text="Original"))
        result = db.upsert_review(
            "place1", _make_review("r1", text="Changed"),
            scrape_mode="full",
        )
        assert result == "updated"

    def test_flush_batch_passes_scrape_mode(self, db):
        """flush_batch respects scrape_mode parameter."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review("r1"))
        session_id = db.start_session("place1")
        # In new_only mode, r1 with changed text should still be "unchanged"
        batch = [_make_review("r1", text="Different")]
        stats = db.flush_batch("place1", batch, session_id, scrape_mode="new_only")
        assert stats["unchanged"] == 1

    def test_hash_uses_raw_date_not_parsed(self, db):
        """Changing review_date (parsed ISO) should NOT cause 'updated' when
        raw date string stays the same — prevents false updates from relative
        date parsing volatility (e.g. '2 months ago' → different ISO each run)."""
        db.upsert_place("place1", "Test", "http://test")
        db.upsert_review("place1", _make_review(
            "r1", date="2 months ago", review_date="2025-12-08T14:00:00+00:00"
        ))
        # Same raw date, different parsed ISO (simulates next-day scrape)
        result = db.upsert_review("place1", _make_review(
            "r1", date="2 months ago", review_date="2025-12-09T10:30:00+00:00"
        ))
        assert result == "unchanged"
