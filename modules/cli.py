"""
Command line interface handling for Google Maps Reviews Scraper.

Subcommands:
  scrape          Scrape reviews (default behavior)
  export          Export reviews from DB to JSON/CSV
  db-stats        Show database statistics
  clear           Clear data for a place or all places
  hide            Soft-delete a review
  restore         Restore a soft-deleted review
  sync-status     Show sync checkpoint status
  prune-history   Prune old audit history entries
  migrate         Import existing JSON/MongoDB data into SQLite
  api-key-create  Create a new API key
  api-key-list    List all API keys
  api-key-revoke  Revoke an API key
  api-key-stats   Show API key usage statistics
  audit-log       Query the API audit log
  prune-audit     Prune old audit log entries
  logs            View structured JSON log files
"""

import argparse
import json
from pathlib import Path

from modules.config import DEFAULT_CONFIG_PATH


def _str_to_bool(value: str) -> bool:
    """Parse boolean string for argparse (type=bool is broken)."""
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    if value.lower() in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got '{value}'")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments shared across subcommands."""
    parser.add_argument(
        "--config", type=str, default=None,
        help="path to custom configuration file",
    )
    parser.add_argument(
        "--db-path", type=str, default=None,
        help="path to SQLite database file (default: reviews.db)",
    )


def _add_scrape_args(parser: argparse.ArgumentParser) -> None:
    """Add scrape-specific arguments (shared between subcommand and top-level)."""
    parser.add_argument(
        "-q", "--headless", action="store_true",
        help="run Chrome in the background",
    )
    parser.add_argument(
        "-s", "--sort", dest="sort_by",
        choices=("newest", "highest", "lowest", "relevance"),
        default=None, help="sorting order for reviews",
    )
    parser.add_argument(
        "--scrape-mode", type=str, default=None,
        choices=("new_only", "update", "full"),
        help="scrape mode: new_only, update (default), or full",
    )
    parser.add_argument(
        "--stop-threshold", type=int, default=None,
        help="consecutive fully-matched scroll batches before stopping (default: 3)",
    )
    parser.add_argument(
        "--max-reviews", type=int, default=None,
        help="maximum number of reviews to scrape (0 = unlimited)",
    )
    parser.add_argument(
        "--max-scroll-attempts", type=int, default=None,
        help="maximum scroll iterations (default: 50)",
    )
    parser.add_argument(
        "--scroll-idle-limit", type=int, default=None,
        help="max idle iterations with zero new cards (default: 15)",
    )
    parser.add_argument(
        "--url", type=str, default=None,
        help="Google Maps URL to scrape",
    )
    # Legacy flags — hidden but still accepted for backward compatibility
    parser.add_argument(
        "--stop-on-match", action="store_true", default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--overwrite", action="store_true", dest="overwrite_existing",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--use-mongodb", type=_str_to_bool, default=None,
        help="whether to use MongoDB for storage (true/false)",
    )
    parser.add_argument(
        "--convert-dates", type=_str_to_bool, default=None,
        help="convert string dates to MongoDB Date objects (true/false)",
    )
    parser.add_argument(
        "--download-images", type=_str_to_bool, default=None,
        help="download images from reviews (true/false)",
    )
    parser.add_argument(
        "--image-dir", type=str, default=None,
        help="directory to store downloaded images",
    )
    parser.add_argument(
        "--download-threads", type=int, default=None,
        help="number of threads for downloading images",
    )
    parser.add_argument(
        "--store-local-paths", type=_str_to_bool, default=None,
        help="whether to store local image paths (true/false)",
    )
    parser.add_argument(
        "--replace-urls", type=_str_to_bool, default=None,
        help="whether to replace original URLs (true/false)",
    )
    parser.add_argument(
        "--custom-url-base", type=str, default=None,
        help="base URL for replacement",
    )
    parser.add_argument(
        "--custom-url-profiles", type=str, default=None,
        help="path for profile images",
    )
    parser.add_argument(
        "--custom-url-reviews", type=str, default=None,
        help="path for review images",
    )
    parser.add_argument(
        "--preserve-original-urls", type=_str_to_bool, default=None,
        help="whether to preserve original URLs (true/false)",
    )
    parser.add_argument(
        "--custom-params", type=str, default=None,
        help='JSON string with custom parameters (e.g. \'{"company":"MyBiz"}\')',
    )


def _build_scrape_parser(sub: argparse._SubParsersAction) -> None:
    """Build the 'scrape' subcommand."""
    sp = sub.add_parser("scrape", help="Scrape Google Maps reviews")
    _add_common_args(sp)
    _add_scrape_args(sp)


def _build_export_parser(sub: argparse._SubParsersAction) -> None:
    """Build the 'export' subcommand."""
    sp = sub.add_parser("export", help="Export reviews from database")
    _add_common_args(sp)
    sp.add_argument(
        "--format", choices=("json", "csv"), default="json",
        help="output format (default: json)",
    )
    sp.add_argument(
        "--place-id", type=str, default=None,
        help="export only this place (default: all places)",
    )
    sp.add_argument(
        "--output", "-o", type=str, default=None,
        help="output file or directory path",
    )
    sp.add_argument(
        "--include-deleted", action="store_true",
        help="include soft-deleted reviews",
    )


def _build_management_parsers(sub: argparse._SubParsersAction) -> None:
    """Build management subcommands."""
    # db-stats
    sp = sub.add_parser("db-stats", help="Show database statistics")
    _add_common_args(sp)

    # clear
    sp = sub.add_parser("clear", help="Clear data for a place or all places")
    _add_common_args(sp)
    sp.add_argument(
        "--place-id", type=str, default=None,
        help="clear only this place (omit for all)",
    )
    sp.add_argument(
        "--confirm", action="store_true",
        help="skip confirmation prompt",
    )

    # hide
    sp = sub.add_parser("hide", help="Soft-delete a review")
    _add_common_args(sp)
    sp.add_argument("review_id", help="review ID to hide")
    sp.add_argument("place_id", help="place ID the review belongs to")

    # restore
    sp = sub.add_parser("restore", help="Restore a soft-deleted review")
    _add_common_args(sp)
    sp.add_argument("review_id", help="review ID to restore")
    sp.add_argument("place_id", help="place ID the review belongs to")

    # sync-status
    sp = sub.add_parser("sync-status", help="Show sync checkpoint status")
    _add_common_args(sp)

    # prune-history
    sp = sub.add_parser("prune-history", help="Prune old audit history entries")
    _add_common_args(sp)
    sp.add_argument(
        "--older-than", type=int, default=90,
        help="delete entries older than N days (default: 90)",
    )
    sp.add_argument(
        "--dry-run", action="store_true",
        help="show count without deleting",
    )

    # migrate
    sp = sub.add_parser(
        "migrate",
        help="Import existing JSON/MongoDB data into SQLite",
    )
    _add_common_args(sp)
    sp.add_argument(
        "--source", choices=("json", "mongodb"), required=True,
        help="data source to import from",
    )
    sp.add_argument(
        "--json-path", type=str, default=None,
        help="path to JSON file (for --source json)",
    )
    sp.add_argument(
        "--place-url", type=str, default=None,
        help="Google Maps URL associated with this data",
    )


def _build_api_key_parsers(sub: argparse._SubParsersAction) -> None:
    """Build API key management subcommands."""
    # api-key-create
    sp = sub.add_parser("api-key-create", help="Create a new API key")
    _add_common_args(sp)
    sp.add_argument("name", help="descriptive name for this key")

    # api-key-list
    sp = sub.add_parser("api-key-list", help="List all API keys")
    _add_common_args(sp)

    # api-key-revoke
    sp = sub.add_parser("api-key-revoke", help="Revoke an API key")
    _add_common_args(sp)
    sp.add_argument("key_id", type=int, help="ID of the key to revoke")

    # api-key-stats
    sp = sub.add_parser("api-key-stats", help="Show API key usage statistics")
    _add_common_args(sp)
    sp.add_argument("key_id", type=int, help="ID of the key")

    # audit-log
    sp = sub.add_parser("audit-log", help="Query the API audit log")
    _add_common_args(sp)
    sp.add_argument("--key-id", type=int, default=None, help="filter by key ID")
    sp.add_argument("--limit", type=int, default=50, help="max rows (default: 50)")
    sp.add_argument("--since", type=str, default=None, help="ISO timestamp lower bound")

    # prune-audit
    sp = sub.add_parser("prune-audit", help="Prune old API audit log entries")
    _add_common_args(sp)
    sp.add_argument(
        "--older-than-days", type=int, default=90,
        help="delete entries older than N days (default: 90)",
    )
    sp.add_argument("--dry-run", action="store_true", help="show count without deleting")


def _build_logs_parser(sub: argparse._SubParsersAction) -> None:
    """Build the 'logs' subcommand."""
    sp = sub.add_parser("logs", help="View structured JSON log files")
    _add_common_args(sp)
    sp.add_argument(
        "--lines", "-n", type=int, default=50,
        help="number of lines to show (default: 50)",
    )
    sp.add_argument(
        "--level", type=str, default=None,
        help="filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    sp.add_argument(
        "--follow", "-f", action="store_true",
        help="follow log output (like tail -f)",
    )


def parse_arguments():
    """Parse command line arguments with subcommands."""
    ap = argparse.ArgumentParser(
        description="Google Maps Reviews Scraper Pro",
    )

    sub = ap.add_subparsers(dest="command")

    _build_scrape_parser(sub)
    _build_export_parser(sub)
    _build_management_parsers(sub)
    _build_api_key_parsers(sub)
    _build_logs_parser(sub)

    # If no subcommand given, add top-level scrape args for backward compat
    _add_common_args(ap)
    _add_scrape_args(ap)

    args = ap.parse_args()

    # Default to scrape if no subcommand
    if args.command is None:
        args.command = "scrape"

    # Handle config path
    if hasattr(args, "config") and args.config is not None:
        args.config = Path(args.config)
    else:
        args.config = DEFAULT_CONFIG_PATH

    # Process custom params if provided
    if hasattr(args, "custom_params") and args.custom_params:
        try:
            args.custom_params = json.loads(args.custom_params)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse custom params JSON: {args.custom_params}")
            args.custom_params = None

    return args
