# Changelog

All notable changes to Google Reviews Scraper Pro.

## [Unreleased]

## [1.2.1] - 2026-02-09

### Added
- **Unified S3 provider config** — `s3.provider` key with presets for `"aws"` (default), `"minio"` (auto-sets `path_style: true`, `acl: ""`), and `"r2"` (auto-sets `region_name: "auto"`, `acl: ""`). Explicit config always overrides preset defaults.
- **S3 endpoint_url support** — `s3.endpoint_url` param for connecting to MinIO, R2, or any S3-compatible storage. URL generation adapts automatically.
- **S3 path-style addressing** — `s3.path_style` option enables path-style S3 requests (required by MinIO).
- **Configurable S3 ACL** — `s3.acl` setting (default `"public-read"`). Set to empty string to skip ACL entirely (required by R2).
- **Structured logging** — Rich colored console output to stderr + rotating JSON log files in `logs/` directory. Configurable via `log_level`, `log_dir`, `log_file` in config.
- **`logs` CLI command** — `python start.py logs [--lines N] [--level LEVEL] [--follow]` to view and tail structured log files.
- **`modules/log_manager.py`** — centralized `setup_logging()` with `RichHandler` (stderr), `RotatingFileHandler` (JSON lines, 5MB rotation, 5 backups), and noisy logger suppression.
- 24 new tests — `test_s3_providers.py` (17 tests: preset resolution, URL generation, ACL handling, client init) and `test_log_manager.py` (8 tests: handler setup, JSON format, level filtering).
- `rich>=13.7.0` added to `requirements.txt`.
- **SQLite-based API key management** — `ApiKeyDB` class in `modules/api_keys.py` stores SHA-256 hashed keys with create, verify, revoke, list, and stats operations. Replaces env var / config-based single key.
- **API audit logging** — every API request logged to `api_audit_log` table with key ID, endpoint, method, client IP, status code, and response time. `AuditMiddleware` in `api_server.py`.
- **6 new CLI commands** — `api-key-create`, `api-key-list`, `api-key-revoke`, `api-key-stats`, `audit-log`, `prune-audit`.
- **ScrapeRequest API fields** — `scrape_mode`, `stop_threshold`, `max_reviews`, `max_scroll_attempts`, `scroll_idle_limit` added to the `/scrape` endpoint.
- **API endpoint restructure** — all endpoints organized into 5 tagged `APIRouter` groups (System, Jobs, Places, Reviews, Audit Log) for cleaner Swagger docs.
- **Places endpoints** — `GET /places` (list all) and `GET /places/{place_id}` (get details) to query registered places from SQLite.
- **Reviews endpoints** — `GET /reviews/{place_id}` (paginated list with `limit`/`offset`/`include_deleted`), `GET /reviews/{place_id}/{review_id}` (single review), `GET /reviews/{place_id}/{review_id}/history` (change history with deserialized `changed_fields`).
- **Audit log endpoint** — `GET /audit-log` with `key_id`, `limit`, and `since` query filters. API key management remains CLI-only for security.
- **Database stats endpoint** — `GET /db-stats` returns full ReviewDB statistics (places, reviews, sessions, history counts, db size, per-place breakdown). Replaces `GET /stats` which only returned job manager stats.
- **ReviewDB.count_reviews()** method for pagination totals.
- **Dependency injection** — `get_review_db()` and `get_api_key_db()` helpers for cleaner endpoint signatures.
- ReviewDB initialized in API server lifespan for read-only queries (safe with WAL mode).

### Changed
- Replaced `tqdm` progress bar with `rich.progress.Progress` in scraper scroll loop.
- Removed `logging.basicConfig()` from `config.py` and `api_server.py` — logging now initialized via `setup_logging()` in both entrypoints (`start.py`, `api_server.py`).
- API authentication switched from single `API_KEY` env var to SQLite-managed keys. Open access when no keys exist; auth enforced when at least one active DB key exists.
- Removed `api_key` from config files (`config.sample.yaml`, `config.yaml`). CORS `allowed_origins` remains.
- Removed legacy `stop_on_match` and `overwrite_existing` fields from `ScrapeRequest` model (replaced by `scrape_mode`).
- `GET /stats` renamed to `GET /db-stats` — now returns ReviewDB statistics instead of job-only stats. Job stats remain available via `GET /jobs`.
- API version bumped to 1.2.1.

## [1.1.1] - 2026-02-08

### Added
- **Post-scrape pipeline** — new `PostScrapeRunner` in `modules/pipeline.py` runs processing (dates, images, S3, cleanup, custom params) once, then writes to each enabled target (MongoDB, JSON). Eliminates duplicate image downloads when both MongoDB and JSON are enabled.
- **S3 `sync_mode`** — `s3.sync_mode` config option (`"new_only"`, `"update"`, `"full"`) controls whether existing S3 files are skipped or overwritten.
- **`S3Handler.list_existing_keys()`** — lists existing S3 keys under prefix for `sync_mode="new_only"`.
- **Pure-writer methods** — `MongoDBStorage.write_reviews()` and `JSONStorage.write_json_docs()` accept already-processed reviews without re-running date/image/param logic.

### Changed
- Scraper post-scrape block replaced with single `PostScrapeRunner` call. Removed `MongoDBStorage`/`JSONStorage` init from scraper `__init__`. Processing happens once in the pipeline instead of per-target.
- Backward-compat: `save_reviews()` and `save_json_docs()` still work for external callers (e.g. `api_server.py`).

## [1.1.0] - 2026-02-08

**Major release** — biggest update since 1.0. The scraper now uses SQLite as its primary storage engine with full multi-business support, a new CLI toolkit, and significantly improved scrape efficiency. See the full list of changes below.

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
- **`scrape_mode` enum** — replaces `overwrite_existing` and `stop_on_match` booleans with a single `scrape_mode` setting: `"new_only"` (skip existing), `"update"` (default, insert new + update changed), `"full"` (re-process all).
- **Batch-level early stop** — `stop_threshold` counts consecutive fully-matched scroll batches (entire batch unchanged) instead of individual reviews. Minimum 3 reviews per batch to prevent false stops from tiny tail batches.
- **Configurable scroll limits** — `max_reviews`, `max_scroll_attempts`, and `scroll_idle_limit` exposed as config parameters (previously hardcoded).
- **Sort safety guard** — `stop_threshold` auto-disabled at runtime when sort-by-newest fails or `sort_by != "newest"`, preventing incorrect early stops.
- **Legacy config alias resolution** — `overwrite_existing: true` maps to `scrape_mode: "full"`, `stop_on_match: true` maps to `stop_threshold: 3` with deprecation warnings. New names always win.
- 181 unit tests across 10 test files covering database operations, CLI commands, config loading, migration, and start commands.
- `config.sample.yaml` and `config.businesses.sample.yaml` with documented examples for all configuration options.

### Fixed
- **Content hash volatility** — `compute_content_hash()` now uses the raw date string (e.g., "2 months ago") instead of the parsed ISO timestamp, which changed every second due to `datetime.now()` and caused all reviews to show as "updated" on every scrape.
- **Sort menu duplicate selection** — Google Maps menu items had duplicate DOM elements (parent + child). Deduplication now uses Selenium's stable element ID and filters out container elements with newlines. Sort selection uses text-first matching against localized labels with position-based fallback.
- **Review card double-processing** — cards already in the database were being re-parsed and upserted on every scroll iteration (each review processed twice per session). Cards in `seen` are now counted as "unchanged" for batch stop without re-upsert, eliminating hash flip-flop and halving DB writes.
- **Image download URL mutation** — downloading images no longer overwrites the original URL reference; a separate `download_url` is used for the HTTP request.

### Changed
- Extracted `merge_review()` to `modules/data_logic.py` to prevent circular imports (backward-compatible re-export from `data_storage.py`).
- Scraper pipeline now writes to SQLite as primary storage, with MongoDB and JSON as optional sync targets.
- `place_id` field added to all review documents in MongoDB/JSON exports for per-business filtering.
- README rewritten with all new CLI commands, multi-business config, output structure, and configuration reference table.
- Repeat scrapes with no changes now complete in ~42s (down from ~109s) thanks to batch-level early stop.

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
