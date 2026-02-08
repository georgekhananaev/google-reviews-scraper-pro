#!/usr/bin/env python3
"""
Google Maps Reviews Scraper Pro
================================

Main entry point supporting scrape + management commands.
"""

import json
import sys
from pathlib import Path

from modules.cli import parse_arguments
from modules.config import load_config


def _apply_scrape_overrides(config, args):
    """Apply CLI argument overrides to config for scrape command."""
    overrides = {
        "headless": args.headless if args.headless else None,
        "sort_by": args.sort_by,
        "scrape_mode": getattr(args, "scrape_mode", None),
        "stop_threshold": getattr(args, "stop_threshold", None),
        "max_reviews": getattr(args, "max_reviews", None),
        "max_scroll_attempts": getattr(args, "max_scroll_attempts", None),
        "scroll_idle_limit": getattr(args, "scroll_idle_limit", None),
        "url": args.url,
        "use_mongodb": getattr(args, "use_mongodb", None),
        "convert_dates": getattr(args, "convert_dates", None),
        "download_images": getattr(args, "download_images", None),
        "image_dir": getattr(args, "image_dir", None),
        "download_threads": getattr(args, "download_threads", None),
        "store_local_paths": getattr(args, "store_local_paths", None),
        "replace_urls": getattr(args, "replace_urls", None),
        "custom_url_base": getattr(args, "custom_url_base", None),
        "custom_url_profiles": getattr(args, "custom_url_profiles", None),
        "custom_url_reviews": getattr(args, "custom_url_reviews", None),
        "preserve_original_urls": getattr(args, "preserve_original_urls", None),
    }

    # Legacy CLI flags → new config keys
    if getattr(args, "overwrite_existing", False) and not getattr(args, "scrape_mode", None):
        overrides["scrape_mode"] = "full"
    if getattr(args, "stop_on_match", False):
        overrides["stop_threshold"] = overrides.get("stop_threshold") or 3

    for key, value in overrides.items():
        if value is not None:
            config[key] = value

    if getattr(args, "db_path", None):
        config["db_path"] = args.db_path

    custom_params = getattr(args, "custom_params", None)
    if custom_params:
        config.setdefault("custom_params", {}).update(custom_params)


def _get_db_path(config, args):
    """Resolve database path from CLI args or config."""
    if getattr(args, "db_path", None):
        return args.db_path
    return config.get("db_path", "reviews.db")


def _resolve_businesses(config):
    """Resolve business list from config (supports businesses, urls, or url)."""
    businesses = config.get("businesses", [])
    if businesses:
        # Each entry is a dict with 'url' + optional overrides
        return [b if isinstance(b, dict) else {"url": b} for b in businesses]

    # Fallback: flat urls list or single url
    urls = config.get("urls", [])
    single_url = config.get("url")
    if not urls and single_url:
        urls = [single_url]
    return [{"url": u} for u in urls]


def _build_business_config(base_config, overrides):
    """Merge per-business overrides into a copy of the global config."""
    import copy
    from modules.config import resolve_aliases
    merged = copy.deepcopy(base_config)
    for key, value in overrides.items():
        if key == "url":
            merged["url"] = value
        elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key].update(value)
        else:
            merged[key] = value
    resolve_aliases(merged)
    return merged


def _run_scrape(config, args):
    """Run the scrape command."""
    from modules.scraper import GoogleReviewsScraper

    _apply_scrape_overrides(config, args)

    businesses = _resolve_businesses(config)
    if not businesses:
        print("Error: No URL configured. Use --url or set 'businesses'/'urls' in config.yaml")
        sys.exit(1)

    for i, biz in enumerate(businesses):
        biz_config = _build_business_config(config, biz)
        url = biz_config.get("url", "")
        if len(businesses) > 1:
            print(f"\n--- Scraping business {i + 1}/{len(businesses)}: {url} ---")

        scraper = GoogleReviewsScraper(biz_config)
        try:
            scraper.scrape()
        finally:
            scraper.review_db.close()


def _run_export(config, args):
    """Run the export command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        fmt = getattr(args, "format", "json")
        place_id = getattr(args, "place_id", None)
        output = getattr(args, "output", None)
        include_deleted = getattr(args, "include_deleted", False)

        if fmt == "json":
            if place_id:
                data = db.export_reviews_json(place_id, include_deleted)
            else:
                data = db.export_all_json(include_deleted)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            if output:
                with open(output, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"Exported to {output}")
            else:
                print(text)
        elif fmt == "csv":
            if place_id:
                path = output or f"reviews_{place_id}.csv"
                count = db.export_reviews_csv(place_id, path, include_deleted)
                print(f"Exported {count} reviews to {path}")
            else:
                out_dir = output or "exports"
                counts = db.export_all_csv(out_dir, include_deleted)
                for pid, count in counts.items():
                    print(f"  {pid}: {count} reviews")
                print(f"Exported to {out_dir}/")
    finally:
        db.close()


def _run_db_stats(config, args):
    """Run the db-stats command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        stats = db.get_stats()
        print("Database Statistics")
        print("=" * 40)
        print(f"  Places:           {stats.get('places_count', 0)}")
        print(f"  Reviews:          {stats.get('reviews_count', 0)}")
        print(f"  Sessions:         {stats.get('scrape_sessions_count', 0)}")
        print(f"  History entries:   {stats.get('review_history_count', 0)}")
        print(f"  Sync checkpoints: {stats.get('sync_checkpoints_count', 0)}")
        print(f"  Aliases:          {stats.get('place_aliases_count', 0)}")
        size_bytes = stats.get("db_size_bytes", 0)
        if size_bytes > 1024 * 1024:
            print(f"  DB size:          {size_bytes / (1024*1024):.1f} MB")
        else:
            print(f"  DB size:          {size_bytes / 1024:.1f} KB")

        places = stats.get("places", [])
        if places:
            print(f"\nPer-place breakdown:")
            for p in places:
                print(f"  {p['place_id']}: {p.get('place_name', '?')} "
                      f"({p.get('total_reviews', 0)} reviews, "
                      f"last scraped: {p.get('last_scraped', 'never')})")
    finally:
        db.close()


def _run_clear(config, args):
    """Run the clear command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        place_id = getattr(args, "place_id", None)
        confirm = getattr(args, "confirm", False)

        if not confirm:
            target = place_id or "ALL places"
            answer = input(f"Clear data for {target}? This cannot be undone. [y/N]: ")
            if answer.lower() != "y":
                print("Cancelled.")
                return

        if place_id:
            counts = db.clear_place(place_id)
            print(f"Cleared place {place_id}:")
        else:
            counts = db.clear_all()
            print("Cleared all data:")
        for table, count in counts.items():
            print(f"  {table}: {count} rows")
    finally:
        db.close()


def _run_hide(config, args):
    """Run the hide command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        if db.hide_review(args.review_id, args.place_id):
            print(f"Review {args.review_id} hidden.")
        else:
            print(f"Review {args.review_id} not found or already hidden.")
    finally:
        db.close()


def _run_restore(config, args):
    """Run the restore command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        if db.restore_review(args.review_id, args.place_id):
            print(f"Review {args.review_id} restored.")
        else:
            print(f"Review {args.review_id} not found or not hidden.")
    finally:
        db.close()


def _run_sync_status(config, args):
    """Run the sync-status command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        statuses = db.get_all_sync_status()
        if not statuses:
            print("No sync checkpoints found.")
            return
        print("Sync Checkpoints")
        print("=" * 60)
        for s in statuses:
            print(f"  {s.get('place_id', '?')} -> {s.get('target', '?')}: "
                  f"status={s.get('status', '?')}, "
                  f"last_synced={s.get('last_synced_at', 'never')}, "
                  f"attempts={s.get('attempt_count', 0)}")
            if s.get("error_message"):
                print(f"    error: {s['error_message']}")
    finally:
        db.close()


def _run_prune_history(config, args):
    """Run the prune-history command."""
    from modules.review_db import ReviewDB

    db = ReviewDB(_get_db_path(config, args))
    try:
        older_than = getattr(args, "older_than", 90)
        dry_run = getattr(args, "dry_run", False)
        count = db.prune_history(older_than, dry_run)
        if dry_run:
            print(f"Would prune {count} history entries older than {older_than} days.")
        else:
            print(f"Pruned {count} history entries older than {older_than} days.")
    finally:
        db.close()


def _run_migrate(config, args):
    """Run the migrate command."""
    from modules.migration import migrate_json, migrate_mongodb

    db_path = _get_db_path(config, args)
    source = getattr(args, "source", "json")
    place_url = getattr(args, "place_url", None) or config.get("url", "")

    if source == "json":
        json_path = getattr(args, "json_path", None) or config.get("json_path", "google_reviews.json")
        stats = migrate_json(json_path, db_path, place_url)
        print(f"Migrated from JSON: {stats}")
    elif source == "mongodb":
        stats = migrate_mongodb(config, db_path, place_url)
        print(f"Migrated from MongoDB: {stats}")


# ------------------------------------------------------------------
# API key management commands
# ------------------------------------------------------------------

def _run_api_key_create(config, args):
    """Create a new API key."""
    from modules.api_keys import ApiKeyDB

    db = ApiKeyDB(_get_db_path(config, args))
    try:
        key_id, raw_key = db.create_key(args.name)
        print(f"Created API key #{key_id} for '{args.name}'")
        print(f"Key: {raw_key}")
        print("Store this key securely — it cannot be retrieved later.")
    finally:
        db.close()


def _run_api_key_list(config, args):
    """List all API keys."""
    from modules.api_keys import ApiKeyDB

    db = ApiKeyDB(_get_db_path(config, args))
    try:
        keys = db.list_keys()
        if not keys:
            print("No API keys found.")
            return
        print(f"{'ID':<5} {'Name':<20} {'Prefix':<18} {'Active':<8} {'Uses':<8} {'Last Used':<20}")
        print("=" * 79)
        for k in keys:
            active = "yes" if k["is_active"] else "REVOKED"
            last_used = k["last_used_at"] or "never"
            print(f"{k['id']:<5} {k['name']:<20} {k['key_prefix']:<18} "
                  f"{active:<8} {k['usage_count']:<8} {last_used:<20}")
    finally:
        db.close()


def _run_api_key_revoke(config, args):
    """Revoke an API key."""
    from modules.api_keys import ApiKeyDB

    db = ApiKeyDB(_get_db_path(config, args))
    try:
        if db.revoke_key(args.key_id):
            print(f"API key #{args.key_id} revoked.")
        else:
            print(f"Key #{args.key_id} not found or already revoked.")
    finally:
        db.close()


def _run_api_key_stats(config, args):
    """Show API key usage statistics."""
    from modules.api_keys import ApiKeyDB

    db = ApiKeyDB(_get_db_path(config, args))
    try:
        stats = db.get_key_stats(args.key_id)
        if not stats:
            print(f"Key #{args.key_id} not found.")
            return
        active = "active" if stats["is_active"] else "REVOKED"
        print(f"Key #{stats['id']}: {stats['name']} ({active})")
        print(f"  Prefix:    {stats['key_prefix']}")
        print(f"  Created:   {stats['created_at']}")
        print(f"  Last used: {stats['last_used_at'] or 'never'}")
        print(f"  Uses:      {stats['usage_count']}")
        recent = stats.get("recent_requests", [])
        if recent:
            print(f"\n  Recent requests ({len(recent)}):")
            for r in recent:
                print(f"    {r['timestamp']}  {r['method']} {r['endpoint']}  -> {r['status_code']}")
    finally:
        db.close()


def _run_audit_log(config, args):
    """Query the API audit log."""
    from modules.api_keys import ApiKeyDB

    db = ApiKeyDB(_get_db_path(config, args))
    try:
        rows = db.query_audit_log(
            key_id=getattr(args, "key_id", None),
            limit=getattr(args, "limit", 50),
            since=getattr(args, "since", None),
        )
        if not rows:
            print("No audit log entries found.")
            return
        print(f"{'ID':<6} {'Timestamp':<20} {'Key':<12} {'Method':<8} {'Endpoint':<30} {'Status':<7} {'ms':<6}")
        print("=" * 89)
        for r in rows:
            key_label = r.get("key_name") or str(r.get("key_id") or "-")
            print(f"{r['id']:<6} {r['timestamp']:<20} {key_label:<12} "
                  f"{r['method']:<8} {r['endpoint']:<30} "
                  f"{r.get('status_code') or '-':<7} {r.get('response_time_ms') or '-':<6}")
    finally:
        db.close()


def _run_prune_audit(config, args):
    """Prune old API audit log entries."""
    from modules.api_keys import ApiKeyDB

    db = ApiKeyDB(_get_db_path(config, args))
    try:
        days = getattr(args, "older_than_days", 90)
        dry_run = getattr(args, "dry_run", False)
        count = db.prune_audit_log(days, dry_run)
        if dry_run:
            print(f"Would prune {count} audit entries older than {days} days.")
        else:
            print(f"Pruned {count} audit entries older than {days} days.")
    finally:
        db.close()


def _run_logs(config, args):
    """Run the logs viewer command."""
    import sys
    log_dir = config.get("log_dir", "logs")
    log_file = config.get("log_file", "scraper.log")
    log_path = Path(log_dir) / log_file

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        sys.exit(1)

    lines = getattr(args, "lines", 50)
    level_filter = (getattr(args, "level", None) or "").upper()
    follow = getattr(args, "follow", False)

    def _print_lines(path, n, level):
        with open(path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-n:] if n < len(all_lines) else all_lines
        for line in tail:
            line = line.rstrip()
            if not line:
                continue
            if level:
                try:
                    entry = json.loads(line)
                    if entry.get("level", "") != level:
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass
            print(line)

    _print_lines(log_path, lines, level_filter)

    if follow:
        import time
        with open(log_path, "r", encoding="utf-8") as f:
            f.seek(0, 2)  # seek to end
            try:
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.3)
                        continue
                    line = line.rstrip()
                    if level_filter:
                        try:
                            entry = json.loads(line)
                            if entry.get("level", "") != level_filter:
                                continue
                        except (json.JSONDecodeError, KeyError):
                            pass
                    print(line)
            except KeyboardInterrupt:
                pass


def main():
    """Main function to initialize and run the scraper or management commands."""
    args = parse_arguments()
    config = load_config(args.config)

    # Setup structured logging (skip for 'logs' viewer — it reads raw files)
    if args.command != "logs":
        from modules.log_manager import setup_logging
        setup_logging(
            level=config.get("log_level", "INFO"),
            log_dir=config.get("log_dir", "logs"),
            log_file=config.get("log_file", "scraper.log"),
        )

    commands = {
        "scrape": _run_scrape,
        "export": _run_export,
        "db-stats": _run_db_stats,
        "clear": _run_clear,
        "hide": _run_hide,
        "restore": _run_restore,
        "sync-status": _run_sync_status,
        "prune-history": _run_prune_history,
        "migrate": _run_migrate,
        "api-key-create": _run_api_key_create,
        "api-key-list": _run_api_key_list,
        "api-key-revoke": _run_api_key_revoke,
        "api-key-stats": _run_api_key_stats,
        "audit-log": _run_audit_log,
        "prune-audit": _run_prune_audit,
        "logs": _run_logs,
    }

    handler = commands.get(args.command)
    if handler:
        handler(config, args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
