"""Tests for unified S3 provider config (AWS / MinIO / R2)."""

from unittest.mock import patch, MagicMock

import pytest

from modules.s3_handler import _resolve_s3_config, S3Handler


# ---------------------------------------------------------------------------
# _resolve_s3_config
# ---------------------------------------------------------------------------

class TestResolveS3Config:
    def test_aws_default_no_changes(self):
        cfg = _resolve_s3_config({"bucket_name": "b"})
        assert cfg["bucket_name"] == "b"
        assert cfg.get("path_style") is None or cfg.get("path_style") is False

    def test_minio_preset(self):
        cfg = _resolve_s3_config({"provider": "minio", "bucket_name": "b"})
        assert cfg["path_style"] is True
        assert cfg["acl"] == ""
        assert cfg["bucket_name"] == "b"

    def test_r2_preset(self):
        cfg = _resolve_s3_config({"provider": "r2", "bucket_name": "b"})
        assert cfg["region_name"] == "auto"
        assert cfg["acl"] == ""

    def test_explicit_overrides_preset(self):
        cfg = _resolve_s3_config({
            "provider": "minio",
            "path_style": False,
            "acl": "private",
        })
        assert cfg["path_style"] is False
        assert cfg["acl"] == "private"

    def test_unknown_provider_no_crash(self):
        cfg = _resolve_s3_config({"provider": "unknown", "bucket_name": "b"})
        assert cfg["bucket_name"] == "b"

    def test_none_values_skipped(self):
        cfg = _resolve_s3_config({"provider": "minio", "endpoint_url": None})
        assert "endpoint_url" not in cfg


# ---------------------------------------------------------------------------
# S3Handler URL generation
# ---------------------------------------------------------------------------

class TestS3UrlGeneration:
    def _make_handler(self, s3_overrides=None):
        """Create an S3Handler with mocked boto3 client."""
        s3_cfg = {
            "bucket_name": "test-bucket",
            "region_name": "us-west-2",
            "prefix": "reviews/",
            **(s3_overrides or {}),
        }
        config = {"use_s3": True, "s3": s3_cfg}
        with patch("modules.s3_handler.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            handler = S3Handler(config)
        return handler

    def test_aws_url(self):
        h = self._make_handler()
        url = h.get_s3_url("reviews/img.jpg")
        assert url == "https://test-bucket.s3.us-west-2.amazonaws.com/reviews/img.jpg"

    def test_custom_base_url(self):
        h = self._make_handler({"s3_base_url": "https://cdn.example.com"})
        url = h.get_s3_url("reviews/img.jpg")
        assert url == "https://cdn.example.com/reviews/img.jpg"

    def test_endpoint_url(self):
        h = self._make_handler({"endpoint_url": "http://localhost:9000"})
        url = h.get_s3_url("reviews/img.jpg")
        assert url == "http://localhost:9000/test-bucket/reviews/img.jpg"

    def test_base_url_takes_precedence_over_endpoint(self):
        h = self._make_handler({
            "endpoint_url": "http://localhost:9000",
            "s3_base_url": "https://cdn.example.com",
        })
        url = h.get_s3_url("reviews/img.jpg")
        assert url == "https://cdn.example.com/reviews/img.jpg"


# ---------------------------------------------------------------------------
# ACL handling
# ---------------------------------------------------------------------------

class TestACLHandling:
    def _make_handler(self, s3_overrides=None):
        s3_cfg = {
            "bucket_name": "test-bucket",
            "prefix": "reviews/",
            **(s3_overrides or {}),
        }
        config = {"use_s3": True, "s3": s3_cfg}
        with patch("modules.s3_handler.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            handler = S3Handler(config)
        return handler

    def test_default_acl_public_read(self):
        h = self._make_handler()
        args = h._build_extra_args()
        assert args["ACL"] == "public-read"

    def test_empty_acl_omits_acl_key(self):
        h = self._make_handler({"acl": ""})
        args = h._build_extra_args()
        assert "ACL" not in args

    def test_custom_acl(self):
        h = self._make_handler({"acl": "private"})
        args = h._build_extra_args()
        assert args["ACL"] == "private"

    def test_minio_preset_skips_acl(self):
        h = self._make_handler({"provider": "minio"})
        args = h._build_extra_args()
        assert "ACL" not in args

    def test_r2_preset_skips_acl(self):
        h = self._make_handler({"provider": "r2"})
        args = h._build_extra_args()
        assert "ACL" not in args


# ---------------------------------------------------------------------------
# Client init kwargs
# ---------------------------------------------------------------------------

class TestClientInit:
    def test_path_style_config(self):
        config = {
            "use_s3": True,
            "s3": {
                "provider": "minio",
                "bucket_name": "b",
                "endpoint_url": "http://localhost:9000",
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
            },
        }
        with patch("modules.s3_handler.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            S3Handler(config)

            call_kwargs = mock_boto3.client.call_args[1]
            assert call_kwargs["endpoint_url"] == "http://localhost:9000"
            assert call_kwargs["config"].s3["addressing_style"] == "path"

    def test_aws_no_extra_kwargs(self):
        config = {
            "use_s3": True,
            "s3": {
                "bucket_name": "b",
                "aws_access_key_id": "key",
                "aws_secret_access_key": "secret",
            },
        }
        with patch("modules.s3_handler.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            S3Handler(config)

            call_kwargs = mock_boto3.client.call_args[1]
            assert "endpoint_url" not in call_kwargs
            assert "config" not in call_kwargs
