"""
Migration utilities for importing existing JSON/MongoDB data into SQLite.

Usage:
    python start.py migrate --source json --json-path google_reviews.json
    python start.py migrate --source mongodb
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

from modules.place_id import extract_place_id
from modules.review_db import ReviewDB

log = logging.getLogger("scraper")


def _legacy_to_review_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a legacy review document to the format expected by ReviewDB.upsert_review."""
    review_id = doc.get("review_id", "")
    if not review_id:
        return {}

    # Extract text and lang from legacy description dict or flat text field
    text = ""
    lang = "en"
    description = doc.get("description", {})
    if isinstance(description, dict) and description:
        lang = next(iter(description))
        text = description[lang]
    elif doc.get("text"):
        text = doc["text"]
        lang = doc.get("lang", "en")

    # Extract owner response text
    owner_text = ""
    owner_responses = doc.get("owner_responses", {})
    if isinstance(owner_responses, dict) and owner_responses:
        first_lang = next(iter(owner_responses))
        resp = owner_responses[first_lang]
        owner_text = resp.get("text", "") if isinstance(resp, dict) else str(resp)
    elif doc.get("owner_text"):
        owner_text = doc["owner_text"]

    photos = doc.get("user_images", doc.get("photos", doc.get("photo_urls", [])))
    if not isinstance(photos, list):
        photos = []

    return {
        "review_id": review_id,
        "text": text,
        "rating": doc.get("rating", 0),
        "likes": doc.get("likes", 0),
        "lang": lang,
        "date": doc.get("date", ""),
        "review_date": doc.get("review_date", ""),
        "author": doc.get("author", ""),
        "profile": doc.get("author_profile_url", doc.get("profile_link", doc.get("profile", ""))),
        "avatar": doc.get("profile_picture", doc.get("avatar_url", doc.get("avatar", ""))),
        "owner_text": owner_text,
        "photos": photos,
    }


def migrate_json(
    json_path: str,
    db_path: str = "reviews.db",
    place_url: str = "",
) -> Dict[str, int]:
    """
    Import reviews from a JSON file into the SQLite database.

    Args:
        json_path: Path to the JSON file containing review data.
        db_path: Path to the SQLite database.
        place_url: Google Maps URL associated with this data.

    Returns:
        Dict with counts: {'total': N, 'new': N, 'updated': N, 'skipped': N}
    """
    path = Path(json_path)
    if not path.exists():
        log.error(f"JSON file not found: {json_path}")
        return {"total": 0, "new": 0, "updated": 0, "skipped": 0}

    data = json.loads(path.read_text(encoding="utf-8"))

    # Support both list and dict formats
    if isinstance(data, list):
        docs = data
    elif isinstance(data, dict):
        docs = list(data.values())
    else:
        log.error(f"Unexpected JSON format in {json_path}")
        return {"total": 0, "new": 0, "updated": 0, "skipped": 0}

    if not docs:
        log.info("No reviews found in JSON file.")
        return {"total": 0, "new": 0, "updated": 0, "skipped": 0}

    db = ReviewDB(db_path)
    try:
        place_id = extract_place_id(place_url, place_url)
        place_id = db.upsert_place(place_id, "", place_url)
        session_id = db.start_session(place_id, action="migrate_json")

        stats = {"total": len(docs), "new": 0, "updated": 0, "skipped": 0}

        for doc in docs:
            review_dict = _legacy_to_review_dict(doc)
            if not review_dict:
                stats["skipped"] += 1
                continue
            result = db.upsert_review(place_id, review_dict, session_id)
            if result == "new":
                stats["new"] += 1
            elif result in ("updated", "restored"):
                stats["updated"] += 1

        db.end_session(
            session_id, "completed",
            reviews_found=stats["total"],
            reviews_new=stats["new"],
            reviews_updated=stats["updated"],
        )
        log.info(f"Migration from JSON complete: {stats}")
        return stats
    finally:
        db.close()


def migrate_mongodb(
    config: Dict[str, Any],
    db_path: str = "reviews.db",
    place_url: str = "",
) -> Dict[str, int]:
    """
    Import reviews from MongoDB into the SQLite database.

    Args:
        config: Full application config (needs mongodb section).
        db_path: Path to the SQLite database.
        place_url: Google Maps URL associated with this data.

    Returns:
        Dict with counts: {'total': N, 'new': N, 'updated': N, 'skipped': N}
    """
    try:
        import pymongo
    except ImportError:
        log.error("pymongo not installed. Install with: pip install pymongo")
        return {"total": 0, "new": 0, "updated": 0, "skipped": 0}

    mongodb_config = config.get("mongodb", {})
    uri = mongodb_config.get("uri", "mongodb://localhost:27017")
    db_name = mongodb_config.get("database", "reviews")
    collection_name = mongodb_config.get("collection", "google_reviews")

    try:
        client = pymongo.MongoClient(uri, connectTimeoutMS=10000)
        client.admin.command("ping")
    except Exception as e:
        log.error(f"Cannot connect to MongoDB: {e}")
        return {"total": 0, "new": 0, "updated": 0, "skipped": 0}

    collection = client[db_name][collection_name]
    docs = list(collection.find({}, {"_id": 0}))
    client.close()

    if not docs:
        log.info("No reviews found in MongoDB.")
        return {"total": 0, "new": 0, "updated": 0, "skipped": 0}

    db = ReviewDB(db_path)
    try:
        place_id = extract_place_id(place_url, place_url)
        place_id = db.upsert_place(place_id, "", place_url)
        session_id = db.start_session(place_id, action="migrate_mongodb")

        stats = {"total": len(docs), "new": 0, "updated": 0, "skipped": 0}

        for doc in docs:
            review_dict = _legacy_to_review_dict(doc)
            if not review_dict:
                stats["skipped"] += 1
                continue
            result = db.upsert_review(place_id, review_dict, session_id)
            if result == "new":
                stats["new"] += 1
            elif result in ("updated", "restored"):
                stats["updated"] += 1

        db.end_session(
            session_id, "completed",
            reviews_found=stats["total"],
            reviews_new=stats["new"],
            reviews_updated=stats["updated"],
        )
        log.info(f"Migration from MongoDB complete: {stats}")
        return stats
    finally:
        db.close()
