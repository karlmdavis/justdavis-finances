#!/usr/bin/env python3
"""
Integration tests for YNAB FlowNode implementations.

Tests FlowNode orchestration logic with real filesystem operations.
"""

from datetime import datetime

import pytest

from finances.core.flow import FlowContext
from finances.core.json_utils import write_json
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
                            "amount": -29990,  # milliunits (negative for expense) = -$29.99
                            "date": "2025-01-01",
                        },
                        "best_match": {
                            "amazon_orders": [
                                {
                                    "items": [
                                        {
                                            "name": "Test Item 1",
                                            "amount": 1999,  # cents
                                            "quantity": 1,
                                            "asin": "B0123456",
                                            "unit_price": 1999,
                                        },
                                        {
                                            "name": "Test Item 2",
                                            "amount": 1000,  # cents
                                            "quantity": 1,
                                            "asin": "B0123457",
                                            "unit_price": 1000,
                                        },
                                    ]
                                }
                            ]
                        },
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

    # test_execute_no_matches removed - covered by parameterized test_flownode_interface.py


@pytest.mark.integration
@pytest.mark.ynab
class TestYnabSyncFlowNode:
    """Integration tests for YnabSyncFlowNode."""

    # test_check_changes_no_cache removed - covered by parameterized test_flownode_interface.py
