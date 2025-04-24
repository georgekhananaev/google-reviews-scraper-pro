"""
Command line interface handling for Google Maps Reviews Scraper.
"""

import argparse
import json
from pathlib import Path

from modules.config import DEFAULT_CONFIG_PATH


def parse_arguments():
    """Parse command line arguments"""
    ap = argparse.ArgumentParser(description="Google‑Maps review scraper with MongoDB integration")
    ap.add_argument("-q", "--headless", action="store_true",
                    help="run Chrome in the background")
    ap.add_argument("-s", "--sort", dest="sort_by",
                    choices=("newest", "highest", "lowest", "relevance"),
                    default=None, help="sorting order for reviews")
    ap.add_argument("--stop-on-match", action="store_true",
                    help="stop scrolling when first already‑seen id is met "
                         "(useful with --sort newest)")
    ap.add_argument("--url", type=str, default=None,
                    help="custom Google Maps URL to scrape")
    ap.add_argument("--overwrite", action="store_true", dest="overwrite_existing",
                    help="overwrite existing reviews instead of appending")
    ap.add_argument("--config", type=str, default=None,
                    help="path to custom configuration file")
    ap.add_argument("--use-mongodb", type=bool, default=None,
                    help="whether to use MongoDB for storage")

    # Arguments for date conversion and image downloading
    ap.add_argument("--convert-dates", type=bool, default=None,
                    help="convert string dates to MongoDB Date objects")
    ap.add_argument("--download-images", type=bool, default=None,
                    help="download images from reviews")
    ap.add_argument("--image-dir", type=str, default=None,
                    help="directory to store downloaded images")
    ap.add_argument("--download-threads", type=int, default=None,
                    help="number of threads for downloading images")

    # Arguments for local image paths and URL replacement
    ap.add_argument("--store-local-paths", type=bool, default=None,
                    help="whether to store local image paths in documents")
    ap.add_argument("--replace-urls", type=bool, default=None,
                    help="whether to replace original URLs with custom ones")
    ap.add_argument("--custom-url-base", type=str, default=None,
                    help="base URL for replacement")
    ap.add_argument("--custom-url-profiles", type=str, default=None,
                    help="path for profile images")
    ap.add_argument("--custom-url-reviews", type=str, default=None,
                    help="path for review images")
    ap.add_argument("--preserve-original-urls", type=bool, default=None,
                    help="whether to preserve original URLs in original_* fields")

    # Arguments for custom parameters
    ap.add_argument("--custom-params", type=str, default=None,
                    help="JSON string with custom parameters to add to each document (e.g. '{\"company\":\"Thaitours\"}')")

    args = ap.parse_args()

    # Handle config path
    if args.config is not None:
        args.config = Path(args.config)
    else:
        args.config = DEFAULT_CONFIG_PATH

    # Process custom params if provided
    if args.custom_params:
        try:
            args.custom_params = json.loads(args.custom_params)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse custom params JSON: {args.custom_params}")
            args.custom_params = None

    return args
