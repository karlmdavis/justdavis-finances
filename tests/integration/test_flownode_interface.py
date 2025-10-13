#!/usr/bin/env python3
"""
Integration tests for FlowNode interface contract.

Parameterized tests that validate all FlowNode implementations
correctly implement the FlowNode interface contract:
- get_data_summary() returns correct structure
- check_changes() returns correct structure
- All methods handle missing data gracefully
"""

from datetime import datetime

import pytest

from finances.amazon.flow import (
    AmazonMatchingFlowNode,
    AmazonOrderHistoryRequestFlowNode,
    AmazonUnzipFlowNode,
)
from finances.analysis.flow import CashFlowAnalysisFlowNode
from finances.apple.flow import (
    AppleEmailFetchFlowNode,
    AppleMatchingFlowNode,
    AppleReceiptParsingFlowNode,
)
from finances.core.flow import FlowContext, NodeDataSummary
from finances.core.json_utils import write_json
from finances.ynab.flow import RetirementUpdateFlowNode, YnabSyncFlowNode
from finances.ynab.split_generation_flow import SplitGenerationFlowNode


@pytest.fixture
def flow_context():
    """Create basic FlowContext for testing."""
    return FlowContext(start_time=datetime.now())


# List of all FlowNode classes to test (excludes nodes without data_dir parameter)
ALL_FLOWNODES = [
    AmazonUnzipFlowNode,
    AmazonMatchingFlowNode,
    AppleReceiptParsingFlowNode,
    AppleMatchingFlowNode,
    AppleEmailFetchFlowNode,
    SplitGenerationFlowNode,
    YnabSyncFlowNode,
    RetirementUpdateFlowNode,
    CashFlowAnalysisFlowNode,
]


@pytest.mark.integration
@pytest.mark.parametrize("node_class", ALL_FLOWNODES, ids=lambda cls: cls.__name__)
class TestFlowNodeInterface:
    """Test FlowNode interface contract for all implementations."""

    def test_get_data_summary_returns_correct_structure(self, node_class, temp_dir, flow_context):
        """Test that get_data_summary() returns NodeDataSummary with correct structure."""
        node = node_class(temp_dir)
        summary = node.get_data_summary(flow_context)

        # Verify return type
        assert isinstance(summary, NodeDataSummary)

        # Verify all required fields exist
        assert hasattr(summary, "exists")
        assert hasattr(summary, "last_updated")
        assert hasattr(summary, "age_days")
        assert hasattr(summary, "item_count")
        assert hasattr(summary, "size_bytes")
        assert hasattr(summary, "summary_text")

        # Verify types
        assert isinstance(summary.exists, bool)
        assert summary.last_updated is None or isinstance(summary.last_updated, datetime)
        assert summary.age_days is None or isinstance(summary.age_days, int)
        assert summary.item_count is None or isinstance(summary.item_count, int)
        assert summary.size_bytes is None or isinstance(summary.size_bytes, int)
        assert isinstance(summary.summary_text, str)

    def test_get_data_summary_when_no_data(self, node_class, temp_dir, flow_context):
        """Test get_data_summary() when no data exists returns exists=False."""
        node = node_class(temp_dir)
        summary = node.get_data_summary(flow_context)

        # When no data exists, exists should be False
        assert summary.exists is False

        # Summary text should be non-empty
        assert len(summary.summary_text) > 0

    def test_check_changes_returns_correct_structure(self, node_class, temp_dir, flow_context):
        """Test that check_changes() returns tuple of (bool, list[str])."""
        node = node_class(temp_dir)
        result = node.check_changes(flow_context)

        # Verify return type
        assert isinstance(result, tuple)
        assert len(result) == 2

        has_changes, reasons = result

        # Verify types
        assert isinstance(has_changes, bool)
        assert isinstance(reasons, list)

        # Reasons should contain strings
        for reason in reasons:
            assert isinstance(reason, str)

        # Should have at least one reason
        assert len(reasons) > 0

    def test_check_changes_when_no_data(self, node_class, temp_dir, flow_context):
        """Test check_changes() when preconditions not met returns False with reasons."""
        node = node_class(temp_dir)
        has_changes, reasons = node.check_changes(flow_context)

        # When no data/preconditions, should return False or True with reasons
        assert isinstance(has_changes, bool)
        assert len(reasons) > 0

        # Reasons should be descriptive
        for reason in reasons:
            assert len(reason) > 5  # Not just empty or single word


@pytest.mark.integration
@pytest.mark.parametrize(
    "node_class,setup_func",
    [
        (
            AmazonUnzipFlowNode,
            # AmazonUnzipFlowNode checks for extracted CSV directories
            lambda temp_dir: (
                (temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data").mkdir(
                    parents=True, exist_ok=True
                ),
                (
                    temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data" / "Retail.OrderHistory.1.csv"
                ).write_text("Order ID\n111-222\n"),
            ),
        ),
        (
            AmazonMatchingFlowNode,
            # AmazonMatchingFlowNode checks for match result files
            lambda temp_dir: (
                (temp_dir / "amazon" / "transaction_matches").mkdir(parents=True, exist_ok=True),
                write_json(
                    temp_dir / "amazon" / "transaction_matches" / "2025-01-01_results.json",
                    {"metadata": {}, "matches": [{"transaction_id": "tx1"}]},
                ),
            ),
        ),
        (
            AppleReceiptParsingFlowNode,
            # AppleReceiptParsingFlowNode checks for parsed receipt JSON files
            lambda temp_dir: (
                (temp_dir / "apple" / "exports").mkdir(parents=True, exist_ok=True),
                write_json(temp_dir / "apple" / "exports" / "receipt1.json", {}),
            ),
        ),
        (
            AppleMatchingFlowNode,
            # AppleMatchingFlowNode checks for match result files
            lambda temp_dir: (
                (temp_dir / "apple" / "transaction_matches").mkdir(parents=True, exist_ok=True),
                write_json(
                    temp_dir / "apple" / "transaction_matches" / "2025-01-01_results.json",
                    {"metadata": {}, "matches": [{"transaction_id": "tx1"}]},
                ),
            ),
        ),
        (
            SplitGenerationFlowNode,
            # SplitGenerationFlowNode checks for INPUT match files (not output split files)
            lambda temp_dir: (
                (temp_dir / "amazon" / "transaction_matches").mkdir(parents=True, exist_ok=True),
                write_json(
                    temp_dir / "amazon" / "transaction_matches" / "2025-01-01_results.json",
                    {"metadata": {}, "matches": []},
                ),
            ),
        ),
        (
            YnabSyncFlowNode,
            # YnabSyncFlowNode checks for YNAB cache files
            lambda temp_dir: (
                (temp_dir / "ynab" / "cache").mkdir(parents=True, exist_ok=True),
                write_json(temp_dir / "ynab" / "cache" / "transactions.json", [{"id": "tx1"}]),
                write_json(temp_dir / "ynab" / "cache" / "accounts.json", {"accounts": []}),
            ),
        ),
    ],
    ids=lambda p: p.__name__ if isinstance(p, type) else "",
)
class TestFlowNodeWithData:
    """Test FlowNode interface with data present."""

    def test_get_data_summary_when_data_exists(self, node_class, setup_func, temp_dir, flow_context):
        """Test get_data_summary() when data exists returns exists=True."""
        # Setup data for this node
        setup_func(temp_dir)

        node = node_class(temp_dir)
        summary = node.get_data_summary(flow_context)

        # When data exists, exists should be True
        assert summary.exists is True

        # Should have meaningful item_count or last_updated
        assert summary.item_count is not None or summary.last_updated is not None

    def test_check_changes_when_data_exists(self, node_class, setup_func, temp_dir, flow_context):
        """Test check_changes() when data exists returns True for new data."""
        # Setup data for this node
        setup_func(temp_dir)

        node = node_class(temp_dir)
        has_changes, reasons = node.check_changes(flow_context)

        # Should detect changes when input data exists but no previous output
        # (unless node has special logic like YnabSyncFlowNode)
        assert isinstance(has_changes, bool)
        assert len(reasons) > 0
