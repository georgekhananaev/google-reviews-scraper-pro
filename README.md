# Google Reviews Scraper Pro (2026)

![Google Reviews Scraper Pro](https://img.shields.io/badge/Version-1.2.1-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Last Update](https://img.shields.io/badge/Last%20Updated-February%202026-red)

**FINALLY! A scraper that ACTUALLY WORKS in 2026!** While others break with every Google update, this bad boy keeps on trucking. Say goodbye to the frustration of constantly broken scrapers and hello to a beast that rips through Google's defenses like a hot knife through butter. Multi-business support, SQLite database, MongoDB sync, S3 uploads, and a full CLI toolkit — all in one battle-tested, rock-solid package.

## Feature Artillery

- **Bulletproof in 2026**: While the competition falls apart, we've cracked Google's latest tricks. Google locked reviews behind a "limited view" in Feb 2026? We bypassed it the same day via search-based navigation — no login needed!
- **Multi-Business Madness**: Scrape multiple businesses in one run with per-business config overrides. One config to rule them all.
- **SQLite Fortress**: Primary storage with full audit history, change detection, and per-place isolation. Your data ain't going anywhere.
- **MongoDB Sync**: Incremental sync — only changed reviews are pushed, unchanged reviews are skipped. Because why waste bandwidth?
- **S3-Compatible Cloud Storage**: Auto-upload images to AWS S3, Cloudflare R2, MinIO, or any S3-compatible bucket with per-business folder structure. Cloud-native, baby!
- **CLI Toolkit**: Export, import, hide/restore reviews, prune history, view stats, tail logs — all from the command line like a true hacker
- **Enhanced SeleniumBase UC Mode**: Superior anti-detection with automatic Chrome/ChromeDriver version matching — no more version headaches!
- **Polyglot Powerhouse**: Devours reviews in a smorgasbord of languages — English, Hebrew, Thai, German, you name it! 25+ languages!
- **Aggressive Image Capture**: Multi-threaded downloading that would make NASA jealous. Snags EVERY damn photo from reviews and profiles, organized per-business.
- **REST API Server**: Trigger scraping jobs via HTTP endpoints with background processing
- **Change Detection on Steroids**: Tracks new, updated, restored, and unchanged reviews per scrape session
- **Audit History**: Every change logged with old/new values, timestamps, and session IDs. We don't miss a thing.
- **Time-Bending Magic**: Transforms Google's vague "2 weeks ago" garbage into precise ISO timestamps
- **Battle-Hardened Resilience**: Network hiccups? Google's tricks? HAH! We eat those for breakfast
- **Structured Logging**: Rich colored CLI output + rotating JSON log files in `logs/`. Filter and follow logs via `python start.py logs`

## Battle Station Requirements

```
Python 3.10+ (don't even try with 3.9, seriously)
Chrome browser (the fresher the better)
```

Optional (but c'mon, live a little):
- MongoDB (for syncing reviews to a MongoDB collection)
- AWS S3 / Cloudflare R2 / MinIO / any S3-compatible storage (for cloud image storage)
- Coffee (mandatory for watching thousands of reviews roll in)

## Deployment Instructions

1. Grab the source code:
```bash
git clone https://github.com/georgekhananaev/google-reviews-scraper-pro.git
cd google-reviews-scraper-pro
```

2. Arm your environment:
```bash
pip install -r requirements.txt
# Pro tip: Use a virtual env unless you enjoy dependency hell
```

3. Make sure this sucker works:
```bash
cp config.sample.yaml config.yaml
# Edit config.yaml — set your business URLs
python start.py
# If reviews start flowing, you're golden. If not, check your config!
```

The SQLite database (`reviews.db`) is created automatically on first run.

## Fine-Tuning Your Beast

Look, this isn't some one-size-fits-all garbage. You've got full control over every aspect.

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

Each business can override any global setting — different MongoDB servers, S3 buckets, or image settings per business. Go nuts:

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
| | `mongodb.tls_allow_invalid_certs` | `false` | Allow self-signed TLS certificates |
| **S3-Compatible** | `use_s3` | `false` | Enable S3-compatible upload (AWS S3, R2, MinIO, etc.) |
| | `s3.provider` | `"aws"` | Provider preset: `aws`, `minio`, or `r2` (applies sensible defaults) |
| | `s3.bucket_name` | `""` | Bucket name |
| | `s3.prefix` | `"google_reviews/"` | Key prefix (stored as `{prefix}/{place_id}/`) |
| | `s3.region_name` | `"us-east-1"` | Region (or `"auto"` for R2) |
| | `s3.endpoint_url` | `null` | Custom endpoint for R2/MinIO (leave empty for AWS) |
| | `s3.path_style` | `false` | Path-style addressing (MinIO requires `true`) |
| | `s3.acl` | `"public-read"` | ACL for uploads (empty string = skip ACL entirely) |
| | `s3.delete_local_after_upload` | `false` | Remove local files after upload |
| **URL Replacement** | `replace_urls` | `false` | Replace Google URLs with custom CDN URLs |
| | `custom_url_base` | `""` | Base URL for replacements |
| | `preserve_original_urls` | `true` | Keep originals in `original_*` fields |
| **Logging** | `log_level` | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| | `log_dir` | `"logs"` | Directory for rotating JSON log files |
| | `log_file` | `"scraper.log"` | Log file name (inside `log_dir`) |
| **JSON** | `backup_to_json` | `true` | Export JSON snapshot after each scrape |
| | `json_path` | `"google_reviews.json"` | Output file path |

## Unleashing Hell

### Battle-Tested Recipes

```bash
# The basics — just run it
python start.py
# Boom. That's it. Now go grab a coffee while the magic happens.

# Override URL from command line
python start.py --url "https://maps.app.goo.gl/YOUR_URL"

# Stealth Mode + Fresh Stuff First (perfect for cron jobs)
python start.py -q --sort newest --stop-threshold 5
# They'll never see you coming.

# Only insert new reviews (skip existing — why waste CPU cycles?)
python start.py --scrape-mode new_only -q

# Force full rescan of all reviews (the nuclear option)
python start.py --scrape-mode full -q

# Custom Tags Galore — brand these puppies however you want
python start.py --custom-params '{"company":"Hotel California","location":"Los Angeles"}'
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

### Logs

```bash
# View last 50 log entries (structured JSON)
python start.py logs

# Show last 100 entries, filter by level
python start.py logs --lines 100 --level ERROR

# Follow log output in real-time (like tail -f)
python start.py logs --follow
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

## API Server Mode

Want to trigger scraping jobs via REST API? We've got you covered:

```bash
python api_server.py
# Server runs on http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

Endpoints are organized into 5 tagged groups (visible in `/docs`):

### System

```bash
# Health check (no auth)
curl http://localhost:8000/

# Database statistics (places, reviews, sessions, db size)
curl -H "X-API-Key: grs_your_key_here" http://localhost:8000/db-stats

# Manual job cleanup
curl -X POST -H "X-API-Key: grs_your_key_here" "http://localhost:8000/cleanup?max_age_hours=24"
```

### Jobs

```bash
# Start a scraping job
curl -X POST "http://localhost:8000/scrape" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: grs_your_key_here" \
  -d '{"url": "https://maps.app.goo.gl/YOUR_URL", "headless": true}'

# List all jobs (with optional status filter)
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/jobs"

# Check job status
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/jobs/{job_id}"

# Start a pending job manually
curl -X POST -H "X-API-Key: grs_your_key_here" "http://localhost:8000/jobs/{job_id}/start"

# Cancel a running job
curl -X POST -H "X-API-Key: grs_your_key_here" "http://localhost:8000/jobs/{job_id}/cancel"

# Delete a completed/failed/cancelled job
curl -X DELETE -H "X-API-Key: grs_your_key_here" "http://localhost:8000/jobs/{job_id}"
```

### Places

```bash
# List all places
curl -H "X-API-Key: grs_your_key_here" http://localhost:8000/places

# Get a specific place
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/places/{place_id}"
```

### Reviews

```bash
# Paginated reviews for a place
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/reviews/{place_id}?limit=10&offset=0"

# Get a single review
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/reviews/{place_id}/{review_id}"

# Get review change history
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/reviews/{place_id}/{review_id}/history"
```

### Audit Log

```bash
# Query audit log
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/audit-log?limit=50"

# Filter by key ID
curl -H "X-API-Key: grs_your_key_here" "http://localhost:8000/audit-log?key_id=1&limit=20"
```

### Authentication (SQLite-Managed API Keys)

API keys are managed via SQLite — hashed with SHA-256 and stored in `reviews.db`. Every API request is audit-logged with key ID, endpoint, response time, and client IP.

```bash
# Create a named key (prints the raw key — store it securely!)
python start.py api-key-create "production-frontend"

# List all keys with usage stats
python start.py api-key-list

# Show detailed stats + recent requests for a key
python start.py api-key-stats 1

# Revoke a key (immediate, cannot be undone)
python start.py api-key-revoke 1

# View audit log (who called what, when, how fast)
python start.py audit-log
python start.py audit-log --key-id 1 --limit 20

# Prune old audit entries
python start.py prune-audit --older-than-days 90
python start.py prune-audit --dry-run
```

When at least one active DB key exists, all endpoints require a valid `X-API-Key` header. If no keys exist, auth is disabled (open access).

### CORS Configuration

Control which origins can access the API via the `ALLOWED_ORIGINS` environment variable:

```bash
# Allow specific origins (recommended for production)
ALLOWED_ORIGINS="https://yourdomain.com,https://admin.yourdomain.com" python api_server.py

# Allow all origins (default — credentials disabled for safety)
python api_server.py
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |

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

### Log Files

Structured JSON logs with automatic rotation:

```
logs/
├── scraper.log              # Current log file (JSON lines)
├── scraper.log.1            # Rotated (5MB max, 5 backups)
├── scraper.log.2
└── ...
```

View with: `python start.py logs --lines 50 --level ERROR --follow`

### JSON Backup

Full snapshot exported after each scrape: `google_reviews.json`

### MongoDB

All reviews in a single collection with `place_id` field for filtering:

```js
db.google_reviews.find({ place_id: "0x305037cbd917b293:0" })
```

## The Juicy Data Payload

Here's what you'll rip out of Google's clutches for each review (and yes, it's *way* more than their official API gives you):

```json
{
  "review_id": "ChdDSUhNMG9nS0VJQ0FnSUNVck95dDlBRRAB",
  "place_id": "0x305037cbd917b293:0",
  "author": "John Smith",
  "rating": 4.0,
  "description": {
    "en": "Great place, loved the service!",
    "th": "สถานที่ยอดเยี่ยม บริการดีมาก!"
    // Multilingual gold mine - ALL languages preserved!
  },
  "likes": 3, // Yes, we even grab those useless "likes" numbers
  "user_images": [
    "https://lh5.googleusercontent.com/p/AF1QipOj..."
    // ALL review images - not just the first one like inferior scrapers
  ],
  "author_profile_url": "https://www.google.com/maps/contrib/112419...",
  "profile_picture": "https://lh3.googleusercontent.com/a-/ALV-UjX...",
  "owner_responses": {
    "en": {
      "text": "Thank you for your kind words!"
      // Yes, even those canned replies from the business owner
    }
  },
  "review_date": "2025-04-15T08:15:22+00:00",
  "created_date": "2025-04-22T14:30:45+00:00",
  "last_modified_date": "2025-04-22T14:30:45+00:00",
  "company": "Your Business Name",
  "source": "Google Maps"
  // Add whatever other fields you want - this baby is extensible
}
```

## When Shit Hits The Fan

### DEFCON Scenarios & Quick Fixes

1. **Chrome/Driver Having a Lovers' Quarrel**
   - **Good news!** SeleniumBase handles Chrome/ChromeDriver version matching automatically
   - Update Chrome browser: Go to chrome://settings/help
   - SeleniumBase will automatically download the matching ChromeDriver — no manual intervention needed!
   - If issues persist: `pip install --upgrade seleniumbase`

2. **MongoDB Throwing a Tantrum**
   - Double-check your connection string — typos are the #1 culprit
   - Is your IP whitelisted? MongoDB Atlas loves to block new IPs
   - Run `nc -zv your-mongodb-host 27017` to check if the port's even reachable
   - Did you forget to start Mongo? `sudo systemctl start mongod` (Linux) or `brew services start mongodb-community` (Mac)
   - **SSL/TLS errors?** If using self-signed certs or local MongoDB, set `mongodb.tls_allow_invalid_certs: true` in your `config.yaml`

3. **"Where Are My Reviews?!" Crisis**
   - **Google "Limited View" (Feb 2026):** Google now shows a "limited view" to non-logged users on direct place URLs. Our scraper handles this automatically via search-based navigation — just make sure you're on the latest version!
   - Make sure your URL isn't garbage — copy directly from the address bar in Google Maps
   - Not all sort options work for all businesses. Try `--sort relevance` if all else fails
   - Some locations have zero reviews. Yes, it happens. No, it's not the scraper's fault.

4. **Image Download Apocalypse**
   - Check if Google is throttling you (likely if you've been hammering them)
   - Check file permissions on the `review_images/` directory
   - Some images vanish from Google's CDN faster than your ex. Nothing we can do about that.

5. **S3/R2/MinIO Upload Chaos**
   - Double-check your credentials and bucket permissions
   - For R2/MinIO: make sure `endpoint_url` is set correctly
   - Make sure your bucket exists and is in the specified region
   - Check if your bucket policy allows public-read for uploaded objects

## Cloud Storage Setup (S3 / R2 / MinIO)

Works with any S3-compatible storage. Pick your poison:

### AWS S3

```yaml
use_s3: true
s3:
  provider: "aws"                # Optional — "aws" is the default
  aws_access_key_id: "YOUR_KEY"
  aws_secret_access_key: "YOUR_SECRET"
  region_name: "us-east-1"
  bucket_name: "your-bucket"
  prefix: "google_reviews/"
  delete_local_after_upload: false
```

### Cloudflare R2

```yaml
use_s3: true
s3:
  provider: "r2"                 # Sets region_name: "auto", acl: "" automatically
  aws_access_key_id: "YOUR_R2_ACCESS_KEY"
  aws_secret_access_key: "YOUR_R2_SECRET_KEY"
  bucket_name: "your-r2-bucket"
  endpoint_url: "https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"
  s3_base_url: "https://pub-HASH.r2.dev"  # Public R2 bucket URL
  prefix: "google_reviews/"
```

### MinIO (Self-Hosted)

```yaml
use_s3: true
s3:
  provider: "minio"              # Sets path_style: true, acl: "" automatically
  aws_access_key_id: "minioadmin"
  aws_secret_access_key: "minioadmin"
  bucket_name: "reviews"
  endpoint_url: "http://localhost:9000"
  prefix: "google_reviews/"
```

### Any S3-Compatible Provider

DigitalOcean Spaces, Backblaze B2, Wasabi, etc. — just set `endpoint_url` and credentials. If it speaks S3, we speak to it.

Images are organized per-business: `{prefix}/{place_id}/profiles/` and `{prefix}/{place_id}/reviews/`

### Pro Tips:

- **Cost Optimization**: Enable S3 Intelligent Tiering (AWS) or use R2 for zero egress fees
- **CDN**: Add CloudFront (AWS) or use R2's built-in CDN for faster global delivery
- **Self-Hosted**: MinIO gives you full control — run it on a Raspberry Pi if you're feeling adventurous
- **Security**: Use IAM roles instead of hardcoded keys in production
- **Monitoring**: Enable access logging to track usage

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Quick unit tests only (no external services needed)
python -m pytest tests/ -v -k "not s3 and not mongodb and not seleniumbase"
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## FAQs From The Trenches

**Q: Is scraping Google Maps reviews legal?**
A: Look, I'm not your lawyer. Google doesn't want you to do it. It violates their ToS. It's your business whether that scares you or not. This tool exists for "research purposes" (wink wink). Use at your own risk, hotshot.

**Q: Will this still work tomorrow/next week/when Google changes stuff?**
A: Unlike 99% of the GitHub garbage that breaks when Google changes a CSS class, we're battle-hardened veterans of Google's interface wars. We update this beast CONSTANTLY. Google locked reviews behind a "limited view" in Feb 2026? We bypassed it the same day. This thing adapts faster than Google can change.

**Q: How do I avoid Google's ban hammer?**
A: Our undetected-chromedriver does the heavy lifting, but:
- Don't be stupid greedy — set reasonable delays
- Spread requests across IPs if you're going enterprise-level
- Rotate user agents if you're truly paranoid
- Consider a proxy rotation service (worth every penny)

**Q: Can this handle enterprise-level scraping (10k+ reviews)?**
A: Damn straight. We've pulled 50k+ reviews without breaking a sweat. The SQLite + MongoDB combo isn't just for show — it's made for serious volume. Just make sure your machine has the RAM to handle it.

**Q: I found a bug/have a killer feature idea!**
A: Jump on GitHub and file an issue or PR. But do your homework first — if you're reporting something already in the README, we'll roast you publicly.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of releases and what changed.

## Links

- [Python Documentation](https://docs.python.org/3/)
- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [MongoDB Documentation](https://docs.mongodb.com/)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

---

## SEO Keywords

Google Maps reviews scraper, Google reviews scraper 2026, Google reviews exporter, review analysis tool, business review tool, Python web scraper, scrape Google reviews Python, MongoDB review database, SQLite review database, multilingual review scraper, Google Maps data extraction, business intelligence tool, customer feedback analysis, review data mining, Google business reviews, local SEO analysis, review image downloader, Python Selenium scraper, SeleniumBase undetected chromedriver, automated review collection, Google Maps API alternative, review monitoring tool, scrape Google reviews, Google business ratings, multi-business review scraper, Google reviews to JSON, Google reviews to CSV, Google reviews MongoDB sync, Cloudflare R2 image storage, MinIO image upload, S3 compatible storage reviews, AWS S3 review images, Google Maps review bypass, Google limited view bypass, review change detection, review audit history, headless Chrome scraper, REST API scraper, bulk Google reviews download, Google reviews backup tool, review scraping automation, Google Maps scraper no login