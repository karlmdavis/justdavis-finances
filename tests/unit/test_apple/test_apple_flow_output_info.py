"""Tests for Apple flow node OutputInfo implementations."""

import tempfile
from pathlib import Path

import pytest

from finances.apple.flow import AppleEmailFetchFlowNode, AppleReceiptParsingFlowNode, AppleMatchingFlowNode


def test_apple_email_output_info_is_data_ready_returns_false_when_no_files():
    """Verify is_data_ready returns False when no .eml files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        node = AppleEmailFetchFlowNode(data_dir)

        info = node.get_output_info()

        assert info.is_data_ready() is False


def test_apple_email_output_info_is_data_ready_returns_true_with_eml_files():
    """Verify is_data_ready returns True when .eml files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        emails_dir = data_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)

        # Create .eml file
        (emails_dir / "test_email.eml").write_text("From: test@apple.com")

        node = AppleEmailFetchFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_apple_email_output_info_get_output_files_returns_empty_when_no_dir():
    """Verify get_output_files returns empty list when directory doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        node = AppleEmailFetchFlowNode(data_dir)

        info = node.get_output_info()
        files = info.get_output_files()

        assert files == []


def test_apple_email_output_info_get_output_files_returns_eml_files():
    """Verify get_output_files returns all .eml files with record counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        emails_dir = data_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)

        # Create .eml files
        (emails_dir / "email1.eml").write_text("From: test1@apple.com")
        (emails_dir / "email2.eml").write_text("From: test2@apple.com")

        node = AppleEmailFetchFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 2
        assert all(f.path.suffix == ".eml" for f in files)
        assert all(f.record_count == 1 for f in files)


def test_apple_receipt_output_info_is_data_ready_returns_true_with_html_files():
    """Verify is_data_ready returns True when .json files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        exports_dir = data_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)

        # Create .json file (what dependencies consume)
        (exports_dir / "receipt.json").write_text('{"receipts": []}')

        node = AppleReceiptParsingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_apple_receipt_output_info_is_data_ready_returns_false_without_html():
    """Verify is_data_ready returns False even if other files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        exports_dir = data_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)

        # Create .eml and .txt but no .html
        (exports_dir / "receipt.eml").write_text("Email content")
        (exports_dir / "receipt.txt").write_text("Text content")

        node = AppleReceiptParsingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is False


def test_apple_receipt_output_info_get_output_files_returns_all_types():
    """Verify get_output_files returns .json files (what dependencies consume)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        exports_dir = data_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)

        # Create .json file (what dependencies consume)
        (exports_dir / "receipt.json").write_text('{"receipts": []}')
        # Also create other file types that should be ignored
        (exports_dir / "receipt.eml").write_text("Email content")
        (exports_dir / "receipt.txt").write_text("Text content")

        node = AppleReceiptParsingFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        # Only .json files should be returned
        assert len(files) == 1
        assert files[0].path.suffix == ".json"


def test_apple_matching_output_info_is_data_ready_returns_true_with_json_files():
    """Verify is_data_ready returns True when .json match files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "apple" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON
        (matches_dir / "2024-10-19_results.json").write_text('{"matches": []}')

        node = AppleMatchingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_apple_matching_output_info_get_output_files_returns_json_with_match_counts():
    """Verify get_output_files returns .json files with match counts from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "apple" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON with matches
        import json

        match_data = {"matches": [{"tx_id": "1"}, {"tx_id": "2"}, {"tx_id": "3"}]}
        (matches_dir / "2024-10-19_results.json").write_text(json.dumps(match_data))

        node = AppleMatchingFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 1
        assert files[0].path.suffix == ".json"
        assert files[0].record_count == 3  # 3 matches
