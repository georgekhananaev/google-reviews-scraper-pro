"""
Tests for GET /health/scrape: sessions where Google capped the review list
(status "limited") must not count as healthy.
"""

import asyncio

import pytest

from modules.review_db import ReviewDB


@pytest.fixture
def scrape_health():
    from api_server import scrape_health as endpoint
    return endpoint


@pytest.fixture
def db(tmp_path):
    review_db = ReviewDB(str(tmp_path / "health.db"))
    review_db.upsert_place("p1", "Place 1", "https://maps.example/p1", None)
    yield review_db
    review_db.close()


def end(db, status, found=5, error=None):
    session_id = db.start_session("p1")
    db.end_session(session_id, status, reviews_found=found, error=error)


def test_completed_sessions_are_healthy(scrape_health, db):
    end(db, "completed", found=40)
    result = asyncio.run(scrape_health(review_db=db))
    assert result["status"] == "healthy"
    assert result["limited_sessions_24h"] == 0


def test_limited_session_degrades_health(scrape_health, db):
    end(db, "limited", error="Google showed only 5 of about 746 reviews")
    result = asyncio.run(scrape_health(review_db=db))
    assert result["status"] == "degraded"
    assert result["limited_sessions_24h"] == 1
    assert result["last_session_status"] == "limited"
    assert result["last_synthetic_success"] is None
