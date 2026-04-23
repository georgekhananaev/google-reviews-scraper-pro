"""
Selector health telemetry.

Records hit/miss/stale outcomes per CSS selector per scrape session, so
selector decay (Google changing class names) surfaces in telemetry rather
than as a flood of "scraper returns 0 reviews" issues.

Writes are best-effort — if the table is missing or the DB is locked,
we log at DEBUG and move on. Telemetry never blocks the scrape.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("scraper")


SCHEMA = """
CREATE TABLE IF NOT EXISTS selector_health (
    session_id INTEGER NOT NULL,
    selector   TEXT    NOT NULL,
    outcome    TEXT    NOT NULL,
    count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, selector, outcome)
);
"""


class SelectorHealth:
    """Thin recorder around the `selector_health` table."""

    def __init__(self, backend: Any, session_id: int | None):
        self._backend = backend
        self._session_id = session_id
        self._buffer: dict[tuple[str, str], int] = {}
        self._installed = False

    def _ensure_table(self) -> None:
        if self._installed or self._backend is None:
            return
        try:
            self._backend.execute(SCHEMA)
            self._backend.commit()
            self._installed = True
        except Exception as e:  # noqa: BLE001
            log.debug("selector_health: schema install failed: %s", e)

    def record(self, selector: str, outcome: str) -> None:
        """Buffer one observation. Flushed on `flush()`."""
        if outcome not in ("hit", "miss", "stale"):
            return
        key = (selector, outcome)
        self._buffer[key] = self._buffer.get(key, 0) + 1

    def flush(self) -> None:
        """Write buffered counts. Safe to call repeatedly."""
        if not self._buffer or self._backend is None or self._session_id is None:
            self._buffer.clear()
            return
        self._ensure_table()
        try:
            for (selector, outcome), count in self._buffer.items():
                self._backend.execute(
                    "INSERT INTO selector_health (session_id, selector, outcome, count) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(session_id, selector, outcome) "
                    "DO UPDATE SET count = count + excluded.count",
                    (self._session_id, selector, outcome, count),
                )
            self._backend.commit()
        except Exception as e:  # noqa: BLE001
            log.debug("selector_health: flush failed: %s", e)
        finally:
            self._buffer.clear()


def aggregate_hit_rates(backend: Any, last_n_sessions: int = 30) -> list[dict]:
    """Return per-selector hit-rate across the most recent N sessions."""
    if backend is None:
        return []
    try:
        rows = backend.fetchall(
            """
            WITH recent AS (
                SELECT session_id FROM scrape_sessions
                ORDER BY session_id DESC LIMIT ?
            )
            SELECT selector,
                   SUM(CASE WHEN outcome = 'hit' THEN count ELSE 0 END)  AS hits,
                   SUM(CASE WHEN outcome = 'miss' THEN count ELSE 0 END) AS misses,
                   SUM(CASE WHEN outcome = 'stale' THEN count ELSE 0 END) AS stales,
                   SUM(count) AS total
            FROM selector_health
            WHERE session_id IN (SELECT session_id FROM recent)
            GROUP BY selector
            ORDER BY total DESC
            """,
            (last_n_sessions,),
        )
    except Exception as e:  # noqa: BLE001
        log.debug("selector_health: aggregate failed: %s", e)
        return []

    result = []
    for row in rows:
        hits = row.get("hits", 0) or 0
        total = row.get("total", 0) or 0
        rate = (hits / total) if total else 0.0
        result.append({
            "selector": row["selector"],
            "hits": hits,
            "misses": row.get("misses", 0) or 0,
            "stales": row.get("stales", 0) or 0,
            "total": total,
            "hit_rate": round(rate, 3),
        })
    return result
