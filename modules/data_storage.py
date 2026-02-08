"""
Data storage modules for Google Maps Reviews Scraper.
"""

import copy
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

import pymongo

from modules.date_converter import DateConverter
from modules.image_handler import ImageHandler
from modules.data_logic import merge_review, merge_review_with_translation

# Logger
log = logging.getLogger("scraper")


class MongoDBStorage:
    """MongoDB storage handler for Google Maps reviews"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize MongoDB storage with configuration"""
        mongodb_config = config.get("mongodb", {})
        self.uri = mongodb_config.get("uri")
        self.db_name = mongodb_config.get("database")
        self.collection_name = mongodb_config.get("collection")
        self.tls_allow_invalid_certs = mongodb_config.get("tls_allow_invalid_certs", False)
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
            self.client = pymongo.MongoClient(
                self.uri,
                tlsAllowInvalidCertificates=self.tls_allow_invalid_certs,
                connectTimeoutMS=30000,
                socketTimeoutMS=None,
                connect=True,
                maxPoolSize=50,
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

    def fetch_existing_ids(self) -> Set[str]:
        """Fetch existing review IDs from MongoDB (lightweight projection).

        Raises on connection/query failure so callers can distinguish
        "empty collection" from "database unreachable".
        """
        if not self.connected and not self.connect():
            raise ConnectionError("MongoDB connection failed")
        return {
            doc["review_id"]
            for doc in self.collection.find({}, {"review_id": 1, "_id": 0})
            if "review_id" in doc
        }

    def save_reviews(self, reviews: Dict[str, Dict[str, Any]], sync_mode: str = "update"):
        """Save reviews to MongoDB using bulk operations.

        Works independently from the scrape — always receives the full review
        set from SQLite and decides what to write based on *sync_mode*:

          "new_only" — query MongoDB for existing IDs, insert only missing docs.
          "update"   — upsert all: insert missing + update existing ($set).
          "full"     — same write as "update".
        """
        if not reviews:
            log.info("No reviews to save to MongoDB")
            return

        if not self.connected and not self.connect():
            log.warning("Cannot save reviews - MongoDB connection failed")
            return

        try:
            # Deep copy to avoid mutating caller's data
            processed_reviews = copy.deepcopy(reviews)

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

            # For "new_only": check MongoDB and skip existing reviews
            if sync_mode == "new_only":
                existing_ids = self.fetch_existing_ids()
                filtered = {rid: r for rid, r in processed_reviews.items()
                            if r.get("review_id") not in existing_ids}
                skipped = len(processed_reviews) - len(filtered)
                if skipped:
                    log.info("sync_mode=new_only: skipping %d existing reviews", skipped)
                processed_reviews = filtered

            if not processed_reviews:
                log.info("No new reviews to sync to MongoDB")
                return

            operations = []
            for review in processed_reviews.values():
                if "_id" in review:
                    del review["_id"]
                operations.append(
                    pymongo.UpdateOne(
                        {"review_id": review["review_id"]},
                        {"$set": review},
                        upsert=True,
                    )
                )

            if operations:
                result = self.collection.bulk_write(operations)
                log.info(f"MongoDB: Upserted {result.upserted_count}, modified {result.modified_count} reviews")
        except Exception as e:
            log.error(f"Error saving reviews to MongoDB: {e}")

    def write_reviews(self, reviews: Dict[str, Dict[str, Any]], sync_mode: str = "update"):
        """Pure writer — no date/image/param processing.

        Expects already-processed reviews from the pipeline.
        sync_mode filtering + bulk upsert only.
        """
        if not reviews:
            log.info("No reviews to write to MongoDB")
            return

        if not self.connected and not self.connect():
            log.warning("Cannot write reviews - MongoDB connection failed")
            return

        try:
            target = reviews

            if sync_mode == "new_only":
                existing_ids = self.fetch_existing_ids()
                target = {
                    rid: r for rid, r in reviews.items()
                    if r.get("review_id") not in existing_ids
                }
                skipped = len(reviews) - len(target)
                if skipped:
                    log.info("sync_mode=new_only: skipping %d existing reviews", skipped)

            if not target:
                log.info("No new reviews to sync to MongoDB")
                return

            operations = []
            for review in target.values():
                doc = {k: v for k, v in review.items() if k != "_id"}
                operations.append(
                    pymongo.UpdateOne(
                        {"review_id": doc["review_id"]},
                        {"$set": doc},
                        upsert=True,
                    )
                )

            if operations:
                result = self.collection.bulk_write(operations)
                log.info(
                    "MongoDB: Upserted %d, modified %d reviews",
                    result.upserted_count, result.modified_count,
                )
        except Exception as e:
            log.error(f"Error writing reviews to MongoDB: {e}")


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
            backup = self.json_path.with_suffix(
                f".corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy2(self.json_path, backup)
            log.warning(
                "Corrupt JSON file backed up to %s — starting with empty data", backup
            )
            return {}

    def save_json_docs(self, docs: Dict[str, Dict[str, Any]]):
        """Save reviews to JSON file"""
        # Deep copy to avoid mutating caller's data
        processed_docs = copy.deepcopy(docs)

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

    def write_json_docs(self, docs: Dict[str, Dict[str, Any]]):
        """Pure writer — no date/image/param processing.

        Expects already-processed reviews from the pipeline.
        Deep-copies, serializes datetimes, writes JSON file.
        """
        out = copy.deepcopy(docs)
        for doc in out.values():
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()

        self.json_path.write_text(
            json.dumps(list(out.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_seen(self) -> Set[str]:
        """Load set of already seen review IDs"""
        return set(
            self.seen_ids_path.read_text(encoding="utf-8").splitlines()) if self.seen_ids_path.exists() else set()

    def save_seen(self, ids: Set[str]):
        """Save set of already seen review IDs"""
        self.seen_ids_path.write_text("\n".join(ids), encoding="utf-8")


# Re-exported from modules.data_logic for backward compatibility
__all__ = ["MongoDBStorage", "JSONStorage", "merge_review", "merge_review_with_translation"]
