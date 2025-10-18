#!/usr/bin/env python3
"""
Tests for DataStore interface contracts across all domains.

These tests verify that all DataStore implementations follow the same interface
contract, ensuring consistent behavior across Amazon, Apple, YNAB, and Analysis domains.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from finances.amazon.datastore import AmazonMatchResultsStore, AmazonRawDataStore
from finances.analysis.datastore import CashFlowResultsStore
from finances.apple.datastore import (
    AppleEmailStore,
    AppleMatchResultsStore,
    AppleReceiptStore,
)
from finances.ynab.datastore import YnabCacheStore, YnabEditsStore


@pytest.mark.parametrize(
    "store_class,base_path",
    [
        (AmazonRawDataStore, "amazon/raw"),
        (AmazonMatchResultsStore, "amazon/transaction_matches"),
        (AppleEmailStore, "apple/emails"),
        (AppleReceiptStore, "apple/exports"),
        (AppleMatchResultsStore, "apple/transaction_matches"),
        (YnabCacheStore, "ynab/cache"),
        (YnabEditsStore, "ynab/edits"),
        (CashFlowResultsStore, "cash_flow/charts"),
    ],
    ids=[
        "AmazonRawDataStore",
        "AmazonMatchResultsStore",
        "AppleEmailStore",
        "AppleReceiptStore",
        "AppleMatchResultsStore",
        "YnabCacheStore",
        "YnabEditsStore",
        "CashFlowResultsStore",
    ],
)
def test_datastore_load_raises_when_no_data(store_class, base_path):
    """Test that all datastores raise FileNotFoundError when load() called with no data."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store_path = temp_dir / base_path
        store = store_class(store_path)

        with pytest.raises(FileNotFoundError):
            store.load()
    finally:
        shutil.rmtree(temp_dir)
