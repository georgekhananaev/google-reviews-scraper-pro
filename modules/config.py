"""
Configuration management for Google Maps Reviews Scraper.
"""

import copy
import logging
import os
from pathlib import Path
from typing import Dict, Any

import yaml

log = logging.getLogger("scraper")

# Default configuration path
DEFAULT_CONFIG_PATH = Path("config.yaml")

# Default configuration - will be overridden by config file
DEFAULT_CONFIG = {
    "url": "",
    "urls": [],
    "businesses": [],
    "headless": True,
    "sort_by": "relevance",
    "scrape_mode": "update",
    "stop_on_match": False,
    "overwrite_existing": False,
    "max_reviews": 0,
    "max_scroll_attempts": 50,
    "scroll_idle_limit": 15,
    "use_mongodb": True,
    "mongodb": {
        "uri": "mongodb://localhost:27017",
        "database": "reviews",
        "collection": "google_reviews",
        "sync_mode": "update",
    },
    "backup_to_json": True,
    "json_path": "google_reviews.json",
    "seen_ids_path": "google_reviews.ids",
    "convert_dates": True,
    "download_images": True,
    "image_dir": "review_images",
    "download_threads": 4,
    "store_local_paths": True,  # Option to control storing local image paths
    "replace_urls": False,  # Option to control URL replacement
    "custom_url_base": "https://mycustomurl.com",  # Base URL for replacement
    "custom_url_profiles": "/profiles/",  # Path for profile images
    "custom_url_reviews": "/reviews/",  # Path for review images
    "preserve_original_urls": True,  # Option to preserve original URLs
    "custom_params": {  # Custom parameters to add to each document
        "company": "Thaitours",  # Default example
        "source": "Google Maps"  # Default example
    },
    "s3": {
        "provider": "aws",
        "endpoint_url": None,
        "path_style": False,
        "acl": "public-read",
        "sync_mode": "update",
    },
    "log_level": "INFO",
    "log_dir": "logs",
    "log_file": "scraper.log",
    "db_path": "reviews.db",
    "stop_threshold": 3,
}


_VALID_SCRAPE_MODES = {"new_only", "update", "full"}
_VALID_SYNC_MODES = {"new_only", "update", "full"}


def resolve_aliases(config: Dict[str, Any]) -> None:
    """Map legacy config keys to new equivalents (mutates *config* in place)."""
    has_scrape_mode = "scrape_mode" in config and config["scrape_mode"] != DEFAULT_CONFIG["scrape_mode"]

    if config.get("overwrite_existing") and not has_scrape_mode:
        config["scrape_mode"] = "full"
        log.warning(
            "Deprecated: 'overwrite_existing: true' mapped to 'scrape_mode: full'. "
            "Please update your config."
        )

    if config.get("stop_on_match") and config.get("stop_threshold", 0) == 0:
        config["stop_threshold"] = 3
        log.warning(
            "Deprecated: 'stop_on_match: true' mapped to 'stop_threshold: 3'. "
            "Please update your config."
        )


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate config values, falling back to safe defaults on bad input."""
    mode = config.get("scrape_mode", "update")
    if mode not in _VALID_SCRAPE_MODES:
        log.warning("Invalid scrape_mode '%s', falling back to 'update'", mode)
        config["scrape_mode"] = "update"

    for key in ("max_reviews", "stop_threshold", "max_scroll_attempts", "scroll_idle_limit"):
        val = config.get(key)
        if not isinstance(val, int) or val < 0:
            config[key] = DEFAULT_CONFIG[key]

    mongo_cfg = config.get("mongodb", {})
    sync_mode = mongo_cfg.get("sync_mode", "update")
    if sync_mode not in _VALID_SYNC_MODES:
        log.warning("Invalid mongodb.sync_mode '%s', falling back to 'update'", sync_mode)
        mongo_cfg["sync_mode"] = "update"

    s3_cfg = config.get("s3", {})
    s3_sync = s3_cfg.get("sync_mode", "update")
    if s3_sync not in _VALID_SYNC_MODES:
        log.warning("Invalid s3.sync_mode '%s', falling back to 'update'", s3_sync)
        s3_cfg["sync_mode"] = "update"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load configuration from YAML file or use defaults"""
    config = copy.deepcopy(DEFAULT_CONFIG)

    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Merge configs, with nested dictionary support
                    def deep_update(d, u):
                        for k, v in u.items():
                            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                                deep_update(d[k], v)
                            else:
                                d[k] = v

                    deep_update(config, user_config)
                    log.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            log.error(f"Error loading config from {config_path}: {e}")
            log.info("Using default configuration")
    else:
        log.info(f"Config file {config_path} not found, using default configuration")
        # Create a default config file for future use
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            log.info(f"Created default configuration file at {config_path}")

    resolve_aliases(config)
    _validate_config(config)
    return config
