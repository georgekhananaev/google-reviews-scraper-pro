"""
Tests for GET /health/scrape: sessions where Google capped the review list
(status "limited") must not count as healthy.
"""

import asyncio

import pytest

from modules.review_db import ReviewDB


@pytest.fixture
def scrape_health(monkeypatch):
    import api_server
    # Don't depend on the developer's config.yaml (it may set a real profile).
    monkeypatch.setattr(api_server, "_config", {})
    return api_server.scrape_health


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


def test_profile_not_configured(scrape_health, db):
    assert asyncio.run(scrape_health(review_db=db))["browser_profile"] == "not_configured"


def test_signed_out_profile_degrades_health(scrape_health, db, tmp_path, monkeypatch):
    import api_server
    monkeypatch.setattr(api_server, "_config", {"browser_profile_dir": str(tmp_path / "profile")})
    end(db, "completed", found=40)
    result = asyncio.run(scrape_health(review_db=db))
    assert result["browser_profile"] == "signed_out"
    assert result["status"] == "degraded"


def test_limited_session_degrades_health(scrape_health, db):
    end(db, "limited", error="Google showed only 5 of about 746 reviews")
    result = asyncio.run(scrape_health(review_db=db))
    assert result["status"] == "degraded"
    assert result["limited_sessions_24h"] == 1
    assert result["last_session_status"] == "limited"
    assert result["last_synthetic_success"] is None
