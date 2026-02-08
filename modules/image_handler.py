"""
Image downloading and handling for Google Maps Reviews Scraper.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Set, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from modules.s3_handler import S3Handler

# Logger
log = logging.getLogger("scraper")


class ImageHandler:
    """Handler for downloading and managing review images"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize image handler with configuration"""
        self.image_dir = Path(config.get("image_dir", "review_images"))
        self.max_workers = config.get("download_threads", 4)
        self.store_local_paths = config.get("store_local_paths", True)
        
        # Image dimension settings
        self.max_width = config.get("max_width", 1200)
        self.max_height = config.get("max_height", 1200)

        # URL replacement settings
        self.replace_urls = config.get("replace_urls", False)
        self.custom_url_base = config.get("custom_url_base", "https://mycustomurl.com")
        self.custom_url_profiles = config.get("custom_url_profiles", "/profiles/")
        self.custom_url_reviews = config.get("custom_url_reviews", "/reviews/")
        self.preserve_original_urls = config.get("preserve_original_urls", True)

        # Subdirectories for different image types (per-place isolation)
        self._place_id = None
        self.profile_dir = self.image_dir / "profiles"
        self.review_dir = self.image_dir / "reviews"

        # HTTP session with automatic retries (exponential backoff)
        self._session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._session.mount("http://", HTTPAdapter(max_retries=retry))

        # Initialize S3 handler
        self.s3_handler = S3Handler(config)
        self.use_s3 = config.get("use_s3", False)

    def set_place_id(self, place_id: str):
        """Set place ID to organize images into per-business subdirectories."""
        self._place_id = place_id
        base = self.image_dir / place_id
        self.profile_dir = base / "profiles"
        self.review_dir = base / "reviews"

    def ensure_directories(self):
        """Ensure all image directories exist"""
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.review_dir.mkdir(parents=True, exist_ok=True)

    def is_not_custom_url(self, url: str) -> bool:
        """Check if the URL is not one of our custom URLs"""
        if not url:
            return False

        # Check if the URL starts with our custom URL base - if so, skip it
        if self.custom_url_base and url.startswith(self.custom_url_base):
            return False

        return True

    def get_filename_from_url(self, url: str, is_profile: bool = False) -> str:
        """Extract filename from URL and add .jpg extension"""
        if not url:
            return ""

        # Skip our custom URLs
        if not self.is_not_custom_url(url):
            return ""

        # For profile pictures
        if is_profile:
            # Extract unique identifier from profile URL
            parts = url.split('/')
            if len(parts) > 1:
                filename = parts[-2] if parts[-1] == '' else parts[-1]
                filename = filename.split('=')[0]
                return f"{filename}.jpg"

        # For review images
        url = url.split('=')[0]
        filename = url.split('/')[-1]
        return f"{filename}.jpg"

    def get_custom_url(self, filename: str, is_profile: bool = False) -> str:
        """Generate a custom URL for the image"""
        if not self.replace_urls or not filename:
            return ""

        base_url = self.custom_url_base.rstrip('/')
        path = self.custom_url_profiles if is_profile else self.custom_url_reviews
        path = path.strip('/')

        return f"{base_url}/{path}/{filename}"

    def _build_download_url(self, url: str) -> str:
        """Build a download URL with configured dimensions for Google images."""
        if 'googleusercontent.com' in url or 'ggpht.com' in url or 'gstatic.com' in url:
            base_url = url.split('=')[0]
            return base_url + f"=w{self.max_width}-h{self.max_height}-no"
        return url.split("=")[0]

    def download_image(self, url_info: Tuple[str, bool]) -> Tuple[str, str, str, str]:
        """
        Download an image from URL and save to disk.

        Args:
            url_info: Tuple of (url, is_profile)

        Returns:
            Tuple of (original_url, download_url, local filename, custom url)
        """
        url, is_profile = url_info

        # Skip our custom URLs
        if not self.is_not_custom_url(url):
            return url, url, "", ""

        try:
            filename = self.get_filename_from_url(url, is_profile)
            if not filename:
                return url, url, "", ""

            download_url = self._build_download_url(url)

            # Choose directory based on image type
            target_dir = self.profile_dir if is_profile else self.review_dir
            filepath = target_dir / filename

            # Skip if file already exists
            if filepath.exists():
                custom_url = self.get_custom_url(filename, is_profile)
                return url, download_url, filename, custom_url

            response = self._session.get(download_url, stream=True, timeout=10)
            response.raise_for_status()

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            custom_url = self.get_custom_url(filename, is_profile)
            return url, download_url, filename, custom_url

        except Exception as e:
            log.error(f"Error downloading image from {url}: {e}")
            return url, url, "", ""

    def download_all_images(self, reviews: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Download all images (review images and profile pictures) for all reviews.

        Args:
            reviews: Dictionary of review documents

        Returns:
            Updated reviews with local image paths and custom URLs
        """
        self.ensure_directories()

        # Collect all unique image URLs (both review images and profile pictures)
        # Exclude custom URLs
        review_urls: Set[str] = set()
        profile_urls: Set[str] = set()

        for review in reviews.values():
            # Collect review images - exclude custom URLs
            if "user_images" in review and isinstance(review["user_images"], list):
                for url in review["user_images"]:
                    if self.is_not_custom_url(url):
                        review_urls.add(url)
                # If we have original image URLs stored separately, add those too
                if "original_image_urls" in review and isinstance(review["original_image_urls"], list):
                    for orig_url in review["original_image_urls"]:
                        if self.is_not_custom_url(orig_url):
                            review_urls.add(orig_url)

            # Collect profile pictures - exclude custom URLs
            if "profile_picture" in review and review["profile_picture"]:
                profile_url = review["profile_picture"]
                if self.is_not_custom_url(profile_url):
                    profile_urls.add(profile_url)
                # If we have original profile URL stored separately, add that too
                if "original_profile_picture" in review and review["original_profile_picture"]:
                    orig_profile_url = review["original_profile_picture"]
                    if self.is_not_custom_url(orig_profile_url):
                        profile_urls.add(orig_profile_url)

        # Prepare download tasks with URL type info
        download_tasks = [(url, False) for url in review_urls] + [(url, True) for url in profile_urls]

        if not download_tasks:
            log.info("No images to download")
            return reviews

        log.info(
            f"Downloading {len(download_tasks)} images ({len(profile_urls)} profiles, {len(review_urls)} review images)...")

        # Create mappings: original URL → filename, custom URL, and download URL
        url_to_filename = {}
        url_to_custom_url = {}
        url_to_download_url = {}

        # Download images in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = executor.map(self.download_image, download_tasks)
            for orig_url, dl_url, filename, custom_url in results:
                if filename:
                    url_to_filename[orig_url] = filename
                if custom_url:
                    url_to_custom_url[orig_url] = custom_url
                if dl_url != orig_url:
                    url_to_download_url[orig_url] = dl_url

        # Upload to S3 if enabled
        s3_url_mapping = {}
        if self.use_s3 and self.s3_handler.enabled and url_to_filename:
            log.info("Uploading images to S3...")
            
            # Prepare files for S3 upload
            files_to_upload = {}
            for url, filename in url_to_filename.items():
                # Determine if it's a profile image
                is_profile = any(url == profile_url for profile_url in profile_urls)
                
                # Get local file path
                local_path = (self.profile_dir if is_profile else self.review_dir) / filename
                
                if local_path.exists():
                    files_to_upload[filename] = (local_path, is_profile)
            
            # Upload to S3
            s3_results = self.s3_handler.upload_images_batch(files_to_upload)
            
            # Create mapping from original URL to S3 URL
            for url, filename in url_to_filename.items():
                if filename in s3_results:
                    s3_url_mapping[url] = s3_results[filename]

        # Update review documents
        for review_id, review in reviews.items():
            # Find the original URLs to use for lookup - important for both user_images and profile_picture
            user_images_original = []
            profile_picture_original = ""

            # For user_images, either use original URLs if we have them, or the current user_images
            if "original_image_urls" in review and isinstance(review["original_image_urls"], list):
                user_images_original = review["original_image_urls"]
            elif "user_images" in review and isinstance(review["user_images"], list):
                user_images_original = review["user_images"].copy()

            # For profile_picture, either use original URL if we have it, or the current profile_picture
            if "original_profile_picture" in review and review["original_profile_picture"]:
                profile_picture_original = review["original_profile_picture"]
            elif "profile_picture" in review:
                profile_picture_original = review["profile_picture"]

            # Process user_images
            if "user_images" in review and isinstance(review["user_images"], list):
                # Add local image paths if enabled
                if self.store_local_paths:
                    local_images = [url_to_filename.get(url, "") for url in user_images_original
                                    if url and self.is_not_custom_url(url)]
                    review["local_images"] = [img for img in local_images if img]

                if self.replace_urls:
                    # Store original URLs if needed and not already stored
                    if self.preserve_original_urls and "original_image_urls" not in review:
                        review["original_image_urls"] = review["user_images"].copy()

                    # Create custom URLs for each image
                    custom_images = []
                    for url in user_images_original:
                        # Prefer S3 URL if available, then custom URL
                        if url in s3_url_mapping:
                            custom_images.append(s3_url_mapping[url])
                        elif url in url_to_custom_url:
                            custom_images.append(url_to_custom_url[url])
                        elif not self.is_not_custom_url(url):  # Already a custom URL
                            custom_images.append(url)

                    if custom_images:
                        review["user_images"] = custom_images
                else:
                    # No custom URL replacement — update URLs to use configured dimensions
                    review["user_images"] = [
                        url_to_download_url.get(url, url) for url in user_images_original
                    ]

            # Process profile_picture
            if "profile_picture" in review and review["profile_picture"]:
                # Add local profile picture path if enabled
                if self.store_local_paths and profile_picture_original in url_to_filename:
                    review["local_profile_picture"] = url_to_filename[profile_picture_original]

                if self.replace_urls:
                    # Store original URL if needed and not already stored
                    if self.preserve_original_urls and "original_profile_picture" not in review:
                        review["original_profile_picture"] = review["profile_picture"]

                    # Replace with S3 URL if available, otherwise use custom URL
                    if profile_picture_original in s3_url_mapping:
                        review["profile_picture"] = s3_url_mapping[profile_picture_original]
                    elif profile_picture_original in url_to_custom_url:
                        review["profile_picture"] = url_to_custom_url[profile_picture_original]
                    elif not self.is_not_custom_url(review["profile_picture"]):
                        pass
                    elif profile_picture_original:
                        filename = url_to_filename.get(profile_picture_original, "")
                        if filename:
                            custom_url = self.get_custom_url(filename, True)
                            if custom_url:
                                review["profile_picture"] = custom_url
                elif profile_picture_original in url_to_download_url:
                    # No custom URL replacement — update to use configured dimensions
                    review["profile_picture"] = url_to_download_url[profile_picture_original]

        log.info(f"Downloaded {len(url_to_filename)} images")
        if self.use_s3 and s3_url_mapping:
            log.info(f"Uploaded {len(s3_url_mapping)} images to S3")
        if self.replace_urls:
            total_replaced = len(s3_url_mapping) + len(url_to_custom_url)
            log.info(f"Replaced URLs for {total_replaced} images")

        return reviews
