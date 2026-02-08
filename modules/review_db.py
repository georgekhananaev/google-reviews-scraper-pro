"""
SQLite-backed review storage with multi-business support.

Thread safety: Each thread/job MUST create its own ReviewDB instance
(and thus its own connection). WAL mode allows concurrent readers
and one writer without blocking.

Do NOT share a single ReviewDB instance across threads.
"""

import csv
import hashlib
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Set, List

from modules.database_backend import SQLiteBackend
from modules.place_id import canonicalize_url

log = logging.getLogger("scraper")

SCHEMA_VERSION = 1

_SCHEMA_DDL = """
-- Schema version tracking (single-row model)
CREATE TABLE IF NOT EXISTS schema_version (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    version        INTEGER NOT NULL,
    applied_at     TEXT NOT NULL,
    description    TEXT
);

-- Business/place registry
CREATE TABLE IF NOT EXISTS places (
    place_id       TEXT PRIMARY KEY,
    place_name     TEXT,
    original_url   TEXT NOT NULL,
    resolved_url   TEXT,
    latitude       REAL,
    longitude      REAL,
    first_seen     TEXT NOT NULL,
    last_scraped   TEXT,
    total_reviews  INTEGER DEFAULT 0
);

-- Place aliases
CREATE TABLE IF NOT EXISTS place_aliases (
    alias_id       TEXT NOT NULL,
    canonical_id   TEXT NOT NULL,
    original_url   TEXT,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (alias_id),
    FOREIGN KEY (canonical_id) REFERENCES places(place_id) ON DELETE CASCADE
);

-- Scrape session log (declared before reviews for FK validity)
CREATE TABLE IF NOT EXISTS scrape_sessions (
    session_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id       TEXT NOT NULL,
    action         TEXT NOT NULL DEFAULT 'scrape',
    started_at     TEXT NOT NULL,
    completed_at   TEXT,
    status         TEXT NOT NULL DEFAULT 'running',
    reviews_found  INTEGER DEFAULT 0,
    reviews_new    INTEGER DEFAULT 0,
    reviews_updated INTEGER DEFAULT 0,
    sort_by        TEXT,
    error_message  TEXT,
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE
);

-- Reviews table
CREATE TABLE IF NOT EXISTS reviews (
    review_id      TEXT NOT NULL,
    place_id       TEXT NOT NULL,
    author         TEXT,
    rating         REAL,
    review_text    TEXT,
    review_date    TEXT,
    raw_date       TEXT,
    likes          INTEGER DEFAULT 0,
    user_images    TEXT,
    s3_images      TEXT,
    profile_url    TEXT,
    profile_picture TEXT,
    s3_profile_picture TEXT,
    owner_responses TEXT,
    created_date   TEXT NOT NULL,
    last_modified  TEXT NOT NULL,
    last_seen_session INTEGER,
    last_changed_session INTEGER,
    is_deleted     INTEGER DEFAULT 0,
    content_hash   TEXT,
    engagement_hash TEXT,
    row_version    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (review_id, place_id),
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (last_seen_session) REFERENCES scrape_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY (last_changed_session) REFERENCES scrape_sessions(session_id) ON DELETE SET NULL
);

-- Review history / audit trail
CREATE TABLE IF NOT EXISTS review_history (
    history_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id      TEXT NOT NULL,
    place_id       TEXT NOT NULL,
    session_id     INTEGER,
    actor          TEXT NOT NULL DEFAULT 'scraper',
    action         TEXT NOT NULL,
    changed_fields TEXT,
    old_content_hash TEXT,
    new_content_hash TEXT,
    old_engagement_hash TEXT,
    new_engagement_hash TEXT,
    timestamp      TEXT NOT NULL,
    FOREIGN KEY (review_id, place_id) REFERENCES reviews(review_id, place_id) ON DELETE CASCADE,
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES scrape_sessions(session_id) ON DELETE SET NULL
);

-- Sync checkpoints
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    place_id       TEXT NOT NULL,
    target         TEXT NOT NULL,
    last_synced_at TEXT,
    last_synced_session INTEGER,
    cursor_review_id TEXT,
    cursor_updated_at TEXT,
    attempt_count  INTEGER DEFAULT 0,
    status         TEXT DEFAULT 'ok',
    error_message  TEXT,
    PRIMARY KEY (place_id, target),
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (last_synced_session) REFERENCES scrape_sessions(session_id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_reviews_place ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(place_id, review_date);
CREATE INDEX IF NOT EXISTS idx_reviews_hash ON reviews(place_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_reviews_deleted ON reviews(place_id, is_deleted);
CREATE INDEX IF NOT EXISTS idx_reviews_modified ON reviews(place_id, last_modified);
CREATE INDEX IF NOT EXISTS idx_reviews_changed_session ON reviews(last_changed_session);
CREATE INDEX IF NOT EXISTS idx_sessions_place ON scrape_sessions(place_id);
CREATE INDEX IF NOT EXISTS idx_sessions_action ON scrape_sessions(action);
CREATE INDEX IF NOT EXISTS idx_aliases_canonical ON place_aliases(canonical_id);
CREATE INDEX IF NOT EXISTS idx_history_review ON review_history(review_id, place_id);
CREATE INDEX IF NOT EXISTS idx_history_session ON review_history(session_id);
CREATE INDEX IF NOT EXISTS idx_history_action ON review_history(action);
CREATE INDEX IF NOT EXISTS idx_sync_target ON sync_checkpoints(target);
"""


def _now_utc() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ReviewDB:
    """
    SQLite database for review storage and deduplication.

    Thread safety: Each thread/job MUST create its own ReviewDB instance.
    WAL mode allows concurrent readers and one writer without blocking.
    """

    def __init__(self, db_path: str = "reviews.db"):
        self.backend = SQLiteBackend(db_path)
        self.backend.connect()
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist, apply migrations if needed."""
        current = self.backend.get_schema_version()
        if current == 0:
            self.backend.init_schema(SCHEMA_VERSION, [_SCHEMA_DDL])
        elif current < SCHEMA_VERSION:
            self.backend.migrate(current, SCHEMA_VERSION, _MIGRATIONS)

    @contextmanager
    def transaction(self):
        """Context manager for explicit write transactions."""
        with self.backend.transaction():
            yield

    # === Place Management ===

    def upsert_place(self, place_id: str, place_name: str,
                     original_url: str, resolved_url: str = "",
                     lat: float = None, lng: float = None) -> str:
        """
        Register or update a business place.
        Checks for alias resolution: if resolved_url matches an existing
        place, returns the canonical place_id instead.
        """
        # Check alias resolution first
        if resolved_url:
            canonical = self.resolve_alias(place_id, resolved_url)
            if canonical != place_id:
                # Update last_scraped on canonical
                self.backend.execute(
                    "UPDATE places SET last_scraped = ? WHERE place_id = ?",
                    (_now_utc(), canonical)
                )
                self.backend.commit()
                return canonical

        now = _now_utc()
        canon_url = canonicalize_url(resolved_url) if resolved_url else None
        existing = self.get_place(place_id)
        if existing:
            self.backend.execute(
                "UPDATE places SET place_name = ?, resolved_url = ?, "
                "latitude = ?, longitude = ?, last_scraped = ? WHERE place_id = ?",
                (place_name or existing["place_name"], canon_url or existing.get("resolved_url"),
                 lat, lng, now, place_id)
            )
        else:
            self.backend.execute(
                "INSERT INTO places (place_id, place_name, original_url, resolved_url, "
                "latitude, longitude, first_seen, last_scraped, total_reviews) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (place_id, place_name, original_url, canon_url, lat, lng, now, now)
            )
        self.backend.commit()
        return place_id

    def resolve_alias(self, place_id: str, resolved_url: str) -> str:
        """
        Check if this place_id should be aliased to an existing canonical ID.
        Returns canonical_id if alias found, else returns place_id unchanged.
        """
        # First check existing aliases
        row = self.backend.fetchone(
            "SELECT canonical_id FROM place_aliases WHERE alias_id = ?",
            (place_id,)
        )
        if row:
            return row["canonical_id"]

        # Check if resolved_url matches any existing place
        if resolved_url:
            canon_url = canonicalize_url(resolved_url)
            row = self.backend.fetchone(
                "SELECT place_id FROM places WHERE resolved_url = ? AND place_id != ?",
                (canon_url, place_id)
            )
            if row:
                # Create alias mapping
                self.backend.execute(
                    "INSERT OR IGNORE INTO place_aliases "
                    "(alias_id, canonical_id, original_url, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (place_id, row["place_id"], resolved_url, _now_utc())
                )
                self.backend.commit()
                return row["place_id"]

        return place_id

    def get_place(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Get place info by ID (checks aliases too)."""
        row = self.backend.fetchone(
            "SELECT * FROM places WHERE place_id = ?", (place_id,)
        )
        if row:
            return row
        # Check aliases
        alias = self.backend.fetchone(
            "SELECT canonical_id FROM place_aliases WHERE alias_id = ?",
            (place_id,)
        )
        if alias:
            return self.backend.fetchone(
                "SELECT * FROM places WHERE place_id = ?",
                (alias["canonical_id"],)
            )
        return None

    def list_places(self) -> List[Dict[str, Any]]:
        """List all registered places."""
        return self.backend.fetchall("SELECT * FROM places ORDER BY first_seen")

    # === Review Operations ===

    def get_review_ids(self, place_id: str) -> Set[str]:
        """Get all non-deleted review IDs for a place (for dedup)."""
        rows = self.backend.fetchall(
            "SELECT review_id FROM reviews WHERE place_id = ? AND is_deleted = 0",
            (place_id,)
        )
        return {r["review_id"] for r in rows}

    def get_review(self, review_id: str, place_id: str) -> Optional[Dict[str, Any]]:
        """Get a single review by ID and place."""
        row = self.backend.fetchone(
            "SELECT * FROM reviews WHERE review_id = ? AND place_id = ?",
            (review_id, place_id)
        )
        if row:
            return self._deserialize_review(row)
        return None

    def count_reviews(self, place_id: str, include_deleted: bool = False) -> int:
        """Count reviews for a place (used for pagination totals)."""
        sql = "SELECT COUNT(*) as cnt FROM reviews WHERE place_id = ?"
        params: list = [place_id]
        if not include_deleted:
            sql += " AND is_deleted = 0"
        row = self.backend.fetchone(sql, tuple(params))
        return row["cnt"] if row else 0

    def get_reviews(self, place_id: str, limit: int = None,
                    offset: int = 0, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get reviews for a place with pagination."""
        sql = "SELECT * FROM reviews WHERE place_id = ?"
        params: list = [place_id]
        if not include_deleted:
            sql += " AND is_deleted = 0"
        sql += " ORDER BY created_date DESC"
        if limit:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = self.backend.fetchall(sql, tuple(params))
        return [self._deserialize_review(r) for r in rows]

    def upsert_review(self, place_id: str, review: Dict[str, Any],
                      session_id: int = None, max_retries: int = 3,
                      scrape_mode: str = "update") -> str:
        """
        Insert or update a single review.

        Uses ON CONFLICT DO UPDATE (not INSERT OR REPLACE) to avoid row deletion.
        Optimistic locking: UPDATE ... WHERE row_version = ? — retries on conflict.
        Resurrection: if existing.is_deleted=1 and review reappears, sets is_deleted=0.

        Returns: 'new', 'updated', 'restored', or 'unchanged'
        """
        review_id = review["review_id"]
        now = _now_utc()

        existing = self.get_review(review_id, place_id)

        if not existing:
            # New review — INSERT
            content_hash = self.compute_content_hash(
                review.get("text", ""),
                review.get("rating", 0),
                review.get("date", "")
            )
            engagement_hash = self.compute_engagement_hash(
                review.get("likes", 0),
                self._extract_owner_text(review)
            )

            review_text = json.dumps(self._build_text_dict(review), ensure_ascii=False)
            user_images = json.dumps(review.get("photos", []), ensure_ascii=False)
            owner_responses = json.dumps(
                self._build_owner_dict(review), ensure_ascii=False
            )

            self.backend.execute(
                "INSERT INTO reviews ("
                "review_id, place_id, author, rating, review_text, review_date, "
                "raw_date, likes, user_images, profile_url, profile_picture, "
                "owner_responses, created_date, last_modified, last_seen_session, "
                "last_changed_session, is_deleted, content_hash, engagement_hash, row_version"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1)",
                (review_id, place_id, review.get("author", ""),
                 review.get("rating", 0), review_text,
                 review.get("review_date", ""), review.get("date", ""),
                 review.get("likes", 0), user_images,
                 review.get("profile", ""), review.get("avatar", ""),
                 owner_responses, now, now, session_id, session_id,
                 content_hash, engagement_hash)
            )
            self.backend.commit()

            self.log_history(review_id, place_id, "insert", session_id=session_id,
                             new_content_hash=content_hash,
                             new_engagement_hash=engagement_hash)
            return "new"

        # Existing review — check for changes
        new_content_hash = self.compute_content_hash(
            review.get("text", ""),
            review.get("rating", 0),
            review.get("date", "")
        )
        new_engagement_hash = self.compute_engagement_hash(
            review.get("likes", 0),
            self._extract_owner_text(review)
        )

        old_content_hash = existing.get("content_hash", "")
        old_engagement_hash = existing.get("engagement_hash", "")
        content_changed = new_content_hash != old_content_hash
        engagement_changed = new_engagement_hash != old_engagement_hash
        was_deleted = existing.get("is_deleted", 0) == 1

        # "new_only" mode: skip all updates to existing reviews (but resurrect deleted)
        if scrape_mode == "new_only" and not was_deleted:
            self.backend.execute(
                "UPDATE reviews SET last_seen_session = ? WHERE review_id = ? AND place_id = ?",
                (session_id, review_id, place_id)
            )
            self.backend.commit()
            return "unchanged"

        if not content_changed and not engagement_changed and not was_deleted:
            # No changes — just update last_seen
            self.backend.execute(
                "UPDATE reviews SET last_seen_session = ? "
                "WHERE review_id = ? AND place_id = ?",
                (session_id, review_id, place_id)
            )
            self.backend.commit()
            return "unchanged"

        # Merge review data
        merged_text = existing.get("_review_text_raw", {})
        new_text = self._build_text_dict(review)
        if isinstance(merged_text, dict):
            merged_text.update(new_text)
        else:
            merged_text = new_text

        merged_images = list(set(
            existing.get("_user_images_raw", []) + review.get("photos", [])
        ))

        merged_owner = existing.get("_owner_responses_raw", {})
        new_owner = self._build_owner_dict(review)
        if isinstance(merged_owner, dict):
            merged_owner.update(new_owner)
        else:
            merged_owner = new_owner

        # Determine best avatar
        avatar = review.get("avatar", "")
        if avatar and (not existing.get("profile_picture")
                       or len(avatar) > len(existing.get("profile_picture", ""))):
            profile_picture = avatar
        else:
            profile_picture = existing.get("profile_picture", "")

        # Determine best likes
        likes = max(review.get("likes", 0), existing.get("likes", 0))

        changed_fields = {}
        if content_changed:
            changed_fields["content_hash"] = [old_content_hash, new_content_hash]
        if engagement_changed:
            changed_fields["engagement_hash"] = [old_engagement_hash, new_engagement_hash]

        # Optimistic locking with retry
        old_version = existing.get("row_version", 1)
        for attempt in range(max_retries):
            result = self.backend.execute(
                "UPDATE reviews SET "
                "author = ?, rating = ?, review_text = ?, review_date = ?, "
                "raw_date = ?, likes = ?, user_images = ?, profile_url = ?, "
                "profile_picture = ?, owner_responses = ?, last_modified = ?, "
                "last_seen_session = ?, last_changed_session = ?, "
                "is_deleted = 0, content_hash = ?, engagement_hash = ?, "
                "row_version = row_version + 1 "
                "WHERE review_id = ? AND place_id = ? AND row_version = ?",
                (review.get("author", "") or existing.get("author", ""),
                 review.get("rating", 0) or existing.get("rating", 0),
                 json.dumps(merged_text, ensure_ascii=False),
                 review.get("review_date", "") or existing.get("review_date", ""),
                 review.get("date", "") or existing.get("raw_date", ""),
                 likes,
                 json.dumps(merged_images, ensure_ascii=False),
                 review.get("profile", "") or existing.get("profile_url", ""),
                 profile_picture,
                 json.dumps(merged_owner, ensure_ascii=False),
                 now, session_id, session_id,
                 new_content_hash, new_engagement_hash,
                 review_id, place_id, old_version)
            )
            self.backend.commit()

            if result.rowcount > 0:
                break
            # Row version changed — re-read and retry
            existing = self.get_review(review_id, place_id)
            if not existing:
                return "new"  # concurrent delete, treat as new
            old_version = existing.get("row_version", 1)

        action = "restored" if was_deleted else "updated"
        self.log_history(
            review_id, place_id, "restore" if was_deleted else "update",
            session_id=session_id,
            changed_fields=changed_fields if changed_fields else None,
            old_content_hash=old_content_hash,
            new_content_hash=new_content_hash,
            old_engagement_hash=old_engagement_hash,
            new_engagement_hash=new_engagement_hash
        )
        return action

    def flush_batch(self, place_id: str, batch: List[Dict[str, Any]],
                    session_id: int, scrape_mode: str = "update") -> Dict[str, int]:
        """
        Flush a batch of reviews to the database in a single transaction.
        Returns: {'new': N, 'updated': N, 'restored': N, 'unchanged': N}
        """
        stats = {"new": 0, "updated": 0, "restored": 0, "unchanged": 0}
        for review in batch:
            result = self.upsert_review(place_id, review, session_id,
                                        scrape_mode=scrape_mode)
            stats[result] = stats.get(result, 0) + 1

        # Update place total_reviews
        count_row = self.backend.fetchone(
            "SELECT COUNT(*) as cnt FROM reviews "
            "WHERE place_id = ? AND is_deleted = 0",
            (place_id,)
        )
        if count_row:
            self.backend.execute(
                "UPDATE places SET total_reviews = ? WHERE place_id = ?",
                (count_row["cnt"], place_id)
            )
            self.backend.commit()

        return stats

    def review_changed(self, review_id: str, place_id: str,
                       new_content_hash: str) -> bool:
        """Check if a review's content has changed since last scrape."""
        row = self.backend.fetchone(
            "SELECT content_hash FROM reviews WHERE review_id = ? AND place_id = ?",
            (review_id, place_id)
        )
        if not row:
            return True  # new review = changed
        return row["content_hash"] != new_content_hash

    @staticmethod
    def compute_content_hash(text: str, rating: float, raw_date: str) -> str:
        """Compute SHA-256 hash of stable review content.

        Uses the raw date string (e.g. "2 months ago") rather than the parsed
        ISO timestamp, because relative dates parsed via datetime.now() change
        every second and would cause false "updated" results on every scrape.
        """
        content = f"{text}|{rating}|{raw_date}"
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def compute_engagement_hash(likes: int, owner_response_text: str) -> str:
        """Compute SHA-256 hash of volatile engagement data."""
        content = f"{likes}|{owner_response_text}"
        return hashlib.sha256(content.encode()).hexdigest()

    # === Stop-on-Match Logic ===

    def should_stop(self, review_id: str, place_id: str,
                    new_content_hash: str, consecutive_unchanged: int,
                    threshold: int = 3) -> bool:
        """
        Database-driven stop_on_match.
        Returns True only after threshold consecutive unchanged reviews.
        """
        if not self.review_changed(review_id, place_id, new_content_hash):
            return (consecutive_unchanged + 1) >= threshold
        return False

    # === Stale Review Detection ===

    def mark_stale(self, place_id: str, session_id: int,
                   scraped_ids: Set[str], min_unseen_sessions: int = 3) -> int:
        """
        After a full scrape, mark reviews not seen in this session as
        potentially deleted. Returns count of newly marked stale reviews.
        """
        if not scraped_ids:
            return 0

        # Get all non-deleted review IDs for this place
        all_ids = self.get_review_ids(place_id)
        missing = all_ids - scraped_ids

        count = 0
        now = _now_utc()
        for rid in missing:
            self.backend.execute(
                "UPDATE reviews SET is_deleted = 1, last_modified = ?, "
                "last_changed_session = ? "
                "WHERE review_id = ? AND place_id = ? AND is_deleted = 0",
                (now, session_id, rid, place_id)
            )
            if self.backend.execute(
                "SELECT changes()"
            ).fetchone()[0] > 0:
                count += 1
                self.log_history(rid, place_id, "soft_delete",
                                 session_id=session_id, actor="scraper")

        if count:
            self.backend.commit()
        return count

    # === Session Tracking ===

    def start_session(self, place_id: str, sort_by: str = None,
                      action: str = "scrape") -> int:
        """Create a scrape session record. Returns session_id."""
        cursor = self.backend.execute(
            "INSERT INTO scrape_sessions (place_id, action, started_at, status, sort_by) "
            "VALUES (?, ?, ?, 'running', ?)",
            (place_id, action, _now_utc(), sort_by)
        )
        self.backend.commit()
        return cursor.lastrowid

    def end_session(self, session_id: int, status: str,
                    reviews_found: int = 0, reviews_new: int = 0,
                    reviews_updated: int = 0, error: str = None) -> None:
        """Complete a scrape session record."""
        self.backend.execute(
            "UPDATE scrape_sessions SET completed_at = ?, status = ?, "
            "reviews_found = ?, reviews_new = ?, reviews_updated = ?, "
            "error_message = ? WHERE session_id = ?",
            (_now_utc(), status, reviews_found, reviews_new,
             reviews_updated, error, session_id)
        )
        self.backend.commit()

    # === History / Audit Trail ===

    def log_history(self, review_id: str, place_id: str, action: str,
                    session_id: int = None, actor: str = "scraper",
                    changed_fields: Dict = None,
                    old_content_hash: str = None, new_content_hash: str = None,
                    old_engagement_hash: str = None,
                    new_engagement_hash: str = None) -> None:
        """Log a review mutation to the history table."""
        self.backend.execute(
            "INSERT INTO review_history ("
            "review_id, place_id, session_id, actor, action, changed_fields, "
            "old_content_hash, new_content_hash, old_engagement_hash, "
            "new_engagement_hash, timestamp"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (review_id, place_id, session_id, actor, action,
             json.dumps(changed_fields) if changed_fields else None,
             old_content_hash, new_content_hash,
             old_engagement_hash, new_engagement_hash, _now_utc())
        )
        self.backend.commit()

    def get_review_history(self, review_id: str, place_id: str) -> List[Dict]:
        """Get full change history for a specific review."""
        return self.backend.fetchall(
            "SELECT * FROM review_history "
            "WHERE review_id = ? AND place_id = ? ORDER BY timestamp",
            (review_id, place_id)
        )

    def get_session_history(self, session_id: int) -> List[Dict]:
        """Get all changes made during a specific scrape session."""
        return self.backend.fetchall(
            "SELECT * FROM review_history WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )

    # === Export (JSON / CSV) ===

    def export_reviews_json(self, place_id: str,
                            include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Export reviews for a place as JSON-serializable list."""
        return self.get_reviews(place_id, include_deleted=include_deleted)

    def export_all_json(self, include_deleted: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """Export all reviews grouped by place_id."""
        places = self.list_places()
        result = {}
        for place in places:
            pid = place["place_id"]
            result[pid] = self.export_reviews_json(pid, include_deleted)
        return result

    def export_reviews_csv(self, place_id: str, output_path: str,
                           include_deleted: bool = False) -> int:
        """Export reviews for a place as CSV file. Returns row count."""
        reviews = self.get_reviews(place_id, include_deleted=include_deleted)
        if not reviews:
            return 0

        # Collect all language keys from review_text
        all_langs = set()
        all_owner_langs = set()
        for r in reviews:
            if isinstance(r.get("review_text"), dict):
                all_langs.update(r["review_text"].keys())
            if isinstance(r.get("owner_responses"), dict):
                all_owner_langs.update(r["owner_responses"].keys())

        fieldnames = [
            "review_id", "author", "rating", "review_date", "raw_date", "likes",
            "profile_url", "profile_picture", "user_images",
        ]
        for lang in sorted(all_langs):
            fieldnames.append(f"text_{lang}")
        for lang in sorted(all_owner_langs):
            fieldnames.append(f"owner_response_{lang}")
        fieldnames.extend(["created_date", "last_modified", "is_deleted"])

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in reviews:
                row = {
                    "review_id": r.get("review_id"),
                    "author": r.get("author"),
                    "rating": r.get("rating"),
                    "review_date": r.get("review_date"),
                    "raw_date": r.get("raw_date"),
                    "likes": r.get("likes"),
                    "profile_url": r.get("profile_url"),
                    "profile_picture": r.get("profile_picture"),
                    "user_images": ";".join(r.get("user_images", []) if isinstance(r.get("user_images"), list) else []),
                    "created_date": r.get("created_date"),
                    "last_modified": r.get("last_modified"),
                    "is_deleted": r.get("is_deleted"),
                }
                if isinstance(r.get("review_text"), dict):
                    for lang, text in r["review_text"].items():
                        row[f"text_{lang}"] = text
                if isinstance(r.get("owner_responses"), dict):
                    for lang, resp in r["owner_responses"].items():
                        row[f"owner_response_{lang}"] = resp.get("text", "") if isinstance(resp, dict) else resp
                writer.writerow(row)

        return len(reviews)

    def export_all_csv(self, output_dir: str,
                       include_deleted: bool = False) -> Dict[str, int]:
        """Export all places to separate CSV files."""
        os.makedirs(output_dir, exist_ok=True)
        places = self.list_places()
        result = {}
        for place in places:
            pid = place["place_id"]
            path = os.path.join(output_dir, f"reviews_{pid}.csv")
            result[pid] = self.export_reviews_csv(pid, path, include_deleted)
        return result

    # === MongoDB Sync ===

    def get_reviews_for_sync(self, place_id: str,
                             since_session: int = None,
                             since_timestamp: str = None) -> List[Dict[str, Any]]:
        """
        Get reviews from DB ready for sync.
        Supports incremental sync via session or timestamp.
        """
        if since_session:
            return self.backend.fetchall(
                "SELECT * FROM reviews WHERE place_id = ? "
                "AND (last_changed_session > ? OR last_modified > ?)",
                (place_id, since_session,
                 since_timestamp or "1970-01-01T00:00:00")
            )
        return self.get_reviews(place_id, include_deleted=True)

    # === S3 Image Sync ===

    def get_pending_images(self, place_id: str) -> List[Dict[str, Any]]:
        """Get reviews with images not yet uploaded to S3."""
        rows = self.backend.fetchall(
            "SELECT review_id, place_id, user_images, profile_picture "
            "FROM reviews WHERE place_id = ? AND is_deleted = 0 "
            "AND user_images IS NOT NULL AND s3_images IS NULL",
            (place_id,)
        )
        result = []
        for r in rows:
            row = dict(r)
            if row.get("user_images"):
                try:
                    row["user_images"] = json.loads(row["user_images"])
                except (json.JSONDecodeError, TypeError):
                    row["user_images"] = []
            result.append(row)
        return result

    def mark_images_uploaded(self, review_id: str, place_id: str,
                             s3_urls: Dict[str, str],
                             s3_profile_picture: str = None) -> None:
        """Store S3 URLs without mutating original image URLs."""
        self.backend.execute(
            "UPDATE reviews SET s3_images = ?, s3_profile_picture = ?, "
            "last_modified = ? "
            "WHERE review_id = ? AND place_id = ?",
            (json.dumps(s3_urls, ensure_ascii=False), s3_profile_picture,
             _now_utc(), review_id, place_id)
        )
        self.backend.commit()

    # === Database Management ===

    def clear_place(self, place_id: str) -> Dict[str, int]:
        """Delete all data for a specific place. Returns counts per table."""
        counts = {}
        for table in ["review_history", "sync_checkpoints", "reviews",
                       "scrape_sessions"]:
            row = self.backend.fetchone(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE place_id = ?",
                (place_id,)
            )
            counts[table] = row["cnt"] if row else 0

        # place_aliases uses canonical_id, not place_id
        row = self.backend.fetchone(
            "SELECT COUNT(*) as cnt FROM place_aliases WHERE canonical_id = ?",
            (place_id,)
        )
        counts["place_aliases"] = row["cnt"] if row else 0

        # Delete the place (cascades to all dependents)
        self.backend.execute(
            "DELETE FROM places WHERE place_id = ?", (place_id,)
        )
        self.backend.commit()
        counts["places"] = 1
        return counts

    def clear_all(self) -> Dict[str, int]:
        """Delete ALL data from all tables. Schema remains intact."""
        counts = {}
        for table in ["review_history", "sync_checkpoints", "reviews",
                       "scrape_sessions", "place_aliases", "places"]:
            row = self.backend.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
            counts[table] = row["cnt"] if row else 0
            self.backend.execute(f"DELETE FROM {table}")
        self.backend.commit()
        return counts

    def get_stats(self) -> Dict[str, Any]:
        """Database statistics."""
        stats: Dict[str, Any] = {}
        for table in ["places", "reviews", "scrape_sessions",
                       "review_history", "sync_checkpoints", "place_aliases"]:
            row = self.backend.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
            stats[f"{table}_count"] = row["cnt"] if row else 0

        # DB file size
        db_path = Path(self.backend.db_path)
        stats["db_size_bytes"] = db_path.stat().st_size if db_path.exists() else 0

        # Per-place stats
        stats["places"] = self.backend.fetchall(
            "SELECT p.place_id, p.place_name, p.total_reviews, p.last_scraped "
            "FROM places p ORDER BY p.last_scraped DESC"
        )
        return stats

    def vacuum(self) -> None:
        """Reclaim disk space after large deletions."""
        self.backend.vacuum()

    # === Review Management (CLI) ===

    def hide_review(self, review_id: str, place_id: str) -> bool:
        """Manually soft-delete a review."""
        result = self.backend.execute(
            "UPDATE reviews SET is_deleted = 1, last_modified = ?, "
            "row_version = row_version + 1 "
            "WHERE review_id = ? AND place_id = ? AND is_deleted = 0",
            (_now_utc(), review_id, place_id)
        )
        self.backend.commit()
        if result.rowcount > 0:
            self.log_history(review_id, place_id, "soft_delete", actor="cli_hide")
            return True
        return False

    def restore_review(self, review_id: str, place_id: str) -> bool:
        """Restore a soft-deleted review."""
        result = self.backend.execute(
            "UPDATE reviews SET is_deleted = 0, last_modified = ?, "
            "row_version = row_version + 1 "
            "WHERE review_id = ? AND place_id = ? AND is_deleted = 1",
            (_now_utc(), review_id, place_id)
        )
        self.backend.commit()
        if result.rowcount > 0:
            self.log_history(review_id, place_id, "restore", actor="cli_restore")
            return True
        return False

    # === Sync Checkpoints ===

    def get_sync_checkpoint(self, place_id: str, target: str) -> Optional[Dict]:
        """Get last sync checkpoint for a place/target pair."""
        return self.backend.fetchone(
            "SELECT * FROM sync_checkpoints WHERE place_id = ? AND target = ?",
            (place_id, target)
        )

    def update_sync_checkpoint(self, place_id: str, target: str,
                                session_id: int, status: str = "ok",
                                cursor_review_id: str = None,
                                cursor_updated_at: str = None,
                                error: str = None) -> None:
        """Update or create sync checkpoint after sync operation."""
        now = _now_utc()
        existing = self.get_sync_checkpoint(place_id, target)
        if existing:
            self.backend.execute(
                "UPDATE sync_checkpoints SET last_synced_at = ?, "
                "last_synced_session = ?, cursor_review_id = ?, "
                "cursor_updated_at = ?, attempt_count = ?, "
                "status = ?, error_message = ? "
                "WHERE place_id = ? AND target = ?",
                (now, session_id, cursor_review_id, cursor_updated_at,
                 0 if status == "ok" else (existing.get("attempt_count", 0) + 1),
                 status, error, place_id, target)
            )
        else:
            self.backend.execute(
                "INSERT INTO sync_checkpoints "
                "(place_id, target, last_synced_at, last_synced_session, "
                "cursor_review_id, cursor_updated_at, attempt_count, status, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (place_id, target, now, session_id, cursor_review_id,
                 cursor_updated_at, 0 if status == "ok" else 1, status, error)
            )
        self.backend.commit()

    def reset_sync_checkpoint(self, place_id: str, target: str) -> None:
        """Reset checkpoint to force full resync."""
        self.backend.execute(
            "DELETE FROM sync_checkpoints WHERE place_id = ? AND target = ?",
            (place_id, target)
        )
        self.backend.commit()

    def get_all_sync_status(self) -> List[Dict]:
        """Get sync status for all places/targets."""
        return self.backend.fetchall(
            "SELECT sc.*, p.place_name FROM sync_checkpoints sc "
            "LEFT JOIN places p ON sc.place_id = p.place_id "
            "ORDER BY sc.place_id, sc.target"
        )

    # === History Management ===

    def prune_history(self, older_than_days: int = 90,
                      dry_run: bool = False) -> int:
        """Delete history entries older than N days. Returns count."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        if dry_run:
            row = self.backend.fetchone(
                "SELECT COUNT(*) as cnt FROM review_history WHERE timestamp < ?",
                (cutoff,)
            )
            return row["cnt"] if row else 0

        self.backend.execute(
            "DELETE FROM review_history WHERE timestamp < ?", (cutoff,)
        )
        count = self.backend.execute("SELECT changes()").fetchone()[0]
        self.backend.commit()
        return count

    # === Schema Management ===

    def get_schema_version(self) -> int:
        """Get current schema version."""
        return self.backend.get_schema_version()

    # === URL Canonicalization ===

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """Delegate to place_id module."""
        return canonicalize_url(url)

    # === Cleanup ===

    def close(self) -> None:
        """Close the database connection."""
        self.backend.close()

    # === Private helpers ===

    @staticmethod
    def _deserialize_review(row: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize JSON fields from a review row."""
        result = dict(row)
        for field in ("review_text", "owner_responses", "s3_images"):
            if result.get(field) and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        for field in ("user_images",):
            if result.get(field) and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = []
        # Store raw values for merge logic
        result["_review_text_raw"] = result.get("review_text", {})
        result["_user_images_raw"] = result.get("user_images", [])
        result["_owner_responses_raw"] = result.get("owner_responses", {})
        return result

    @staticmethod
    def _build_text_dict(review: Dict[str, Any]) -> Dict[str, str]:
        """Build language->text dict from a raw review."""
        text = review.get("text", "")
        lang = review.get("lang", "en")
        if text:
            return {lang: text}
        return {}

    @staticmethod
    def _build_owner_dict(review: Dict[str, Any]) -> Dict[str, Any]:
        """Build owner responses dict from a raw review."""
        owner_text = review.get("owner_text", "")
        if owner_text:
            from modules.utils import detect_lang
            lang = detect_lang(owner_text)
            return {lang: {"text": owner_text}}
        return {}

    @staticmethod
    def _extract_owner_text(review: Dict[str, Any]) -> str:
        """Extract owner response text for hash computation."""
        return review.get("owner_text", "")


# Migration definitions (version -> list of DDL statements)
_MIGRATIONS: Dict[int, List[str]] = {
    # Future migrations go here:
    # 2: ["ALTER TABLE reviews ADD COLUMN new_field TEXT;"],
}
