"""Tests for CLI argument parsing and subcommands."""

import sys
import pytest
from unittest.mock import patch

from modules.cli import parse_arguments, _str_to_bool


class TestStrToBool:
    """Tests for the boolean string parser."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on"])
    def test_truthy_values(self, value):
        assert _str_to_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "off"])
    def test_falsy_values(self, value):
        assert _str_to_bool(value) is False

    def test_invalid_value_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            _str_to_bool("maybe")


class TestParseArguments:
    """Tests for argument parsing."""

    def test_default_command_is_scrape(self):
        with patch("sys.argv", ["start.py"]):
            args = parse_arguments()
            assert args.command == "scrape"

    def test_scrape_subcommand(self):
        with patch("sys.argv", ["start.py", "scrape", "--headless"]):
            args = parse_arguments()
            assert args.command == "scrape"
            assert args.headless is True

    def test_export_json(self):
        with patch("sys.argv", ["start.py", "export", "--format", "json",
                                 "--place-id", "test123"]):
            args = parse_arguments()
            assert args.command == "export"
            assert args.format == "json"
            assert args.place_id == "test123"

    def test_export_csv(self):
        with patch("sys.argv", ["start.py", "export", "--format", "csv",
                                 "--output", "/tmp/out"]):
            args = parse_arguments()
            assert args.command == "export"
            assert args.format == "csv"
            assert args.output == "/tmp/out"

    def test_db_stats(self):
        with patch("sys.argv", ["start.py", "db-stats"]):
            args = parse_arguments()
            assert args.command == "db-stats"

    def test_clear_with_place_id(self):
        with patch("sys.argv", ["start.py", "clear", "--place-id", "p1",
                                 "--confirm"]):
            args = parse_arguments()
            assert args.command == "clear"
            assert args.place_id == "p1"
            assert args.confirm is True

    def test_hide_review(self):
        with patch("sys.argv", ["start.py", "hide", "r123", "p456"]):
            args = parse_arguments()
            assert args.command == "hide"
            assert args.review_id == "r123"
            assert args.place_id == "p456"

    def test_restore_review(self):
        with patch("sys.argv", ["start.py", "restore", "r123", "p456"]):
            args = parse_arguments()
            assert args.command == "restore"
            assert args.review_id == "r123"
            assert args.place_id == "p456"

    def test_sync_status(self):
        with patch("sys.argv", ["start.py", "sync-status"]):
            args = parse_arguments()
            assert args.command == "sync-status"

    def test_prune_history(self):
        with patch("sys.argv", ["start.py", "prune-history", "--older-than", "30",
                                 "--dry-run"]):
            args = parse_arguments()
            assert args.command == "prune-history"
            assert args.older_than == 30
            assert args.dry_run is True

    def test_migrate_json(self):
        with patch("sys.argv", ["start.py", "migrate", "--source", "json",
                                 "--json-path", "data.json"]):
            args = parse_arguments()
            assert args.command == "migrate"
            assert args.source == "json"
            assert args.json_path == "data.json"

    def test_boolean_args_work_correctly(self):
        with patch("sys.argv", ["start.py", "--use-mongodb", "false"]):
            args = parse_arguments()
            assert args.use_mongodb is False

    def test_boolean_args_true(self):
        with patch("sys.argv", ["start.py", "--use-mongodb", "true"]):
            args = parse_arguments()
            assert args.use_mongodb is True

    def test_backward_compat_headless(self):
        with patch("sys.argv", ["start.py", "-q"]):
            args = parse_arguments()
            assert args.command == "scrape"
            assert args.headless is True

    def test_sort_order(self):
        with patch("sys.argv", ["start.py", "-s", "newest"]):
            args = parse_arguments()
            assert args.sort_by == "newest"

    def test_stop_threshold(self):
        with patch("sys.argv", ["start.py", "--stop-threshold", "5"]):
            args = parse_arguments()
            assert args.stop_threshold == 5

    def test_db_path_arg(self):
        with patch("sys.argv", ["start.py", "db-stats", "--db-path", "/tmp/test.db"]):
            args = parse_arguments()
            assert args.db_path == "/tmp/test.db"

    def test_custom_params_json(self):
        with patch("sys.argv", ["start.py", "--custom-params", '{"company":"Test"}']):
            args = parse_arguments()
            assert args.custom_params == {"company": "Test"}

    def test_scrape_mode_flag(self):
        with patch("sys.argv", ["start.py", "--scrape-mode", "new_only"]):
            args = parse_arguments()
            assert args.scrape_mode == "new_only"

    def test_scrape_mode_full(self):
        with patch("sys.argv", ["start.py", "scrape", "--scrape-mode", "full"]):
            args = parse_arguments()
            assert args.scrape_mode == "full"

    def test_max_reviews_flag(self):
        with patch("sys.argv", ["start.py", "--max-reviews", "500"]):
            args = parse_arguments()
            assert args.max_reviews == 500

    def test_max_scroll_attempts_flag(self):
        with patch("sys.argv", ["start.py", "--max-scroll-attempts", "100"]):
            args = parse_arguments()
            assert args.max_scroll_attempts == 100

    def test_scroll_idle_limit_flag(self):
        with patch("sys.argv", ["start.py", "--scroll-idle-limit", "20"]):
            args = parse_arguments()
            assert args.scroll_idle_limit == 20

    def test_legacy_overwrite_still_works(self):
        with patch("sys.argv", ["start.py", "--overwrite"]):
            args = parse_arguments()
            assert args.overwrite_existing is True

    def test_legacy_stop_on_match_still_works(self):
        with patch("sys.argv", ["start.py", "--stop-on-match"]):
            args = parse_arguments()
            assert args.stop_on_match is True
