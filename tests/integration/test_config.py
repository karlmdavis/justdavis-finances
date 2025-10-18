#!/usr/bin/env python3
"""
Integration tests for configuration module.

Tests configuration loading and path resolution structure.
"""

from pathlib import Path

import pytest

from finances.core.config import get_config, get_data_dir, is_development, is_test, is_production


@pytest.mark.integration
class TestConfigLoading:
    """Test configuration loading and structure."""

    def test_config_loads_successfully(self):
        """Test that config loads without errors."""
        config = get_config()

        # Verify config has expected structure
        assert config is not None
        assert hasattr(config, "data_dir")
        assert hasattr(config, "ynab")
        assert hasattr(config, "environment")

    def test_config_data_directory_is_path(self):
        """Test that data directory is resolved as Path."""
        config = get_config()

        assert isinstance(config.data_dir, Path)
        assert config.data_dir.is_absolute()

    def test_config_has_ynab_configuration(self):
        """Test that YNAB configuration is present."""
        config = get_config()

        assert hasattr(config.ynab, "api_token")
        assert hasattr(config.ynab, "base_url")

    def test_environment_detection_functions(self):
        """Test environment detection helper functions."""
        # These should return booleans without errors
        dev_result = is_development()
        test_result = is_test()
        prod_result = is_production()

        assert isinstance(dev_result, bool)
        assert isinstance(test_result, bool)
        assert isinstance(prod_result, bool)

    def test_get_data_dir_returns_absolute_path(self):
        """Test get_data_dir() returns absolute path."""
        data_dir = get_data_dir()

        assert isinstance(data_dir, Path)
        assert data_dir.is_absolute()
