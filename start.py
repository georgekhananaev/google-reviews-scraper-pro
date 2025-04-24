#!/usr/bin/env python3
"""
Google‑Maps review scraper with MongoDB integration
=================================================

Main entry point for the scraper.
"""

from modules.cli import parse_arguments
from modules.config import load_config
from modules.scraper import GoogleReviewsScraper


def main():
    """Main function to initialize and run the scraper"""
    # Parse command line arguments
    args = parse_arguments()

    # Load configuration
    config = load_config(args.config)

    # Override config with command line arguments if provided
    if args.headless:
        config["headless"] = True
    if args.sort_by is not None:
        config["sort_by"] = args.sort_by
    if args.stop_on_match:
        config["stop_on_match"] = True
    if args.url is not None:
        config["url"] = args.url
    if args.overwrite_existing:
        config["overwrite_existing"] = True
    if args.use_mongodb is not None:
        config["use_mongodb"] = args.use_mongodb

    # Handle arguments for date conversion and image downloading
    if args.convert_dates is not None:
        config["convert_dates"] = args.convert_dates
    if args.download_images is not None:
        config["download_images"] = args.download_images
    if args.image_dir is not None:
        config["image_dir"] = args.image_dir
    if args.download_threads is not None:
        config["download_threads"] = args.download_threads

    # Handle arguments for local image paths and URL replacement
    if args.store_local_paths is not None:
        config["store_local_paths"] = args.store_local_paths
    if args.replace_urls is not None:
        config["replace_urls"] = args.replace_urls
    if args.custom_url_base is not None:
        config["custom_url_base"] = args.custom_url_base
    if args.custom_url_profiles is not None:
        config["custom_url_profiles"] = args.custom_url_profiles
    if args.custom_url_reviews is not None:
        config["custom_url_reviews"] = args.custom_url_reviews
    if args.preserve_original_urls is not None:
        config["preserve_original_urls"] = args.preserve_original_urls

    # Handle custom parameters
    if args.custom_params is not None:
        if "custom_params" not in config:
            config["custom_params"] = {}
        # Update config with the provided custom parameters
        config["custom_params"].update(args.custom_params)

    # Initialize and run scraper
    scraper = GoogleReviewsScraper(config)
    scraper.scrape()


if __name__ == "__main__":
    main()
