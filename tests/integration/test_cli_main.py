#!/usr/bin/env python3
"""
Integration tests for CLI Main Entry Point

Tests end-to-end CLI command execution with real command invocation.
Focuses on meaningful workflows, not trivial code coverage.
"""

import subprocess

import pytest
from click.testing import CliRunner

from finances.cli.main import main


@pytest.mark.integration
class TestCLIMainIntegration:
    """Test main CLI entry point with real command execution."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_help_command_lists_all_subcommands(self):
        """Test finances --help shows all registered subcommands."""
        result = self.runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Davis Family Finances" in result.output

        # Verify all subcommands are listed
        expected_commands = ["amazon", "apple", "ynab", "cashflow", "retirement", "flow"]

        for command in expected_commands:
            assert command in result.output

    def test_version_command_shows_version_info(self):
        """Test finances --version displays version and author."""
        result = self.runner.invoke(main, ["version"])

        assert result.exit_code == 0
        assert "Davis Family Finances" in result.output
        assert "v" in result.output  # Version number with 'v' prefix
        assert "Author:" in result.output

    def test_config_command_shows_configuration(self):
        """Test finances config displays current configuration."""
        result = self.runner.invoke(main, ["config"])

        assert result.exit_code == 0
        assert "Current Configuration:" in result.output
        assert "Environment:" in result.output
        assert "Data Directory:" in result.output
        assert "Cache Directory:" in result.output
        assert "Output Directory:" in result.output
        assert "Debug Mode:" in result.output
        assert "Log Level:" in result.output

    def test_invalid_command_shows_error(self):
        """Test that invalid command shows helpful error."""
        result = self.runner.invoke(main, ["invalid-command"])

        assert result.exit_code != 0
        # Click shows "No such command" or similar error
        assert "Error" in result.output or "No such" in result.output

    def test_verbose_flag_enables_verbose_output(self):
        """Test --verbose flag enables detailed output."""
        result = self.runner.invoke(main, ["--verbose", "config"])

        assert result.exit_code == 0
        # Verbose mode should show environment and data directory on separate lines
        assert "Environment:" in result.output
        assert "Data directory:" in result.output
        # The config command also shows these, so we're verifying verbose adds extra info
        assert "Current Configuration:" in result.output

    def test_config_env_override_changes_environment(self):
        """Test --config-env flag overrides environment."""
        result = self.runner.invoke(main, ["--config-env", "test", "config"])

        assert result.exit_code == 0
        assert "Environment: test" in result.output

    def test_subprocess_execution_version(self):
        """Test actual CLI execution via subprocess for version command."""
        # This tests the actual CLI as it would be called from the command line
        result = subprocess.run(
            ["uv", "run", "finances", "version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "Davis Family Finances" in result.stdout
        assert "v" in result.stdout

    def test_subprocess_execution_help(self):
        """Test actual CLI execution via subprocess for help command."""
        result = subprocess.run(
            ["uv", "run", "finances", "--help"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "Davis Family Finances" in result.stdout
        assert "amazon" in result.stdout
        assert "apple" in result.stdout
        assert "ynab" in result.stdout

    def test_subcommand_help_accessible(self):
        """Test that subcommand help is accessible."""
        # Test a few key subcommands to verify they're properly registered
        subcommands = ["amazon", "apple", "ynab", "retirement", "cashflow", "flow"]

        for subcommand in subcommands:
            result = self.runner.invoke(main, [subcommand, "--help"])
            assert result.exit_code == 0
            # Each subcommand should show its own help text
            assert "Usage:" in result.output or "Commands:" in result.output

    def test_config_env_test_environment(self):
        """Test that test environment configuration works correctly."""
        result = self.runner.invoke(main, ["--config-env", "test", "config"])

        assert result.exit_code == 0
        output_lines = result.output.split("\n")

        # Verify test environment is set
        env_line = next(line for line in output_lines if "Environment:" in line)
        assert "test" in env_line

    def test_config_env_development_environment(self):
        """Test that development environment configuration works correctly."""
        result = self.runner.invoke(main, ["--config-env", "development", "config"])

        assert result.exit_code == 0
        # Note: autouse fixture in conftest.py overrides to test, so we just verify command executes
        # In real usage, this would set development environment
        assert "Environment:" in result.output
        assert "Current Configuration:" in result.output

    def test_multiple_global_options(self):
        """Test combining multiple global options."""
        result = self.runner.invoke(main, ["--config-env", "test", "--verbose", "config"])

        assert result.exit_code == 0
        # Should show both verbose output and test environment
        assert "Environment: test" in result.output
        assert "Data directory:" in result.output
        assert "Current Configuration:" in result.output
