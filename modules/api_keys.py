"""
API key management with full audit logging.

Stores hashed API keys and request audit logs in SQLite alongside review data.
Uses its own tables (api_keys, api_audit_log) — no coupling to review schema.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from modules.database_backend import SQLiteBackend

_KEY_PREFIX = "grs_"
_KEY_HEX_LEN = 32  # 32 hex chars = 16 bytes of entropy
_DISPLAY_PREFIX_LEN = len(_KEY_PREFIX) + 8  # e.g. "grs_a1b2c3d4..."

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL,
        key_hash     TEXT NOT NULL UNIQUE,
        key_prefix   TEXT NOT NULL,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        last_used_at TEXT,
        usage_count  INTEGER NOT NULL DEFAULT 0,
        is_active    INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_audit_log (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp        TEXT NOT NULL DEFAULT (datetime('now')),
        key_id           INTEGER,
        key_name         TEXT,
        endpoint         TEXT NOT NULL,
        method           TEXT NOT NULL,
        client_ip        TEXT,
        status_code      INTEGER,
        response_time_ms INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON api_audit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_audit_key_id ON api_audit_log(key_id)",
]


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKeyDB:
    """Manages API keys and audit logs stored in SQLite."""

    def __init__(self, db_path: str = "reviews.db"):
        self._db = SQLiteBackend(db_path)
        self._db.connect()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        for ddl in _DDL:
            self._db.execute(ddl)
        self._db.commit()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def create_key(self, name: str) -> tuple:
        """Create a new API key. Returns (key_id, raw_key)."""
        raw_key = _KEY_PREFIX + secrets.token_hex(_KEY_HEX_LEN // 2)
        key_hash = _hash_key(raw_key)
        key_prefix = raw_key[:_DISPLAY_PREFIX_LEN]

        self._db.execute(
            "INSERT INTO api_keys (name, key_hash, key_prefix) VALUES (?, ?, ?)",
            (name, key_hash, key_prefix),
        )
        self._db.commit()
        row = self._db.fetchone(
            "SELECT id FROM api_keys WHERE key_hash = ?", (key_hash,)
        )
        return (row["id"], raw_key)

    def verify_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """Verify a raw API key. Returns key info dict or None."""
        key_hash = _hash_key(raw_key)
        row = self._db.fetchone(
            "SELECT id, name, key_prefix, created_at, last_used_at, usage_count "
            "FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (key_hash,),
        )
        if not row:
            return None

        self._db.execute(
            "UPDATE api_keys SET last_used_at = datetime('now'), "
            "usage_count = usage_count + 1 WHERE id = ?",
            (row["id"],),
        )
        self._db.commit()
        return dict(row)

    def list_keys(self) -> List[Dict[str, Any]]:
        """List all API keys (without hashes)."""
        return self._db.fetchall(
            "SELECT id, name, key_prefix, created_at, last_used_at, "
            "usage_count, is_active FROM api_keys ORDER BY id"
        )

    def revoke_key(self, key_id: int) -> bool:
        """Revoke an API key. Returns True if a key was updated."""
        cursor = self._db.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ? AND is_active = 1",
            (key_id,),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def has_active_keys(self) -> bool:
        """Return True if at least one active key exists."""
        row = self._db.fetchone(
            "SELECT 1 FROM api_keys WHERE is_active = 1 LIMIT 1"
        )
        return row is not None

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def log_request(
        self,
        key_id: Optional[int],
        key_name: Optional[str],
        endpoint: str,
        method: str,
        client_ip: Optional[str],
        status_code: Optional[int],
        response_time_ms: Optional[int],
    ) -> None:
        """Insert a request audit row."""
        self._db.execute(
            "INSERT INTO api_audit_log "
            "(key_id, key_name, endpoint, method, client_ip, status_code, response_time_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key_id, key_name, endpoint, method, client_ip, status_code, response_time_ms),
        )
        self._db.commit()

    def get_key_stats(self, key_id: int) -> Optional[Dict[str, Any]]:
        """Return key info plus recent audit summary."""
        key = self._db.fetchone(
            "SELECT id, name, key_prefix, created_at, last_used_at, "
            "usage_count, is_active FROM api_keys WHERE id = ?",
            (key_id,),
        )
        if not key:
            return None

        recent = self._db.fetchall(
            "SELECT endpoint, method, status_code, timestamp "
            "FROM api_audit_log WHERE key_id = ? ORDER BY id DESC LIMIT 10",
            (key_id,),
        )
        result = dict(key)
        result["recent_requests"] = [dict(r) for r in recent]
        return result

    def query_audit_log(
        self,
        key_id: Optional[int] = None,
        limit: int = 50,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query audit log with optional filters."""
        clauses: List[str] = []
        params: List[Any] = []

        if key_id is not None:
            clauses.append("key_id = ?")
            params.append(key_id)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._db.fetchall(
            f"SELECT * FROM api_audit_log {where} ORDER BY id DESC LIMIT ?",
            tuple(params) + (limit,),
        )

    def prune_audit_log(self, older_than_days: int = 90, dry_run: bool = False) -> int:
        """Delete audit entries older than N days. Returns affected count."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=older_than_days)
        ).strftime("%Y-%m-%d %H:%M:%S")

        row = self._db.fetchone(
            "SELECT COUNT(*) AS cnt FROM api_audit_log WHERE timestamp < ?",
            (cutoff,),
        )
        count = row["cnt"] if row else 0

        if not dry_run and count > 0:
            self._db.execute(
                "DELETE FROM api_audit_log WHERE timestamp < ?", (cutoff,)
            )
            self._db.commit()

        return count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._db.close()
