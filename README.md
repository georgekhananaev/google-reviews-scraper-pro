# Google Reviews Scraper Pro (2026)

![Google Reviews Scraper Pro](https://img.shields.io/badge/Version-1.1.1-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Last Update](https://img.shields.io/badge/Last%20Updated-February%202026-red)

**A scraper that ACTUALLY WORKS in 2026.** While others break with every Google update, this battle-tested solution extracts every detail from Google reviews. Multi-business support, SQLite database, MongoDB sync, S3 uploads, and a full CLI toolkit — all in one package.

## Features

- **Works in 2026**: Bypasses Google's "limited view" for non-logged users via search-based navigation — no login needed
- **Multi-Business**: Scrape multiple businesses in one run with per-business config overrides
- **SQLite Database**: Primary storage with full audit history, change detection, and per-place isolation
- **MongoDB Sync**: Incremental sync — only changed reviews are pushed, unchanged reviews are skipped
- **S3 Cloud Storage**: Auto-upload images to AWS S3 with per-business folder structure
- **CLI Management**: Export, import, hide/restore reviews, prune history, view stats — all from the command line
- **SeleniumBase UC Mode**: Anti-detection with automatic Chrome/ChromeDriver version matching
- **Multilingual**: Parses dates and reviews in 25+ languages
- **Image Capture**: Multi-threaded download of all review and profile images, organized per-business
- **REST API**: Trigger scraping jobs via HTTP endpoints with background processing
- **Change Detection**: Tracks new, updated, restored, and unchanged reviews per scrape session
- **Audit History**: Every change logged with old/new values, timestamps, and session IDs

## Requirements

```
Python 3.10+
Chrome browser
```

Optional:
- MongoDB (for syncing reviews to a MongoDB collection)
- AWS S3 (for cloud image storage)

## Installation

```bash
git clone https://github.com/georgekhananaev/google-reviews-scraper-pro.git
cd google-reviews-scraper-pro
pip install -r requirements.txt
```

## Quick Start

1. Copy the sample config:
```bash
cp config.sample.yaml config.yaml
```

2. Edit `config.yaml` — set your business URLs:
```yaml
businesses:
  - url: "https://maps.app.goo.gl/YOUR_PLACE_LINK"
```

3. Run:
```bash
python start.py
```

The SQLite database (`reviews.db`) is created automatically on first run.

## Configuration

### Minimal Config

```yaml
headless: true
sort_by: "newest"
db_path: "reviews.db"

businesses:
  - url: "https://maps.app.goo.gl/YOUR_PLACE"
    custom_params:
      company: "My Business"
```

### Multi-Business with Shared Settings

Global settings serve as defaults. Each business inherits them automatically:

```yaml
# Global defaults
headless: true
sort_by: "newest"
use_mongodb: true
mongodb:
  uri: "mongodb://localhost:27017"
  database: "reviews"
  collection: "google_reviews"

businesses:
  - url: "https://maps.app.goo.gl/PLACE_1"
    custom_params:
      company: "Hotel Sunrise"
  - url: "https://maps.app.goo.gl/PLACE_2"
    custom_params:
      company: "Hotel Moonlight"
```

### Per-Business Overrides

Each business can override any global setting — different MongoDB servers, S3 buckets, or image settings per business:

```yaml
# Global defaults
use_mongodb: true
mongodb:
  uri: "mongodb://localhost:27017"
  database: "reviews"
  collection: "google_reviews"

businesses:
  - url: "https://maps.app.goo.gl/PLACE_1"
    custom_params:
      company: "Client A"
    mongodb:
      uri: "mongodb://server-a:27017"
      database: "client_a"

  - url: "https://maps.app.goo.gl/PLACE_2"
    custom_params:
      company: "Client B"
    mongodb:
      uri: "mongodb://server-b:27017"
      database: "client_b"
    s3:
      bucket_name: "client-b-bucket"
```

See `config.sample.yaml` for all available settings and `config.businesses.sample.yaml` for detailed multi-business examples.

### All Configuration Options

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| **Scraper** | `headless` | `true` | Run Chrome without visible window |
| | `sort_by` | `"newest"` | `newest`, `highest`, `lowest`, `relevance` |
| | `scrape_mode` | `"update"` | `new_only`, `update`, or `full` |
| | `stop_threshold` | `3` | Consecutive fully-matched scroll batches before stopping (0 = disabled) |
| | `max_reviews` | `0` | Max reviews to scrape (0 = unlimited) |
| | `max_scroll_attempts` | `50` | Max scroll iterations |
| | `scroll_idle_limit` | `15` | Max idle iterations with zero new cards |
| **Database** | `db_path` | `"reviews.db"` | SQLite database path (auto-created) |
| **Processing** | `convert_dates` | `true` | Convert relative dates to ISO format |
| **Images** | `download_images` | `true` | Download review/profile images |
| | `image_dir` | `"review_images"` | Base directory (stored as `{image_dir}/{place_id}/`) |
| | `download_threads` | `4` | Parallel download threads |
| | `max_width` | `1200` | Max image width |
| | `max_height` | `1200` | Max image height |
| **MongoDB** | `use_mongodb` | `false` | Enable MongoDB sync |
| | `mongodb.uri` | `"mongodb://localhost:27017"` | Connection string |
| | `mongodb.database` | `"reviews"` | Database name |
| | `mongodb.collection` | `"google_reviews"` | Collection name |
| **S3** | `use_s3` | `false` | Enable S3 upload |
| | `s3.bucket_name` | `""` | S3 bucket name |
| | `s3.prefix` | `"google_reviews/"` | Key prefix (stored as `{prefix}/{place_id}/`) |
| | `s3.region_name` | `"us-east-1"` | AWS region |
| | `s3.delete_local_after_upload` | `false` | Remove local files after upload |
| **URL Replacement** | `replace_urls` | `false` | Replace Google URLs with custom CDN URLs |
| | `custom_url_base` | `""` | Base URL for replacements |
| | `preserve_original_urls` | `true` | Keep originals in `original_*` fields |
| **JSON** | `backup_to_json` | `true` | Export JSON snapshot after each scrape |
| | `json_path` | `"google_reviews.json"` | Output file path |

## CLI Commands

### Scrape Reviews

```bash
# Use config.yaml (default)
python start.py

# Override URL from command line
python start.py --url "https://maps.app.goo.gl/YOUR_URL"

# Headless + newest first + stop after 5 unchanged batches
python start.py -q --sort newest --stop-threshold 5

# Only insert new reviews (skip existing)
python start.py --scrape-mode new_only -q

# Force full rescan of all reviews
python start.py --scrape-mode full -q

# Custom parameters via CLI
python start.py --custom-params '{"company":"My Hotel","location":"Bangkok"}'
```

### Export Reviews

```bash
# Export all reviews as JSON
python start.py export

# Export as CSV
python start.py export --format csv

# Export specific business
python start.py export --place-id "0x305037cbd917b293:0"

# Export to specific file
python start.py export -o my_reviews.json

# Include soft-deleted reviews
python start.py export --include-deleted
```

### Database Management

```bash
# Show database statistics (review counts, places, sessions)
python start.py db-stats

# Clear all data for a specific place
python start.py clear --place-id "0x305037cbd917b293:0" --confirm

# Clear entire database
python start.py clear --confirm
```

### Review Management

```bash
# Soft-delete a review (hide from exports)
python start.py hide REVIEW_ID PLACE_ID

# Restore a soft-deleted review
python start.py restore REVIEW_ID PLACE_ID
```

### History & Sync

```bash
# Show sync checkpoint status
python start.py sync-status

# Prune audit history older than 90 days (dry run)
python start.py prune-history --dry-run

# Actually prune
python start.py prune-history --older-than 90
```

### Data Migration

```bash
# Import from existing JSON file
python start.py migrate --source json --json-path google_reviews.json

# Import from MongoDB
python start.py migrate --source mongodb

# Associate imported data with a specific place URL
python start.py migrate --source json --json-path reviews.json --place-url "https://maps.app.goo.gl/YOUR_URL"
```

## API Server

```bash
python api_server.py
# Server runs on http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

```bash
# Start a scraping job
curl -X POST "http://localhost:8000/scrape" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://maps.app.goo.gl/YOUR_URL", "headless": true}'

# Check job status
curl "http://localhost:8000/jobs/{job_id}"

# List all jobs
curl "http://localhost:8000/jobs"
```

## Output Structure

### SQLite Database

Primary storage. Reviews are isolated per `place_id` with full audit history:

```
reviews.db
├── places          — registered businesses with coordinates
├── reviews         — all review data with change tracking
├── review_history  — audit log of every change (old/new values)
├── scrape_sessions — session metadata (start, end, counts)
└── schema_version  — database migration tracking
```

### Images (per-business)

```
review_images/
├── 0x305037cbd917b293:0/     # Place ID for Business A
│   ├── profiles/
│   │   └── user123.jpg
│   └── reviews/
│       └── review789.jpg
├── 0x30e29edb0244829f:0/     # Place ID for Business B
│   ├── profiles/
│   └── reviews/
```

### S3 Bucket (per-business)

```
your-bucket/
├── google_reviews/
│   ├── 0x305037cbd917b293:0/
│   │   ├── profiles/
│   │   └── reviews/
│   ├── 0x30e29edb0244829f:0/
│   │   ├── profiles/
│   │   └── reviews/
```

### JSON Backup

Full snapshot exported after each scrape: `google_reviews.json`

### MongoDB

All reviews in a single collection with `place_id` field for filtering:

```js
db.google_reviews.find({ place_id: "0x305037cbd917b293:0" })
```

## Review Data Format

```json
{
  "review_id": "ChdDSUhNMG9nS0VJQ0FnSUNVck95dDlBRRAB",
  "place_id": "0x305037cbd917b293:0",
  "author": "John Smith",
  "rating": 4.0,
  "description": {
    "en": "Great place, loved the service!",
    "th": "สถานที่ยอดเยี่ยม บริการดีมาก!"
  },
  "likes": 3,
  "user_images": [
    "https://lh5.googleusercontent.com/p/AF1QipOj..."
  ],
  "author_profile_url": "https://www.google.com/maps/contrib/112419...",
  "profile_picture": "https://lh3.googleusercontent.com/a-/ALV-UjX...",
  "owner_responses": {
    "en": {
      "text": "Thank you for your kind words!"
    }
  },
  "review_date": "2025-04-15T08:15:22+00:00",
  "created_date": "2025-04-22T14:30:45+00:00",
  "last_modified_date": "2025-04-22T14:30:45+00:00",
  "company": "Your Business Name",
  "source": "Google Maps"
}
```

## Troubleshooting

**Chrome/Driver issues**
- SeleniumBase handles version matching automatically
- Update Chrome: `chrome://settings/help`
- Update SeleniumBase: `pip install --upgrade seleniumbase`

**"Where are my reviews?"**
- Google shows a "limited view" to non-logged users (Feb 2026). The scraper bypasses this automatically via search-based navigation.
- Copy URL directly from Google Maps address bar
- Try `--sort relevance` if other sort options return no results

**MongoDB connection issues**
- Check connection string and credentials
- Verify the server is reachable: `nc -zv your-host 27017`
- For Docker: `docker run -d --name mongodb -p 27017:27017 mongo:latest`

**Image download failures**
- Google may throttle after heavy usage
- Check file permissions on the `review_images/` directory

## AWS S3 Setup

1. Create an S3 bucket with public read access (if images should be publicly accessible)
2. Create an IAM user with `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` permissions
3. Configure in `config.yaml`:

```yaml
use_s3: true
s3:
  aws_access_key_id: "YOUR_KEY"
  aws_secret_access_key: "YOUR_SECRET"
  region_name: "us-east-1"
  bucket_name: "your-bucket"
  prefix: "google_reviews/"
  delete_local_after_upload: false
```

Images are organized per-business: `{prefix}/{place_id}/profiles/` and `{prefix}/{place_id}/reviews/`

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Quick unit tests only (no external services needed)
python -m pytest tests/ -v -k "not s3 and not mongodb and not seleniumbase"
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of releases.
