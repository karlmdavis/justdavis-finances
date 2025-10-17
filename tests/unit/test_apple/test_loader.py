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

            # Write test receipts to JSON file
            receipts_file = export_path / "all_receipts_combined.json"
            with open(receipts_file, "w") as f:
                json.dump(test_receipts, f, indent=2)

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
        assert all(isinstance(r, ParsedReceipt) for r in receipts), (
            "All items should be ParsedReceipt instances, not dicts"
        )

    @pytest.mark.apple
    def test_loaded_receipts_have_typed_fields(self, temp_export_dir):
        """
        Test that loaded receipts have properly typed domain model fields.

        Verifies Money and FinancialDate types are correctly set.
        """
        # Act
        receipts = load_apple_receipts(temp_export_dir)

        # Assert - Check first receipt has proper types
        first_receipt = receipts[0]
        assert isinstance(first_receipt.total, Money), "total should be Money type"
        assert isinstance(first_receipt.receipt_date, FinancialDate), (
            "receipt_date should be FinancialDate type"
        )
        assert first_receipt.total.to_cents() == 3299, "Should correctly parse $32.99"
        assert first_receipt.receipt_date.to_iso_string() == "2024-10-15", (
            "Should correctly parse date"
        )

    @pytest.mark.apple
    def test_loaded_receipts_preserve_all_fields(self, temp_export_dir):
        """Test that all receipt fields are preserved during loading."""
        # Act
        receipts = load_apple_receipts(temp_export_dir)

        # Assert - Check all fields present
        first_receipt = receipts[0]
        assert first_receipt.order_id == "M123456789"
        assert first_receipt.apple_id == "test@example.com"
        assert first_receipt.format_detected == "modern_custom"
        assert first_receipt.document_number == "DOC001"
        assert first_receipt.subtotal.to_cents() == 2999
        assert first_receipt.tax.to_cents() == 300
        assert len(first_receipt.items) == 1
        assert first_receipt.items[0].title == "Procreate"
        assert first_receipt.items[0].cost.to_cents() == 2999
