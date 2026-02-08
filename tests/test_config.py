"""Tests for configuration management."""

import yaml
import pytest
from modules.config import load_config, resolve_aliases, _validate_config, DEFAULT_CONFIG


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


class TestNewDefaults:
    """Verify new config defaults."""

    def test_scrape_mode_default(self, tmp_path):
        config = load_config(tmp_path / "config.yaml")
        assert config["scrape_mode"] == "update"

    def test_max_reviews_default(self, tmp_path):
        config = load_config(tmp_path / "config.yaml")
        assert config["max_reviews"] == 0

    def test_max_scroll_attempts_default(self, tmp_path):
        config = load_config(tmp_path / "config.yaml")
        assert config["max_scroll_attempts"] == 50

    def test_scroll_idle_limit_default(self, tmp_path):
        config = load_config(tmp_path / "config.yaml")
        assert config["scroll_idle_limit"] == 15


class TestAliasResolution:
    """Verify legacy key → new key mapping."""

    def test_old_overwrite_maps_to_full_mode(self, tmp_path):
        """overwrite_existing: true → scrape_mode: full."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({"overwrite_existing": True}))
        config = load_config(cfg_path)
        assert config["scrape_mode"] == "full"

    def test_old_stop_on_match_sets_threshold(self, tmp_path):
        """stop_on_match: true with stop_threshold 0 → stop_threshold: 3."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({"stop_on_match": True, "stop_threshold": 0}))
        config = load_config(cfg_path)
        assert config["stop_threshold"] == 3

    def test_new_name_wins(self, tmp_path):
        """When both old and new keys specified, new key wins."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({
            "overwrite_existing": True,
            "scrape_mode": "new_only",
        }))
        config = load_config(cfg_path)
        assert config["scrape_mode"] == "new_only"

    def test_resolve_aliases_no_op_when_clean(self):
        """No warnings when config has no legacy keys."""
        config = {"scrape_mode": "update", "stop_threshold": 3}
        resolve_aliases(config)
        assert config["scrape_mode"] == "update"
        assert config["stop_threshold"] == 3


class TestValidation:
    """Verify config validation and fallback behavior."""

    def test_invalid_scrape_mode_fallback(self):
        config = {"scrape_mode": "invalid_mode"}
        _validate_config(config)
        assert config["scrape_mode"] == "update"

    def test_scrape_mode_validation_accepts_valid(self):
        for mode in ("new_only", "update", "full"):
            config = {"scrape_mode": mode}
            _validate_config(config)
            assert config["scrape_mode"] == mode

    def test_negative_int_falls_back(self):
        config = {"max_reviews": -1, "stop_threshold": -5,
                  "max_scroll_attempts": -10, "scroll_idle_limit": -1}
        _validate_config(config)
        assert config["max_reviews"] == DEFAULT_CONFIG["max_reviews"]
        assert config["stop_threshold"] == DEFAULT_CONFIG["stop_threshold"]

    def test_non_int_falls_back(self):
        config = {"max_reviews": "abc"}
        _validate_config(config)
        assert config["max_reviews"] == DEFAULT_CONFIG["max_reviews"]
