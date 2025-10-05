#!/usr/bin/env python3
"""
Integration tests for YNAB CLI command parameters.

Tests parameter acceptance and basic behavior for YNAB CLI commands.
Note: Some commands have placeholder implementations, so tests verify
parameter handling rather than full functionality.
"""

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from finances.cli.ynab import ynab


class TestYNABCLIParameters:
    """Test YNAB CLI command parameter handling."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_generate_splits_accepts_required_parameters(self):
        """Test ynab generate-splits accepts required --input-file parameter."""
        # Create a dummy match results file
        match_file = self.temp_dir / "amazon_matches.json"
        match_data = {
            "metadata": {"start_date": "2024-07-01", "end_date": "2024-07-31"},
            "matches": [],
        }
        match_file.write_text(json.dumps(match_data))

        result = self.runner.invoke(
            ynab,
            ["generate-splits", "--input-file", str(match_file), "--output-dir", str(self.temp_dir)],
            obj={},
        )

        # Should accept parameters
        assert result.exit_code == 0

    def test_generate_splits_confidence_threshold(self):
        """Test ynab generate-splits --confidence-threshold parameter is accepted."""
        match_file = self.temp_dir / "amazon_matches.json"
        match_data = {"metadata": {}, "matches": []}
        match_file.write_text(json.dumps(match_data))

        result = self.runner.invoke(
            ynab,
            [
                "generate-splits",
                "--input-file",
                str(match_file),
                "--output-dir",
                str(self.temp_dir),
                "--confidence-threshold",
                "0.85",
            ],
            obj={},
        )

        assert result.exit_code == 0

    def test_generate_splits_dry_run_flag(self):
        """Test ynab generate-splits --dry-run flag is accepted."""
        match_file = self.temp_dir / "amazon_matches.json"
        match_data = {"metadata": {}, "matches": []}
        match_file.write_text(json.dumps(match_data))

        result = self.runner.invoke(
            ynab,
            [
                "generate-splits",
                "--input-file",
                str(match_file),
                "--output-dir",
                str(self.temp_dir),
                "--dry-run",
            ],
            obj={},
        )

        assert result.exit_code == 0

    def test_generate_splits_verbose_flag(self):
        """Test ynab generate-splits --verbose flag is accepted."""
        match_file = self.temp_dir / "amazon_matches.json"
        match_data = {"metadata": {}, "matches": []}
        match_file.write_text(json.dumps(match_data))

        result = self.runner.invoke(
            ynab,
            [
                "generate-splits",
                "--input-file",
                str(match_file),
                "--output-dir",
                str(self.temp_dir),
                "--verbose",
            ],
            obj={},
        )

        assert result.exit_code == 0

    def test_sync_cache_days_parameter(self):
        """Test ynab sync-cache --days parameter is accepted."""
        result = self.runner.invoke(ynab, ["sync-cache", "--days", "30"])

        # Command should accept parameter (implementation is placeholder)
        assert result.exit_code in [0, 1]

    def test_sync_cache_verbose_flag(self):
        """Test ynab sync-cache --verbose flag is accepted."""
        result = self.runner.invoke(ynab, ["sync-cache", "--verbose"])

        assert result.exit_code in [0, 1]
