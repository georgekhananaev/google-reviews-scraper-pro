# Changelog

All notable changes to Google Reviews Scraper Pro.

## [Unreleased]

### Added
- **Date-range filter** (issue #19) — `date_filter.after` / `date_filter.before` in config, plus `--after` / `--before` / `--date-mode` CLI flags and a `date_filter` field on `POST /scrape`. Two modes: `post_filter` (default — filters writes to MongoDB/JSON/S3; SQLite retains everything) and `early_stop` (requires `sort_by: newest`; stops scrolling after 3 consecutive cards older than `after`).
- **Sub-review / category ratings** (issue #18) — `RawReview.sub_ratings` captures per-category scores (Service/Food/Cleanliness/Rooms/…) shown on hotels and restaurants. New nullable `reviews.sub_ratings` column (additive migration to schema v2). Canonical English keys; unknown labels preserved in `_other`. Multilingual label canonicalization in new `modules/sub_rating_labels.py`.
- **Driver session-death recovery** (issue #20) — new `resilience` config section with `retry_on_session_death`, `retry_backoff_base_seconds`, `rate_limit_cooldown_seconds`. Scraper probes the driver each scroll iteration; on `InvalidSessionIdException` / `WebDriverException` it flushes partial results, marks the session `partial`, and retries once with a fresh driver. Rate-limit signals set status `rate_limited` and enforce a cooldown.
- **Scoped post-scrape pipeline** — `PostScrapeRunner.set_changed_ids()` lets the scraper tell the pipeline which reviews actually changed. Image, S3, and MongoDB tasks skip unchanged reviews entirely. Typical repeat scrape of an existing place: from hundreds of filename + HTTP checks down to zero.
- **Selector health telemetry** — new `selector_health` SQLite table records hit/miss/stale outcomes per CSS selector per scrape session. New `python start.py selector-health` CLI prints hit-rate across recent sessions so DOM regressions surface as telemetry, not support tickets.
- **Scraper health endpoint** — `GET /health/scrape` returns `{status, last_session_status, empty_sessions_24h, degraded_sessions_24h, last_synthetic_success}` derived from recent session rows. Good for uptime probes / dashboards.
- **`health` CLI command** — `python start.py health --url <URL>` runs a synthetic single-review scrape to verify end-to-end scraping is working.
- **`db-vacuum` CLI command** — `python start.py db-vacuum` runs `PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM` to reclaim space and truncate the WAL.
- **Session-status granularity** — completed sessions now get `"empty"` when zero reviews extracted, `"degraded"` when >30% of cards failed parsing, plus `"partial"` / `"rate_limited"` from the resilience layer. Previously everything was `"completed"`.
- **Browser cookie forwarding** — scraper extracts cookies from the Selenium driver before quit and passes them to the `ImageHandler.requests.Session`. Unlocks downloads for newer `ABOP9p…`-prefix googleusercontent URLs that were previously returning 403.
- **Google Maps URL allowlist** on `POST /scrape` — rejects non-Google URLs with 400 before queuing a job. Prevents abuse of the job queue with arbitrary URLs.
- **Image host allowlist** — SSRF guard on `ImageHandler`, only downloads from `googleusercontent.com` / `ggpht.com` / `gstatic.com` / `google.com` subdomains.
- **Graceful startup** — API server boots even if the API key DB or review DB fails to initialize (fails closed rather than crashing). Audit log pruned on startup per `audit.retention_days` (default 90).
- **`constraints.txt`** — known-good exact dependency versions for reproducible installs: `pip install -r requirements.txt -c constraints.txt`.
- **New config sections** — `date_filter`, `resilience`, `health`, `metrics`, `adaptive`, `audit`. All optional; omitting them preserves v1.2.1 behavior exactly.
- **44 new tests** — `test_scraper_tab_detection.py` (tab-scoring regression), `test_date_filter.py` (inclusion/early-stop semantics), `test_sub_ratings.py` (canonicalization + DB merge), `test_api_concurrency.py` (cross-thread sqlite stress).

### Fixed
- **Menu-tab misclick** (issues #21, #17, and part of #15) — `is_reviews_tab()` rewritten with weighted multi-signal scoring. `data-tab-index="1"` alone is no longer accepted; the tab must also match a review keyword in aria-label or text, and is penalized if it matches a known non-review label (Menu, Photos, Overview, …). `[role="tab"][aria-label*="review" i]` and localized variants moved to the top of the selector list; `[data-tab-index="1"]` demoted to last resort.
- **Silent-stub parse** — parse failures during scroll no longer store an empty `RawReview(id, text="", lang="und")` stub that polluted content hashes downstream. Failed cards are skipped and counted via `batch_stats["parse_errors"]`.
- **Silent review truncation** — `models.py` hardcoded `MORE_BTN = "button.kyuRq"` now has fallback selectors; if Google changes the class name, review text is no longer silently truncated at ~280 chars. Same pattern applied to photo, rating, date, owner-response, and text selectors.
- **Cross-thread sqlite `ProgrammingError`** — the single shared `ReviewDB` on `app.state` now uses `check_same_thread=False` + an internal `threading.RLock` on writes. Previously a latent crash waiting to hit under concurrent API load.
- **Non-atomic review upsert** — insert/update and `review_history` log now share a single `backend.transaction()`. Review can no longer exist without its audit trail.
- **Timing channel in API key verify** — switched to `secrets.compare_digest` over all active keys. Match case no longer short-circuits.
- **20 bare `except:` blocks** in `modules/scraper.py` replaced with `except Exception:` — no longer swallows `KeyboardInterrupt` / `SystemExit`.
- **Empty-stub review count** — session `reviews_found` now reports real reviews, not stubs.
- **WAL growth** — `SQLiteBackend.close()` runs `PRAGMA wal_checkpoint(TRUNCATE)`; prevents unbounded `.db-wal` file.
- **`ScrapeRequest` error leak** — 500 responses no longer include raw exception text; log it server-side only.
- **Filename truncation** — `ImageHandler._sanitize_filename` cap raised from 120 to 200 chars so googleusercontent tokens (~142 chars) aren't truncated into collisions.

### Changed
- **Python 3.14 supported** — `pydantic` pin relaxed from `~=2.11.5` to `>=2.11.5,<3` in both `requirements.txt` and `pyproject.toml`. Adds `Programming Language :: Python :: 3.14` classifier.
- **Language detection** — `detect_lang()` now identifies Arabic, Hindi, Russian, Greek, Korean, Japanese, and Chinese in addition to Hebrew and Thai. Covers the 25+ languages the date parser already supports.
- **Extended `REVIEW_WORDS`** with French (`avis`, `critiques`), German, Spanish, Portuguese, Italian, Russian, Polish, Turkish, Vietnamese, Indonesian, Swedish, Norwegian, Danish, Finnish, Greek, Czech, Romanian, Hungarian, Bulgarian. New `NON_REVIEW_TAB_WORDS` set used for penalty scoring.
- **Multilingual limited-view detection** — `_is_limited_view()` checks French/German/Spanish/Hebrew/Thai/Russian/Japanese/Korean/Chinese/Arabic/Turkish/Polish/Dutch strings, plus a structural signal (sign-in button present + zero tabs).
- **403 logging** — per-URL errors demoted to DEBUG; a single summary info line replaces the error wall at end of batch.

### Removed
- Empty-stub review entries on parse failure — previously written, now skipped.

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
