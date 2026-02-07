"""
Database backend abstraction for review storage.

Provides a Protocol defining the database interface plus a concrete SQLiteBackend.
Future PostgreSQL/MySQL backends implement the same protocol.
"""

import sqlite3
from contextlib import contextmanager
from typing import Protocol, Dict, Any, Optional, List


class DatabaseBackend(Protocol):
    """
    Protocol defining the database interface.
    Implementations: SQLiteBackend, PostgreSQLBackend (future), MySQLBackend (future).
    """

    # Connection lifecycle
    def connect(self) -> None: ...
    def close(self) -> None: ...

    # Query execution
    def execute(self, sql: str, params: tuple = ()) -> Any: ...
    def executemany(self, sql: str, params_list: List[tuple]) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]: ...
    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]: ...

    # Transactions
    def begin_write(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

    # Schema management
    def table_exists(self, name: str) -> bool: ...
    def init_schema(self, version: int, ddl_statements: List[str]) -> None: ...
    def get_schema_version(self) -> int: ...
    def migrate(self, from_version: int, to_version: int,
                migrations: Dict[int, List[str]]) -> None: ...

    # Dialect helpers
    def placeholder(self) -> str: ...
    def now_utc(self) -> str: ...
    def upsert_sql(self, table: str, columns: List[str],
                   conflict_keys: List[str], update_columns: List[str]) -> str: ...
    def vacuum(self) -> None: ...


class SQLiteBackend:
    """SQLite implementation (default, zero external dependencies)."""

    def __init__(self, db_path: str = "reviews.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self.conn = sqlite3.connect(self.db_path, timeout=30.0)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def _ensure_connected(self) -> sqlite3.Connection:
        if self.conn is None:
            self.connect()
        return self.conn  # type: ignore[return-value]

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._ensure_connected().execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        return self._ensure_connected().executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        cursor = self.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

    def begin_write(self) -> None:
        self._ensure_connected().execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self._ensure_connected().commit()

    def rollback(self) -> None:
        self._ensure_connected().rollback()

    @contextmanager
    def transaction(self):
        """Context manager for write transactions with auto-commit/rollback."""
        self.begin_write()
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise

    def table_exists(self, name: str) -> bool:
        row = self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,)
        )
        return row is not None

    def init_schema(self, version: int, ddl_statements: List[str]) -> None:
        conn = self._ensure_connected()
        for ddl in ddl_statements:
            conn.executescript(ddl)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (id, version, applied_at, description) "
            "VALUES (1, ?, datetime('now'), ?)",
            (version, f"Initial schema v{version}")
        )
        conn.commit()

    def get_schema_version(self) -> int:
        if not self.table_exists("schema_version"):
            return 0
        row = self.fetchone("SELECT version FROM schema_version WHERE id = 1")
        return row["version"] if row else 0

    def migrate(self, from_version: int, to_version: int,
                migrations: Dict[int, List[str]]) -> None:
        conn = self._ensure_connected()
        for v in range(from_version + 1, to_version + 1):
            if v not in migrations:
                raise ValueError(f"Missing migration for version {v}")
            for sql in migrations[v]:
                conn.executescript(sql)
            conn.execute(
                "UPDATE schema_version SET version = ?, applied_at = datetime('now'), "
                "description = ? WHERE id = 1",
                (v, f"Migration to v{v}")
            )
        conn.commit()

    def placeholder(self) -> str:
        return "?"

    def now_utc(self) -> str:
        return "datetime('now')"

    def upsert_sql(self, table: str, columns: List[str],
                   conflict_keys: List[str], update_columns: List[str]) -> str:
        """Generate SQLite ON CONFLICT DO UPDATE upsert SQL."""
        placeholders = ", ".join(["?"] * len(columns))
        col_list = ", ".join(columns)
        conflict = ", ".join(conflict_keys)
        updates = ", ".join(f"{c} = excluded.{c}" for c in update_columns)
        return (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO UPDATE SET {updates}"
        )

    def vacuum(self) -> None:
        self._ensure_connected().execute("VACUUM")


def create_database(config: Dict[str, Any]) -> SQLiteBackend:
    """
    Create the appropriate database backend from config.

    Supports:
    - database.engine = "sqlite" (default)
    - Flat db_path key (backward compat)
    - Future: "postgresql", "mysql"
    """
    db_config = config.get("database", {})
    engine = db_config.get("engine", "sqlite")

    if engine == "sqlite":
        path = db_config.get("path", config.get("db_path", "reviews.db"))
        backend = SQLiteBackend(path)
        backend.connect()
        return backend
    elif engine == "postgresql":
        raise NotImplementedError(
            "PostgreSQL backend not yet implemented. Use engine='sqlite'."
        )
    elif engine == "mysql":
        raise NotImplementedError(
            "MySQL backend not yet implemented. Use engine='sqlite'."
        )
    else:
        raise ValueError(f"Unknown database engine: {engine}")
