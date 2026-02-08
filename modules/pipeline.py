"""
Post-scrape processing pipeline.

Runs processing (dates, images, S3, cleanup, custom params) once,
then writes to each enabled target (MongoDB, JSON).
"""

import copy
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

from modules.date_converter import DateConverter
from modules.image_handler import ImageHandler
from modules.s3_handler import S3Handler

log = logging.getLogger("scraper")


class SyncTask(ABC):
    """Base class for pipeline tasks."""

    name: str

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @property
    @abstractmethod
    def enabled(self) -> bool:
        ...

    @abstractmethod
    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        ...

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Processing tasks (mutate reviews in place)
# ---------------------------------------------------------------------------

class DateTask(SyncTask):
    name = "dates"

    @property
    def enabled(self) -> bool:
        return self.config.get("convert_dates", True)

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        DateConverter.convert_dates_in_reviews(reviews)


class ImageTask(SyncTask):
    name = "images"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Build config with S3 disabled — S3 is handled separately by S3Task
        img_config = dict(config, use_s3=False)
        self._handler = ImageHandler(img_config)

    @property
    def enabled(self) -> bool:
        return self.config.get("download_images", False)

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        if place_id:
            self._handler.set_place_id(place_id)
        self._handler.download_all_images(reviews)


class S3Task(SyncTask):
    name = "s3"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._handler = S3Handler(config)
        s3_cfg = config.get("s3", {})
        self._sync_mode = s3_cfg.get("sync_mode", "update")
        self._image_dir = Path(config.get("image_dir", "review_images"))
        self._replace_urls = config.get("replace_urls", False)

    @property
    def enabled(self) -> bool:
        return self.config.get("use_s3", False) and self._handler.enabled

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        if place_id:
            self._handler.set_place_id(place_id)

        # Collect local files from reviews
        files_to_upload: Dict[str, tuple] = {}
        for review in reviews.values():
            # Review images
            for filename in review.get("local_images", []):
                if filename and filename not in files_to_upload:
                    base = self._image_dir / place_id if place_id else self._image_dir
                    local_path = base / "reviews" / filename
                    if local_path.exists():
                        files_to_upload[filename] = (local_path, False)

            # Profile picture
            pp = review.get("local_profile_picture")
            if pp and pp not in files_to_upload:
                base = self._image_dir / place_id if place_id else self._image_dir
                local_path = base / "profiles" / pp
                if local_path.exists():
                    files_to_upload[pp] = (local_path, True)

        if not files_to_upload:
            log.info("S3: no local files to upload")
            return

        # For new_only: skip files already on S3
        if self._sync_mode == "new_only":
            existing = self._handler.list_existing_keys(place_id)
            before = len(files_to_upload)
            files_to_upload = {
                fn: info for fn, info in files_to_upload.items()
                if self._build_key(fn, info[1], place_id) not in existing
            }
            skipped = before - len(files_to_upload)
            if skipped:
                log.info("S3 sync_mode=new_only: skipping %d existing files", skipped)

        if not files_to_upload:
            log.info("S3: all files already uploaded")
            return

        s3_results = self._handler.upload_images_batch(files_to_upload)

        # Replace URLs in reviews if configured
        if self._replace_urls and s3_results:
            filename_to_s3 = s3_results  # filename → s3_url
            for review in reviews.values():
                # Replace user_images
                if "user_images" in review and isinstance(review["user_images"], list):
                    for local_fn in review.get("local_images", []):
                        if local_fn in filename_to_s3:
                            s3_url = filename_to_s3[local_fn]
                            # Find and replace matching custom/download URLs
                            _replace_image_url(review, local_fn, s3_url, is_profile=False)

                # Replace profile_picture
                pp = review.get("local_profile_picture")
                if pp and pp in filename_to_s3:
                    review["profile_picture"] = filename_to_s3[pp]

    def _build_key(self, filename: str, is_profile: bool, place_id: str) -> str:
        folder = self._handler.profiles_folder if is_profile else self._handler.reviews_folder
        place_segment = f"{place_id}/" if place_id else ""
        return f"{self._handler.prefix}{place_segment}{folder}/{filename}"


def _replace_image_url(
    review: Dict[str, Any],
    local_fn: str,
    s3_url: str,
    is_profile: bool,
) -> None:
    """Replace a review image URL with its S3 counterpart by matching filename."""
    if is_profile:
        review["profile_picture"] = s3_url
        return

    images = review.get("user_images", [])
    for i, url in enumerate(images):
        # Match by filename suffix (the filename is the tail of the URL path)
        if url.endswith(local_fn) or local_fn.rstrip(".jpg") in url:
            images[i] = s3_url
            break


class CleanupTask(SyncTask):
    name = "cleanup"

    @property
    def enabled(self) -> bool:
        return True  # always runs

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        store_local = self.config.get("store_local_paths", True)
        replace_urls = self.config.get("replace_urls", False)
        preserve_orig = self.config.get("preserve_original_urls", True)

        for review in reviews.values():
            if not store_local:
                review.pop("local_images", None)
                review.pop("local_profile_picture", None)

            if replace_urls and not preserve_orig:
                review.pop("original_image_urls", None)
                review.pop("original_profile_picture", None)


class CustomParamsTask(SyncTask):
    name = "custom_params"

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("custom_params"))

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        params = self.config["custom_params"]
        log.info("Adding custom parameters to %d documents", len(reviews))
        for review in reviews.values():
            review.update(params)


# ---------------------------------------------------------------------------
# Writer tasks (read final reviews, write to targets)
# ---------------------------------------------------------------------------

class MongoDBTask(SyncTask):
    name = "mongodb"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._storage = None  # lazy init

    @property
    def enabled(self) -> bool:
        return self.config.get("use_mongodb", False)

    def _ensure_storage(self):
        if self._storage is None:
            from modules.data_storage import MongoDBStorage
            self._storage = MongoDBStorage(config=self.config)

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        self._ensure_storage()
        mongo_cfg = self.config.get("mongodb", {})
        sync_mode = mongo_cfg.get("sync_mode", "update")
        log.info(
            "Syncing %d reviews to MongoDB (sync_mode=%s)...",
            len(reviews), sync_mode,
        )
        self._storage.write_reviews(reviews, sync_mode=sync_mode)

    def close(self) -> None:
        if self._storage:
            self._storage.close()


class JSONTask(SyncTask):
    name = "json"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._json_path = Path(config.get("json_path", "google_reviews.json"))

    @property
    def enabled(self) -> bool:
        return self.config.get("backup_to_json", False)

    def run(self, reviews: Dict[str, Dict[str, Any]], place_id: str) -> None:
        from modules.data_storage import JSONStorage
        storage = JSONStorage(self.config)
        storage.write_json_docs(reviews)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class PostScrapeRunner:
    """Orchestrates post-scrape processing and writing."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._tasks = self._build_tasks()

    def _build_tasks(self):
        return [
            DateTask(self.config),
            ImageTask(self.config),
            S3Task(self.config),
            CleanupTask(self.config),
            CustomParamsTask(self.config),
            MongoDBTask(self.config),
            JSONTask(self.config),
        ]

    def run(
        self,
        reviews: Dict[str, Dict[str, Any]],
        place_id: str,
        seen: Set[str] | None = None,
    ) -> None:
        if not reviews:
            log.info("PostScrapeRunner: no reviews to process")
            return

        log.info("PostScrapeRunner: processing %d reviews through %d tasks",
                 len(reviews), len(self._tasks))

        for task in self._tasks:
            if not task.enabled:
                log.debug("PostScrapeRunner: skipping disabled task '%s'", task.name)
                continue
            t0 = time.time()
            try:
                task.run(reviews, place_id)
                elapsed = time.time() - t0
                log.info("PostScrapeRunner: task '%s' completed in %.2fs",
                         task.name, elapsed)
            except Exception:
                log.exception("PostScrapeRunner: task '%s' failed", task.name)

        # Save seen IDs (JSON backup bookkeeping)
        if seen is not None and self.config.get("backup_to_json", False):
            from modules.data_storage import JSONStorage
            JSONStorage(self.config).save_seen(seen)

    def close(self) -> None:
        for task in self._tasks:
            try:
                task.close()
            except Exception:
                log.exception("PostScrapeRunner: error closing task '%s'", task.name)
