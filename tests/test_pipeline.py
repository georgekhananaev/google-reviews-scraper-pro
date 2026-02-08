"""Tests for the post-scrape pipeline."""

import copy
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.pipeline import (
    CleanupTask,
    CustomParamsTask,
    DateTask,
    ImageTask,
    JSONTask,
    MongoDBTask,
    PostScrapeRunner,
    S3Task,
    SyncTask,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_config(**overrides):
    cfg = {
        "convert_dates": False,
        "download_images": False,
        "use_s3": False,
        "use_mongodb": False,
        "backup_to_json": False,
        "store_local_paths": True,
        "replace_urls": False,
        "preserve_original_urls": True,
        "custom_params": {},
        "image_dir": "review_images",
        "download_threads": 1,
        "max_width": 800,
        "max_height": 800,
        "json_path": "test_reviews.json",
        "seen_ids_path": "test_reviews.ids",
        "mongodb": {"uri": "mongodb://localhost:27017", "database": "test", "collection": "test", "sync_mode": "update"},
        "s3": {"sync_mode": "update"},
    }
    cfg.update(overrides)
    return cfg


def _sample_reviews():
    return {
        "rev1": {
            "review_id": "rev1",
            "place_id": "place123",
            "author": "Alice",
            "rating": 5,
            "description": {"en": "Great place"},
            "review_date": "2 months ago",
            "created_date": "2026-01-01T00:00:00",
            "last_modified_date": "",
            "user_images": ["https://lh3.googleusercontent.com/img1=w100"],
            "profile_picture": "https://lh3.googleusercontent.com/prof1=s100",
        },
        "rev2": {
            "review_id": "rev2",
            "place_id": "place123",
            "author": "Bob",
            "rating": 3,
            "description": {"en": "Ok"},
            "review_date": "a week ago",
            "created_date": "",
            "last_modified_date": "",
            "user_images": [],
            "profile_picture": "",
        },
    }


# ---------------------------------------------------------------------------
# DateTask
# ---------------------------------------------------------------------------

class TestDateTask:
    def test_disabled_when_convert_dates_false(self):
        task = DateTask(_base_config(convert_dates=False))
        assert not task.enabled

    def test_enabled_when_convert_dates_true(self):
        task = DateTask(_base_config(convert_dates=True))
        assert task.enabled

    def test_run_converts_dates(self):
        task = DateTask(_base_config(convert_dates=True))
        reviews = _sample_reviews()
        task.run(reviews, "place123")
        # review_date should now be a datetime (DateConverter parses relative dates)
        assert isinstance(reviews["rev1"]["review_date"], datetime)


# ---------------------------------------------------------------------------
# ImageTask
# ---------------------------------------------------------------------------

class TestImageTask:
    def test_disabled_when_download_images_false(self):
        task = ImageTask(_base_config(download_images=False))
        assert not task.enabled

    def test_enabled_when_download_images_true(self):
        task = ImageTask(_base_config(download_images=True))
        assert task.enabled

    @patch("modules.pipeline.ImageHandler")
    def test_s3_disabled_in_image_task(self, mock_ih_cls):
        """ImageTask should create ImageHandler with use_s3=False."""
        cfg = _base_config(download_images=True, use_s3=True)
        ImageTask(cfg)
        # ImageHandler should have been called with use_s3=False
        call_kwargs = mock_ih_cls.call_args
        passed_config = call_kwargs[0][0]
        assert passed_config["use_s3"] is False


# ---------------------------------------------------------------------------
# S3Task
# ---------------------------------------------------------------------------

class TestS3Task:
    def test_disabled_when_use_s3_false(self):
        task = S3Task(_base_config(use_s3=False))
        assert not task.enabled

    @patch("modules.pipeline.S3Handler")
    def test_enabled_when_use_s3_and_handler_enabled(self, mock_s3_cls):
        mock_handler = MagicMock()
        mock_handler.enabled = True
        mock_s3_cls.return_value = mock_handler
        task = S3Task(_base_config(use_s3=True))
        assert task.enabled

    @patch("modules.pipeline.S3Handler")
    def test_new_only_skips_existing(self, mock_s3_cls):
        mock_handler = MagicMock()
        mock_handler.enabled = True
        mock_handler.prefix = "reviews/"
        mock_handler.profiles_folder = "profiles"
        mock_handler.reviews_folder = "reviews"
        mock_handler.list_existing_keys.return_value = {"reviews/place123/reviews/img1.jpg"}
        mock_handler.upload_images_batch.return_value = {}
        mock_s3_cls.return_value = mock_handler

        cfg = _base_config(use_s3=True, s3={"sync_mode": "new_only"})
        task = S3Task(cfg)

        reviews = {
            "rev1": {
                "review_id": "rev1",
                "local_images": ["img1.jpg"],
                "user_images": ["https://example.com/img1.jpg"],
            }
        }

        # Create the local file so it would be found
        img_dir = Path("review_images/place123/reviews")
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / "img1.jpg").write_bytes(b"fake")

        try:
            task.run(reviews, "place123")
            # list_existing_keys should have been called
            mock_handler.list_existing_keys.assert_called_once_with("place123")
        finally:
            (img_dir / "img1.jpg").unlink(missing_ok=True)
            # cleanup dirs
            for d in [img_dir, img_dir.parent, img_dir.parent.parent]:
                try:
                    d.rmdir()
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# CleanupTask
# ---------------------------------------------------------------------------

class TestCleanupTask:
    def test_always_enabled(self):
        task = CleanupTask(_base_config())
        assert task.enabled

    def test_strips_local_paths_when_disabled(self):
        task = CleanupTask(_base_config(store_local_paths=False))
        reviews = {
            "r1": {
                "review_id": "r1",
                "local_images": ["img.jpg"],
                "local_profile_picture": "prof.jpg",
            }
        }
        task.run(reviews, "p1")
        assert "local_images" not in reviews["r1"]
        assert "local_profile_picture" not in reviews["r1"]

    def test_strips_originals_when_replace_no_preserve(self):
        task = CleanupTask(_base_config(replace_urls=True, preserve_original_urls=False))
        reviews = {
            "r1": {
                "review_id": "r1",
                "original_image_urls": ["https://example.com/old"],
                "original_profile_picture": "https://example.com/old_prof",
            }
        }
        task.run(reviews, "p1")
        assert "original_image_urls" not in reviews["r1"]
        assert "original_profile_picture" not in reviews["r1"]

    def test_preserves_originals_when_configured(self):
        task = CleanupTask(_base_config(replace_urls=True, preserve_original_urls=True))
        reviews = {
            "r1": {
                "review_id": "r1",
                "original_image_urls": ["url"],
                "original_profile_picture": "url2",
            }
        }
        task.run(reviews, "p1")
        assert "original_image_urls" in reviews["r1"]
        assert "original_profile_picture" in reviews["r1"]


# ---------------------------------------------------------------------------
# CustomParamsTask
# ---------------------------------------------------------------------------

class TestCustomParamsTask:
    def test_disabled_when_empty(self):
        task = CustomParamsTask(_base_config(custom_params={}))
        assert not task.enabled

    def test_enabled_when_params_set(self):
        task = CustomParamsTask(_base_config(custom_params={"company": "Test"}))
        assert task.enabled

    def test_injects_params(self):
        task = CustomParamsTask(_base_config(custom_params={"company": "Acme", "source": "Maps"}))
        reviews = _sample_reviews()
        task.run(reviews, "p1")
        assert reviews["rev1"]["company"] == "Acme"
        assert reviews["rev1"]["source"] == "Maps"
        assert reviews["rev2"]["company"] == "Acme"


# ---------------------------------------------------------------------------
# MongoDBTask
# ---------------------------------------------------------------------------

class TestMongoDBTask:
    def test_disabled_when_use_mongodb_false(self):
        task = MongoDBTask(_base_config(use_mongodb=False))
        assert not task.enabled

    def test_enabled_when_use_mongodb_true(self):
        task = MongoDBTask(_base_config(use_mongodb=True))
        assert task.enabled

    @patch("modules.pipeline.MongoDBStorage" if False else "modules.data_storage.MongoDBStorage")
    def test_run_calls_write_reviews(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage

        task = MongoDBTask(_base_config(use_mongodb=True))
        reviews = _sample_reviews()

        with patch("modules.data_storage.MongoDBStorage", mock_storage_cls):
            task.run(reviews, "p1")

        mock_storage.write_reviews.assert_called_once()


# ---------------------------------------------------------------------------
# JSONTask
# ---------------------------------------------------------------------------

class TestJSONTask:
    def test_disabled_when_backup_false(self):
        task = JSONTask(_base_config(backup_to_json=False))
        assert not task.enabled

    def test_enabled_when_backup_true(self):
        task = JSONTask(_base_config(backup_to_json=True))
        assert task.enabled

    def test_run_writes_file(self, tmp_path):
        json_file = tmp_path / "out.json"
        cfg = _base_config(backup_to_json=True, json_path=str(json_file))
        task = JSONTask(cfg)
        reviews = {
            "r1": {"review_id": "r1", "author": "Test", "created_date": datetime(2026, 1, 1)},
        }
        task.run(reviews, "p1")
        data = json.loads(json_file.read_text())
        assert len(data) == 1
        assert data[0]["review_id"] == "r1"
        # datetime should be serialized to ISO string
        assert data[0]["created_date"] == "2026-01-01T00:00:00"


# ---------------------------------------------------------------------------
# PostScrapeRunner
# ---------------------------------------------------------------------------

class TestPostScrapeRunner:
    def test_skips_disabled_tasks(self):
        """All tasks disabled → no errors, no mutations."""
        cfg = _base_config()
        runner = PostScrapeRunner(cfg)
        reviews = _sample_reviews()
        original = copy.deepcopy(reviews)
        runner.run(reviews, "p1")
        runner.close()
        # Only CleanupTask runs (always enabled), but with default config it's a no-op
        assert reviews == original

    def test_empty_reviews_noop(self):
        cfg = _base_config()
        runner = PostScrapeRunner(cfg)
        runner.run({}, "p1")  # should not raise
        runner.close()

    def test_task_failure_isolation(self):
        """A failing task should not block subsequent tasks."""
        cfg = _base_config(
            convert_dates=True,
            custom_params={"tag": "test"},
        )
        runner = PostScrapeRunner(cfg)

        # Monkey-patch DateTask to raise
        for task in runner._tasks:
            if task.name == "dates":
                task.run = MagicMock(side_effect=RuntimeError("boom"))
                break

        reviews = _sample_reviews()
        runner.run(reviews, "p1")
        runner.close()

        # CustomParamsTask should still have run despite DateTask failure
        assert reviews["rev1"]["tag"] == "test"

    def test_saves_seen_ids(self, tmp_path):
        ids_file = tmp_path / "seen.ids"
        cfg = _base_config(
            backup_to_json=True,
            json_path=str(tmp_path / "out.json"),
            seen_ids_path=str(ids_file),
        )
        runner = PostScrapeRunner(cfg)
        reviews = _sample_reviews()
        runner.run(reviews, "p1", seen={"rev1", "rev2"})
        runner.close()

        saved = set(ids_file.read_text().splitlines())
        assert saved == {"rev1", "rev2"}

    def test_close_handles_errors(self):
        cfg = _base_config()
        runner = PostScrapeRunner(cfg)
        # Force a close error on one task
        runner._tasks[0].close = MagicMock(side_effect=RuntimeError("close fail"))
        runner.close()  # should not raise
