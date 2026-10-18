"""
Tests for the full hex place id and the move away from truncated ids.

Older versions stored "0x<cell>:0" instead of "0x<cell>:0x<cid>". A place is
moved to its full id (every table, plus its image folder) the next time it
is scraped from the same URL; the old id keeps working as an alias.
"""

import asyncio
import os

import pytest

from modules.image_handler import place_image_dir
from modules.place_id import extract_place_id, truncated_hex_id
from modules.review_db import ReviewDB

URL = "https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9"
FULL = "0x30e29edb0244829f:0x1a0f476260d32f1"
LEGACY = "0x30e29edb0244829f:0"

skip_on_windows = pytest.mark.skipif(os.name == "nt", reason="':' is not allowed in Windows folder names")


class TestExtraction:

    def test_full_hex_id_is_kept(self):
        url = "https://www.google.com/maps/place/X/data=!4m6!3m5!1s0x882b21e060e098b7:0xf363a20a02c068c8!8m2"
        assert extract_place_id("", url) == "0x882b21e060e098b7:0xf363a20a02c068c8"

    def test_truncated_hex_id(self):
        assert truncated_hex_id("0x882b21e060e098b7:0xf363a20a02c068c8") == "0x882b21e060e098b7:0"
        assert truncated_hex_id("0x882b21e060e098b7:0") == ""
        assert truncated_hex_id("cid:12345") == ""


def review(i):
    return {"review_id": f"r{i}", "author": f"User {i}", "rating": 5, "text": f"text {i}",
            "lang": "en", "date": "1 day ago", "review_date": "2026-10-01T00:00:00+00:00"}


@pytest.fixture
def db(tmp_path):
    review_db = ReviewDB(str(tmp_path / "reviews.db"))
    review_db.upsert_place(LEGACY, "Thai Tours", URL, "")
    session_id = review_db.start_session(LEGACY)
    for i in range(3):
        review_db.upsert_review(LEGACY, review(i), session_id=session_id)
    review_db.end_session(session_id, "completed", reviews_found=3)
    review_db.update_sync_checkpoint(LEGACY, "mongodb", session_id)
    yield review_db
    review_db.close()


def count(db, table, place_id):
    return db.backend.fetchone(f"SELECT COUNT(*) AS n FROM {table} WHERE place_id = ?", (place_id,))["n"]


class TestMigration:

    def test_moves_every_table(self, db):
        assert db.migrate_truncated_place_id(FULL, URL) == LEGACY

        for table in ("places", "reviews", "review_history", "scrape_sessions", "sync_checkpoints"):
            assert count(db, table, LEGACY) == 0, table
            assert count(db, table, FULL) > 0, table
        assert db.get_review_ids(FULL) == {"r0", "r1", "r2"}
        assert db.backend.fetchall("PRAGMA foreign_key_check") == []

    def test_old_id_still_resolves(self, db):
        db.migrate_truncated_place_id(FULL, URL)
        assert db.get_place(LEGACY)["place_id"] == FULL

    def test_scraping_after_move_updates_instead_of_duplicating(self, db):
        db.migrate_truncated_place_id(FULL, URL)
        place_id = db.upsert_place(FULL, "Thai Tours", URL, "")
        session_id = db.start_session(place_id)
        assert db.upsert_review(place_id, review(0), session_id=session_id) == "unchanged"
        assert db.count_reviews(FULL) == 3

    def test_different_url_is_not_merged(self, db):
        """Places at the same location can share the first half of the id."""
        assert db.migrate_truncated_place_id(FULL, "https://maps.app.goo.gl/other") == ""
        assert count(db, "reviews", LEGACY) == 3

    def test_existing_full_id_is_left_alone(self, db):
        db.upsert_place(FULL, "Thai Tours", URL, "")
        assert db.migrate_truncated_place_id(FULL, URL) == ""
        assert count(db, "reviews", LEGACY) == 3

    def test_other_id_formats_are_ignored(self, db):
        assert db.migrate_truncated_place_id("cid:123", URL) == ""
        assert db.migrate_truncated_place_id(LEGACY, URL) == ""


class TestImageFolder:

    @skip_on_windows
    def test_raw_legacy_folder_moves_to_full_id(self, tmp_path):
        (tmp_path / LEGACY / "profiles").mkdir(parents=True)
        base = place_image_dir(tmp_path, FULL, previous_ids=(LEGACY,))
        assert base == tmp_path / "0x30e29edb0244829f_0x1a0f476260d32f1"
        assert (base / "profiles").is_dir()
        assert not (tmp_path / LEGACY).exists()

    def test_safe_legacy_folder_moves_to_full_id(self, tmp_path):
        (tmp_path / "0x30e29edb0244829f_0" / "reviews").mkdir(parents=True)
        base = place_image_dir(tmp_path, FULL, previous_ids=(LEGACY,))
        assert (base / "reviews").is_dir()
        assert not (tmp_path / "0x30e29edb0244829f_0").exists()


def test_api_reviews_by_old_id(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # importing api_server may write config.yaml
    from api_server import list_reviews, get_review

    db.migrate_truncated_place_id(FULL, URL)
    page = asyncio.run(list_reviews(LEGACY, limit=50, offset=0, include_deleted=False, review_db=db))
    assert page.total == 3
    assert page.place_id == FULL
    assert asyncio.run(get_review(LEGACY, "r1", review_db=db)).review_id == "r1"
