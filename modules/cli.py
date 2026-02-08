"""
Command line interface handling for Google Maps Reviews Scraper.

Subcommands:
  scrape        Scrape reviews (default behavior)
  export        Export reviews from DB to JSON/CSV
  db-stats      Show database statistics
  clear         Clear data for a place or all places
  hide          Soft-delete a review
  restore       Restore a soft-deleted review
  sync-status   Show sync checkpoint status
  prune-history Prune old audit history entries
  migrate       Import existing JSON/MongoDB data into SQLite
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


def _build_scrape_parser(sub: argparse._SubParsersAction) -> None:
    """Build the 'scrape' subcommand."""
    sp = sub.add_parser("scrape", help="Scrape Google Maps reviews")
    _add_common_args(sp)
    sp.add_argument(
        "-q", "--headless", action="store_true",
        help="run Chrome in the background",
    )
    sp.add_argument(
        "-s", "--sort", dest="sort_by",
        choices=("newest", "highest", "lowest", "relevance"),
        default=None, help="sorting order for reviews",
    )
    sp.add_argument(
        "--stop-on-match", action="store_true",
        help="stop scrolling after N consecutive unchanged reviews",
    )
    sp.add_argument(
        "--stop-threshold", type=int, default=None,
        help="number of consecutive unchanged reviews before stopping (default: 3)",
    )
    sp.add_argument(
        "--url", type=str, default=None,
        help="Google Maps URL to scrape",
    )
    sp.add_argument(
        "--overwrite", action="store_true", dest="overwrite_existing",
        help="overwrite existing reviews instead of appending",
    )
    sp.add_argument(
        "--use-mongodb", type=_str_to_bool, default=None,
        help="whether to use MongoDB for storage (true/false)",
    )
    sp.add_argument(
        "--convert-dates", type=_str_to_bool, default=None,
        help="convert string dates to MongoDB Date objects (true/false)",
    )
    sp.add_argument(
        "--download-images", type=_str_to_bool, default=None,
        help="download images from reviews (true/false)",
    )
    sp.add_argument(
        "--image-dir", type=str, default=None,
        help="directory to store downloaded images",
    )
    sp.add_argument(
        "--download-threads", type=int, default=None,
        help="number of threads for downloading images",
    )
    sp.add_argument(
        "--store-local-paths", type=_str_to_bool, default=None,
        help="whether to store local image paths (true/false)",
    )
    sp.add_argument(
        "--replace-urls", type=_str_to_bool, default=None,
        help="whether to replace original URLs (true/false)",
    )
    sp.add_argument(
        "--custom-url-base", type=str, default=None,
        help="base URL for replacement",
    )
    sp.add_argument(
        "--custom-url-profiles", type=str, default=None,
        help="path for profile images",
    )
    sp.add_argument(
        "--custom-url-reviews", type=str, default=None,
        help="path for review images",
    )
    sp.add_argument(
        "--preserve-original-urls", type=_str_to_bool, default=None,
        help="whether to preserve original URLs (true/false)",
    )
    sp.add_argument(
        "--custom-params", type=str, default=None,
        help='JSON string with custom parameters (e.g. \'{"company":"MyBiz"}\')',
    )


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


def parse_arguments():
    """Parse command line arguments with subcommands."""
    ap = argparse.ArgumentParser(
        description="Google Maps Reviews Scraper Pro",
    )

    sub = ap.add_subparsers(dest="command")

    _build_scrape_parser(sub)
    _build_export_parser(sub)
    _build_management_parsers(sub)

    # If no subcommand given, add top-level scrape args for backward compat
    _add_common_args(ap)
    ap.add_argument("-q", "--headless", action="store_true",
                    help="run Chrome in the background")
    ap.add_argument("-s", "--sort", dest="sort_by",
                    choices=("newest", "highest", "lowest", "relevance"),
                    default=None, help="sorting order for reviews")
    ap.add_argument("--stop-on-match", action="store_true",
                    help="stop scrolling after N consecutive unchanged reviews")
    ap.add_argument("--stop-threshold", type=int, default=None,
                    help="consecutive unchanged reviews before stopping (default: 3)")
    ap.add_argument("--url", type=str, default=None,
                    help="Google Maps URL to scrape")
    ap.add_argument("--overwrite", action="store_true", dest="overwrite_existing",
                    help="overwrite existing reviews instead of appending")
    ap.add_argument("--use-mongodb", type=_str_to_bool, default=None,
                    help="whether to use MongoDB (true/false)")
    ap.add_argument("--convert-dates", type=_str_to_bool, default=None,
                    help="convert string dates (true/false)")
    ap.add_argument("--download-images", type=_str_to_bool, default=None,
                    help="download images from reviews (true/false)")
    ap.add_argument("--image-dir", type=str, default=None,
                    help="directory to store downloaded images")
    ap.add_argument("--download-threads", type=int, default=None,
                    help="number of threads for downloading images")
    ap.add_argument("--store-local-paths", type=_str_to_bool, default=None,
                    help="store local image paths (true/false)")
    ap.add_argument("--replace-urls", type=_str_to_bool, default=None,
                    help="replace original URLs (true/false)")
    ap.add_argument("--custom-url-base", type=str, default=None,
                    help="base URL for replacement")
    ap.add_argument("--custom-url-profiles", type=str, default=None,
                    help="path for profile images")
    ap.add_argument("--custom-url-reviews", type=str, default=None,
                    help="path for review images")
    ap.add_argument("--preserve-original-urls", type=_str_to_bool, default=None,
                    help="preserve original URLs (true/false)")
    ap.add_argument("--custom-params", type=str, default=None,
                    help='JSON string with custom parameters')

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
