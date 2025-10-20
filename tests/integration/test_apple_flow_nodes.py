#!/usr/bin/env python3
"""
Integration tests for Apple FlowNode implementations.

Tests FlowNode orchestration logic with real filesystem operations.
"""

from datetime import datetime

import pytest

from finances.apple.flow import AppleMatchingFlowNode, AppleReceiptParsingFlowNode
from finances.core.flow import FlowContext
from finances.core.json_utils import write_json


@pytest.fixture
def flow_context():
    """Create basic FlowContext for testing."""
    return FlowContext(start_time=datetime.now())


@pytest.mark.integration
@pytest.mark.apple
class TestAppleReceiptParsingFlowNode:
    """Integration tests for AppleReceiptParsingFlowNode."""

    def test_execute_with_html_files(self, temp_dir, flow_context):
        """Test execute() with HTML email files."""
        node = AppleReceiptParsingFlowNode(temp_dir)

        # Create mock HTML emails
        emails_dir = temp_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)
        html_file = emails_dir / "receipt_001.html"
        html_file.write_text(
            """
            <html><body>
            <div>Order ID: ML7PQ2XYZ</div>
            <div>Order Date: Aug 15, 2024</div>
            <div>Total: $32.97</div>
            <div>Item: Test App - $29.99</div>
            </body></html>
        """
        )

        # Execute
        result = node.execute(flow_context)

        # Verify
        assert result.success is True
        assert result.items_processed == 1
        exports_dir = temp_dir / "apple" / "exports"
        assert exports_dir.exists()
        # File should be named by order_id (ML7PQ2XYZ), not email filename (receipt_001)
        assert (exports_dir / "ML7PQ2XYZ.json").exists()

    # test_execute_no_html_files removed - covered by parameterized test_flownode_interface.py


@pytest.mark.integration
@pytest.mark.apple
class TestAppleMatchingFlowNode:
    """Integration tests for AppleMatchingFlowNode."""

    # Removed tests covered by parameterized test_flownode_interface.py:
    # - test_execute_no_receipts (missing input data handling)
    # - test_execute_no_apple_transactions (no matching transactions scenario)
    # - test_check_changes_no_ynab_cache (missing dependency handling)
