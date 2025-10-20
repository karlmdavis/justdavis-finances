"""Tests for NoOutputInfo (nodes with no persistent output)."""

from finances.core.flow import NoOutputInfo


def test_no_output_info_is_data_ready_returns_true():
    """Verify NoOutputInfo is always ready (no dependencies blocked)."""
    info = NoOutputInfo()
    assert info.is_data_ready() is True


def test_no_output_info_get_output_files_returns_empty():
    """Verify NoOutputInfo returns no files."""
    info = NoOutputInfo()
    assert info.get_output_files() == []
