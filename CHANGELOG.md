# Changelog

All notable changes to Google Reviews Scraper Pro.

## [Unreleased]

### Added
- **SQLite database foundation** — new `ReviewDB` class with 7 tables (places, reviews, scrape_sessions, review_history, place_aliases, sync_checkpoints, schema_version), 40+ methods, optimistic locking, dual-hash change detection, and full audit trail.
- **Database backend abstraction** — `DatabaseBackend` protocol with `SQLiteBackend` implementation (WAL mode, foreign keys, busy_timeout). Pre-ready for PostgreSQL/MySQL via config switch.
- **Place ID extraction** — `extract_place_id()` handles CID, hex ID, short links, and SHA-256 fallback. `canonicalize_url()` normalizes URLs for alias matching.
- **Multi-business support** — new `businesses` config format with per-business overrides for MongoDB, S3, custom_params, and all other settings. Backward compatible with `urls` and `url`.
- **CLI management commands** — `export` (JSON/CSV), `db-stats`, `clear`, `hide`, `restore`, `sync-status`, `prune-history`, and `migrate` (from JSON/MongoDB).
- **Per-business image isolation** — images stored under `{image_dir}/{place_id}/profiles/` and `/reviews/` instead of flat directories.
- **Per-business S3 paths** — uploads organized as `{prefix}/{place_id}/profiles/` and `/reviews/`.
- **Incremental MongoDB sync** — only changed reviews (new/updated/restored) are synced; unchanged reviews are skipped.
- **Data migration** — `migrate` command imports existing JSON files or MongoDB collections into the SQLite database.
- **181 unit tests** across 10 test files covering database operations, CLI commands, config loading, migration, and start commands.
- `config.sample.yaml` and `config.businesses.sample.yaml` with documented examples for all configuration options.

### Changed
- Extracted `merge_review()` to `modules/data_logic.py` to prevent circular imports (backward-compatible re-export from `data_storage.py`).
- Scraper pipeline now writes to SQLite as primary storage, with MongoDB and JSON as optional sync targets.
- `place_id` field added to all review documents in MongoDB/JSON exports for per-business filtering.
- README rewritten with all new CLI commands, multi-business config, output structure, and configuration reference table.

## [1.0.3] - 2026-02-07

### Fixed
- **Broken date parser** — `parse_date_to_iso()` had incorrect imports (`datetime.now()` on the module, `timezone.timedelta` instead of `timedelta`), causing it to silently fail and return empty strings for every review date.

### Added
- **Multilingual date parsing** — review dates now parse correctly in 25+ languages (Indonesian, Spanish, French, German, Italian, Portuguese, Russian, Japanese, Korean, Chinese, Arabic, Hindi, Turkish, Dutch, Polish, Vietnamese, Thai, Hebrew, and more). Previously only English "X ago" strings were recognized.
- Arabic/Hebrew dual-form support (e.g., "שנתיים" = 2 years, "سنتين" = 2 years).

### Changed
- Removed ~130 lines of dead commented-out code from `utils.py`.

## [1.0.2] - 2026-02-07

### Added
- **Google Maps "Limited View" bypass** - Google started restricting reviews for non-logged users, showing "You're seeing a limited view of Google Maps". The scraper now bypasses this via search-based navigation (`/maps/search/`) instead of direct place URLs.
- `navigate_to_place()` method with multi-step bypass strategy: session warm-up on google.com, place name extraction, search-based navigation, and direct URL fallback.
- `_extract_place_name()` helper to parse place names from URLs or page titles (supports shortened URLs like `maps.app.goo.gl`).
- `_extract_place_coords()` helper to extract lat/lng from Google Maps URLs for precise search targeting.
- `pyproject.toml` for modern Python packaging and `uv` support.

### Changed
- Synced version strings across `api_server.py`, `README.md`, and `pyproject.toml` to 1.0.2.
- Added changelog reference section to `README.md`.

## [1.0.1] - 2025-12-07

### Changed
- Migrated from `undetected-chromedriver` to **SeleniumBase UC Mode** for automatic Chrome/ChromeDriver version management.
- No more manual version matching headaches - SeleniumBase handles it automatically.

## [1.0.0] - 2025-06-03

### Added
- REST API server (`api_server.py`) with FastAPI - trigger scraping jobs via HTTP endpoints.
- Background job processing with concurrent execution (max 3 jobs).
- Job management: create, list, cancel, delete jobs with status tracking.
- API endpoints: `/scrape`, `/jobs`, `/jobs/{id}`, `/stats`, `/cleanup`.
- `pytest` test suite for S3 and core functionality.
- AWS S3 image upload support with custom folder structure.
- S3 handler module for cloud image storage.

## [0.9.2] - 2025-08-09

### Changed
- Get original size images from Google instead of thumbnails.

## [0.9.1] - 2025-06-02

### Fixed
- Fixed English localization issues in review extraction.
- Fixed English scraper text parsing.

## [0.9.0] - 2025-05-12

### Added
- Configuration file support (`config.yaml`) for all scraper settings.
- MongoDB integration for persistent review storage.
- JSON backup storage with deduplication via `.ids` file.
- Image download pipeline with multi-threaded downloading.
- URL replacement support for custom CDN domains.
- Custom parameters injection for each review document.
- Multi-language review tab detection (50+ languages).
- Multi-language sort order support (20+ languages).
- Relative date parsing with multi-language support.
- Review merging logic for incremental scraping.

## [0.1.0] - 2025-04-24

### Added
- Initial release of Google Reviews Scraper Pro v1.0.0.
- SeleniumBase-based Google Maps review scraping.
- Multi-language review extraction.
- Profile picture and review image downloading.
- Owner response extraction.
- Sample output and configuration examples.
