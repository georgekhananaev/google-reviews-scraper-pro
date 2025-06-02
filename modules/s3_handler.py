"""
S3 upload handler for Google Maps Reviews Scraper.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger("scraper")


class S3Handler:
    """Handler for uploading images to AWS S3"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize S3 handler with configuration"""
        self.enabled = config.get("use_s3", False)
        
        if not self.enabled:
            return
            
        s3_config = config.get("s3", {})
        
        self.aws_access_key_id = s3_config.get("aws_access_key_id", "")
        self.aws_secret_access_key = s3_config.get("aws_secret_access_key", "")
        self.region_name = s3_config.get("region_name", "us-east-1")
        self.bucket_name = s3_config.get("bucket_name", "")
        self.prefix = s3_config.get("prefix", "reviews/").rstrip("/") + "/"
        self.profiles_folder = s3_config.get("profiles_folder", "profiles/").strip("/")
        self.reviews_folder = s3_config.get("reviews_folder", "reviews/").strip("/")
        self.delete_local_after_upload = s3_config.get("delete_local_after_upload", False)
        self.s3_base_url = s3_config.get("s3_base_url", "")
        
        # Validate required settings
        if not self.bucket_name:
            log.error("S3 bucket_name is required when use_s3 is enabled")
            self.enabled = False
            return
            
        # Initialize S3 client
        try:
            session_kwargs = {"region_name": self.region_name}
            
            # Use credentials if provided, otherwise rely on environment/IAM
            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key
                })
            
            self.s3_client = boto3.client("s3", **session_kwargs)
            
            # Test connection by checking if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            log.info(f"S3 handler initialized successfully for bucket: {self.bucket_name}")
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                log.error(f"S3 bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                log.error(f"Access denied to S3 bucket '{self.bucket_name}'")
            else:
                log.error(f"Error connecting to S3: {e}")
            self.enabled = False
            
        except Exception as e:
            log.error(f"Error initializing S3 client: {e}")
            self.enabled = False

    def get_s3_url(self, key: str) -> str:
        """Generate S3 URL for uploaded file"""
        if self.s3_base_url:
            return f"{self.s3_base_url.rstrip('/')}/{key}"
        else:
            return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"

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
            log.warning(f"Local file does not exist: {local_path}")
            return None
            
        try:
            # Upload file
            self.s3_client.upload_file(
                str(local_path),
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'ACL': 'public-read'  # Make images publicly readable
                }
            )
            
            # Generate S3 URL
            s3_url = self.get_s3_url(s3_key)
            
            # Delete local file if requested
            if self.delete_local_after_upload:
                try:
                    local_path.unlink()
                    log.debug(f"Deleted local file: {local_path}")
                except Exception as e:
                    log.warning(f"Failed to delete local file {local_path}: {e}")
            
            log.debug(f"Uploaded {local_path} to s3://{self.bucket_name}/{s3_key}")
            return s3_url
            
        except ClientError as e:
            log.error(f"Failed to upload {local_path} to S3: {e}")
            return None
        except Exception as e:
            log.error(f"Unexpected error uploading {local_path} to S3: {e}")
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
            
        # Create S3 key with appropriate folder structure
        folder = self.profiles_folder if is_profile else self.reviews_folder
        s3_key = f"{self.prefix}{folder}/{filename}"
        
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
            log.info(f"Successfully uploaded {len(results)} images to S3")
            
        return results