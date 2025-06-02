"""
Test S3 connection functionality.
"""

import pytest
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
import tempfile
import os


class TestS3Connection:
    """Test S3 connection and basic operations"""

    def test_s3_connection_when_enabled(self, use_s3, s3_config):
        """Test S3 connection when S3 is enabled in config"""
        if not use_s3:
            pytest.skip("S3 is disabled in configuration")
            
        if not s3_config:
            pytest.fail("S3 is enabled but no S3 configuration found")
            
        # Validate required configuration
        bucket_name = s3_config.get("bucket_name")
        if not bucket_name:
            pytest.fail("S3 bucket name not found in configuration")
            
        region_name = s3_config.get("region_name", "us-east-1")
        
        try:
            # Create S3 client with credentials from config
            session_kwargs = {"region_name": region_name}
            
            aws_access_key_id = s3_config.get("aws_access_key_id")
            aws_secret_access_key = s3_config.get("aws_secret_access_key")
            
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key
                })
            
            s3_client = boto3.client("s3", **session_kwargs)
            
            # Test bucket access by checking if bucket exists
            s3_client.head_bucket(Bucket=bucket_name)
            
        except NoCredentialsError:
            pytest.fail("AWS credentials not found. Check your configuration or environment.")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                pytest.fail(f"S3 bucket '{bucket_name}' not found")
            elif error_code == '403':
                pytest.fail(f"Access denied to S3 bucket '{bucket_name}'. Check your credentials and permissions.")
            else:
                pytest.fail(f"S3 client error: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error testing S3 connection: {e}")

    def test_s3_upload_download_when_enabled(self, use_s3, s3_config):
        """Test S3 upload and download functionality"""
        if not use_s3:
            pytest.skip("S3 is disabled in configuration")
            
        if not s3_config:
            pytest.fail("S3 is enabled but no S3 configuration found")
            
        bucket_name = s3_config.get("bucket_name")
        if not bucket_name:
            pytest.fail("S3 bucket name not found in configuration")
            
        region_name = s3_config.get("region_name", "us-east-1")
        prefix = s3_config.get("prefix", "reviews/").rstrip("/") + "/"
        profiles_folder = s3_config.get("profiles_folder", "profiles/").strip("/")
        reviews_folder = s3_config.get("reviews_folder", "reviews/").strip("/")
        
        try:
            # Create S3 client
            session_kwargs = {"region_name": region_name}
            
            aws_access_key_id = s3_config.get("aws_access_key_id")
            aws_secret_access_key = s3_config.get("aws_secret_access_key")
            
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key
                })
            
            s3_client = boto3.client("s3", **session_kwargs)
            
            # Create a temporary test file
            test_content = b"This is a test file for S3 upload"
            # Test with reviews folder structure
            test_key = f"{prefix}{reviews_folder}/test_file.txt"
            
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(test_content)
                tmp_file_path = tmp_file.name
            
            try:
                # Test upload
                s3_client.upload_file(
                    tmp_file_path,
                    bucket_name,
                    test_key,
                    ExtraArgs={'ACL': 'public-read'}
                )
                
                # Test that file exists in S3
                s3_client.head_object(Bucket=bucket_name, Key=test_key)
                
                # Test download
                with tempfile.NamedTemporaryFile(delete=False) as download_file:
                    download_path = download_file.name
                
                s3_client.download_file(bucket_name, test_key, download_path)
                
                # Verify downloaded content matches uploaded content
                with open(download_path, 'rb') as f:
                    downloaded_content = f.read()
                
                assert downloaded_content == test_content, "Downloaded content doesn't match uploaded content"
                
                # Clean up S3 object
                s3_client.delete_object(Bucket=bucket_name, Key=test_key)
                
            finally:
                # Clean up temporary files
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                if os.path.exists(download_path):
                    os.unlink(download_path)
                    
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '403':
                pytest.fail(f"Access denied during S3 operations. Check your permissions.")
            else:
                pytest.fail(f"S3 operation failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error during S3 test: {e}")

    def test_s3_config_validation(self, use_s3, s3_config):
        """Test that S3 configuration is valid when enabled"""
        if not use_s3:
            pytest.skip("S3 is disabled in configuration")
            
        # Check required configuration fields
        assert "bucket_name" in s3_config, "S3 bucket_name is required"
        assert s3_config["bucket_name"].strip(), "S3 bucket_name cannot be empty"
        
        # Check optional fields have reasonable defaults
        region_name = s3_config.get("region_name", "us-east-1")
        assert region_name.strip(), "S3 region_name cannot be empty"
        
        # Validate prefix format if provided
        prefix = s3_config.get("prefix", "")
        if prefix and not prefix.endswith("/"):
            # This is not an error, but log a warning that prefix should end with "/"
            pass

    def test_s3_skipped_when_disabled(self, use_s3):
        """Test that S3 tests are skipped when disabled"""
        if use_s3:
            pytest.skip("S3 is enabled, this test is for disabled state")
            
        # This test passes if we reach here, meaning S3 is properly disabled
        assert True

    def test_s3_handler_initialization(self, config):
        """Test S3Handler class initialization with current config"""
        try:
            # Import the S3Handler class
            import sys
            sys.path.append(str(Path(__file__).parent.parent))
            from modules.s3_handler import S3Handler
            
            # Test initialization
            s3_handler = S3Handler(config)
            
            # Check that handler respects the use_s3 setting
            expected_enabled = config.get("use_s3", False)
            assert s3_handler.enabled == expected_enabled, f"S3Handler enabled state should match config use_s3 setting"
            
            if expected_enabled:
                # If S3 is enabled, check that configuration was loaded
                s3_config = config.get("s3", {})
                bucket_name = s3_config.get("bucket_name", "")
                
                if bucket_name:
                    assert s3_handler.bucket_name == bucket_name, "S3Handler should load bucket name from config"
                else:
                    # If no bucket name, handler should be disabled
                    assert not s3_handler.enabled, "S3Handler should be disabled when bucket_name is missing"
                    
        except ImportError:
            pytest.fail("Could not import S3Handler class")
        except Exception as e:
            pytest.fail(f"Error testing S3Handler initialization: {e}")