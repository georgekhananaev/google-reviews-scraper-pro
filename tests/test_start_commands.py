"""Tests for start.py command dispatch and management commands."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from modules.review_db import ReviewDB


def _make_db(tmp_path, reviews=None):
    """Create a test DB and optionally populate it."""
    db_path = str(tmp_path / "test.db")
    db = ReviewDB(db_path)
    if reviews:
        db.upsert_place("place1", "Test Place", "http://test")
        for r in reviews:
            db.upsert_review("place1", r)
    return db, db_path


def _make_review(rid="r1", text="Great!", rating=5.0):
    return {
        "review_id": rid, "text": text, "rating": rating,
        "likes": 1, "lang": "en", "date": "3 months ago",
        "review_date": "2025-06-15", "author": "Test",
        "profile": "", "avatar": "", "owner_text": "", "photos": [],
    }


class TestExportCommand:
    """Tests for the export command."""

    def test_export_json(self, tmp_path):
        db, db_path = _make_db(tmp_path, [_make_review("r1"), _make_review("r2")])
        db.close()

        output_path = str(tmp_path / "export.json")
        from start import _run_export, _get_db_path
        from types import SimpleNamespace

        args = SimpleNamespace(
            db_path=db_path, config=None,
            format="json", place_id="place1",
            output=output_path, include_deleted=False,
        )
        _run_export({}, args)

        data = json.loads(Path(output_path).read_text())
        assert len(data) == 2

    def test_export_csv(self, tmp_path):
        db, db_path = _make_db(tmp_path, [_make_review("r1")])
        db.close()

        output_path = str(tmp_path / "export.csv")
        from start import _run_export
        from types import SimpleNamespace

        args = SimpleNamespace(
            db_path=db_path, config=None,
            format="csv", place_id="place1",
            output=output_path, include_deleted=False,
        )
        _run_export({}, args)
        assert Path(output_path).exists()


class TestDbStatsCommand:
    """Tests for the db-stats command."""

    def test_shows_stats(self, tmp_path, capsys):
        db, db_path = _make_db(tmp_path, [_make_review("r1")])
        db.close()

        from start import _run_db_stats
        from types import SimpleNamespace
        args = SimpleNamespace(db_path=db_path, config=None)
        _run_db_stats({}, args)

        output = capsys.readouterr().out
        assert "Reviews:" in output
        assert "Places:" in output


class TestClearCommand:
    """Tests for the clear command."""

    def test_clear_place(self, tmp_path):
        db, db_path = _make_db(tmp_path, [_make_review("r1")])
        db.close()

        from start import _run_clear
        from types import SimpleNamespace
        args = SimpleNamespace(
            db_path=db_path, config=None,
            place_id="place1", confirm=True,
        )
        _run_clear({}, args)

        db = ReviewDB(db_path)
        try:
            assert db.get_reviews("place1") == []
        finally:
            db.close()


class TestHideRestoreCommands:
    """Tests for hide and restore commands."""

    def test_hide_and_restore(self, tmp_path, capsys):
        db, db_path = _make_db(tmp_path, [_make_review("r1")])
        db.close()

        from start import _run_hide, _run_restore
        from types import SimpleNamespace

        args = SimpleNamespace(
            db_path=db_path, config=None,
            review_id="r1", place_id="place1",
        )

        _run_hide({}, args)
        output = capsys.readouterr().out
        assert "hidden" in output

        _run_restore({}, args)
        output = capsys.readouterr().out
        assert "restored" in output


class TestPruneHistoryCommand:
    """Tests for prune-history command."""

    def test_prune_dry_run(self, tmp_path, capsys):
        db, db_path = _make_db(tmp_path, [_make_review("r1")])
        db.close()

        from start import _run_prune_history
        from types import SimpleNamespace
        args = SimpleNamespace(
            db_path=db_path, config=None,
            older_than=0, dry_run=True,
        )
        _run_prune_history({}, args)
        output = capsys.readouterr().out
        assert "Would prune" in output


class TestSyncStatusCommand:
    """Tests for sync-status command."""

    def test_no_checkpoints(self, tmp_path, capsys):
        db, db_path = _make_db(tmp_path)
        db.close()

        from start import _run_sync_status
        from types import SimpleNamespace
        args = SimpleNamespace(db_path=db_path, config=None)
        _run_sync_status({}, args)
        output = capsys.readouterr().out
        assert "No sync checkpoints" in output
