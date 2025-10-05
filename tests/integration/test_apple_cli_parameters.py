#!/usr/bin/env python3
"""
Integration tests for Apple CLI command parameters.

Tests parameter acceptance and basic behavior for Apple CLI commands.
Note: Some commands have placeholder implementations, so tests verify
parameter handling rather than full functionality.
"""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from finances.cli.apple import apple


class TestAppleCLIParameters:
    """Test Apple CLI command parameter handling."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_parse_receipts_accepts_required_parameters(self):
        """Test apple parse-receipts accepts required --input-dir parameter."""
        # Create input directory
        input_dir = self.temp_dir / "input"
        input_dir.mkdir()

        result = self.runner.invoke(
            apple, ["parse-receipts", "--input-dir", str(input_dir), "--output-dir", str(self.temp_dir)]
        )

        # Should accept parameters (may have no emails, but that's OK)
        assert result.exit_code in [0, 1]

    def test_parse_receipts_verbose_flag(self):
        """Test apple parse-receipts --verbose flag is accepted."""
        input_dir = self.temp_dir / "input"
        input_dir.mkdir()

        result = self.runner.invoke(
            apple,
            [
                "parse-receipts",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(self.temp_dir),
                "--verbose",
            ],
        )

        assert result.exit_code in [0, 1]

    def test_match_accepts_date_range_parameters(self):
        """Test apple match accepts --start and --end parameters."""
        result = self.runner.invoke(
            apple,
            ["match", "--start", "2024-07-01", "--end", "2024-07-31", "--output-dir", str(self.temp_dir)],
        )

        # Command should accept parameters (implementation is placeholder)
        assert result.exit_code in [0, 1]

    def test_match_verbose_flag(self):
        """Test apple match --verbose flag is accepted."""
        result = self.runner.invoke(
            apple,
            [
                "match",
                "--start",
                "2024-07-01",
                "--end",
                "2024-07-31",
                "--output-dir",
                str(self.temp_dir),
                "--verbose",
            ],
        )

        assert result.exit_code in [0, 1]

    def test_match_apple_ids_filter(self):
        """Test apple match --apple-ids parameter is accepted."""
        result = self.runner.invoke(
            apple,
            [
                "match",
                "--start",
                "2024-07-01",
                "--end",
                "2024-07-31",
                "--output-dir",
                str(self.temp_dir),
                "--apple-ids",
                "karl@example.com",
                "--apple-ids",
                "erica@example.com",
            ],
        )

        assert result.exit_code in [0, 1]
