# Changelog

All notable changes to Google Reviews Scraper Pro.

## [Unreleased]

## [1.3.1] - 2026-10-19

### Added
- **Sign-in expiry shows up in health checks** — `/health/scrape` gains `browser_profile` (`signed_in`, `signed_out`, `unknown` while Chrome holds the profile, or `not_configured`) and reports at least `degraded` when the profile is signed out, since every scrape then gets the capped list. `python start.py health` prints the profile state and says `DEGRADED` when it's signed out. `browser-login --check` says when the profile can't be read because Chrome is using it, instead of reporting it as signed out.

### Changed
- **The `INCOMPLETE` warning names the fix** — a capped run now ends with the likely next step for your setup: set `browser_profile_dir`, run `browser-login` (profile signed out), or a note that the profile is signed in. The message still starts with "Google showed only N of about M reviews".
- **README: keeping signed-in runs modest** — recommends `scrape_mode: "update"` with `stop_threshold` and a `max_reviews` cap for regular runs with a signed-in account.

## [1.3.0] - 2026-10-19

### Added
- **CI** — GitHub Actions runs the test suite on every push and pull request: Ubuntu with Python 3.10 and 3.14, Windows with Python 3.13. The MongoDB/S3 connection tests now skip when the gitignored `config.yaml` is missing (they errored in every fresh clone), and tests that need `:` in folder names skip on Windows.
- **Limited-view detection** — Google currently shows signed-out browsers only the first 5 reviews of a place, followed by a "See more reviews (N)" button that opens a sign-in dialog. The scraper used to scroll 15 more times, store the 5 reviews and report a normal success. It now reads N from that button, clicks it once (if more reviews load, scraping continues), and otherwise stops right away. The session is stored with the new status `limited` and a message like "Google showed only 5 of about 746 reviews", the run ends with an `INCOMPLETE:` warning, API jobs get a new `warning` field (also used as the progress message), `/health/scrape` gains `limited_sessions_24h` and reports `degraded`, and `start.py health` prints `DEGRADED`. Exit codes and job status (`completed`) are unchanged.
- **Signed-in browser profile** (`browser_profile_dir`, off by default) — points Chrome at a profile folder signed in to a Google account instead of a fresh incognito window, the way to get past the limited view. New `python start.py browser-login` opens a normal (not automated) Chrome on that folder at Google's sign-in page and reports whether the sign-in worked; `--check` only reports. The profile is treated as a credential: the folder is created owner-only (0700), only "signed in: yes/no" is ever logged, Google sign-in cookies (`SID`, `__Secure-1PSID`, …) are never passed to the image downloader, common profile folder names are gitignored, and scrapes in one process take turns with the profile because Chrome locks it while open.
- **`place_id` in job responses** (PR #27 by @sajjad-git) — `GET /jobs/{job_id}` and `GET /jobs` now return the scraped place's `place_id`, so clients can go straight to `/reviews/{place_id}` and `/places/{place_id}` without matching URLs. Also set when the scrape fails after the place was registered. Noted in the README API section.

### Fixed
- **`reviews_count` in job responses was always null** (PR #27 by @sajjad-git) — the job manager read `scraper.total_reviews`, which nothing ever set. It now holds the number of reviews this run wrote or re-checked (new + updated + restored + unchanged, parse errors excluded); in `update` and `new_only` mode, reviews already stored are skipped and not counted. Tests added in `tests/test_job_manager.py`.
- **Reviews tab rejected when the place name contains a tab word** (issue #25, PR #26 by @sajjad-git) — Google puts the place name in every tab's aria-label, so "Reviews for Caledon Community Services" lost its match to the "services" penalty and the scraper fell back to clicking any element with a review word. The penalty is now skipped when the same field already has a review keyword, and the place name (from the page title) is removed from the aria-label before scoring, so names like "Davis Diner" (contains "avis") can't make a hidden Menu or Overview tab look like Reviews either. Six regression tests added.
- **Sorting in the Italian UI** (PR #30 by @lollo03) — the Italian sort chip ("Ordina recensioni") had no selector, so a generic fallback picked the "Informazioni" button instead and sorting failed. Added the `Ordina` selector next to the other languages, plus the keyword the PR added so the button passes the sort-keyword check.
- **No images saved on Windows** (PR #31 by @johntranb) — every place id contains `:` (`0x…:0`, `cid:`, `short:`, `hash:`), which Windows rejects in a folder name, so the images task failed with `WinError 123` and wrote nothing. Per-place image folders now use `_` instead of `:` on every OS (`review_images/0x30e29edb0244829f_0/`), in both the image task and the S3 task. Existing folders named with the raw id are renamed once on first use (only folders directly inside `image_dir`), so macOS and Linux users keep their downloaded images. Since `/` and `\` are replaced too, a crafted `cid=` or short-link id containing `../` can no longer create folders outside `image_dir`. S3 keys are unchanged. Tests added in `tests/test_image_handler.py`.
- **Scraping the wrong tab without noticing** (rest of issue #25) — the Reviews-tab check passed on the Overview tab too (it only looked for review cards and star icons, which Overview also shows), so a failed tab click went on to scrape Overview's review snippets as if they were the list. The check now requires the selected tab to be the Reviews tab, or Google's reviews marker `!9m1!1b1` in the URL. If the Reviews tab still isn't open after clicking, the session ends as `failed` instead of scraping something else. The XPath fallback only clicks real tabs now, and the old "URL doesn't contain 'review'" warning (printed on every run, right or wrong) is gone.
- **A failed sort could replace the review list** — when no sort button matched, fallbacks accepted any button with a dropdown attribute (in the Italian UI that was the rating "Informazioni" button), and afterwards a blind click at a fixed offset reset the page. Live, that left zero review cards. Sort candidates must now sit in the place panel, outside review cards, and either name sorting in their text or aria-label (case-insensitive, about 20 languages, place name ignored) or be the dropdown that shows the current order (a menu button with text; the info button next to it has neither `aria-expanded` nor text and is the legal-disclosure toggle). Failed attempts close the menu with Escape instead of clicking.
- **Place ids were cut in half** — the hex id regex stopped at the `x` after the colon, so every place was stored as `0x…:0` instead of `0x…:0x…`. The dropped half is the CID, the part that identifies the business; places at the same location could share the stored id. Ids are now complete. A place stored under the old short id moves to its full id the next time it is scraped **from the same URL**: all its rows (reviews, history, sessions, sync checkpoints, aliases) are renamed in one transaction, its image folder is renamed together with the Windows-safe rename above (one migration, not two), and the old id stays as an alias, so `/places/{old_id}` and `/reviews/{old_id}/…` keep working. That run re-syncs all of the place's reviews so MongoDB documents and S3 keys get the new id; S3 objects under the old prefix are left in place. Different URLs are never merged.
- **`images_count` in job responses was always null** — nothing set it. It now holds the number of images on disk (downloaded now or earlier) for the reviews the run handled, and stays `null` when image download is off.
- **`places.total_reviews` was always 0** — only a batch upsert path no scrape uses kept it current. It is now recounted (visible, not soft-deleted reviews) at the end of every scrape and after `hide`/`restore`, so `/places`, `/db-stats` and `start.py db-stats` show real numbers. Existing places show the right number after their next scrape.
- **Re-scrapes with nothing new were marked `empty`** — a session counted as empty when it saved no new or changed review, even though it had looked at reviews that were simply already stored, and `/health/scrape` counts empty sessions as degraded. `empty` now means no review was seen at all; a run that only finds stored reviews is `completed`.
- **Non-ASCII `config.yaml` on Windows** (taken from PR #24 by @ardadalbas) — the config was read with the OS default encoding, so on Windows any non-ASCII text (business names, `custom_params`) failed to decode, `load_config()` logged an error and silently fell back to defaults ("No URL configured"). The file is now read and written as UTF-8.

### Changed
- **Config defaults no longer leak into your data** — `custom_params` defaulted to `{company: "Thaitours", source: "Google Maps"}`, so every user's reviews were stamped with the maintainer's company name, and because configs are deep-merged an empty `custom_params: {}` could not switch it off. The default is now empty: documents only get the extra fields you configure. **If you relied on the old `company`/`source` fields, add them to `custom_params` in `config.yaml`.**
- **`use_mongodb` defaults to `false`**, as the README and `config.sample.yaml` already said. The code default was `true`, so a config without the key tried to reach MongoDB. **If you sync to MongoDB without setting the key, add `use_mongodb: true`.**
- **A missing `config.yaml` is no longer created on read** — `load_config()` wrote a full default config into the working directory whenever the file was missing, including on `import api_server` and in tests (which then made the MongoDB/S3 tests try a live MongoDB). It now logs that defaults are used and points at `config.sample.yaml`.
- **`max_reviews` limits the reviews a run looks at** — it used to compare against every review already stored for the place, so with 571 stored and `max_reviews: 40` an `update` run stopped after a single new review. It now counts the reviews looked at in this run, stored ones included ("check the newest N"), and the run ends with `Stopping: looked at max_reviews (N) reviews` instead of the unrelated "No new reviews found after 15 scroll attempts".

## [1.2.3] - 2026-04-23

### Fixed
- **Rate-limit detection now actually triggers** — `_RateLimited` is raised from the driver-probe loop when `driver.current_url` matches `/sorry/`, `recaptcha`, or `captcha`. Previously the exception class and cooldown handler shipped in v1.2.2 but nothing raised the exception, so the CAPTCHA-cooldown path was dead code.

### Changed
- **README.md** — Python badge extended to 3.14 (matches `pyproject.toml` classifiers). Feature list gains date-range filtering, sub-rating capture, indestructible scraping, and selector health telemetry. Config table documents the 5 new v1.2.2 sections (`date_filter`, `resilience`, `health`, `audit`, `adaptive`). API section adds `/health/scrape` example and a `POST /scrape` example with `date_filter` payload.
- **config.sample.yaml** — commented example blocks for `date_filter`, `resilience`, `health`, `audit`, `adaptive` sections, each labelled `v1.2.2+` so users can see what's new.

## [1.2.2] - 2026-04-23

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
