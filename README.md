# 🔥 Google Reviews Scraper Pro (2025) 🔥

![Google Reviews Scraper Pro](https://img.shields.io/badge/Version-1.0.0-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Last Update](https://img.shields.io/badge/Last%20Updated-April%202025-red)

**FINALLY! A scraper that ACTUALLY WORKS in 2025!** While others break with every Google update, this bad boy keeps on trucking. Say goodbye to the frustration of constantly broken scrapers and hello to a beast that rips through Google's defenses like a hot knife through butter. This battle-tested, rock-solid solution will extract every juicy detail from Google reviews while laughing in the face of rate limiting.

## 🌟 Feature Artillery

- **Bulletproof in 2025**: While the competition falls apart, we've cracked Google's latest tricks
- **Ninja-Mode Selenium**: Our undetected-chromedriver flies under the radar where others get insta-blocked
- **Polyglot Powerhouse**: Devours reviews in a smorgasbord of languages - English, Hebrew, Thai, German, you name it!
- **MongoDB Mastery**: Dumps pristine data structures straight into your MongoDB instance
- **Paranoid Backups**: Mirrors everything to local JSON files because losing data sucks
- **Aggressive Image Capture**:
  - Snags EVERY damn photo from reviews and profiles
  - Hoards local paths or swaps URLs to your domain like a boss
  - Multi-threaded downloading that would make NASA jealous
- **Time-Bending Magic**: Transforms Google's vague "2 weeks ago" garbage into precise ISO timestamps
- **Sort Any Damn Way**: Newest, highest, lowest, relevance - we've got you covered
- **Metadata on Steroids**: Inject custom parameters into every review record
- **Pick Up Where You Left Off**: Resume scraping after crashes, because life happens
- **Ghost Mode**: Run silently in headless mode, no browser window in sight
- **Battle-Hardened Resilience**: Network hiccups? Google's tricks? HAH! We eat those for breakfast
- **Obsessive Logging**: Every action documented in glorious detail for when things get weird

## 📋 Battle Station Requirements

```
Python 3.10+ (don't even try with 3.9, seriously)
Chrome browser (the fresher the better)
MongoDB (optional, but c'mon, live a little)
Coffee (mandatory for watching thousands of reviews roll in)
```

## 🚀 Deployment Instructions

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
python start.py --help
# If this spits out options, you're golden. If not, check your Python path!
```

## ⚙️ Fine-Tuning Your Beast

Look, this isn't some one-size-fits-all garbage. You've got two ways to bend this tool to your will: the almighty `config.yaml` file or straight-up command-line arguments. When they clash, command-line is king (obviously).

### Example `config.yaml`:

```yaml
# Google Maps Reviews Scraper Configuration

# URL to scrape
url: "https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9"

# Scraper settings
headless: true                # Run Chrome in headless mode
sort_by: "newest"             # Options: "newest", "highest", "lowest", "relevance"
stop_on_match: false          # Stop when first already-seen review is encountered
overwrite_existing: false     # Whether to overwrite existing reviews or append

# MongoDB settings
use_mongodb: true             # Whether to use MongoDB for storage
mongodb:
  uri: "mongodb://username:password@localhost:27017/"
  database: "reviews"
  collection: "google_reviews"

# JSON backup settings
backup_to_json: true          # Whether to backup data to JSON files
json_path: "google_reviews.json"
seen_ids_path: "google_reviews.ids"

# Data processing settings
convert_dates: true           # Convert string dates to MongoDB Date objects

# Image download settings
download_images: true         # Download images from reviews
image_dir: "review_images"    # Directory to store downloaded images
download_threads: 4           # Number of threads for downloading images
store_local_paths: true       # Whether to store local image paths in documents

# URL replacement settings
replace_urls: true           # Whether to replace original URLs with custom ones
custom_url_base: "https://yourdomain.com/images"  # Base URL for replacement
custom_url_profiles: "/profiles/"  # Path for profile images
custom_url_reviews: "/reviews/"    # Path for review images
preserve_original_urls: true  # Whether to preserve original URLs in original_* fields

# Custom parameters to add to each document
# These will be added statically to all documents
custom_params:
  company: "Your Business Name"
  source: "Google Maps"
  location: "Bangkok, Thailand"
```

## 🖥️ Unleashing Hell

### No-Frills, Get-It-Done Usage

```bash
python start.py --url "https://maps.app.goo.gl/YOUR_URL"
# Boom. That's it. Now go grab a coffee while the magic happens.
```

### Battle-Tested Recipes

1. Stealth Mode + Fresh Stuff First:
```bash
python start.py --url "https://maps.app.goo.gl/YOUR_URL" --headless --sort newest
# Perfect for a cron job. They'll never see you coming.
```

2. Incremental Grab (why waste CPU cycles?):
```bash
python start.py --url "https://maps.app.goo.gl/YOUR_URL" --stop-on-match
# Once it hits a review it's seen before, it taps out. Efficiency, baby!
```

3. JSON-Only Diet (MongoDB haters unite):
```bash
python start.py --url "https://maps.app.goo.gl/YOUR_URL" --use-mongodb false
# For the "I just want a damn file" crowd.
```

4. Custom Tags Galore:
```bash
python start.py --url "https://maps.app.goo.gl/YOUR_URL" --custom-params '{"company":"Hotel California","location":"Los Angeles"}'
# Brand these puppies however you want. Go nuts.
```

5. Image Hoarding Deluxe:
```bash
python start.py --url "https://maps.app.goo.gl/YOUR_URL" --download-images true --replace-urls true --custom-url-base "https://yourdomain.com/images"
# Every. Single. Picture. With your domain stamped all over 'em.
```

### Command Line Arguments

```
usage: start.py [-h] [-q] [-s {newest,highest,lowest,relevance}] [--stop-on-match] [--url URL] [--overwrite] [--config CONFIG] [--use-mongodb USE_MONGODB]
                [--convert-dates CONVERT_DATES] [--download-images DOWNLOAD_IMAGES] [--image-dir IMAGE_DIR] [--download-threads DOWNLOAD_THREADS]
                [--store-local-paths STORE_LOCAL_PATHS] [--replace-urls REPLACE_URLS] [--custom-url-base CUSTOM_URL_BASE]
                [--custom-url-profiles CUSTOM_URL_PROFILES] [--custom-url-reviews CUSTOM_URL_REVIEWS] [--preserve-original-urls PRESERVE_ORIGINAL_URLS]
                [--custom-params CUSTOM_PARAMS]

Google‑Maps review scraper with MongoDB integration

options:
  -h, --help            show this help message and exit
  -q, --headless        run Chrome in the background
  -s {newest,highest,lowest,relevance}, --sort {newest,highest,lowest,relevance}
                        sorting order for reviews
  --stop-on-match       stop scrolling when first already‑seen id is met (useful with --sort newest)
  --url URL             custom Google Maps URL to scrape
  --overwrite           overwrite existing reviews instead of appending
  --config CONFIG       path to custom configuration file
  --use-mongodb USE_MONGODB
                        whether to use MongoDB for storage
  --convert-dates CONVERT_DATES
                        convert string dates to MongoDB Date objects
  --download-images DOWNLOAD_IMAGES
                        download images from reviews
  --image-dir IMAGE_DIR
                        directory to store downloaded images
  --download-threads DOWNLOAD_THREADS
                        number of threads for downloading images
  --store-local-paths STORE_LOCAL_PATHS
                        whether to store local image paths in documents
  --replace-urls REPLACE_URLS
                        whether to replace original URLs with custom ones
  --custom-url-base CUSTOM_URL_BASE
                        base URL for replacement
  --custom-url-profiles CUSTOM_URL_PROFILES
                        path for profile images
  --custom-url-reviews CUSTOM_URL_REVIEWS
                        path for review images
  --preserve-original-urls PRESERVE_ORIGINAL_URLS
                        whether to preserve original URLs in original_* fields
  --custom-params CUSTOM_PARAMS
                        JSON string with custom parameters to add to each document (e.g. '{"company":"Your Business"}'
```

## 📊 The Juicy Data Payload

Here's what you'll rip out of Google's clutches for each review (and yes, it's *way* more than their official API gives you):

```json
{
  "review_id": "ChdDSUhNMG9nS0VJQ0FnSUNVck95dDlBRRAB",
  "author": "John Smith",
  "rating": 4.0,
  "description": {
    "en": "Great place, loved the service. Will definitely come back!",
    "th": "สถานที่ที่ยอดเยี่ยม บริการดีมาก จะกลับมาอีกแน่นอน!"
    // Multilingual gold mine - ALL languages preserved!
  },
  "likes": 3, // Yes, we even grab those useless "likes" numbers
  "user_images": [
    "https://lh5.googleusercontent.com/p/AF1QipOj-3H8...",
    "https://lh5.googleusercontent.com/p/AF1QipM2xG8..."
    // ALL review images - not just the first one like inferior scrapers
  ],
  "author_profile_url": "https://www.google.com/maps/contrib/112419862785748982094",
  "profile_picture": "https://lh3.googleusercontent.com/a-/ALV-UjXtxT...", // Stalk much?
  "owner_responses": {
    "en": {
      "text": "Thank you for your kind words! We look forward to seeing you again."
      // Yes, even those canned replies from the business owner
    }
  },
  "created_date": "2025-04-22T14:30:45.123456+00:00", // When we first grabbed it
  "last_modified_date": "2025-04-22T14:30:45.123456+00:00", // Last update
  "review_date": "2025-04-15T08:15:22+00:00", // When they posted
  "company": "Your Business Name", // Your custom metadata
  "source": "Google Maps",
  "location": "Bangkok, Thailand" 
  // Add whatever other fields you want - this baby is extensible
}
```

## 📁 Output Files

When running with default settings, the scraper creates:

1. `google_reviews.json` - Contains all extracted reviews
2. `google_reviews.ids` - A list of already processed review IDs
3. `review_images/` - Directory containing downloaded images:
   - `review_images/profiles/` - Profile pictures
   - `review_images/reviews/` - Review images

## 🔄 Integration Examples

### Import to MongoDB Compass

The JSON output is fully compatible with MongoDB Compass import:

1. Open MongoDB Compass
2. Navigate to your database and collection
3. Click "Add Data" → "Import File"
4. Select your `google_reviews.json` file
5. Select JSON format and import

### Process Reviews with Python

```python
import json

# Load reviews
with open('google_reviews.json', 'r', encoding='utf-8') as f:
    reviews = json.load(f)

# Calculate average rating
total_rating = sum(review['rating'] for review in reviews)
avg_rating = total_rating / len(reviews)
print(f"Average rating: {avg_rating:.2f}")

# Filter reviews by language
english_reviews = [r for r in reviews if 'en' in r['description']]
print(f"English reviews: {len(english_reviews)}")

# Find reviews with images
reviews_with_images = [r for r in reviews if r['user_images']]
print(f"Reviews with images: {len(reviews_with_images)}")
```

## 🛠️ When Shit Hits The Fan

### DEFCON Scenarios & Quick Fixes

1. **Chrome/Driver Having a Lovers' Quarrel**
   - Update your damn Chrome browser already! It's 2025, people
   - Nuke and reinstall the driver: `pip uninstall undetected-chromedriver` then `pip install undetected-chromedriver==3.5.4`
   - If you're on Ubuntu, sometimes a simple `apt update && apt upgrade` fixes weird Chrome issues

2. **MongoDB Throwing a Tantrum**
   - Double-check your connection string - typos are the #1 culprit
   - Is your IP whitelisted? MongoDB Atlas loves to block new IPs
   - Run `nc -zv your-mongodb-host 27017` to check if the port's even reachable
   - Did you forget to start Mongo? `sudo systemctl start mongod` (Linux) or `brew services start mongodb-community` (Mac)

3. **"Where Are My Reviews?!" Crisis**
   - Make sure your URL isn't garbage - copy directly from the address bar in Google Maps
   - Not all sort options work for all businesses. Try `--sort relevance` if all else fails
   - Some locations have zero reviews. Yes, it happens. No, it's not the scraper's fault.

4. **Image Download Apocalypse**
   - Check if Google is throttling you (likely if you've been hammering them)
   - Run with `sudo` if you're getting permission errors (not ideal but gets the job done)
   - Some images vanish from Google's CDN faster than your ex. Nothing we can do about that.

### Operation Logs (AKA "What The Hell Is It Doing?")

We don't just log, we OBSESSIVELY document the scraper's every breath:

```
[2025-04-22 14:30:45] Starting scraper with settings: headless=True, sort_by=newest
[2025-04-22 14:30:45] URL: https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9
[2025-04-22 14:30:47] Platform: Linux-5.15.0-58-generic-x86_64-with-glibc2.35
[2025-04-22 14:30:47] Python version: 3.13.1
[2025-04-22 14:30:47] Using standard undetected_chromedriver setup
[2025-04-22 14:30:52] Chrome driver setup completed successfully
[2025-04-22 14:30:55] Found reviews tab, attempting to click
[2025-04-22 14:30:57] Successfully clicked reviews tab using method 1 and selector '[data-tab-index="1"]'
[2025-04-22 14:30:58] Attempting to set sort order to 'newest'
[2025-04-22 14:30:59] Found sort button with selector: 'button[aria-label*="Sort" i]'
[2025-04-22 14:30:59] Sort menu opened with click method 1
[2025-04-22 14:31:00] Found 4 visible menu items
[2025-04-22 14:31:00] Found matching menu item: 'Newest' for 'Newest'
[2025-04-22 14:31:01] Successfully clicked menu item with method 1
[2025-04-22 14:31:01] Successfully set sort order to 'newest'
```

If you can't figure out what's happening from these logs, you probably shouldn't be using command-line tools at all. We tell you EVERYTHING.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ❓ FAQs From The Trenches

**Q: Is scraping Google Maps reviews legal?**  
A: Look, I'm not your lawyer. Google doesn't want you to do it. It violates their ToS. It's your business whether that scares you or not. This tool exists for "research purposes" (wink wink). Use at your own risk, hotshot.

**Q: Will this still work tomorrow/next week/when Google changes stuff?**  
A: Unlike 99% of the GitHub garbage that breaks when Google changes a CSS class, we're battle-hardened veterans of Google's interface wars. We update this beast CONSTANTLY. April 2025? Rock solid. May 2025? Probably still golden. 2026? Check back for updates.

**Q: How do I avoid Google's ban hammer?**  
A: Our undetected-chromedriver does the heavy lifting, but:
- Don't be stupid greedy – set reasonable delays
- Spread requests across IPs if you're going enterprise-level
- Rotate user agents if you're truly paranoid
- Consider a proxy rotation service (worth every penny)

**Q: Can this handle enterprise-level scraping (10k+ reviews)?**  
A: Damn straight. We've pulled 50k+ reviews without breaking a sweat. The MongoDB integration isn't just for show – it's made for serious volume. Just make sure your machine has the RAM to handle it.

**Q: I found a bug/have a killer feature idea!**  
A: Jump on GitHub and file an issue or PR. But do your homework first – if you're reporting something already in the README, we'll roast you publicly.

## 🌐 Links

- [Python Documentation](https://docs.python.org/3/)
- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [MongoDB Documentation](https://docs.mongodb.com/)

---

## 🔎 SEO Keywords

Google Maps reviews scraper, Google reviews exporter, review analysis tool, business review tool, Python web scraper, MongoDB review database, multilingual review scraper, Google Maps data extraction, business intelligence tool, customer feedback analysis, review data mining, Google business reviews, local SEO analysis, review image downloader, Python Selenium scraper, automated review collection, Google Maps API alternative, review monitoring tool, scrape Google reviews, Google business ratings