"""
Data storage modules for Google Maps Reviews Scraper.
"""

import json
import logging
import ssl
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

import pymongo

from modules.date_converter import parse_relative_date, DateConverter
from modules.image_handler import ImageHandler
from modules.models import RawReview
from modules.utils import detect_lang, get_current_iso_date

# Configure SSL for MongoDB connection
ssl._create_default_https_context = ssl._create_unverified_context  # macOS SSL fix

# Logger
log = logging.getLogger("scraper")

RAW_LANG = "en"


class MongoDBStorage:
    """MongoDB storage handler for Google Maps reviews"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize MongoDB storage with configuration"""
        mongodb_config = config.get("mongodb", {})
        self.uri = mongodb_config.get("uri")
        self.db_name = mongodb_config.get("database")
        self.collection_name = mongodb_config.get("collection")
        self.client = None
        self.collection = None
        self.connected = False
        self.convert_dates = config.get("convert_dates", True)
        self.download_images = config.get("download_images", False)
        self.store_local_paths = config.get("store_local_paths", True)
        self.replace_urls = config.get("replace_urls", False)
        self.preserve_original_urls = config.get("preserve_original_urls", True)
        self.custom_params = config.get("custom_params", {})
        self.image_handler = ImageHandler(config) if self.download_images else None

    def connect(self) -> bool:
        """Connect to MongoDB"""
        try:
            # Use the correct TLS parameters for newer PyMongo versions
            self.client = pymongo.MongoClient(
                self.uri,
                tlsAllowInvalidCertificates=True,  # Equivalent to ssl_cert_reqs=CERT_NONE
                connectTimeoutMS=30000,
                socketTimeoutMS=None,
                connect=True,
                maxPoolSize=50
            )
            # Test connection
            self.client.admin.command('ping')
            db = self.client[self.db_name]
            self.collection = db[self.collection_name]
            self.connected = True
            log.info(f"Connected to MongoDB: {self.db_name}.{self.collection_name}")
            return True
        except Exception as e:
            log.error(f"Failed to connect to MongoDB: {e}")
            self.connected = False
            return False

    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.connected = False

    def fetch_existing_reviews(self) -> Dict[str, Dict[str, Any]]:
        """Fetch existing reviews from MongoDB"""
        if not self.connected and not self.connect():
            log.warning("Cannot fetch existing reviews - MongoDB connection failed")
            return {}

        try:
            reviews = {}
            for doc in self.collection.find({}, {"_id": 0}):
                review_id = doc.get("review_id")
                if review_id:
                    reviews[review_id] = doc
            log.info(f"Fetched {len(reviews)} existing reviews from MongoDB")
            return reviews
        except Exception as e:
            log.error(f"Error fetching reviews from MongoDB: {e}")
            return {}

    def save_reviews(self, reviews: Dict[str, Dict[str, Any]]):
        """Save reviews to MongoDB using bulk operations"""
        if not reviews:
            log.info("No reviews to save to MongoDB")
            return

        if not self.connected and not self.connect():
            log.warning("Cannot save reviews - MongoDB connection failed")
            return

        try:
            # Process reviews before saving
            processed_reviews = reviews.copy()

            # Convert string dates to datetime objects if enabled
            if self.convert_dates:
                processed_reviews = DateConverter.convert_dates_in_reviews(processed_reviews)

            # Download and process images if enabled
            if self.download_images and self.image_handler:
                processed_reviews = self.image_handler.download_all_images(processed_reviews)

                # If not storing local paths, remove them from the documents
                if not self.store_local_paths:
                    for review in processed_reviews.values():
                        if "local_images" in review:
                            del review["local_images"]
                        if "local_profile_picture" in review:
                            del review["local_profile_picture"]

                # If not preserving original URLs, remove them from the documents
                if self.replace_urls and not self.preserve_original_urls:
                    for review in processed_reviews.values():
                        if "original_image_urls" in review:
                            del review["original_image_urls"]
                        if "original_profile_picture" in review:
                            del review["original_profile_picture"]

            # Add custom parameters to each document
            if self.custom_params:
                log.info(f"Adding custom parameters to {len(processed_reviews)} documents")
                for review in processed_reviews.values():
                    for key, value in self.custom_params.items():
                        review[key] = value

            operations = []
            for review in processed_reviews.values():
                # Convert to proper MongoDB document
                # Exclude _id for inserts, MongoDB will generate it
                if "_id" in review:
                    del review["_id"]

                operations.append(
                    pymongo.UpdateOne(
                        {"review_id": review["review_id"]},
                        {"$set": review},
                        upsert=True
                    )
                )

            if operations:
                result = self.collection.bulk_write(operations)
                log.info(f"MongoDB: Upserted {result.upserted_count}, modified {result.modified_count} reviews")
        except Exception as e:
            log.error(f"Error saving reviews to MongoDB: {e}")


class JSONStorage:
    """JSON file-based storage handler for Google Maps reviews"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize JSON storage with configuration"""
        self.json_path = Path(config.get("json_path", "google_reviews.json"))
        self.seen_ids_path = Path(config.get("seen_ids_path", "google_reviews.ids"))
        self.convert_dates = config.get("convert_dates", True)
        self.download_images = config.get("download_images", False)
        self.store_local_paths = config.get("store_local_paths", True)
        self.replace_urls = config.get("replace_urls", False)
        self.preserve_original_urls = config.get("preserve_original_urls", True)
        self.custom_params = config.get("custom_params", {})
        self.image_handler = ImageHandler(config) if self.download_images else None

    def load_json_docs(self) -> Dict[str, Dict[str, Any]]:
        """Load reviews from JSON file"""
        if not self.json_path.exists():
            return {}
        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))
            # Index by review_id for fast lookups
            return {d.get("review_id", ""): d for d in data if d.get("review_id")}
        except json.JSONDecodeError:
            log.warning("⚠️ Error reading JSON file, starting with empty data")
            return {}

    def save_json_docs(self, docs: Dict[str, Dict[str, Any]]):
        """Save reviews to JSON file"""
        # Create a copy of the docs to avoid modifying the original
        processed_docs = {review_id: review.copy() for review_id, review in docs.items()}

        # Process reviews before saving
        # Convert string dates to datetime objects if enabled
        if self.convert_dates:
            processed_docs = DateConverter.convert_dates_in_reviews(processed_docs)

        # Download and process images if enabled
        if self.download_images and self.image_handler:
            processed_docs = self.image_handler.download_all_images(processed_docs)

            # If not storing local paths, remove them from the documents
            if not self.store_local_paths:
                for review in processed_docs.values():
                    if "local_images" in review:
                        del review["local_images"]
                    if "local_profile_picture" in review:
                        del review["local_profile_picture"]

            # If not preserving original URLs, remove them from the documents
            if self.replace_urls and not self.preserve_original_urls:
                for review in processed_docs.values():
                    if "original_image_urls" in review:
                        del review["original_image_urls"]
                    if "original_profile_picture" in review:
                        del review["original_profile_picture"]

        # Add custom parameters to each document
        if self.custom_params:
            log.info(f"Adding custom parameters to {len(processed_docs)} documents")
            for review in processed_docs.values():
                for key, value in self.custom_params.items():
                    review[key] = value

        # Convert datetime objects back to strings for JSON serialization
        for doc in processed_docs.values():
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()

        # Write to JSON file
        self.json_path.write_text(json.dumps(list(processed_docs.values()),
                                             ensure_ascii=False, indent=2), encoding="utf-8")

    def load_seen(self) -> Set[str]:
        """Load set of already seen review IDs"""
        return set(
            self.seen_ids_path.read_text(encoding="utf-8").splitlines()) if self.seen_ids_path.exists() else set()

    def save_seen(self, ids: Set[str]):
        """Save set of already seen review IDs"""
        self.seen_ids_path.write_text("\n".join(ids), encoding="utf-8")


def merge_review(existing: Dict[str, Any] | None, raw: RawReview) -> Dict[str, Any]:
    """
    Merge a raw review with an existing review document.
    Creates a new document if existing is None.
    """
    if not existing:
        # Create a new review with the updated field names
        existing = {
            "review_id": raw.id,
            "author": raw.author,
            "rating": raw.rating,
            "description": {},  # renamed from "texts"
            "likes": raw.likes,
            "user_images": list(raw.photos),  # renamed from "photo_urls"
            "author_profile_url": raw.profile,  # renamed from "profile_link"
            "profile_picture": raw.avatar,  # renamed from "avatar_url"
            "owner_responses": {},
            "created_date": get_current_iso_date(),
            "review_date": parse_relative_date(raw.date, RAW_LANG),
        }
    else:
        # Handle existing reviews with old field names - migrate them
        if "texts" in existing and "description" not in existing:
            existing["description"] = existing.pop("texts")

        if "photo_urls" in existing and "user_images" not in existing:
            existing["user_images"] = existing.pop("photo_urls")

        if "profile_link" in existing and "author_profile_url" not in existing:
            existing["author_profile_url"] = existing.pop("profile_link")

        if "avatar_url" in existing and "profile_picture" not in existing:
            existing["profile_picture"] = existing.pop("avatar_url")

        # Add ISO dates if not present
        if "created_date" not in existing:
            existing["created_date"] = get_current_iso_date()

        if "review_date" not in existing:
            existing["review_date"] = parse_relative_date(raw.date, RAW_LANG)

        # Remove the 'date' field if it exists
        if "date" in existing:
            del existing["date"]

    if raw.text:
        existing["description"][raw.lang] = raw.text

    if not existing.get("rating"):
        existing["rating"] = raw.rating

    if raw.likes > existing.get("likes", 0):
        existing["likes"] = raw.likes

    # Update the images list
    existing["user_images"] = list({*existing.get("user_images", []), *raw.photos})

    # Update avatar/profile picture
    if raw.avatar and (
            not existing.get("profile_picture") or len(raw.avatar) > len(existing.get("profile_picture", ""))):
        existing["profile_picture"] = raw.avatar

    if raw.owner_text:
        lang = detect_lang(raw.owner_text)
        # Don't store the date string in owner_responses
        existing.setdefault("owner_responses", {})[lang] = {
            "text": raw.owner_text,
        }

    # Update last_modified timestamp
    existing["last_modified_date"] = get_current_iso_date()

    return existing
