#!/usr/bin/env python3
"""
Integration tests for Apple FlowNode implementations.

Tests FlowNode orchestration logic with real filesystem operations.
"""

from datetime import datetime
from pathlib import Path

import pytest

from finances.apple.flow import AppleReceiptParsingFlowNode
from finances.core.flow import FlowContext


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

        # Create mock HTML emails using valid fixture
        emails_dir = temp_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)

        # Copy table_format_receipt.html fixture (has Order ID: ML7PQ2XYZ)
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "apple"
        fixture_html = fixtures_dir / "table_format_receipt.html"

        with open(fixture_html, encoding="utf-8") as f:
            html_content = f.read()

        html_file = emails_dir / "receipt_001.html"
        html_file.write_text(html_content)

        # Execute
        result = node.execute(flow_context)

        # Verify
        assert result.success is True
        assert result.items_processed == 1
        exports_dir = temp_dir / "apple" / "exports"
        assert exports_dir.exists()
        # File should be named by HTML filename stem (receipt_001), not order_id
        # This prevents collisions when multiple receipts have the same order_id
        assert (exports_dir / "receipt_001.json").exists()

    # test_execute_no_html_files removed - covered by parameterized test_flownode_interface.py


@pytest.mark.integration
@pytest.mark.apple
class TestAppleMatchingFlowNode:
    """Integration tests for AppleMatchingFlowNode."""

    # Removed tests covered by parameterized test_flownode_interface.py:
    # - test_execute_no_receipts (missing input data handling)
    # - test_execute_no_apple_transactions (no matching transactions scenario)
    # - test_check_changes_no_ynab_cache (missing dependency handling)
