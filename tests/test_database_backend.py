"""Tests for database abstraction layer."""

import sqlite3

import pytest

from modules.database_backend import SQLiteBackend, create_database


class TestSQLiteBackend:
    """Tests for SQLiteBackend implementation."""

    @pytest.fixture
    def backend(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        b = SQLiteBackend(db_path)
        b.connect()
        yield b
        b.close()

    def test_connect_creates_file(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        b = SQLiteBackend(db_path)
        b.connect()
        assert (tmp_path / "new.db").exists()
        b.close()

    def test_wal_mode_enabled(self, backend):
        row = backend.fetchone("PRAGMA journal_mode")
        assert row["journal_mode"] == "wal"

    def test_foreign_keys_enabled(self, backend):
        row = backend.fetchone("PRAGMA foreign_keys")
        assert row["foreign_keys"] == 1

    def test_execute_returns_cursor(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        cursor = backend.execute("INSERT INTO t (id) VALUES (1)")
        assert cursor.lastrowid == 1

    def test_fetchone_returns_dict(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        backend.execute("INSERT INTO t VALUES (1, 'test')")
        row = backend.fetchone("SELECT * FROM t WHERE id = ?", (1,))
        assert row == {"id": 1, "name": "test"}

    def test_fetchone_returns_none(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER)")
        assert backend.fetchone("SELECT * FROM t WHERE id = ?", (999,)) is None

    def test_fetchall_returns_list(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER)")
        backend.execute("INSERT INTO t VALUES (1)")
        backend.execute("INSERT INTO t VALUES (2)")
        rows = backend.fetchall("SELECT * FROM t ORDER BY id")
        assert rows == [{"id": 1}, {"id": 2}]

    def test_transaction_commit(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER)")
        with backend.transaction():
            backend.execute("INSERT INTO t VALUES (1)")
        assert backend.fetchone("SELECT * FROM t")["id"] == 1

    def test_transaction_rollback(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER)")
        backend.commit()
        with pytest.raises(ValueError):
            with backend.transaction():
                backend.execute("INSERT INTO t VALUES (1)")
                raise ValueError("test error")
        assert backend.fetchone("SELECT * FROM t") is None

    def test_table_exists(self, backend):
        assert not backend.table_exists("nonexistent")
        backend.execute("CREATE TABLE t (id INTEGER)")
        assert backend.table_exists("t")

    def test_init_schema(self, backend):
        ddl = "CREATE TABLE IF NOT EXISTS schema_version (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL, applied_at TEXT NOT NULL, description TEXT);"
        backend.init_schema(1, [ddl])
        assert backend.get_schema_version() == 1

    def test_get_schema_version_no_table(self, backend):
        assert backend.get_schema_version() == 0

    def test_migrate(self, backend):
        ddl = "CREATE TABLE IF NOT EXISTS schema_version (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL, applied_at TEXT NOT NULL, description TEXT);"
        backend.init_schema(1, [ddl])
        backend.execute("CREATE TABLE t (id INTEGER)")
        backend.commit()
        migrations = {
            2: ["ALTER TABLE t ADD COLUMN name TEXT;"],
        }
        backend.migrate(1, 2, migrations)
        assert backend.get_schema_version() == 2

    def test_placeholder(self, backend):
        assert backend.placeholder() == "?"

    def test_upsert_sql(self, backend):
        sql = backend.upsert_sql(
            "reviews", ["id", "name", "rating"],
            ["id"], ["name", "rating"]
        )
        assert "ON CONFLICT(id) DO UPDATE SET" in sql
        assert "name = excluded.name" in sql

    def test_vacuum(self, backend):
        backend.execute("CREATE TABLE t (id INTEGER)")
        backend.execute("INSERT INTO t VALUES (1)")
        backend.execute("DELETE FROM t")
        backend.commit()
        backend.vacuum()  # should not raise

    def test_auto_connect(self, tmp_path):
        db_path = str(tmp_path / "auto.db")
        b = SQLiteBackend(db_path)
        # Should auto-connect on first execute
        b.execute("CREATE TABLE t (id INTEGER)")
        assert b.conn is not None
        b.close()


class TestCreateDatabase:
    """Tests for create_database factory function."""

    def test_default_creates_sqlite(self, tmp_path):
        backend = create_database({"db_path": str(tmp_path / "test.db")})
        assert isinstance(backend, SQLiteBackend)
        backend.close()

    def test_explicit_sqlite(self, tmp_path):
        config = {"database": {"engine": "sqlite", "path": str(tmp_path / "test.db")}}
        backend = create_database(config)
        assert isinstance(backend, SQLiteBackend)
        backend.close()

    def test_unknown_engine_raises(self):
        with pytest.raises(ValueError, match="Unknown database engine"):
            create_database({"database": {"engine": "oracle"}})

    def test_postgresql_not_implemented(self):
        with pytest.raises(NotImplementedError):
            create_database({"database": {"engine": "postgresql", "uri": "..."}})

    def test_mysql_not_implemented(self):
        with pytest.raises(NotImplementedError):
            create_database({"database": {"engine": "mysql", "uri": "..."}})

    def test_backward_compat_db_path(self, tmp_path):
        config = {"db_path": str(tmp_path / "compat.db")}
        backend = create_database(config)
        assert isinstance(backend, SQLiteBackend)
        assert backend.db_path == str(tmp_path / "compat.db")
        backend.close()
