# Google Reviews Scraper Pro - Complete Architecture Documentation

> **Purpose:** This document serves as the definitive reference for AI agents and developers to understand the complete architecture, data flow, and implementation details of the Google Reviews Scraper Pro application without needing to scan multiple files.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Project Structure](#project-structure)
4. [Technology Stack](#technology-stack)
5. [Entry Points & Execution Modes](#entry-points--execution-modes)
6. [Core Components Deep Dive](#core-components-deep-dive)
7. [Data Models & Schemas](#data-models--schemas)
8. [Data Flow & Processing Pipeline](#data-flow--processing-pipeline)
9. [Configuration System](#configuration-system)
10. [Storage Layer](#storage-layer)
11. [Image Processing Pipeline](#image-processing-pipeline)
12. [Cloud Integration (AWS S3)](#cloud-integration-aws-s3)
13. [Job Management & Background Processing](#job-management--background-processing)
14. [REST API Service](#rest-api-service)
15. [Selenium Automation Strategy](#selenium-automation-strategy)
16. [Multi-Language Support](#multi-language-support)
17. [Date & Time Handling](#date--time-handling)
18. [Error Handling & Resilience](#error-handling--resilience)
19. [Performance Optimizations](#performance-optimizations)
20. [Security Considerations](#security-considerations)
21. [Deployment Scenarios](#deployment-scenarios)
22. [Troubleshooting Guide](#troubleshooting-guide)
23. [Extension Points](#extension-points)

---

## Executive Summary

**Google Reviews Scraper Pro** is a production-grade web scraping application designed to extract Google Maps reviews at scale. The system is architected for:

- **Reliability**: Anti-detection mechanisms using undetected-chromedriver
- **Scalability**: Background job processing with concurrent execution
- **Flexibility**: Multiple storage backends (MongoDB, JSON, AWS S3)
- **Maintainability**: Modular design with clear separation of concerns
- **Multi-language**: Supports 50+ languages with automatic detection

### Key Features

1. **Dual Execution Modes**: CLI for one-off scraping, REST API for service-oriented deployments
2. **Intelligent Scraping**: Multi-strategy DOM element detection, automatic retry mechanisms
3. **Data Enrichment**: Date parsing, image downloading, URL rewriting, custom metadata injection
4. **Persistent Storage**: MongoDB for structured storage, JSON for backup, S3 for images
5. **Resume Capability**: Tracks seen IDs to avoid duplicates and support incremental scraping

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ENTRY POINTS                             │
├──────────────────────────┬──────────────────────────────────┤
│   start.py (CLI)         │   api_server.py (REST API)       │
│   - Arg parsing          │   - FastAPI endpoints            │
│   - Direct execution     │   - Job queuing                  │
└──────────┬───────────────┴────────────┬─────────────────────┘
           │                            │
           v                            v
┌─────────────────────────────────────────────────────────────┐
│                   SCRAPER CORE                               │
│  modules/scraper.py - GoogleReviewsScraper                   │
│  - Chrome driver setup                                       │
│  - DOM navigation & extraction                               │
│  - Multi-language tab/menu detection                         │
│  - Scroll & pagination logic                                 │
└──────────┬───────────────────────────────────────────────────┘
           │
           v
┌─────────────────────────────────────────────────────────────┐
│                  DATA PROCESSING                             │
├──────────────────────────┬──────────────────────────────────┤
│  models.py               │  date_converter.py               │
│  - RawReview extraction  │  - Relative date parsing         │
│  - DOM parsing           │  - ISO conversion                │
├──────────────────────────┼──────────────────────────────────┤
│  utils.py                │  image_handler.py                │
│  - Language detection    │  - Multi-threaded download       │
│  - Helper functions      │  - URL resolution hacking        │
└──────────────────────────┴──────────────────────────────────┘
           │
           v
┌─────────────────────────────────────────────────────────────┐
│                   STORAGE LAYER                              │
├──────────────────────────┬──────────────────────────────────┤
│  data_storage.py         │  s3_handler.py                   │
│  - MongoDBStorage        │  - Batch upload                  │
│  - JSONStorage           │  - Custom URL generation         │
│  - Merge logic           │  - Lifecycle management          │
└──────────────────────────┴──────────────────────────────────┘
```

---

## Project Structure

```
google-reviews-scraper-pro/
├── start.py                    # CLI entry point
├── api_server.py               # FastAPI REST API server
├── config.yaml                 # Default configuration
├── requirements.txt            # Python dependencies
├── modules/                    # Core application modules
│   ├── __init__.py
│   ├── cli.py                  # CLI argument parser
│   ├── config.py               # Configuration loader
│   ├── scraper.py              # Main Selenium scraping engine
│   ├── models.py               # Data models (RawReview)
│   ├── data_storage.py         # MongoDB/JSON persistence
│   ├── image_handler.py        # Image download/upload logic
│   ├── s3_handler.py           # AWS S3 integration
│   ├── job_manager.py          # Background job orchestration
│   ├── utils.py                # Utility functions
│   └── date_converter.py       # Date parsing utilities
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md         # This file
│   └── TROUBLESHOOTING.md      # Common issues & solutions
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_mongodb_connection.py
│   └── test_s3_connection.py
└── examples/                   # Example configurations
    └── config-example.txt
```

---

## Technology Stack

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `Python` | 3.10+ | Runtime environment |
| `seleniumbase` | 4.34.9+ | Enhanced browser automation with UC Mode |
| `pymongo` | 4.12.0 | MongoDB client |
| `boto3` | 1.35.1 | AWS S3 SDK |
| `fastapi` | 0.104.1 | REST API framework |
| `uvicorn` | 0.24.0 | ASGI server |
| `pydantic` | 2.11.5 | Data validation |
| `pyyaml` | 6.0.1 | Configuration parsing |
| `beautifulsoup4` | 4.12.3 | HTML parsing (secondary) |
| `requests` | 2.32.3 | HTTP client for image downloads |
| `tqdm` | 4.66.3 | Progress bars |

### Optional Dependencies

- `pytest` (7.4.3) - Testing framework
- `googletrans` (4.0.2) - Translation capabilities (future feature)

---

## Entry Points & Execution Modes

### 1. CLI Mode (`start.py`)

**Purpose**: Direct execution for one-off scraping jobs or cron scheduling.

**Execution Flow**:
```python
main()
  ├─ parse_arguments()          # modules/cli.py
  ├─ load_config()              # modules/config.py
  ├─ Override config with CLI args
  ├─ GoogleReviewsScraper(config)
  └─ scraper.scrape()           # Blocking execution
```

**Key Features**:
- Synchronous execution
- Direct console output
- Exit code based on success/failure
- Suitable for cron jobs and CI/CD pipelines

**Example**:
```bash
python start.py \
  --url "https://maps.app.goo.gl/xyz" \
  --headless \
  --sort newest \
  --download-images true \
  --custom-params '{"client":"CompanyA"}'
```

### 2. API Mode (`api_server.py`)

**Purpose**: Service-oriented deployment for web applications and integrations.

**Execution Flow**:
```python
FastAPI lifespan context
  ├─ startup: JobManager(max_concurrent_jobs=3)
  ├─ POST /scrape → create_job() → start_job()
  │   └─ ThreadPoolExecutor → _run_scraping_job()
  ├─ GET /jobs/{id} → get_job() → return status
  └─ shutdown: executor.shutdown()
```

**Key Features**:
- Asynchronous job processing
- Job queue management
- RESTful API with OpenAPI documentation
- Automatic job cleanup (24-hour retention)
- CORS enabled for web integration

**Example**:
```bash
# Start server
python api_server.py

# Submit job via API
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://maps.app.goo.gl/xyz", "headless": true}'

# Check status
curl http://localhost:8000/jobs/{job_id}
```

---

## Core Components Deep Dive

### 1. Scraper Engine (`modules/scraper.py`)

**Class**: `GoogleReviewsScraper`

**Responsibilities**:
1. Chrome driver lifecycle management
2. Google Maps navigation
3. DOM element detection and interaction
4. Review extraction and pagination
5. Data deduplication

**Key Methods**:

#### `setup_driver(headless: bool) -> Chrome`
- **Purpose**: Initialize Chrome WebDriver with anti-detection measures
- **Environment Detection**:
  - Checks `CHROME_BIN` environment variable for Docker/container deployment
  - Clears `undetected_chromedriver` cache to prevent version mismatches
  - Platform-specific cache paths (macOS, Linux, Windows)
- **Options Applied**:
  ```python
  --window-size=1400,900
  --ignore-certificate-errors
  --disable-gpu
  --disable-dev-shm-usage
  --no-sandbox
  --headless=new  # if headless=True
  ```
- **Fallback Strategy**: If `undetected_chromedriver` fails, falls back to standard Selenium WebDriver

#### `click_reviews_tab(driver: Chrome)`
- **Purpose**: Locate and click the "Reviews" tab across any language/layout
- **Strategy Cascade** (6 detection methods):
  1. **Data Attributes**: `data-tab-index="1"`
  2. **ARIA Roles**: `role="tab"` with review keywords in `aria-label`
  3. **Text Content**: Checks `innerText`, `textContent`, `aria-label` against 50+ language keywords
  4. **Nested Elements**: Recursively searches child elements
  5. **URL Detection**: Checks `href`, `data-href` for "review" patterns
  6. **XPath Fallback**: `contains(text(), '<keyword>')` for each language
- **Review Keywords**: English, Hebrew, Thai, Spanish, French, German, Italian, Portuguese, Russian, Japanese, Korean, Chinese, Arabic, Hindi, Turkish, Dutch, Polish, Vietnamese, Indonesian, Swedish, Norwegian, Danish, Finnish, Greek, Czech, Romanian, Hungarian, Bulgarian
- **Click Methods** (5 attempts per element):
  1. JavaScript `click()`
  2. Direct `element.click()`
  3. ActionChains `move_to_element().click()`
  4. Send `Keys.RETURN`
  5. ActionChains center click with offset
- **Verification**: `verify_reviews_tab_clicked()` confirms success by checking for review cards

#### `set_sort(driver: Chrome, method: str)`
- **Purpose**: Change review sort order (newest, highest, lowest, relevance)
- **Sort Button Detection** (10+ selectors):
  ```python
  'button.HQzyZ[aria-haspopup="true"]'
  'button[aria-label*="Sort" i]'
  'button[aria-label*="סידור"]'  # Hebrew
  'button[aria-label*="เรียง"]'  # Thai
  # ... multilingual selectors
  ```
- **Menu Item Selection**:
  - Waits for `div[role="menuitemradio"]` to appear
  - Matches text against `SORT_OPTIONS` dictionary (contains all language variants)
  - Position-based fallback: relevance=0, newest=1, highest=2, lowest=3
- **Click Methods** (5 attempts): Same as `click_reviews_tab`

#### `scrape()`
- **Main Loop**:
  ```python
  while attempts < max_attempts:
      cards = pane.find_elements(By.CSS_SELECTOR, CARD_SEL)
      for card in cards:
          if card.id in seen: continue
          raw = RawReview.from_card(card)
          docs[raw.id] = merge_review(docs.get(raw.id), raw)
          seen.add(raw.id)
      scroll_pane()
      sleep(dynamic_delay)
  ```
- **Deduplication**: Maintains `seen` set (loaded from `google_reviews.ids`)
- **Stop Condition**: `stop_on_match=True` exits when first duplicate is found (efficient incremental scraping)
- **Progress**: `tqdm` progress bar shows real-time count
- **Stale Element Handling**: Catches `StaleElementReferenceException` and re-finds pane

---

### 2. Data Models (`modules/models.py`)

**Class**: `RawReview`

**Purpose**: Immutable data structure representing a single review as extracted from DOM.

**Fields**:
```python
@dataclass
class RawReview:
    id: str                          # data-review-id
    author: str                      # Reviewer name
    rating: float                    # 1.0-5.0
    date: str                        # Original relative date string
    lang: str                        # ISO 639-1 code (auto-detected)
    text: str                        # Review body
    likes: int                       # Thumbs up count
    photos: list[str]                # Image URLs
    profile: str                     # Author profile link
    avatar: str                      # Profile picture URL
    owner_date: str                  # Business owner response date
    owner_text: str                  # Business owner response text
    review_date: str                 # Parsed ISO date
    translations: dict               # Future: Translated versions
```

**Extraction Method**: `from_card(card: WebElement)`

**DOM Selectors Used**:
```python
MORE_BTN = "button.kyuRq"              # "More" expansion button
LIKE_BTN = 'button[jsaction*="toggleThumbsUp"]'
PHOTO_BTN = "button.Tya61d"
OWNER_RESP = "div.CDe7pd"
```

**Extraction Steps**:
1. Click "More" button to expand truncated text
2. Extract `data-review-id` attribute
3. Parse author name from `div[class*="d4r55"]`
4. Extract rating from `span[role="img"][aria-label]` using regex `[\d\.]+`
5. Parse date from `span[class*="rsqaWe"]`
6. Try multiple selectors for text content (handles layout variations)
7. Detect language using `detect_lang()` (checks for Hebrew/Thai characters)
8. Parse likes from button text or aria-label
9. Extract photos from `style="url(...)"` attributes
10. Parse owner response if `div.CDe7pd` exists

---

### 3. Utility Functions (`modules/utils.py`)

#### Language Detection

```python
@lru_cache(maxsize=1024)
def detect_lang(txt: str) -> str:
    if HEB_CHARS.search(txt):  return "he"   # Hebrew: \u0590-\u05FF
    if THAI_CHARS.search(txt): return "th"   # Thai: \u0E00-\u0E7F
    return "en"
```

**Purpose**: Determine review language for multilingual storage.

**Strategy**: Regex pattern matching against Unicode ranges (expandable to more languages).

#### Safe Integer Parsing

```python
@lru_cache(maxsize=128)
def safe_int(s: str | None) -> int:
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else 0
```

**Purpose**: Extract numeric values from strings like "5 likes" or "3 photos".

#### Element Finding

```python
def try_find(el: WebElement, css: str, *, all=False) -> List[WebElement]:
    try:
        if all:
            return el.find_elements(By.CSS_SELECTOR, css)
        obj = el.find_element(By.CSS_SELECTOR, css)
        return [obj] if obj else []
    except (NoSuchElementException, StaleElementReferenceException):
        return []
```

**Purpose**: Non-throwing element finder (prevents exception chaining).

#### Click Helper

```python
def click_if(driver: Chrome, css: str, delay=0.25, timeout=5.0) -> bool:
    # 1. Find all matching elements
    # 2. Check visibility and enabled state
    # 3. Try direct click
    # 4. Fallback to WebDriverWait + EC.element_to_be_clickable
    # 5. Sleep after successful click
```

**Purpose**: Robust click operation with automatic retry and wait.

---

### 4. Date Conversion (`modules/date_converter.py`)

**Challenge**: Google displays dates as "2 weeks ago", "3 months ago" in user's language.

**Solution**: Multi-language regex parsing with fallback to random date.

#### `parse_relative_date(date_str: str, lang: str) -> str`

**Supported Languages**:
- English: "a day ago", "3 weeks ago", "2 years ago"
- Hebrew: "לפני יום", "לפני שבועיים", "לפני 7 שנים"
- Thai: "3 วันที่แล้ว", "2 สัปดาห์ที่แล้ว"

**Algorithm**:
```python
1. Try parsing with provided language
2. If fails, iterate through all supported languages
3. If all fail, generate random date within last 365 days
4. Return ISO 8601 format string
```

**Regex Patterns**:
```python
# English
r'(?P<num>a|an|\d+)\s+(?P<unit>day|week|month|year)s?\s+ago'

# Hebrew
r'(?P<num>\d+|אחד|אחת)?\s*(?P<unit>שנה|שנים|חודש|חודשים|יום|ימים|שבוע|שבועות)'

# Thai
r'(?P<num>\d+)?\s*(?P<unit>วัน|สัปดาห์|เดือน|ปี)ที่แล้ว'
```

**Time Calculations**:
```python
days = num * 1
weeks = num * 7
months = num * 30   # Approximation
years = num * 365   # Approximation
```

#### `DateConverter.convert_dates_in_document(doc: Dict)`

**Purpose**: Convert string dates to Python `datetime` objects before MongoDB storage.

**Fields Converted**:
- `created_date` (when first scraped)
- `last_modified_date` (when last updated)
- `review_date` (when review was posted)

**Special Handling**:
- Removes legacy `date` field if present
- Handles both ISO strings and relative dates
- Preserves timezone information

---

## Data Flow & Processing Pipeline

### Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ 1. INPUT                                                      │
│    ├─ URL (required)                                          │
│    ├─ Config (YAML + CLI overrides)                           │
│    └─ Custom params (optional metadata)                       │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 2. CHROME DRIVER SETUP                                        │
│    ├─ Detect environment (Docker vs local)                    │
│    ├─ Clear cache if needed                                   │
│    ├─ Launch undetected_chromedriver                          │
│    └─ Set page load timeout (30s)                             │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 3. NAVIGATION                                                 │
│    ├─ driver.get(url)                                         │
│    ├─ Wait for "google.com/maps" in URL                       │
│    ├─ Dismiss cookie consent (if present)                     │
│    ├─ Click "Reviews" tab (multi-strategy detection)          │
│    └─ Set sort order (if not "relevance")                     │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 4. EXTRACTION LOOP                                            │
│    ├─ Find review pane (PANE_SEL)                             │
│    ├─ Scroll pane (JavaScript injection)                      │
│    ├─ Extract cards (CARD_SEL)                                │
│    ├─ For each card:                                          │
│    │   ├─ Get data-review-id                                  │
│    │   ├─ Skip if in 'seen' set                               │
│    │   ├─ RawReview.from_card(card)                           │
│    │   ├─ Add to docs dict                                    │
│    │   └─ Add ID to seen set                                  │
│    ├─ Dynamic sleep (0.7s if many cards, else 1.0s)           │
│    └─ Exit conditions:                                        │
│        ├─ idle >= 3 (no new reviews found)                    │
│        ├─ stop_on_match and duplicate found                   │
│        └─ max_attempts reached (10)                           │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 5. DATA ENRICHMENT                                            │
│    ├─ Merge with existing reviews (merge_review)              │
│    ├─ Convert relative dates to ISO format                    │
│    ├─ Detect language for each text field                     │
│    ├─ Add created_date, last_modified_date                    │
│    └─ Inject custom_params into each document                 │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 6. IMAGE PROCESSING (if download_images=True)                 │
│    ├─ Collect all unique image URLs                           │
│    ├─ Parallel download (ThreadPoolExecutor)                  │
│    │   ├─ Modify Google URLs for max resolution               │
│    │   │   (=w1200-h1200-no)                                  │
│    │   ├─ Save to review_images/profiles/ or /reviews/        │
│    │   └─ Generate filename from URL hash                     │
│    ├─ Upload to S3 (if use_s3=True)                           │
│    │   ├─ Set ACL=public-read                                 │
│    │   ├─ ContentType=image/jpeg                              │
│    │   └─ Delete local files (if configured)                  │
│    └─ Replace URLs in documents                               │
│        ├─ user_images → custom URLs or S3 URLs                │
│        ├─ profile_picture → custom URL or S3 URL              │
│        └─ Store originals in original_* fields (optional)     │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 7. STORAGE                                                    │
│    ├─ MongoDB (if use_mongodb=True)                           │
│    │   ├─ Bulk upsert: UpdateOne({review_id}, {$set: doc})    │
│    │   ├─ Create index on review_id                           │
│    │   └─ Log upserted/modified counts                        │
│    └─ JSON Backup (if backup_to_json=True)                    │
│        ├─ Write to google_reviews.json                        │
│        ├─ Write seen IDs to google_reviews.ids                │
│        └─ Convert datetime objects to ISO strings             │
└────────────┬─────────────────────────────────────────────────┘
             │
             v
┌──────────────────────────────────────────────────────────────┐
│ 8. CLEANUP                                                    │
│    ├─ driver.quit()                                           │
│    ├─ MongoDB connection close                                │
│    └─ Return success/failure status                           │
└──────────────────────────────────────────────────────────────┘
```

---

## Configuration System

### Configuration Priority (Highest to Lowest)

1. **CLI Arguments**: `python start.py --headless --sort newest`
2. **Environment Variables**: `LOG_LEVEL=DEBUG`, `CHROME_BIN=/usr/bin/google-chrome`
3. **config.yaml**: Default configuration file
4. **Hardcoded Defaults**: `modules/config.py::DEFAULT_CONFIG`

### Configuration File Schema (`config.yaml`)

```yaml
# Google Maps URL to scrape
url: "https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9"

# Scraper settings
headless: false                # Run Chrome in headless mode
sort_by: "newest"              # Options: newest, highest, lowest, relevance
stop_on_match: false           # Stop when first already-seen review is encountered
overwrite_existing: false      # Whether to overwrite existing reviews or append

# MongoDB settings
use_mongodb: false             # Whether to use MongoDB for storage
mongodb:
  uri: "mongodb://username:password@localhost:27017/"
  database: "reviews"
  collection: "google_reviews"

# JSON backup settings
backup_to_json: true           # Whether to backup data to JSON files
json_path: "google_reviews.json"
seen_ids_path: "google_reviews.ids"

# Data processing settings
convert_dates: true            # Convert string dates to MongoDB Date objects

# Image download settings
download_images: true          # Download images from reviews
image_dir: "review_images"     # Directory to store downloaded images
download_threads: 4            # Number of threads for downloading images
store_local_paths: false       # Whether to store local image paths in documents
max_width: 1200                # Maximum width for downloaded images
max_height: 1200               # Maximum height for downloaded images

# S3 settings (optional)
use_s3: false                  # Whether to upload images to S3
s3:
  aws_access_key_id: ""        # AWS Access Key ID
  aws_secret_access_key: ""    # AWS Secret Access Key
  region_name: "us-east-1"     # AWS region
  bucket_name: ""              # S3 bucket name
  prefix: "reviews/"           # Base prefix for uploaded files
  profiles_folder: "profiles/" # Folder name for profile images
  reviews_folder: "reviews/"   # Folder name for review images
  delete_local_after_upload: false
  s3_base_url: ""              # Custom S3 base URL (optional)

# URL replacement settings
replace_urls: true                                  # Replace URLs with custom ones
custom_url_base: "https://yourdomain.com/images"    # Base URL for replacement
custom_url_profiles: "/profiles/"                   # Path for profile images
custom_url_reviews: "/reviews/"                     # Path for review images
preserve_original_urls: false                       # Preserve originals in original_* fields

# Custom parameters to add to each document
custom_params:
  company: "Thaitours"
  source: "Google Maps"
```

### Configuration Loading (`modules/config.py`)

**Function**: `load_config(config_path: Path) -> Dict[str, Any]`

**Process**:
```python
1. Load DEFAULT_CONFIG
2. Read config.yaml (if exists)
3. Deep merge using deep_update()
4. If file doesn't exist, create it with defaults
5. Return merged config dict
```

**Deep Merge Logic**:
```python
def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
            deep_update(d[k], v)  # Recursive merge
        else:
            d[k] = v              # Overwrite
```

**Logging**:
```python
logging.basicConfig(
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper()),
    format="[%(asctime)s] %(levelname)s: %(message)s"
)
```

---

## Storage Layer

### 1. MongoDB Storage (`data_storage.py::MongoDBStorage`)

**Connection**:
```python
pymongo.MongoClient(
    uri,
    tlsAllowInvalidCertificates=True,  # macOS SSL compatibility
    connectTimeoutMS=30000,
    socketTimeoutMS=None,
    connect=True,
    maxPoolSize=50
)
```

**Operations**:

#### Fetch Existing Reviews
```python
def fetch_existing_reviews() -> Dict[str, Dict[str, Any]]:
    reviews = {}
    for doc in self.collection.find({}, {"_id": 0}):
        review_id = doc.get("review_id")
        if review_id:
            reviews[review_id] = doc
    return reviews
```

#### Save Reviews (Bulk Upsert)
```python
def save_reviews(reviews: Dict[str, Dict[str, Any]]):
    operations = [
        pymongo.UpdateOne(
            {"review_id": review["review_id"]},
            {"$set": review},
            upsert=True
        )
        for review in processed_reviews.values()
    ]
    result = self.collection.bulk_write(operations)
    log.info(f"Upserted {result.upserted_count}, modified {result.modified_count}")
```

**Schema**:
```json
{
  "_id": ObjectId("..."),           // Auto-generated by MongoDB
  "review_id": "ChdDSUhN...",       // Unique Google review ID
  "author": "John Smith",
  "rating": 4.0,
  "description": {                  // Multi-language support
    "en": "Great place!",
    "es": "¡Lugar genial!",
    "he": "מקום נהדר!"
  },
  "likes": 3,
  "user_images": [                  // Array of image URLs (custom or S3)
    "https://cdn.example.com/reviews/xyz.jpg"
  ],
  "author_profile_url": "https://www.google.com/maps/contrib/...",
  "profile_picture": "https://cdn.example.com/profiles/abc.jpg",
  "owner_responses": {              // Business owner replies
    "en": {
      "text": "Thank you for your feedback!"
    }
  },
  "created_date": ISODate("2025-04-22T14:30:45.123Z"),
  "last_modified_date": ISODate("2025-04-22T14:30:45.123Z"),
  "review_date": ISODate("2025-04-15T08:15:22Z"),
  "company": "Thaitours",           // Custom metadata
  "source": "Google Maps",
  "local_images": [                 // Local file paths (optional)
    "review_images/reviews/xyz.jpg"
  ],
  "local_profile_picture": "review_images/profiles/abc.jpg",
  "original_image_urls": [          // Original Google URLs (optional)
    "https://lh3.googleusercontent.com/..."
  ],
  "original_profile_picture": "https://lh3.googleusercontent.com/..."
}
```

**Indexes**:
```python
# Recommended indexes
db.google_reviews.createIndex({"review_id": 1}, {"unique": true})
db.google_reviews.createIndex({"created_date": -1})
db.google_reviews.createIndex({"rating": 1})
db.google_reviews.createIndex({"company": 1})
```

### 2. JSON Storage (`data_storage.py::JSONStorage`)

**Purpose**: Backup and standalone operation without MongoDB.

**Files**:
- `google_reviews.json` - Array of review documents
- `google_reviews.ids` - Newline-separated list of seen review IDs

**Load**:
```python
def load_json_docs() -> Dict[str, Dict[str, Any]]:
    data = json.loads(self.json_path.read_text(encoding="utf-8"))
    return {d.get("review_id", ""): d for d in data if d.get("review_id")}
```

**Save**:
```python
def save_json_docs(docs: Dict[str, Dict[str, Any]]):
    # Convert datetime objects to ISO strings
    for doc in processed_docs.values():
        for key, value in doc.items():
            if isinstance(value, datetime):
                doc[key] = value.isoformat()

    self.json_path.write_text(
        json.dumps(list(processed_docs.values()), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
```

**Seen IDs**:
```python
def load_seen() -> Set[str]:
    return set(self.seen_ids_path.read_text().splitlines())

def save_seen(ids: Set[str]):
    self.seen_ids_path.write_text("\n".join(ids))
```

### 3. Merge Logic (`merge_review()`)

**Purpose**: Combine new scrape data with existing review records.

**Strategy**:
```python
def merge_review(existing: Dict | None, raw: RawReview) -> Dict:
    if not existing:
        # Create new document with all fields
        existing = {
            "review_id": raw.id,
            "author": raw.author,
            "rating": raw.rating,
            "description": {},
            "likes": raw.likes,
            "user_images": list(raw.photos),
            "author_profile_url": raw.profile,
            "profile_picture": raw.avatar,
            "owner_responses": {},
            "created_date": get_current_iso_date(),
            "review_date": parse_relative_date(raw.date, "en")
        }

    # Update text (multi-language support)
    if raw.text:
        existing["description"][raw.lang] = raw.text

    # Update rating if missing
    if not existing.get("rating"):
        existing["rating"] = raw.rating

    # Take max likes
    if raw.likes > existing.get("likes", 0):
        existing["likes"] = raw.likes

    # Union image lists
    existing["user_images"] = list({*existing.get("user_images", []), *raw.photos})

    # Update avatar if new one is larger (better quality)
    if raw.avatar and len(raw.avatar) > len(existing.get("profile_picture", "")):
        existing["profile_picture"] = raw.avatar

    # Add owner response
    if raw.owner_text:
        lang = detect_lang(raw.owner_text)
        existing.setdefault("owner_responses", {})[lang] = {
            "text": raw.owner_text
        }

    # Update timestamp
    existing["last_modified_date"] = get_current_iso_date()

    return existing
```

**Key Features**:
- **Additive**: Never removes data, only adds or updates
- **Multi-language**: Supports translations by storing description/owner_responses as dicts keyed by language code
- **Quality Preservation**: Takes maximum likes, largest avatar URL
- **Deduplication**: Uses set operations for image URL lists

---

## Image Processing Pipeline

### 1. Image Handler (`modules/image_handler.py`)

**Class**: `ImageHandler`

**Initialization**:
```python
def __init__(self, config: Dict[str, Any]):
    self.image_dir = Path(config.get("image_dir", "review_images"))
    self.max_workers = config.get("download_threads", 4)
    self.max_width = config.get("max_width", 1200)
    self.max_height = config.get("max_height", 1200)
    self.replace_urls = config.get("replace_urls", False)
    self.custom_url_base = config.get("custom_url_base", "https://mycustomurl.com")
    self.s3_handler = S3Handler(config)
```

**Directory Structure**:
```
review_images/
├── profiles/           # Profile pictures
│   ├── user_abc123.jpg
│   └── user_def456.jpg
└── reviews/            # Review images
    ├── img_xyz789.jpg
    └── img_qwe012.jpg
```

### 2. Image Download Process

**Method**: `download_image(url_info: Tuple[str, bool]) -> Tuple[str, str, str]`

**Steps**:
```python
1. Extract filename from URL
   - For profiles: Extract unique ID from URL path
   - For reviews: Use Google image ID
   - Append .jpg extension

2. Check if file already exists
   - If yes, skip download but generate custom URL

3. Modify Google URLs for maximum resolution
   - Original: https://lh3.googleusercontent.com/p/AF1QipN...=w100-h100
   - Modified: https://lh3.googleusercontent.com/p/AF1QipN...=w1200-h1200-no
   - Pattern: base_url + f"=w{max_width}-h{max_height}-no"

4. Download with streaming
   response = requests.get(url, stream=True, timeout=10)
   with open(filepath, 'wb') as f:
       for chunk in response.iter_content(chunk_size=8192):
           f.write(chunk)

5. Generate custom URL
   custom_url = f"{custom_url_base}/{path}/{filename}"

6. Return (original_url, filename, custom_url)
```

**URL Modification Logic**:
```python
if 'googleusercontent.com' in url or 'ggpht.com' in url:
    if '=w' in url or '=h' in url or '=s' in url:
        # Remove existing size parameters
        parts = url.split('=')
        base_url = parts[0]
        # Add new parameters
        url = base_url + f"=w{self.max_width}-h{self.max_height}-no"
    else:
        # No existing parameters
        url = url + f"=w{self.max_width}-h{self.max_height}-no"
```

**Concurrency**:
```python
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    results = executor.map(self.download_image, download_tasks)
```

### 3. URL Replacement Strategy

**Modes**:

1. **No Replacement** (`replace_urls=False`):
   - Stores original Google URLs
   - Optionally stores local paths in `local_images` field

2. **Custom URL Replacement** (`replace_urls=True`, `use_s3=False`):
   - Downloads to local directory
   - Replaces URLs with `custom_url_base + custom_url_profiles/reviews + filename`
   - Original URLs preserved in `original_image_urls` if `preserve_original_urls=True`

3. **S3 Replacement** (`replace_urls=True`, `use_s3=True`):
   - Downloads to local directory
   - Uploads to S3
   - Replaces URLs with S3 URLs
   - Deletes local files if `delete_local_after_upload=True`

**Example**:
```python
# Original
user_images: ["https://lh3.googleusercontent.com/p/AF1QipN...=w100-h100"]

# After Custom URL Replacement
user_images: ["https://cdn.mysite.com/reviews/AF1QipN.jpg"]
original_image_urls: ["https://lh3.googleusercontent.com/p/AF1QipN..."]
local_images: ["review_images/reviews/AF1QipN.jpg"]

# After S3 Replacement
user_images: ["https://mybucket.s3.us-east-1.amazonaws.com/reviews/reviews/AF1QipN.jpg"]
# local_images and original_image_urls: depends on config
```

---

## Cloud Integration (AWS S3)

### S3 Handler (`modules/s3_handler.py`)

**Class**: `S3Handler`

**Initialization**:
```python
boto3.client("s3",
    region_name=self.region_name,
    aws_access_key_id=self.aws_access_key_id,       # Optional, uses IAM if omitted
    aws_secret_access_key=self.aws_secret_access_key
)

# Test connection
self.s3_client.head_bucket(Bucket=self.bucket_name)
```

**Upload Method**:
```python
def upload_file(local_path: Path, s3_key: str) -> Optional[str]:
    self.s3_client.upload_file(
        str(local_path),
        self.bucket_name,
        s3_key,
        ExtraArgs={
            'ContentType': 'image/jpeg',
            'ACL': 'public-read'  # Make publicly accessible
        }
    )
    return self.get_s3_url(s3_key)
```

**S3 Key Structure**:
```python
# Profile image
s3_key = f"{prefix}{profiles_folder}/{filename}"
# Example: "reviews/profiles/user_abc123.jpg"

# Review image
s3_key = f"{prefix}{reviews_folder}/{filename}"
# Example: "reviews/reviews/img_xyz789.jpg"
```

**URL Generation**:
```python
def get_s3_url(key: str) -> str:
    if self.s3_base_url:
        # Custom domain (CloudFront)
        return f"{self.s3_base_url.rstrip('/')}/{key}"
    else:
        # Default S3 URL
        return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"
```

**Batch Upload**:
```python
def upload_images_batch(image_files: Dict[str, tuple]) -> Dict[str, str]:
    results = {}
    for filename, (local_path, is_profile) in image_files.items():
        s3_url = self.upload_image(local_path, filename, is_profile)
        if s3_url:
            results[filename] = s3_url
    return results
```

**Error Handling**:
```python
try:
    self.s3_client.upload_file(...)
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code', '')
    if error_code == '404':
        log.error("Bucket not found")
    elif error_code == '403':
        log.error("Access denied")
```

**Lifecycle Management**:
```python
if self.delete_local_after_upload:
    local_path.unlink()
```

---

## Job Management & Background Processing

### Job Manager (`modules/job_manager.py`)

**Class**: `JobManager`

**Purpose**: Orchestrate concurrent scraping jobs for API mode.

**Architecture**:
```python
JobManager
  ├─ jobs: Dict[str, ScrapingJob]      # In-memory job storage
  ├─ executor: ThreadPoolExecutor      # Background workers
  ├─ lock: threading.Lock              # Thread-safe operations
  └─ max_concurrent_jobs: int          # Concurrency limit
```

**Job Lifecycle**:
```
PENDING → RUNNING → COMPLETED
                 ↘→ FAILED
                 ↘→ CANCELLED
```

**Job Data Structure**:
```python
@dataclass
class ScrapingJob:
    job_id: str                          # UUID
    status: JobStatus                    # Enum: pending, running, completed, failed, cancelled
    url: str                             # Google Maps URL
    config: Dict[str, Any]               # Merged configuration
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    reviews_count: Optional[int]
    images_count: Optional[int]
    progress: Dict[str, Any]             # {"stage": "scraping", "message": "..."}
```

**Methods**:

#### Create Job
```python
def create_job(url: str, config_overrides: Dict) -> str:
    job_id = str(uuid.uuid4())
    config = load_config()
    config["url"] = url
    config.update(config_overrides)

    job = ScrapingJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        url=url,
        config=config,
        created_at=datetime.now(),
        progress={"stage": "created", "message": "Job created and queued"}
    )

    with self.lock:
        self.jobs[job_id] = job

    return job_id
```

#### Start Job
```python
def start_job(job_id: str) -> bool:
    with self.lock:
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]
        if job.status != JobStatus.PENDING:
            return False

        # Check concurrency limit
        running_count = sum(1 for j in self.jobs.values() if j.status == JobStatus.RUNNING)
        if running_count >= self.max_concurrent_jobs:
            return False

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()

    # Submit to thread pool
    self.executor.submit(self._run_scraping_job, job_id)
    return True
```

#### Run Scraping Job (Background Thread)
```python
def _run_scraping_job(job_id: str):
    try:
        job = self.jobs[job_id]

        # Update progress
        job.progress = {"stage": "initializing", "message": "Setting up scraper"}

        # Create scraper instance
        scraper = GoogleReviewsScraper(job.config)

        job.progress = {"stage": "scraping", "message": "Scraping reviews in progress"}

        # Run scraping (blocking call)
        scraper.scrape()

        # Mark as completed
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        job.progress = {"stage": "completed", "message": "Scraping completed successfully"}

    except Exception as e:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now()
        job.error_message = str(e)
        job.progress = {"stage": "failed", "message": f"Job failed: {str(e)}"}
```

#### Cleanup Old Jobs
```python
def cleanup_old_jobs(max_age_hours: int = 24):
    cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

    with self.lock:
        to_delete = []
        for job_id, job in self.jobs.items():
            if job.status in [COMPLETED, FAILED, CANCELLED]:
                if job.completed_at and job.completed_at.timestamp() < cutoff_time:
                    to_delete.append(job_id)

        for job_id in to_delete:
            del self.jobs[job_id]
```

**Concurrency Control**:
- Maximum 3 concurrent jobs by default
- PENDING jobs wait in queue
- ThreadPoolExecutor manages thread lifecycle
- Thread-safe operations using `threading.Lock`

**Statistics**:
```python
def get_stats() -> Dict[str, Any]:
    return {
        "total_jobs": len(self.jobs),
        "by_status": {
            "pending": count_pending,
            "running": count_running,
            "completed": count_completed,
            "failed": count_failed,
            "cancelled": count_cancelled
        },
        "running_jobs": count_running,
        "max_concurrent_jobs": self.max_concurrent_jobs
    }
```

---

## REST API Service

### FastAPI Application (`api_server.py`)

**Lifecycle**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global job_manager
    job_manager = JobManager(max_concurrent_jobs=3)
    asyncio.create_task(cleanup_jobs_periodically())

    yield

    # Shutdown
    if job_manager:
        job_manager.shutdown()
```

**Middleware**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**Endpoints**:

#### 1. Health Check
```http
GET /
```
**Response**:
```json
{
  "message": "Google Reviews Scraper API is running",
  "status": "healthy",
  "version": "1.0.0"
}
```

#### 2. Start Scraping Job
```http
POST /scrape
Content-Type: application/json
```
**Request Body**:
```json
{
  "url": "https://maps.app.goo.gl/xyz",
  "headless": true,
  "sort_by": "newest",
  "stop_on_match": false,
  "download_images": true,
  "use_s3": false,
  "custom_params": {
    "client": "CompanyA",
    "region": "EU"
  }
}
```
**Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "message": "Scraping job started successfully"
}
```

#### 3. Get Job Status
```http
GET /jobs/{job_id}
```
**Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "url": "https://maps.app.goo.gl/xyz",
  "created_at": "2025-04-22T14:30:45.123456",
  "started_at": "2025-04-22T14:30:46.789012",
  "completed_at": null,
  "error_message": null,
  "reviews_count": null,
  "images_count": null,
  "progress": {
    "stage": "scraping",
    "message": "Scraping reviews in progress"
  }
}
```

#### 4. List Jobs
```http
GET /jobs?status=running&limit=10
```
**Response**:
```json
[
  {
    "job_id": "...",
    "status": "running",
    ...
  },
  {
    "job_id": "...",
    "status": "pending",
    ...
  }
]
```

#### 5. Cancel Job
```http
POST /jobs/{job_id}/cancel
```
**Response**:
```json
{
  "message": "Job cancelled successfully"
}
```

#### 6. Delete Job
```http
DELETE /jobs/{job_id}
```
**Response**:
```json
{
  "message": "Job deleted successfully"
}
```

#### 7. Get Statistics
```http
GET /stats
```
**Response**:
```json
{
  "total_jobs": 42,
  "by_status": {
    "pending": 2,
    "running": 3,
    "completed": 35,
    "failed": 2,
    "cancelled": 0
  },
  "running_jobs": 3,
  "max_concurrent_jobs": 3
}
```

#### 8. Manual Cleanup
```http
POST /cleanup?max_age_hours=12
```
**Response**:
```json
{
  "message": "Cleaned up jobs older than 12 hours"
}
```

**Automatic Cleanup**:
```python
async def cleanup_jobs_periodically():
    while True:
        await asyncio.sleep(3600)  # Every hour
        if job_manager:
            job_manager.cleanup_old_jobs(max_age_hours=24)
```

**OpenAPI Documentation**:
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

**Running the Server**:
```bash
# Development mode with auto-reload
python api_server.py

# Production mode with Gunicorn
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Selenium Automation Strategy

### Anti-Detection Measures

1. **Undetected ChromeDriver**: Uses patched driver to bypass bot detection
2. **Human-Like Delays**: Random sleep intervals between actions
3. **Gradual Scrolling**: Smooth scroll animations instead of instant jumps
4. **Natural Clicking**: ActionChains for realistic mouse movements
5. **Session Persistence**: Maintains cookies and local storage

### DOM Element Detection Strategy

**Problem**: Google Maps UI changes frequently and varies by language/region.

**Solution**: Multi-strategy cascade with fallbacks.

**Example: Reviews Tab Detection**

```python
def is_reviews_tab(tab: WebElement) -> bool:
    # Strategy 1: Data Attributes
    if tab.get_attribute("data-tab-index") == "1":
        return True

    # Strategy 2: ARIA Attributes
    aria_label = (tab.get_attribute("aria-label") or "").lower()
    if any(word in aria_label for word in REVIEW_WORDS):
        return True

    # Strategy 3: Text Content
    text = tab.text.lower()
    if any(word in text for word in REVIEW_WORDS):
        return True

    # Strategy 4: Nested Elements
    for child in tab.find_elements(By.CSS_SELECTOR, "*"):
        child_text = child.text.lower()
        if any(word in child_text for word in REVIEW_WORDS):
            return True

    # Strategy 5: URL Detection
    href = (tab.get_attribute("href") or "").lower()
    if "review" in href or "rating" in href:
        return True

    # Strategy 6: Class Detection
    tab_class = tab.get_attribute("class") or ""
    if any(cls in tab_class for cls in ["review", "rating", "g4jrve"]):
        return True

    return False
```

**Review Keywords** (50+ languages):
```python
REVIEW_WORDS = {
    # English
    "reviews", "review", "ratings", "rating",

    # Hebrew
    "ביקורות", "ביקורת", "דירוגים", "דירוג",

    # Thai
    "รีวิว", "บทวิจารณ์", "คะแนน", "ความคิดเห็น",

    # Spanish
    "reseñas", "opiniones", "valoraciones", "críticas",

    # French
    "avis", "commentaires", "évaluations", "critiques",

    # German
    "bewertungen", "rezensionen", "beurteilungen", "meinungen",

    # ... (40+ more languages)
}
```

### Click Reliability

**Multiple Click Methods**:
```python
click_methods = [
    # Method 1: JavaScript click (most reliable)
    lambda: driver.execute_script("arguments[0].click();", element),

    # Method 2: Direct click
    lambda: element.click(),

    # Method 3: ActionChains click
    lambda: ActionChains(driver).move_to_element(element).click().perform(),

    # Method 4: Send RETURN key
    lambda: element.send_keys(Keys.RETURN),

    # Method 5: Center click with offset
    lambda: ActionChains(driver).move_to_element_with_offset(
        element, element.size['width'] // 2, element.size['height'] // 2
    ).click().perform()
]

# Try each method until one succeeds
for i, click_method in enumerate(click_methods):
    try:
        click_method()
        if verify_click_worked():
            return True
    except Exception:
        continue
```

### Scrolling Strategy

**Smooth Scrolling**:
```python
# Cache scrollable pane in window object
driver.execute_script("window.scrollablePane = arguments[0];", pane)

# Smooth scroll using JS
scroll_script = "window.scrollablePane.scrollBy(0, window.scrollablePane.scrollHeight);"
driver.execute_script(scroll_script)

# Fallback if pane becomes stale
try:
    driver.execute_script(scroll_script)
except Exception:
    driver.execute_script("window.scrollBy(0, 300);")
```

**Dynamic Sleep**:
```python
# Sleep less when processing many reviews
sleep_time = 0.7 if len(fresh_cards) > 5 else 1.0
time.sleep(sleep_time)
```

### Stale Element Handling

**Problem**: DOM updates while scraping cause `StaleElementReferenceException`.

**Solution**: Re-find elements and retry.

```python
try:
    cards = pane.find_elements(By.CSS_SELECTOR, CARD_SEL)
except StaleElementReferenceException:
    # Re-find pane
    pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PANE_SEL)))
    driver.execute_script("window.scrollablePane = arguments[0];", pane)
    cards = pane.find_elements(By.CSS_SELECTOR, CARD_SEL)
```

### Timeout Strategy

**Page Load**:
```python
driver.set_page_load_timeout(30)  # 30 seconds max
```

**Element Waits**:
```python
wait = WebDriverWait(driver, 20)  # 20 seconds default
wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
```

**Custom Timeouts**:
```python
# Reviews tab detection: 25 seconds
end_time = time.time() + 25
while time.time() < end_time:
    if find_and_click_tab():
        return True
    time.sleep(0.5)
```

---

## Multi-Language Support

### Language Detection

**Method**: Character set analysis using regex patterns.

```python
HEB_CHARS = re.compile(r"[\u0590-\u05FF]")   # Hebrew Unicode range
THAI_CHARS = re.compile(r"[\u0E00-\u0E7F]")  # Thai Unicode range

@lru_cache(maxsize=1024)
def detect_lang(txt: str) -> str:
    if HEB_CHARS.search(txt):  return "he"
    if THAI_CHARS.search(txt): return "th"
    return "en"
```

**Extensibility**:
```python
# Add more language patterns
ARABIC_CHARS = re.compile(r"[\u0600-\u06FF]")
CHINESE_CHARS = re.compile(r"[\u4E00-\u9FFF]")
JAPANESE_CHARS = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
```

### Multi-Language Storage

**Review Text**:
```json
{
  "description": {
    "en": "Great place, loved the service!",
    "th": "สถานที่ที่ยอดเยี่ยม บริการดีมาก!",
    "he": "מקום נהדר, אהבתי את השירות!"
  }
}
```

**Owner Responses**:
```json
{
  "owner_responses": {
    "en": {
      "text": "Thank you for your kind words!"
    },
    "th": {
      "text": "ขอบคุณสำหรับคำพูดที่ดี!"
    }
  }
}
```

### Translation Support (Future Feature)

**Data Model**:
```python
@dataclass
class RawReview:
    # ... existing fields ...
    translations: dict = field(default_factory=dict)
```

**Usage**:
```python
# Store translations
raw.translations = {
    "en": "Great place!",
    "es": "¡Gran lugar!",
    "fr": "Superbe endroit!"
}
```

**API Integration** (planned):
```python
from googletrans import Translator

translator = Translator()
for lang in target_languages:
    translation = translator.translate(review_text, dest=lang)
    translations[lang] = translation.text
```

---

## Date & Time Handling

### Challenge

Google displays dates as relative strings:
- English: "2 weeks ago", "3 months ago"
- Hebrew: "לפני שבועיים", "לפני 3 חודשים"
- Thai: "2 สัปดาห์ที่แล้ว"

**Goal**: Convert to ISO 8601 format for consistent storage and querying.

### Parsing Algorithm

**Function**: `parse_relative_date(date_str: str, lang: str) -> str`

**Steps**:
```python
1. Try parsing with primary language
   - English: r'(?P<num>a|an|\d+)\s+(?P<unit>day|week|month|year)s?\s+ago'
   - Hebrew: r'(?P<num>\d+)?\s*(?P<unit>שנה|שנים|חודש|חודשים|יום|ימים|שבוע|שבועות)'
   - Thai: r'(?P<num>\d+)?\s*(?P<unit>วัน|สัปดาห์|เดือน|ปี)ที่แล้ว'

2. Extract number and unit
   - "a" or "an" → 1
   - Hebrew "אחד" or "אחת" → 1
   - Numeric string → int(match)

3. Calculate time delta
   - days = num * 1
   - weeks = num * 7
   - months = num * 30  (approximation)
   - years = num * 365  (approximation)

4. Subtract from current time
   result = datetime.now() - timedelta(days=calculated_days)

5. Return ISO 8601 format
   return result.isoformat()
```

**Fallback Strategy**:
```python
# If primary language fails
for alt_lang in ["en", "he", "th"]:
    if alt_lang != lang:
        result = try_parse_date(date_str, alt_lang)
        if result != date_str:
            return result

# If all languages fail, generate random date within last year
random_days_ago = random.randint(1, 365)
random_date = datetime.now() - timedelta(days=random_days_ago)
return random_date.isoformat()
```

### Date Conversion for Storage

**MongoDB**: Stores as ISODate objects.

```python
def convert_dates_in_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    date_fields = ["created_date", "last_modified_date", "review_date"]

    for field in date_fields:
        if field in doc and isinstance(doc[field], str):
            try:
                # Parse ISO format
                doc[field] = datetime.fromisoformat(doc[field].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                # Try parsing as relative date
                lang = next(iter(doc.get("description", {}).keys()), "en")
                date_obj = relative_to_datetime(doc[field], lang)
                if date_obj:
                    doc[field] = date_obj

    return doc
```

**JSON**: Stores as ISO strings.

```python
for doc in documents:
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
```

### Timezone Handling

**All dates stored in UTC**:
```python
from datetime import timezone

now = datetime.now(timezone.utc)
doc["created_date"] = now.isoformat()  # 2025-04-22T14:30:45.123456+00:00
```

**Query Examples**:
```python
# MongoDB: Find reviews from last 30 days
cutoff = datetime.now(timezone.utc) - timedelta(days=30)
db.google_reviews.find({"review_date": {"$gte": cutoff}})

# JSON: Filter by date range
cutoff_str = cutoff.isoformat()
filtered = [r for r in reviews if r["review_date"] >= cutoff_str]
```

---

## Error Handling & Resilience

### Chrome Driver Errors

**Version Mismatch**:
```python
# Clear cache before initializing
if os.path.exists(cache_path):
    log.info("Clearing ChromeDriver cache")
    shutil.rmtree(cache_path, ignore_errors=True)

# Let undetected_chromedriver download fresh version
driver = uc.Chrome(options=opts)
```

**Binary Not Found**:
```python
# Check for environment variable
chrome_binary = os.environ.get('CHROME_BIN')
if chrome_binary and os.path.exists(chrome_binary):
    opts.binary_location = chrome_binary
```

**Container Environment**:
```python
in_container = os.environ.get('CHROME_BIN') is not None

if in_container:
    # Use system-installed Chrome
    try:
        driver = uc.Chrome(options=opts)
    except Exception:
        # Fallback to regular Selenium
        from selenium import webdriver
        driver = webdriver.Chrome(options=opts)
```

### Network Errors

**Image Download Failures**:
```python
try:
    response = requests.get(url, stream=True, timeout=10)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    log.error(f"Failed to download image: {e}")
    return url, "", ""  # Return empty filename, continue with next image
```

**MongoDB Connection Failures**:
```python
try:
    self.client = pymongo.MongoClient(uri, connectTimeoutMS=30000)
    self.client.admin.command('ping')
except Exception as e:
    log.error(f"MongoDB connection failed: {e}")
    self.connected = False
    # Scraper continues with JSON-only mode
```

**S3 Upload Failures**:
```python
try:
    self.s3_client.upload_file(local_path, bucket, s3_key)
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code', '')
    if error_code == '404':
        log.error("Bucket not found")
    elif error_code == '403':
        log.error("Access denied")
    return None  # Continue without S3 URL
```

### DOM Errors

**Stale Element Reference**:
```python
try:
    raw = RawReview.from_card(card)
except StaleElementReferenceException:
    continue  # Skip this card, it will reappear on next scroll
except Exception:
    # Store stub with ID only
    raw_id = card.get_attribute("data-review-id") or ""
    raw = RawReview(id=raw_id, text="", lang="und")
```

**Missing Elements**:
```python
def try_find(el: WebElement, css: str, *, all=False):
    try:
        return el.find_elements(By.CSS_SELECTOR, css) if all else [el.find_element(By.CSS_SELECTOR, css)]
    except (NoSuchElementException, StaleElementReferenceException):
        return []  # Return empty list instead of throwing
```

**Timeout Exceptions**:
```python
try:
    pane = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PANE_SEL)))
except TimeoutException:
    log.warning("Could not find reviews pane. Page structure might have changed.")
    return False  # Exit gracefully
```

### Data Validation

**Review ID Validation**:
```python
cid = card.get_attribute("data-review-id")
if not cid:
    continue  # Skip cards without valid ID

if cid in seen:
    if stop_on_match:
        idle = 999  # Trigger exit
    continue
```

**Rating Validation**:
```python
label = first_attr(card, 'span[role="img"]', "aria-label")
num = re.search(r"[\d\.]+", label.replace(",", ".")) if label else None
rating = float(num.group()) if num else 0.0

# Clamp to valid range
rating = max(0.0, min(5.0, rating))
```

### Logging

**Levels**:
```python
log.debug("Detailed information for debugging")
log.info("General informational messages")
log.warning("Warning messages for non-critical issues")
log.error("Error messages for failures")
```

**Examples**:
```python
log.info(f"Starting scraper with settings: headless={headless}, sort_by={sort_by}")
log.debug("Stale element encountered, re-finding elements")
log.warning("Sort button not found - keeping default sort order")
log.error(f"Error during scraping: {e}")
```

**Configuration**:
```bash
# Set log level via environment variable
export LOG_LEVEL=DEBUG
python start.py
```

---

## Performance Optimizations

### 1. Caching

**Language Detection**:
```python
@lru_cache(maxsize=1024)
def detect_lang(txt: str) -> str:
    # Frequently called with same text
    # Cache avoids repeated regex operations
```

**Safe Integer Parsing**:
```python
@lru_cache(maxsize=128)
def safe_int(s: str | None) -> int:
    # Cache numeric conversions
```

### 2. Parallel Image Downloads

**ThreadPoolExecutor**:
```python
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    results = executor.map(self.download_image, download_tasks)
```

**Optimal Worker Count**:
```yaml
download_threads: 4  # Default
# CPU-bound: set to CPU count
# I/O-bound: set to 2-4x CPU count
```

### 3. Batch Operations

**MongoDB Bulk Write**:
```python
operations = [
    pymongo.UpdateOne(
        {"review_id": review["review_id"]},
        {"$set": review},
        upsert=True
    )
    for review in reviews.values()
]
result = self.collection.bulk_write(operations)
```

**Benefit**: Single network round-trip instead of N individual operations.

### 4. Memory Management

**Set-Based Deduplication**:
```python
seen = set()  # O(1) lookup instead of O(n) list search
```

**Streaming Image Downloads**:
```python
response = requests.get(url, stream=True, timeout=10)
with open(filepath, 'wb') as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)  # Don't load entire image into memory
```

### 5. Dynamic Delays

**Adaptive Sleep**:
```python
sleep_time = 0.7 if len(fresh_cards) > 5 else 1.0
time.sleep(sleep_time)
```

**Benefit**: Faster scraping when many reviews are loading quickly, more patient when few reviews appear.

### 6. JavaScript Injection

**Direct Scroll**:
```python
# Faster than ActionChains
driver.execute_script("window.scrollablePane.scrollBy(0, window.scrollablePane.scrollHeight);")
```

**Cache Pane Reference**:
```python
# Store in window object to avoid repeated DOM queries
driver.execute_script("window.scrollablePane = arguments[0];", pane)
```

### 7. Early Exit Conditions

**Stop on Match**:
```python
if stop_on_match and cid in seen:
    idle = 999  # Trigger immediate exit
```

**Idle Detection**:
```python
if idle >= 3:
    break  # No new reviews found for 3 iterations
```

**Max Attempts**:
```python
if attempts >= max_attempts:
    break  # Safety net to prevent infinite loops
```

---

## Security Considerations

### 1. Credential Management

**Never Commit Secrets**:
```yaml
# .gitignore
config.yaml        # Contains MongoDB URI, AWS keys
google_reviews.*   # Contains scraped data
review_images/     # Downloaded images
.env
```

**Environment Variables** (preferred):
```bash
export MONGODB_URI="mongodb://..."
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
```

**Config File** (secured):
```bash
chmod 600 config.yaml  # Owner read/write only
```

### 2. MongoDB Security

**Authentication**:
```yaml
mongodb:
  uri: "mongodb://username:password@host:27017/?authSource=admin"
```

**TLS/SSL**:
```python
pymongo.MongoClient(
    uri,
    tls=True,
    tlsAllowInvalidCertificates=False,  # Production: False
    tlsCAFile="/path/to/ca.pem"
)
```

**IP Whitelisting** (MongoDB Atlas):
- Add application server IPs
- Avoid 0.0.0.0/0 (allow all)

### 3. AWS S3 Security

**IAM Policies**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket",
        "arn:aws:s3:::my-bucket/*"
      ]
    }
  ]
}
```

**Bucket Policies**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-bucket/reviews/*"
    }
  ]
}
```

**Access Control**:
- Use IAM roles instead of hardcoded keys
- Set ACL=public-read only for necessary objects
- Enable versioning and logging

### 4. API Security

**Rate Limiting** (recommended):
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/scrape")
@limiter.limit("5/minute")  # Max 5 requests per minute
async def start_scrape(request: Request, ...):
    ...
```

**Authentication** (recommended for production):
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != os.environ.get("API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    return api_key

@app.post("/scrape")
async def start_scrape(request: ScrapeRequest, api_key: str = Depends(get_api_key)):
    ...
```

**CORS** (production):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)
```

### 5. Input Validation

**URL Validation**:
```python
from pydantic import HttpUrl

class ScrapeRequest(BaseModel):
    url: HttpUrl  # Pydantic validates URL format
```

**Sanitization**:
```python
# Prevent command injection in custom_params
safe_params = {k: str(v)[:100] for k, v in custom_params.items()}
```

### 6. Terms of Service Compliance

**Google Maps Terms**:
- Scraping violates Google's ToS
- Use at your own risk
- Recommended for personal/research use only
- Consider Google's official APIs for production

**Ethical Scraping**:
- Respect robots.txt (Google Maps blocks bots)
- Implement reasonable rate limits
- Don't scrape personal data without consent
- Store data securely

---

## Deployment Scenarios

### 1. Local Development

**Setup**:
```bash
git clone https://github.com/georgekhananaev/google-reviews-scraper-pro.git
cd google-reviews-scraper-pro
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python start.py --url "https://maps.app.goo.gl/xyz"
```

### 2. Docker Deployment

**Dockerfile** (example):
```dockerfile
FROM python:3.13-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

CMD ["python", "start.py"]
```

**Docker Compose**:
```yaml
version: '3.8'
services:
  scraper:
    build: .
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./review_images:/app/review_images
      - ./google_reviews.json:/app/google_reviews.json
    environment:
      - LOG_LEVEL=INFO
      - MONGODB_URI=mongodb://mongo:27017
    depends_on:
      - mongo

  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  api:
    build: .
    command: python api_server.py
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml
    environment:
      - LOG_LEVEL=INFO
    depends_on:
      - mongo

volumes:
  mongo_data:
```

### 3. Cloud VM (AWS EC2, Google Cloud, etc.)

**Setup Script**:
```bash
#!/bin/bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y python3.13 python3-pip git

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y

# Clone repository
git clone https://github.com/georgekhananaev/google-reviews-scraper-pro.git
cd google-reviews-scraper-pro

# Install Python dependencies
pip3 install -r requirements.txt

# Configure
cp examples/config-example.txt config.yaml
nano config.yaml  # Edit configuration

# Run as service
python3 start.py --headless
```

**Systemd Service** (`/etc/systemd/system/scraper.service`):
```ini
[Unit]
Description=Google Reviews Scraper API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/google-reviews-scraper-pro
ExecStart=/usr/bin/python3 api_server.py
Restart=on-failure
Environment="LOG_LEVEL=INFO"

[Install]
WantedBy=multi-user.target
```

**Enable Service**:
```bash
sudo systemctl enable scraper
sudo systemctl start scraper
sudo systemctl status scraper
```

### 4. Cron Job Scheduling

**Crontab**:
```cron
# Scrape daily at 2 AM
0 2 * * * cd /path/to/scraper && /usr/bin/python3 start.py --headless --sort newest >> /var/log/scraper.log 2>&1

# Scrape every 6 hours
0 */6 * * * cd /path/to/scraper && /usr/bin/python3 start.py --headless --stop-on-match >> /var/log/scraper.log 2>&1
```

### 5. Kubernetes Deployment

**Deployment YAML**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scraper-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: scraper-api
  template:
    metadata:
      labels:
        app: scraper-api
    spec:
      containers:
      - name: api
        image: myregistry/scraper-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: LOG_LEVEL
          value: "INFO"
        - name: MONGODB_URI
          valueFrom:
            secretKeyRef:
              name: scraper-secrets
              key: mongodb-uri
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
          requests:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: scraper-api-service
spec:
  selector:
    app: scraper-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Troubleshooting Guide

### Common Issues

#### 1. Chrome/ChromeDriver Version Mismatch

**Symptoms**:
```
SessionNotCreatedException: This version of ChromeDriver only supports Chrome version 143
Current browser version is 142.0.7444.176
```

**Solution**:
```bash
# Clear cache
rm -rf ~/Library/Application\ Support/undetected_chromedriver  # macOS
rm -rf ~/.local/share/undetected_chromedriver                   # Linux

# Update Chrome
# macOS: Chrome → Help → About Google Chrome
# Linux: sudo apt-get update && sudo apt-get upgrade google-chrome-stable

# Run scraper (will download matching driver)
python start.py
```

#### 2. Reviews Tab Not Found

**Symptoms**:
```
TimeoutException: Reviews tab not found or could not be clicked
```

**Solutions**:
```bash
# Try non-headless mode to see what's happening
python start.py --headless false

# Try different sort order
python start.py --sort relevance

# Check URL is valid Google Maps place URL
# Should contain /maps/place/ or maps.app.goo.gl/
```

#### 3. MongoDB Connection Failed

**Symptoms**:
```
ServerSelectionTimeoutError: connection timed out
```

**Solutions**:
```bash
# Check MongoDB is running
mongosh --eval "db.adminCommand('ping')"

# Check connection URI
python -c "from pymongo import MongoClient; c = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=5000); print(c.server_info())"

# For MongoDB Atlas: whitelist IP address
```

#### 4. S3 Upload Failures

**Symptoms**:
```
ClientError: An error occurred (AccessDenied) when calling the PutObject operation
```

**Solutions**:
```bash
# Check credentials
aws s3 ls s3://your-bucket --profile default

# Verify IAM permissions
aws iam get-user-policy --user-name scraper-user --policy-name s3-upload

# Test upload manually
aws s3 cp test.jpg s3://your-bucket/test.jpg --acl public-read
```

#### 5. Images Not Downloading

**Symptoms**:
- Empty `review_images/` directory
- Missing `user_images` in output

**Solutions**:
```yaml
# Verify config
download_images: true  # Must be true
download_threads: 4    # Increase if network is fast

# Check network connectivity
ping lh3.googleusercontent.com

# Check disk space
df -h
```

### Debugging Tips

**Enable Debug Logging**:
```bash
export LOG_LEVEL=DEBUG
python start.py
```

**Run Non-Headless**:
```bash
python start.py --headless false
# Watch browser actions in real-time
```

**Test Components Independently**:
```python
# Test MongoDB connection
from modules.config import load_config
from modules.data_storage import MongoDBStorage

config = load_config()
storage = MongoDBStorage(config)
if storage.connect():
    print("MongoDB connection successful")

# Test S3 connection
from modules.s3_handler import S3Handler

s3 = S3Handler(config)
if s3.enabled:
    print("S3 connection successful")
```

**Check Logs**:
```bash
# CLI mode
python start.py 2>&1 | tee scraper.log

# API mode
uvicorn api_server:app --log-level debug
```

---

## Extension Points

### Adding New Languages

**1. Add Unicode Range**:
```python
# modules/utils.py
ARABIC_CHARS = re.compile(r"[\u0600-\u06FF]")

@lru_cache(maxsize=1024)
def detect_lang(txt: str) -> str:
    if HEB_CHARS.search(txt):    return "he"
    if THAI_CHARS.search(txt):   return "th"
    if ARABIC_CHARS.search(txt): return "ar"  # New
    return "en"
```

**2. Add Date Patterns**:
```python
# modules/date_converter.py
elif lang.lower() == "ar":
    # Arabic: "منذ 3 أيام"
    pattern = re.compile(r'منذ\s+(?P<num>\d+)\s+(?P<unit>يوم|أسبوع|شهر|سنة)')
    # ... parsing logic
```

**3. Add Sort Labels**:
```python
# modules/scraper.py
SORT_OPTIONS = {
    "newest": (
        "Newest", "החדשות ביותר", "ใหม่ที่สุด",
        "الأحدث"  # Arabic
    ),
    # ... other options
}
```

### Adding New Storage Backends

**Example: PostgreSQL**:
```python
# modules/data_storage.py
class PostgreSQLStorage:
    def __init__(self, config: Dict[str, Any]):
        import psycopg2
        self.conn = psycopg2.connect(config["postgresql"]["uri"])

    def save_reviews(self, reviews: Dict[str, Dict[str, Any]]):
        with self.conn.cursor() as cur:
            for review in reviews.values():
                cur.execute(
                    "INSERT INTO reviews (review_id, data) VALUES (%s, %s) "
                    "ON CONFLICT (review_id) DO UPDATE SET data = EXCLUDED.data",
                    (review["review_id"], json.dumps(review))
                )
        self.conn.commit()
```

**Usage**:
```python
# modules/scraper.py
if config.get("use_postgresql"):
    self.postgres = PostgreSQLStorage(config)
```

### Adding Translation Integration

**Example: Google Translate API**:
```python
# modules/translator.py
from googletrans import Translator

class ReviewTranslator:
    def __init__(self, target_languages: List[str]):
        self.translator = Translator()
        self.target_languages = target_languages

    def translate_review(self, review: Dict[str, Any]) -> Dict[str, Any]:
        # Get original text
        original_lang = list(review["description"].keys())[0]
        original_text = review["description"][original_lang]

        # Translate to all target languages
        for lang in self.target_languages:
            if lang != original_lang:
                translation = self.translator.translate(original_text, dest=lang)
                review["description"][lang] = translation.text

        return review
```

**Usage**:
```python
# In scraper.py
if config.get("translate_reviews"):
    translator = ReviewTranslator(config["target_languages"])
    for review_id, review in docs.items():
        docs[review_id] = translator.translate_review(review)
```

### Adding Custom Metrics

**Example: Sentiment Analysis**:
```python
# modules/sentiment.py
from textblob import TextBlob

def analyze_sentiment(text: str) -> Dict[str, float]:
    blob = TextBlob(text)
    return {
        "polarity": blob.sentiment.polarity,     # -1 to 1
        "subjectivity": blob.sentiment.subjectivity  # 0 to 1
    }
```

**Integration**:
```python
# In merge_review()
if raw.text:
    existing["description"][raw.lang] = raw.text
    existing["sentiment"] = {
        raw.lang: analyze_sentiment(raw.text)
    }
```

### Adding Webhook Notifications

**Example**:
```python
# modules/notifications.py
import requests

def send_webhook(webhook_url: str, data: Dict[str, Any]):
    response = requests.post(webhook_url, json=data)
    response.raise_for_status()

# In scraper.py (after scraping completes)
if config.get("webhook_url"):
    send_webhook(config["webhook_url"], {
        "event": "scraping_completed",
        "reviews_count": len(docs),
        "timestamp": datetime.now().isoformat()
    })
```

---

## Summary

This document provides a complete reference for understanding and working with the Google Reviews Scraper Pro application. Key takeaways:

1. **Modular Design**: Separation of concerns (scraping, storage, image handling, job management)
2. **Resilient Scraping**: Multi-strategy element detection, automatic retries, stale element handling
3. **Flexible Storage**: MongoDB, JSON, and S3 with configurable options
4. **Dual Execution Modes**: CLI for direct execution, REST API for service deployment
5. **Multi-Language Support**: Automatic language detection, multilingual storage schema
6. **Production-Ready**: Error handling, logging, security considerations, deployment guides

**For AI Agents**: This architecture document should serve as the primary reference for understanding the application without needing to read individual source files. All critical implementation details, data flows, and architectural decisions are documented here.

**For Developers**: Use this as a roadmap for extending the application, troubleshooting issues, and understanding design patterns used throughout the codebase.
