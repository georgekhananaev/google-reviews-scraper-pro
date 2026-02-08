"""Tests for JSON/MongoDB migration into SQLite."""

import json
import pytest
from pathlib import Path

from modules.migration import migrate_json, _legacy_to_review_dict
from modules.review_db import ReviewDB


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


class TestLegacyToReviewDict:
    """Tests for legacy document conversion."""

    def test_basic_conversion(self):
        doc = {
            "review_id": "r1",
            "author": "Alice",
            "rating": 5.0,
            "description": {"en": "Great!"},
            "likes": 3,
            "user_images": ["http://img1.jpg"],
            "author_profile_url": "http://profile",
            "profile_picture": "http://avatar.jpg",
            "owner_responses": {"en": {"text": "Thanks!"}},
            "date": "3 months ago",
            "review_date": "2025-06-15",
        }
        result = _legacy_to_review_dict(doc)
        assert result["review_id"] == "r1"
        assert result["text"] == "Great!"
        assert result["lang"] == "en"
        assert result["rating"] == 5.0
        assert result["likes"] == 3
        assert result["photos"] == ["http://img1.jpg"]
        assert result["profile"] == "http://profile"
        assert result["avatar"] == "http://avatar.jpg"
        assert result["owner_text"] == "Thanks!"

    def test_old_field_names(self):
        doc = {
            "review_id": "r2",
            "photo_urls": ["http://img.jpg"],
            "profile_link": "http://profile",
            "avatar_url": "http://avatar.jpg",
        }
        result = _legacy_to_review_dict(doc)
        assert result["photos"] == ["http://img.jpg"]
        assert result["profile"] == "http://profile"
        assert result["avatar"] == "http://avatar.jpg"

    def test_missing_review_id(self):
        result = _legacy_to_review_dict({"author": "Bob"})
        assert result == {}

    def test_flat_text_field(self):
        doc = {"review_id": "r3", "text": "Hello", "lang": "en"}
        result = _legacy_to_review_dict(doc)
        assert result["text"] == "Hello"
        assert result["lang"] == "en"

    def test_empty_description(self):
        doc = {"review_id": "r4", "description": {}}
        result = _legacy_to_review_dict(doc)
        assert result["text"] == ""
        assert result["lang"] == "en"


class TestMigrateJson:
    """Tests for JSON migration."""

    def test_migrate_list_format(self, tmp_path, db_path):
        data = [
            {"review_id": "r1", "author": "Alice", "rating": 5.0,
             "description": {"en": "Great!"}, "likes": 2,
             "user_images": [], "review_date": "2025-06-15"},
            {"review_id": "r2", "author": "Bob", "rating": 4.0,
             "description": {"en": "Good"}, "likes": 1,
             "user_images": [], "review_date": "2025-07-01"},
        ]
        json_path = str(tmp_path / "reviews.json")
        Path(json_path).write_text(json.dumps(data), encoding="utf-8")

        stats = migrate_json(json_path, db_path, "https://maps.app.goo.gl/test123")
        assert stats["total"] == 2
        assert stats["new"] == 2
        assert stats["skipped"] == 0

        # Verify data in DB
        db = ReviewDB(db_path)
        try:
            places = db.list_places()
            assert len(places) == 1
            reviews = db.get_reviews(places[0]["place_id"])
            assert len(reviews) == 2
        finally:
            db.close()

    def test_migrate_dict_format(self, tmp_path, db_path):
        data = {
            "r1": {"review_id": "r1", "author": "Alice", "rating": 5.0,
                   "description": {"en": "Great!"}},
        }
        json_path = str(tmp_path / "reviews.json")
        Path(json_path).write_text(json.dumps(data), encoding="utf-8")

        stats = migrate_json(json_path, db_path)
        assert stats["total"] == 1
        assert stats["new"] == 1

    def test_migrate_nonexistent_file(self, db_path):
        stats = migrate_json("/nonexistent/file.json", db_path)
        assert stats["total"] == 0

    def test_migrate_empty_file(self, tmp_path, db_path):
        json_path = str(tmp_path / "empty.json")
        Path(json_path).write_text("[]", encoding="utf-8")
        stats = migrate_json(json_path, db_path)
        assert stats["total"] == 0

    def test_idempotent_migration(self, tmp_path, db_path):
        data = [{"review_id": "r1", "rating": 5.0, "description": {"en": "Test"}}]
        json_path = str(tmp_path / "reviews.json")
        Path(json_path).write_text(json.dumps(data), encoding="utf-8")

        stats1 = migrate_json(json_path, db_path)
        assert stats1["new"] == 1

        stats2 = migrate_json(json_path, db_path)
        # Second run should find it unchanged
        assert stats2["new"] == 0

    def test_migration_creates_session(self, tmp_path, db_path):
        data = [{"review_id": "r1", "rating": 5.0}]
        json_path = str(tmp_path / "reviews.json")
        Path(json_path).write_text(json.dumps(data), encoding="utf-8")
        migrate_json(json_path, db_path)

        db = ReviewDB(db_path)
        try:
            stats = db.get_stats()
            assert stats["scrape_sessions_count"] == 1
        finally:
            db.close()
