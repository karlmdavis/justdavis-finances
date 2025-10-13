#!/usr/bin/env python3
"""
Integration tests for YNAB FlowNode implementations.

Tests FlowNode orchestration logic with real filesystem operations.
"""

from datetime import datetime

import pytest

from finances.core.flow import FlowContext
from finances.core.json_utils import write_json
from finances.ynab.flow import YnabSyncFlowNode
from finances.ynab.split_generation_flow import SplitGenerationFlowNode


@pytest.fixture
def flow_context():
    """Create basic FlowContext for testing."""
    return FlowContext(start_time=datetime.now())


@pytest.mark.integration
@pytest.mark.ynab
class TestSplitGenerationFlowNode:
    """Integration tests for SplitGenerationFlowNode."""

    def test_execute_with_amazon_matches(self, temp_dir, flow_context):
        """Test execute() with Amazon match data."""
        node = SplitGenerationFlowNode(temp_dir)

        # Create Amazon match results
        amazon_matches_dir = temp_dir / "amazon" / "transaction_matches"
        amazon_matches_dir.mkdir(parents=True)
        write_json(
            amazon_matches_dir / "2025-01-01_results.json",
            {
                "matches": [
                    {
                        "ynab_transaction": {
                            "id": "tx123",
                            "amount": 2999,  # cents
                        },
                        "best_match": {"amazon_orders": [{"items": [{"name": "Test Item", "amount": 2999}]}]},
                    }
                ]
            },
        )

        # Execute
        result = node.execute(flow_context)

        # Verify
        assert result.success is True
        assert result.items_processed >= 1
        edits_dir = temp_dir / "ynab" / "edits"
        assert edits_dir.exists()
        assert len(list(edits_dir.glob("*.json"))) >= 1

    def test_execute_no_matches(self, temp_dir, flow_context):
        """Test execute() with no match files."""
        node = SplitGenerationFlowNode(temp_dir)

        result = node.execute(flow_context)

        assert result.success is True
        assert result.items_processed == 0

    def test_check_changes_no_matches(self, temp_dir, flow_context):
        """Test check_changes() with no match results."""
        node = SplitGenerationFlowNode(temp_dir)

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is False
        assert any("No match results" in r for r in reasons)

    def test_check_changes_no_edits(self, temp_dir, flow_context):
        """Test check_changes() with matches but no edits."""
        node = SplitGenerationFlowNode(temp_dir)

        # Create match files
        amazon_dir = temp_dir / "amazon" / "transaction_matches"
        amazon_dir.mkdir(parents=True)
        write_json(amazon_dir / "results.json", {"matches": []})

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is True
        assert any("No split edits" in r for r in reasons)

    def test_get_data_summary_no_matches(self, temp_dir, flow_context):
        """Test get_data_summary() with no matches."""
        node = SplitGenerationFlowNode(temp_dir)

        summary = node.get_data_summary(flow_context)

        assert summary.exists is False
        assert "No match results" in summary.summary_text

    def test_get_data_summary_with_matches(self, temp_dir, flow_context):
        """Test get_data_summary() with match files."""
        node = SplitGenerationFlowNode(temp_dir)

        # Create match files
        amazon_dir = temp_dir / "amazon" / "transaction_matches"
        amazon_dir.mkdir(parents=True)
        write_json(amazon_dir / "results.json", {"matches": []})

        apple_dir = temp_dir / "apple" / "transaction_matches"
        apple_dir.mkdir(parents=True)
        write_json(apple_dir / "results.json", {"matches": []})

        summary = node.get_data_summary(flow_context)

        assert summary.exists is True
        assert summary.item_count == 2  # 1 Amazon + 1 Apple
        assert "Match files available" in summary.summary_text


@pytest.mark.integration
@pytest.mark.ynab
class TestYnabSyncFlowNode:
    """Integration tests for YnabSyncFlowNode."""

    def test_check_changes_no_cache(self, temp_dir, flow_context):
        """Test check_changes() with no cache."""
        node = YnabSyncFlowNode(temp_dir)

        has_changes, reasons = node.check_changes(flow_context)

        # Should return True when no cache exists
        assert has_changes is True
        assert len(reasons) > 0  # Should have at least one reason

    def test_get_data_summary_no_cache(self, temp_dir, flow_context):
        """Test get_data_summary() with no cache."""
        node = YnabSyncFlowNode(temp_dir)

        summary = node.get_data_summary(flow_context)

        assert summary.exists is False
        assert "No YNAB cache" in summary.summary_text

    def test_get_data_summary_with_cache(self, temp_dir, flow_context):
        """Test get_data_summary() with cache."""
        node = YnabSyncFlowNode(temp_dir)

        # Create mock cache files
        cache_dir = temp_dir / "ynab" / "cache"
        cache_dir.mkdir(parents=True)
        write_json(cache_dir / "transactions.json", [{"id": "tx1"}, {"id": "tx2"}])
        write_json(cache_dir / "accounts.json", {"accounts": []})

        summary = node.get_data_summary(flow_context)

        assert summary.exists is True
        assert summary.item_count == 2  # 2 transactions
        assert "transactions" in summary.summary_text.lower()
