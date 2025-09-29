#!/usr/bin/env python3
"""
Unit tests for retirement CLI command handling.

Tests for the retirement CLI functions and their integration with the flow system.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from finances.cli.retirement import update


class TestRetirementCLI:
    """Test retirement CLI command functionality."""

    def test_update_without_date_parameter_should_not_fail(self):
        """
        Test that the retirement update command doesn't fail when no date is provided.

        This test reproduces the 'NoneType' object has no attribute 'today' error
        that occurs when the date parameter shadows the date class import.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock config
            mock_config = MagicMock()
            mock_config.data_dir = temp_path

            # Create retirement directory structure
            retirement_dir = temp_path / "retirement"
            retirement_dir.mkdir(parents=True)

            # Create empty accounts config
            accounts_config = retirement_dir / "accounts.yaml"
            accounts_config.write_text("accounts: []\n")

            with patch('finances.cli.retirement.get_config', return_value=mock_config):
                with patch('finances.cli.retirement.RetirementTracker') as mock_tracker:
                    # Mock the tracker to return empty accounts list
                    mock_tracker_instance = MagicMock()
                    mock_tracker_instance.get_active_accounts.return_value = []
                    mock_tracker.return_value = mock_tracker_instance

                    # Create a mock click context
                    runner = CliRunner()

                    # This should NOT raise an AttributeError about 'NoneType' and 'today'
                    # When the bug exists, this call will fail with:
                    # AttributeError: 'NoneType' object has no attribute 'today'
                    result = runner.invoke(update, ['--non-interactive'])

                    # The command should complete without the AttributeError
                    # It might exit with a different code due to no accounts, but
                    # it should not crash with the 'NoneType' today error
                    assert "'NoneType' object has no attribute 'today'" not in str(result.exception) if result.exception else True

    def test_update_with_date_parameter_works(self):
        """Test that providing a date parameter works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock config
            mock_config = MagicMock()
            mock_config.data_dir = temp_path

            # Create retirement directory structure
            retirement_dir = temp_path / "retirement"
            retirement_dir.mkdir(parents=True)

            # Create empty accounts config
            accounts_config = retirement_dir / "accounts.yaml"
            accounts_config.write_text("accounts: []\n")

            with patch('finances.cli.retirement.get_config', return_value=mock_config):
                with patch('finances.cli.retirement.RetirementTracker') as mock_tracker:
                    # Mock the tracker to return empty accounts list
                    mock_tracker_instance = MagicMock()
                    mock_tracker_instance.get_active_accounts.return_value = []
                    mock_tracker.return_value = mock_tracker_instance

                    # Create a mock click context
                    runner = CliRunner()

                    # This should work fine with a date parameter
                    result = runner.invoke(update, ['--date', '2024-07-31', '--non-interactive'])

                    # Should not have the 'NoneType' error
                    assert "'NoneType' object has no attribute 'today'" not in str(result.exception) if result.exception else True

    def test_date_shadowing_issue_reproduction(self):
        """
        Direct test to reproduce the date shadowing issue.

        This test directly calls the problematic code path to ensure
        we catch the exact issue that's causing the flow failure.
        """
        # Import the function directly
        from finances.cli.retirement import update

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock config
            mock_config = MagicMock()
            mock_config.data_dir = temp_path

            with patch('finances.cli.retirement.get_config', return_value=mock_config):
                with patch('finances.cli.retirement.RetirementTracker') as mock_tracker:
                    # Mock the tracker
                    mock_tracker_instance = MagicMock()
                    mock_tracker_instance.get_active_accounts.return_value = []
                    mock_tracker.return_value = mock_tracker_instance

                    # Create a mock click context
                    mock_ctx = MagicMock()
                    mock_ctx.obj = {'verbose': False}

                    # Try to call the function with date=None (the problematic case)
                    # This should reproduce the exact error from the flow system
                    try:
                        update(
                            ctx=mock_ctx,
                            interactive=False,
                            account=(),
                            date=None,  # This is the problematic case
                            output_file=None,
                            verbose=False
                        )
                        # If we get here without exception, the bug might be fixed
                        assert True
                    except AttributeError as e:
                        # If we get the expected error, the test has reproduced the issue
                        if "'NoneType' object has no attribute 'today'" in str(e):
                            pytest.fail(f"Reproduced the date shadowing bug: {e}")
                        else:
                            # Different AttributeError, re-raise
                            raise
                    except Exception as e:
                        # Other exceptions are fine - we just want to avoid the specific
                        # 'NoneType' object has no attribute 'today' error
                        assert "'NoneType' object has no attribute 'today'" not in str(e)