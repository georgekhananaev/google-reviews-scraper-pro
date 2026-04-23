"""
Date-range filtering for scraped reviews (issue #19).

Two modes:

- **post_filter** (default): after the scrape, downstream writers drop
  reviews whose parsed date falls outside [after, before]. SQLite retains
  everything — nothing destructive.
- **early_stop**: while scrolling (requires `sort_by: newest`), stop after
  N consecutive cards are older than `after`.

Both modes are additive — omitting the `date_filter` config preserves
v1.2.x behavior exactly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("scraper")

DEFAULT_MODE = "post_filter"
DEFAULT_ON_UNPARSEABLE = "include"
EARLY_STOP_CONSECUTIVE = 3


def _parse_boundary(value: Optional[str]) -> Optional[datetime]:
    """Accept ISO date ('2025-06-01') or full datetime. UTC-normalized."""
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    try:
        if "T" in s or " " in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s + "T00:00:00+00:00")
    except ValueError:
        log.warning("date_filter: could not parse boundary %r", value)
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_review_date(iso_str: str) -> Optional[datetime]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DateFilter:
    """Evaluator for date-range inclusion."""

    def __init__(self, config: dict | None):
        cfg = (config or {}).get("date_filter") or {}
        self.raw_after = cfg.get("after") or None
        self.raw_before = cfg.get("before") or None
        self.after = _parse_boundary(self.raw_after)
        self.before = _parse_boundary(self.raw_before)
        self.mode = (cfg.get("mode") or DEFAULT_MODE).lower()
        self.on_unparseable = (
            (cfg.get("on_unparseable_date") or DEFAULT_ON_UNPARSEABLE).lower()
        )
        self.enabled = self.after is not None or self.before is not None

    @property
    def early_stop_enabled(self) -> bool:
        return self.enabled and self.mode == "early_stop" and self.after is not None

    def includes(self, iso_date: str) -> bool:
        """True if a review with this ISO date should be kept."""
        if not self.enabled:
            return True
        dt = _parse_review_date(iso_date)
        if dt is None:
            return self.on_unparseable != "exclude"
        if self.after and dt < self.after:
            return False
        if self.before and dt > self.before:
            return False
        return True

    def is_past_boundary(self, iso_date: str) -> bool:
        """
        True if the review is older than `after` — used by early-stop mode
        to detect we've scrolled past the requested window.
        """
        if not self.early_stop_enabled:
            return False
        dt = _parse_review_date(iso_date)
        if dt is None:
            return False
        return dt < self.after  # type: ignore[operator]

    def describe(self) -> str:
        if not self.enabled:
            return "disabled"
        return (
            f"mode={self.mode} after={self.raw_after or '∞'} "
            f"before={self.raw_before or '∞'} "
            f"on_unparseable={self.on_unparseable}"
        )
