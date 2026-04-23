"""
Regression test for F-API.4 (cross-thread sqlite).

Before the fix, a single shared `ReviewDB` instance raised
`sqlite3.ProgrammingError` the moment two concurrent request threads used it.
After the fix (check_same_thread=False + internal lock), this test must run
N concurrent threads without any errors.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from modules.review_db import ReviewDB


@pytest.fixture
def shared_db(tmp_path):
    db = ReviewDB(str(tmp_path / "concurrent.db"))
    place_id = db.upsert_place("p1", "Place 1", "https://maps.example/p1", None)
    session_id = db.start_session(place_id)
    # Seed a few reviews so reads return something.
    for i in range(10):
        db.upsert_review(place_id, {
            "review_id": f"rev_{i}",
            "author": f"User {i}",
            "rating": 4,
            "text": f"text {i}",
            "lang": "en",
            "date": "1 day ago",
            "review_date": "2025-06-15T00:00:00+00:00",
        }, session_id=session_id)
    yield db
    db.close()


def test_concurrent_reads_no_sqlite_error(shared_db):
    """20 concurrent reads must not raise ProgrammingError."""
    def reader():
        # Mix of reads that used to share the connection unsafely.
        place = shared_db.get_stats()
        rows = shared_db.get_reviews("p1", limit=5)
        return len(rows), place.get("reviews_count", 0)

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(reader) for _ in range(40)]
        results = [f.result(timeout=10) for f in as_completed(futures)]

    assert len(results) == 40
    for n_rows, total in results:
        assert n_rows == 5
        assert total == 10


def test_concurrent_writes_serialized(shared_db):
    """Concurrent upserts must succeed (lock serializes them)."""
    place_id = "p1"
    session_id = shared_db.start_session(place_id)

    def writer(i):
        shared_db.upsert_review(place_id, {
            "review_id": f"conc_{i}",
            "author": f"Writer {i}",
            "rating": 5,
            "text": f"concurrent {i}",
            "lang": "en",
            "date": "1 day ago",
            "review_date": "2025-06-15T00:00:00+00:00",
        }, session_id=session_id)

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(writer, i) for i in range(30)]
        for f in as_completed(futures):
            f.result(timeout=10)

    rows = shared_db.get_reviews(place_id, limit=100)
    # 10 seed + 30 concurrent
    assert len(rows) == 40
