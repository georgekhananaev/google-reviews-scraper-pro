"""
S3 upload handler for Google Maps Reviews Scraper.

Supports AWS S3, MinIO, and Cloudflare R2 via unified provider config.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Set

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

log = logging.getLogger("scraper")

# Provider presets — explicit config always wins over these defaults.
_PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "aws": {},
    "minio": {"path_style": True, "acl": ""},
    "r2": {"region_name": "auto", "acl": ""},
}


def _resolve_s3_config(s3_config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply provider presets then overlay explicit user config.

    Returns a new dict with all S3 settings resolved.
    """
    provider = s3_config.get("provider", "aws")
    preset = _PROVIDER_PRESETS.get(provider, {})

    # Start with preset defaults, then overlay user-provided values.
    resolved: Dict[str, Any] = {**preset}
    for key, value in s3_config.items():
        if key == "provider":
            continue
        if value is not None:
            resolved[key] = value
    return resolved


class S3Handler:
    """Handler for uploading images to S3-compatible storage."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize S3 handler with configuration."""
        self.enabled = config.get("use_s3", False)

        if not self.enabled:
            return

        raw_s3 = config.get("s3", {})
        s3_config = _resolve_s3_config(raw_s3)

        self.aws_access_key_id = s3_config.get("aws_access_key_id", "")
        self.aws_secret_access_key = s3_config.get("aws_secret_access_key", "")
        self.region_name = s3_config.get("region_name", "us-east-1")
        self.bucket_name = s3_config.get("bucket_name", "")
        self.prefix = s3_config.get("prefix", "reviews/").rstrip("/") + "/"
        self.profiles_folder = s3_config.get("profiles_folder", "profiles/").strip("/")
        self.reviews_folder = s3_config.get("reviews_folder", "reviews/").strip("/")
        self.delete_local_after_upload = s3_config.get("delete_local_after_upload", False)
        self.s3_base_url = s3_config.get("s3_base_url", "")
        self.endpoint_url: Optional[str] = s3_config.get("endpoint_url") or None
        self.path_style: bool = s3_config.get("path_style", False)
        self.acl: str = s3_config.get("acl", "public-read")

        # Validate required settings
        if not self.bucket_name:
            log.error("S3 bucket_name is required when use_s3 is enabled")
            self.enabled = False
            return

        # Initialize S3 client
        try:
            session_kwargs: Dict[str, Any] = {"region_name": self.region_name}

            # Use credentials if provided, otherwise rely on environment/IAM
            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key,
                })

            if self.endpoint_url:
                session_kwargs["endpoint_url"] = self.endpoint_url

            if self.path_style:
                session_kwargs["config"] = BotoConfig(
                    s3={"addressing_style": "path"}
                )

            self.s3_client = boto3.client("s3", **session_kwargs)

            # Test connection by checking if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            log.info("S3 handler initialized successfully for bucket: %s (provider: %s)",
                     self.bucket_name, raw_s3.get("provider", "aws"))

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                log.error("S3 bucket '%s' not found", self.bucket_name)
            elif error_code == '403':
                log.error("Access denied to S3 bucket '%s'", self.bucket_name)
            else:
                log.error("Error connecting to S3: %s", e)
            self.enabled = False

        except Exception as e:
            log.error("Error initializing S3 client: %s", e)
            self.enabled = False

    def set_place_id(self, place_id: str):
        """Set place ID for per-business S3 path isolation."""
        self._place_id = place_id

    def get_s3_url(self, key: str) -> str:
        """Generate S3 URL for uploaded file."""
        if self.s3_base_url:
            return f"{self.s3_base_url.rstrip('/')}/{key}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{key}"
        return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"

    def _build_extra_args(self, content_type: str = "image/jpeg") -> Dict[str, str]:
        """Build ExtraArgs dict for upload, respecting ACL config."""
        args: Dict[str, str] = {"ContentType": content_type}
        if self.acl:
            args["ACL"] = self.acl
        return args

    def upload_file(self, local_path: Path, s3_key: str) -> Optional[str]:
        """
        Upload a file to S3.

        Args:
            local_path: Path to local file
            s3_key: S3 key (path) for the uploaded file

        Returns:
            S3 URL if successful, None if failed
        """
        if not self.enabled:
            return None

        if not local_path.exists():
            log.warning("Local file does not exist: %s", local_path)
            return None

        try:
            self.s3_client.upload_file(
                str(local_path),
                self.bucket_name,
                s3_key,
                ExtraArgs=self._build_extra_args(),
            )

            s3_url = self.get_s3_url(s3_key)

            if self.delete_local_after_upload:
                try:
                    local_path.unlink()
                    log.debug("Deleted local file: %s", local_path)
                except Exception as e:
                    log.warning("Failed to delete local file %s: %s", local_path, e)

            log.debug("Uploaded %s to s3://%s/%s", local_path, self.bucket_name, s3_key)
            return s3_url

        except ClientError as e:
            log.error("Failed to upload %s to S3: %s", local_path, e)
            return None
        except Exception as e:
            log.error("Unexpected error uploading %s to S3: %s", local_path, e)
            return None

    def upload_image(self, local_path: Path, filename: str, is_profile: bool = False) -> Optional[str]:
        """
        Upload an image to S3 with appropriate folder structure.

        Args:
            local_path: Path to local image file
            filename: Name of the file
            is_profile: Whether this is a profile image

        Returns:
            S3 URL if successful, None if failed
        """
        if not self.enabled:
            return None

        folder = self.profiles_folder if is_profile else self.reviews_folder
        place_segment = f"{self._place_id}/" if getattr(self, "_place_id", None) else ""
        s3_key = f"{self.prefix}{place_segment}{folder}/{filename}"

        return self.upload_file(local_path, s3_key)

    def upload_images_batch(self, image_files: Dict[str, tuple]) -> Dict[str, str]:
        """
        Upload multiple images to S3.

        Args:
            image_files: Dict mapping filename to (local_path, is_profile) tuple

        Returns:
            Dict mapping filename to S3 URL for successful uploads
        """
        if not self.enabled:
            return {}

        results = {}

        for filename, (local_path, is_profile) in image_files.items():
            s3_url = self.upload_image(local_path, filename, is_profile)
            if s3_url:
                results[filename] = s3_url

        if results:
            log.info("Successfully uploaded %d images to S3", len(results))

        return results

    def list_existing_keys(self, place_id: str = None) -> Set[str]:
        """List existing S3 keys under prefix (for sync_mode='new_only').

        Args:
            place_id: Optional place ID to scope the listing.

        Returns:
            Set of existing S3 keys.
        """
        if not self.enabled:
            return set()

        search_prefix = self.prefix
        if place_id:
            search_prefix = f"{self.prefix}{place_id}/"

        keys: Set[str] = set()
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=search_prefix):
                for obj in page.get("Contents", []):
                    keys.add(obj["Key"])
            log.info("S3: found %d existing keys under '%s'", len(keys), search_prefix)
        except ClientError as e:
            log.error("Error listing S3 keys: %s", e)
        return keys
