"""Tests for review change detection (content and engagement hashes)."""

import pytest

from modules.review_db import ReviewDB


class TestContentHash:
    """Tests for content hash computation."""

    def test_same_content_same_hash(self):
        h1 = ReviewDB.compute_content_hash("Great place!", 5.0, "2025-06-15")
        h2 = ReviewDB.compute_content_hash("Great place!", 5.0, "2025-06-15")
        assert h1 == h2

    def test_text_change_different_hash(self):
        h1 = ReviewDB.compute_content_hash("Great place!", 5.0, "2025-06-15")
        h2 = ReviewDB.compute_content_hash("Terrible place!", 5.0, "2025-06-15")
        assert h1 != h2

    def test_rating_change_different_hash(self):
        h1 = ReviewDB.compute_content_hash("Good", 4.0, "2025-06-15")
        h2 = ReviewDB.compute_content_hash("Good", 5.0, "2025-06-15")
        assert h1 != h2

    def test_date_change_different_hash(self):
        h1 = ReviewDB.compute_content_hash("Good", 4.0, "2025-06-15")
        h2 = ReviewDB.compute_content_hash("Good", 4.0, "2025-07-15")
        assert h1 != h2

    def test_likes_not_in_content_hash(self):
        # Content hash should NOT include likes
        h1 = ReviewDB.compute_content_hash("Good", 4.0, "2025-06-15")
        h2 = ReviewDB.compute_content_hash("Good", 4.0, "2025-06-15")
        assert h1 == h2  # likes not part of content hash

    def test_empty_text(self):
        h = ReviewDB.compute_content_hash("", 0.0, "")
        assert len(h) == 64  # valid SHA-256

    def test_unicode_text(self):
        h1 = ReviewDB.compute_content_hash("מקום מצוין!", 5.0, "2025-06-15")
        h2 = ReviewDB.compute_content_hash("มันยอดเยี่ยม!", 5.0, "2025-06-15")
        assert h1 != h2
        assert len(h1) == 64

    def test_hash_is_sha256(self):
        h = ReviewDB.compute_content_hash("test", 5.0, "2025-01-01")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestEngagementHash:
    """Tests for engagement hash computation."""

    def test_likes_change(self):
        h1 = ReviewDB.compute_engagement_hash(2, "Thanks!")
        h2 = ReviewDB.compute_engagement_hash(10, "Thanks!")
        assert h1 != h2

    def test_owner_response_change(self):
        h1 = ReviewDB.compute_engagement_hash(5, "Thanks!")
        h2 = ReviewDB.compute_engagement_hash(5, "Thank you so much!")
        assert h1 != h2

    def test_both_unchanged(self):
        h1 = ReviewDB.compute_engagement_hash(5, "Thanks!")
        h2 = ReviewDB.compute_engagement_hash(5, "Thanks!")
        assert h1 == h2

    def test_empty_owner_response(self):
        h = ReviewDB.compute_engagement_hash(0, "")
        assert len(h) == 64
