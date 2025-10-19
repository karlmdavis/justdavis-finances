"""Tests for YNAB flow node OutputInfo implementations."""

import tempfile
from pathlib import Path

import pytest

from finances.ynab.flow import YnabSyncFlowNode, RetirementUpdateFlowNode
from finances.ynab.split_generation_flow import SplitGenerationFlowNode


def test_ynab_sync_output_info_is_data_ready_returns_true_with_json_cache():
    """Verify is_data_ready returns True when all three cache files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        cache_dir = data_dir / "ynab" / "cache"
        cache_dir.mkdir(parents=True)

        # Create all three required cache files
        (cache_dir / "transactions.json").write_text('[]')
        (cache_dir / "accounts.json").write_text('{"accounts": []}')
        (cache_dir / "categories.json").write_text('{"category_groups": []}')

        node = YnabSyncFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_ynab_sync_output_info_get_output_files_counts_transactions():
    """Verify get_output_files returns correct counts from different JSON structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        cache_dir = data_dir / "ynab" / "cache"
        cache_dir.mkdir(parents=True)

        # transactions.json: direct array
        (cache_dir / "transactions.json").write_text('[{"id": "1"}, {"id": "2"}, {"id": "3"}]')

        # accounts.json: nested in "accounts" key
        (cache_dir / "accounts.json").write_text('{"accounts": [{"id": "a"}, {"id": "b"}]}')

        # categories.json: nested in "category_groups" key
        (cache_dir / "categories.json").write_text('{"category_groups": [{"id": "c"}]}')

        node = YnabSyncFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 3

        # Verify transactions count (direct array)
        tx_file = next(f for f in files if f.path.name == "transactions.json")
        assert tx_file.record_count == 3

        # Verify accounts count (nested)
        acc_file = next(f for f in files if f.path.name == "accounts.json")
        assert acc_file.record_count == 2

        # Verify categories count (nested)
        cat_file = next(f for f in files if f.path.name == "categories.json")
        assert cat_file.record_count == 1


def test_retirement_update_output_info_is_data_ready_returns_true_with_edits():
    """Verify is_data_ready returns True when retirement edit files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        edits_dir = data_dir / "ynab" / "edits"
        edits_dir.mkdir(parents=True)

        # Create retirement edit file (glob pattern: *retirement*.json)
        (edits_dir / "2024-10-19_retirement_updates.json").write_text('[]')

        node = RetirementUpdateFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_split_generation_output_info_is_data_ready_returns_true_with_splits():
    """Verify is_data_ready returns True when split edit files with 'edits' key exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        edits_dir = data_dir / "ynab" / "edits"
        edits_dir.mkdir(parents=True)

        # Create split edit file with "edits" key
        (edits_dir / "2024-10-19_split_edits.json").write_text('{"edits": [{"id": "1"}]}')

        node = SplitGenerationFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True
