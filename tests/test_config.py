"""Tests for configuration management."""

import pytest
from modules.config import load_config, DEFAULT_CONFIG


class TestConfigDeepCopy:
    """Verify the shallow copy bug is fixed."""

    def test_nested_dict_independence(self, tmp_path):
        """Modifying config A should not affect config B."""
        config_path = tmp_path / "config.yaml"
        config_a = load_config(config_path)
        config_b = load_config(config_path)

        # Modify nested dict in config_a
        config_a["mongodb"]["uri"] = "mongodb://modified:27017"

        # config_b should be unaffected
        assert config_b["mongodb"]["uri"] != "mongodb://modified:27017"

    def test_default_config_unchanged(self, tmp_path):
        """Loading config should not modify DEFAULT_CONFIG."""
        config_path = tmp_path / "config.yaml"
        original_uri = DEFAULT_CONFIG["mongodb"]["uri"]

        config = load_config(config_path)
        config["mongodb"]["uri"] = "mongodb://changed:9999"

        assert DEFAULT_CONFIG["mongodb"]["uri"] == original_uri

    def test_db_path_default(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config = load_config(config_path)
        assert config.get("db_path") == "reviews.db"

    def test_stop_threshold_default(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config = load_config(config_path)
        assert config.get("stop_threshold") == 3
