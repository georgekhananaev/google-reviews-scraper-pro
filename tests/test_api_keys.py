"""Tests for ApiKeyDB — API key management and audit logging."""

import pytest

from modules.api_keys import ApiKeyDB


@pytest.fixture
def db(tmp_path):
    """Fresh temp-file database for each test."""
    instance = ApiKeyDB(str(tmp_path / "test.db"))
    yield instance
    instance.close()


# ------------------------------------------------------------------
# Key lifecycle
# ------------------------------------------------------------------

class TestKeyLifecycle:
    def test_create_key_returns_id_and_raw_key(self, db):
        key_id, raw_key = db.create_key("test-key")
        assert key_id >= 1
        assert raw_key.startswith("grs_")
        assert len(raw_key) == 4 + 32  # prefix + 32 hex chars

    def test_verify_valid_key(self, db):
        key_id, raw_key = db.create_key("my-key")
        info = db.verify_key(raw_key)
        assert info is not None
        assert info["id"] == key_id
        assert info["name"] == "my-key"

    def test_verify_invalid_key_returns_none(self, db):
        assert db.verify_key("grs_nonexistent1234567890abcdef12") is None

    def test_verify_updates_usage(self, db):
        _, raw_key = db.create_key("counter-key")
        db.verify_key(raw_key)
        db.verify_key(raw_key)
        keys = db.list_keys()
        assert keys[0]["usage_count"] == 2
        assert keys[0]["last_used_at"] is not None

    def test_list_keys(self, db):
        db.create_key("alpha")
        db.create_key("beta")
        keys = db.list_keys()
        assert len(keys) == 2
        names = [k["name"] for k in keys]
        assert "alpha" in names
        assert "beta" in names

    def test_revoke_key(self, db):
        key_id, raw_key = db.create_key("doomed")
        assert db.revoke_key(key_id) is True
        # Verify fails after revoke
        assert db.verify_key(raw_key) is None

    def test_revoke_nonexistent_key_returns_false(self, db):
        assert db.revoke_key(999) is False

    def test_revoke_already_revoked_returns_false(self, db):
        key_id, _ = db.create_key("twice")
        db.revoke_key(key_id)
        assert db.revoke_key(key_id) is False

    def test_has_active_keys(self, db):
        assert db.has_active_keys() is False
        key_id, _ = db.create_key("active")
        assert db.has_active_keys() is True
        db.revoke_key(key_id)
        assert db.has_active_keys() is False

    def test_duplicate_names_allowed(self, db):
        id1, _ = db.create_key("same")
        id2, _ = db.create_key("same")
        assert id1 != id2
        assert len(db.list_keys()) == 2

    def test_each_key_is_unique(self, db):
        _, key1 = db.create_key("a")
        _, key2 = db.create_key("b")
        assert key1 != key2

    def test_list_shows_revoked_keys(self, db):
        key_id, _ = db.create_key("revokable")
        db.revoke_key(key_id)
        keys = db.list_keys()
        assert len(keys) == 1
        assert keys[0]["is_active"] == 0


# ------------------------------------------------------------------
# Audit logging
# ------------------------------------------------------------------

class TestAuditLog:
    def test_log_request(self, db):
        key_id, _ = db.create_key("logger")
        db.log_request(key_id, "logger", "/scrape", "POST", "127.0.0.1", 200, 42)
        rows = db.query_audit_log()
        assert len(rows) == 1
        assert rows[0]["endpoint"] == "/scrape"
        assert rows[0]["method"] == "POST"
        assert rows[0]["status_code"] == 200
        assert rows[0]["response_time_ms"] == 42

    def test_log_request_without_key(self, db):
        db.log_request(None, None, "/", "GET", "10.0.0.1", 200, 5)
        rows = db.query_audit_log()
        assert len(rows) == 1
        assert rows[0]["key_id"] is None

    def test_query_filter_by_key_id(self, db):
        id1, _ = db.create_key("a")
        id2, _ = db.create_key("b")
        db.log_request(id1, "a", "/x", "GET", None, 200, 1)
        db.log_request(id2, "b", "/y", "GET", None, 200, 1)
        rows = db.query_audit_log(key_id=id1)
        assert len(rows) == 1
        assert rows[0]["key_name"] == "a"

    def test_query_limit(self, db):
        for i in range(10):
            db.log_request(None, None, f"/{i}", "GET", None, 200, 1)
        rows = db.query_audit_log(limit=3)
        assert len(rows) == 3

    def test_prune_audit_log(self, db):
        # Insert an entry, then manually backdate it
        db.log_request(None, None, "/old", "GET", None, 200, 1)
        db._db.execute(
            "UPDATE api_audit_log SET timestamp = datetime('now', '-100 days')"
        )
        db._db.commit()
        db.log_request(None, None, "/new", "GET", None, 200, 1)

        # Dry run
        count = db.prune_audit_log(older_than_days=90, dry_run=True)
        assert count == 1
        assert len(db.query_audit_log()) == 2  # nothing deleted

        # Real prune
        count = db.prune_audit_log(older_than_days=90)
        assert count == 1
        remaining = db.query_audit_log()
        assert len(remaining) == 1
        assert remaining[0]["endpoint"] == "/new"


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

class TestKeyStats:
    def test_get_key_stats(self, db):
        key_id, raw_key = db.create_key("stat-key")
        db.verify_key(raw_key)
        db.log_request(key_id, "stat-key", "/jobs", "GET", "1.2.3.4", 200, 10)

        stats = db.get_key_stats(key_id)
        assert stats is not None
        assert stats["name"] == "stat-key"
        assert stats["usage_count"] == 1
        assert len(stats["recent_requests"]) == 1
        assert stats["recent_requests"][0]["endpoint"] == "/jobs"

    def test_get_key_stats_nonexistent(self, db):
        assert db.get_key_stats(999) is None
