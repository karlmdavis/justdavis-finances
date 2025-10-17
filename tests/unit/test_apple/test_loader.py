#!/usr/bin/env python3
"""
Unit tests for Apple receipt loader.

Tests the load_apple_receipts function to ensure it returns ParsedReceipt domain models
instead of raw dictionaries.
"""

import json
import tempfile
from pathlib import Path

import pytest

from finances.apple.loader import load_apple_receipts
from finances.apple.parser import ParsedReceipt
from finances.core.dates import FinancialDate
from finances.core.money import Money


class TestAppleReceiptLoader:
    """Test Apple receipt loader returns domain models."""

    @pytest.fixture
    def temp_export_dir(self):
        """Create a temporary export directory with test receipt data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir)

            # Create test receipt data (as currently stored in JSON files)
            test_receipts = [
                {
                    "format_detected": "modern_custom",
                    "apple_id": "test@example.com",
                    "receipt_date": "2024-10-15",
                    "order_id": "M123456789",
                    "document_number": "DOC001",
                    "subtotal": 2999,  # $29.99 in cents
                    "tax": 300,  # $3.00 in cents
                    "total": 3299,  # $32.99 in cents
                    "currency": "USD",
                    "payment_method": "Visa ending in 1234",
                    "items": [
                        {
                            "title": "Procreate",
                            "cost": 2999,  # $29.99 in cents
                            "quantity": 1,
                            "subscription": False,
                        }
                    ],
                    "base_name": "test_receipt_001",
                },
                {
                    "format_detected": "legacy_aapl",
                    "apple_id": "user2@example.com",
                    "receipt_date": "2024-10-14",
                    "order_id": "M987654321",
                    "subtotal": 999,  # $9.99 in cents
                    "tax": 100,  # $1.00 in cents
                    "total": 1099,  # $10.99 in cents
                    "currency": "USD",
                    "items": [
                        {
                            "title": "Apple Music (Monthly)",
                            "cost": 999,  # $9.99 in cents
                            "quantity": 1,
                            "subscription": True,
                        }
                    ],
                    "base_name": "test_receipt_002",
                },
            ]

            # Write test receipts as individual JSON files (matches actual system behavior)
            for receipt in test_receipts:
                receipt_file = export_path / f"{receipt['order_id']}.json"
                with open(receipt_file, "w") as f:
                    json.dump(receipt, f, indent=2)

            yield str(export_path)

    @pytest.mark.apple
    def test_load_apple_receipts_returns_domain_models(self, temp_export_dir):
        """
        Test that load_apple_receipts returns ParsedReceipt domain models.

        This is the RED test - it will fail because load_apple_receipts
        currently returns list[dict] instead of list[ParsedReceipt].
        """
        # Act
        receipts = load_apple_receipts(temp_export_dir)

        # Assert - Check return type
        assert isinstance(receipts, list), "Should return a list"
        assert len(receipts) == 2, "Should load both test receipts"
        assert all(
            isinstance(r, ParsedReceipt) for r in receipts
        ), "All items should be ParsedReceipt instances, not dicts"

    @pytest.mark.apple
    def test_loaded_receipts_have_typed_fields(self, temp_export_dir):
        """
        Test that loaded receipts have properly typed domain model fields.

        Verifies Money and FinancialDate types are correctly set.
        """
        # Act
        receipts = load_apple_receipts(temp_export_dir)

        # Assert - Check receipts have proper types (order-independent)
        # Find the M123456789 receipt (glob may return files in any order)
        receipt_m123 = next((r for r in receipts if r.order_id == "M123456789"), None)
        assert receipt_m123 is not None, "Should load M123456789 receipt"

        assert isinstance(receipt_m123.total, Money), "total should be Money type"
        assert isinstance(
            receipt_m123.receipt_date, FinancialDate
        ), "receipt_date should be FinancialDate type"
        assert receipt_m123.total.to_cents() == 3299, "Should correctly parse $32.99"
        assert receipt_m123.receipt_date.to_iso_string() == "2024-10-15", "Should correctly parse date"

    @pytest.mark.apple
    def test_loaded_receipts_preserve_all_fields(self, temp_export_dir):
        """Test that all receipt fields are preserved during loading."""
        # Act
        receipts = load_apple_receipts(temp_export_dir)

        # Assert - Check all fields present (order-independent)
        # Find the M123456789 receipt
        receipt_m123 = next((r for r in receipts if r.order_id == "M123456789"), None)
        assert receipt_m123 is not None, "Should load M123456789 receipt"

        assert receipt_m123.order_id == "M123456789"
        assert receipt_m123.apple_id == "test@example.com"
        assert receipt_m123.format_detected == "modern_custom"
        assert receipt_m123.document_number == "DOC001"
        assert receipt_m123.subtotal.to_cents() == 2999
        assert receipt_m123.tax.to_cents() == 300
        assert len(receipt_m123.items) == 1
        assert receipt_m123.items[0].title == "Procreate"
        assert receipt_m123.items[0].cost.to_cents() == 2999
