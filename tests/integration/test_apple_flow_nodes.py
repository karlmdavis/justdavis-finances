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

    def test_execute_no_html_files(self, temp_dir, flow_context):
        """Test execute() with no HTML files."""
        node = AppleReceiptParsingFlowNode(temp_dir)

        # Create empty emails directory
        emails_dir = temp_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)

        result = node.execute(flow_context)

        assert result.success is True
        assert result.items_processed == 0

    def test_check_changes_no_emails(self, temp_dir, flow_context):
        """Test check_changes() with no emails."""
        node = AppleReceiptParsingFlowNode(temp_dir)

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is False
        assert any("No Apple emails" in r for r in reasons)

    def test_check_changes_no_exports(self, temp_dir, flow_context):
        """Test check_changes() with emails but no exports."""
        node = AppleReceiptParsingFlowNode(temp_dir)

        # Create email file
        emails_dir = temp_dir / "apple" / "emails"
        emails_dir.mkdir(parents=True)
        (emails_dir / "test.eml").write_text("Test email")

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is True
        assert any("No parsed receipts" in r for r in reasons)

    def test_get_data_summary_no_data(self, temp_dir, flow_context):
        """Test get_data_summary() with no data."""
        node = AppleReceiptParsingFlowNode(temp_dir)

        summary = node.get_data_summary(flow_context)

        assert summary.exists is False
        assert "No parsed Apple receipts" in summary.summary_text

    def test_get_data_summary_with_data(self, temp_dir, flow_context):
        """Test get_data_summary() with parsed receipts."""
        node = AppleReceiptParsingFlowNode(temp_dir)

        # Create mock parsed receipts
        exports_dir = temp_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)
        (exports_dir / "receipt1.json").write_text("{}")
        (exports_dir / "receipt2.json").write_text("{}")

        summary = node.get_data_summary(flow_context)

        assert summary.exists is True
        assert summary.item_count == 2
        assert "2 files" in summary.summary_text


@pytest.mark.integration
@pytest.mark.apple
class TestAppleMatchingFlowNode:
    """Integration tests for AppleMatchingFlowNode."""

    def test_execute_no_receipts(self, temp_dir, flow_context):
        """Test execute() with no receipts."""
        node = AppleMatchingFlowNode(temp_dir)

        # Create YNAB cache only
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        write_json(ynab_cache_dir / "transactions.json", [])

        result = node.execute(flow_context)

        # Should succeed gracefully with no work to do
        assert result.success is False or result.items_processed == 0

    def test_execute_no_apple_transactions(self, temp_dir, flow_context):
        """Test execute() when YNAB has no Apple transactions."""
        node = AppleMatchingFlowNode(temp_dir)

        # Create receipt
        exports_dir = temp_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)
        write_json(exports_dir / "receipt1.json", {"id": "ML7", "total": 100})

        # Create YNAB cache with non-Apple transactions
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        write_json(
            ynab_cache_dir / "transactions.json",
            [{"id": "tx123", "payee_name": "Walmart"}],
        )

        result = node.execute(flow_context)

        assert result.success is True
        assert result.items_processed == 0

    def test_check_changes_no_data(self, temp_dir, flow_context):
        """Test check_changes() with no data."""
        node = AppleMatchingFlowNode(temp_dir)

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is False
        assert any("No parsed Apple receipts" in r for r in reasons)

    def test_check_changes_no_ynab_cache(self, temp_dir, flow_context):
        """Test check_changes() with no YNAB cache."""
        node = AppleMatchingFlowNode(temp_dir)

        # Create receipts only
        exports_dir = temp_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)
        write_json(exports_dir / "receipt1.json", {})

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is False
        assert any("No YNAB cache" in r for r in reasons)

    def test_check_changes_no_previous_matches(self, temp_dir, flow_context):
        """Test check_changes() with no previous matches."""
        node = AppleMatchingFlowNode(temp_dir)

        # Create receipts
        exports_dir = temp_dir / "apple" / "exports"
        exports_dir.mkdir(parents=True)
        write_json(exports_dir / "receipt1.json", {})

        # Create YNAB cache
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        write_json(ynab_cache_dir / "transactions.json", [])

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is True
        assert any("No previous matching" in r for r in reasons)

    def test_get_data_summary_no_matches(self, temp_dir, flow_context):
        """Test get_data_summary() with no matches."""
        node = AppleMatchingFlowNode(temp_dir)

        summary = node.get_data_summary(flow_context)

        assert summary.exists is False
        assert "No Apple matches" in summary.summary_text

    def test_get_data_summary_with_matches(self, temp_dir, flow_context):
        """Test get_data_summary() with match results."""
        node = AppleMatchingFlowNode(temp_dir)

        # Create mock match results
        matches_dir = temp_dir / "apple" / "transaction_matches"
        matches_dir.mkdir(parents=True)
        write_json(
            matches_dir / "2025-01-01_results.json",
            {
                "metadata": {},
                "matches": [{"transaction_id": "tx1"}, {"transaction_id": "tx2"}],
            },
        )

        summary = node.get_data_summary(flow_context)

        assert summary.exists is True
        assert summary.item_count == 2
        assert "2 transactions" in summary.summary_text
