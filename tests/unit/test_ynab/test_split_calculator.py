#!/usr/bin/env python3
"""Tests for YNAB split calculation module."""

import pytest

from finances.amazon.models import MatchedOrderItem
from finances.apple.parser import ParsedItem, ParsedReceipt
from finances.core.dates import FinancialDate
from finances.core.money import Money
from finances.ynab import (
    SplitCalculationError,
    YnabSplit,
    YnabTransaction,
    calculate_amazon_splits,
    calculate_apple_splits,
    calculate_generic_splits,
    create_split_summary,
    sort_splits_for_stability,
    validate_split_calculation,
)


class TestAmazonSplitCalculationDomainModels:
    """Test Amazon split calculation with domain models (new signatures)."""

    @pytest.mark.ynab
    def test_amazon_splits_with_domain_models(self):
        """Test calculate_amazon_splits accepts MatchedOrderItem list and returns YnabSplit list."""
        # Create transaction
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -89900,  # $89.90 expense
        })

        # Create MatchedOrderItem (match-layer domain models)
        items = [
            MatchedOrderItem(
                name="Echo Dot (4th Gen)",
                amount=Money.from_cents(4599),
                quantity=1,
                asin="B0AAAAAA1",
                unit_price=Money.from_cents(4599),
            ),
            MatchedOrderItem(
                name="USB-C Cable 6ft - 2 Pack",
                amount=Money.from_cents(2350),
                quantity=2,
                asin="B0AAAAAA2",
                unit_price=Money.from_cents(1175),
            ),
            MatchedOrderItem(
                name="Charging Stand",
                amount=Money.from_cents(2041),
                quantity=1,
                asin="B0AAAAAA3",
                unit_price=Money.from_cents(2041),
            ),
        ]

        # Call with new signature
        splits = calculate_amazon_splits(transaction, items)

        # Should return list of YnabSplit
        assert isinstance(splits, list)
        assert len(splits) == 3
        assert all(isinstance(s, YnabSplit) for s in splits)

        # Check split amounts and memos
        assert splits[0].amount.to_milliunits() == -45990
        assert splits[0].memo == "Echo Dot (4th Gen)"
        assert splits[1].amount.to_milliunits() == -23500
        assert splits[1].memo == "USB-C Cable 6ft - 2 Pack (qty: 2)"
        assert splits[2].amount.to_milliunits() == -20410
        assert splits[2].memo == "Charging Stand"

    @pytest.mark.ynab
    def test_amazon_splits_domain_models_validation(self):
        """Test split validation with domain models."""
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -50000,  # $50.00
        })

        # Items that don't sum to transaction amount
        items = [
            MatchedOrderItem(
                name="Test Item",
                amount=Money.from_cents(3000),  # Only $30.00
                quantity=1,
                asin="B0AAAAAA1",
                unit_price=Money.from_cents(3000),
            ),
        ]

        with pytest.raises(SplitCalculationError, match="doesn't match transaction"):
            calculate_amazon_splits(transaction, items)


class TestAppleSplitCalculation:
    """Test Apple transaction split calculation."""

    @pytest.mark.ynab
    def test_single_app_purchase(self):
        """Test single app purchase."""
        transaction_amount = -29990  # $29.99 in milliunits
        # Transform Apple receipt format to what split calculator expects
        items = [{"name": "Procreate", "price": 2999}]  # $29.99 in cents

        splits = calculate_apple_splits(transaction_amount, items)

        assert len(splits) == 1
        assert splits[0]["amount"] == transaction_amount
        assert "Procreate" in splits[0]["memo"]
        # Memo should contain the item title
        assert splits[0]["memo"] == "Procreate"

    @pytest.mark.ynab
    def test_multiple_app_purchases(self):
        """Test multiple app purchases with different costs."""
        transaction_amount = -599960  # $599.96 in milliunits (299.99+199.99+49.99+49.99)
        # Transform Apple receipt format to what split calculator expects
        items = [
            {"name": "Final Cut Pro", "price": 29999},  # $299.99 in cents
            {"name": "Logic Pro", "price": 19999},  # $199.99 in cents
            {"name": "Compressor", "price": 4999},  # $49.99 in cents
            {"name": "Motion", "price": 4999},  # $49.99 in cents
        ]

        splits = calculate_apple_splits(transaction_amount, items)

        assert len(splits) == 4

        # Check amounts match costs (converted to negative milliunits)
        expected_amounts = [-299990, -199990, -49990, -49990]  # Correct milliunits
        actual_amounts = [split["amount"] for split in splits]
        assert actual_amounts == expected_amounts

    @pytest.mark.ynab
    def test_subscription_handling(self):
        """Test handling of subscription renewals."""
        transaction_amount = -9990  # $9.99 in milliunits
        # Transform Apple receipt format to what split calculator expects
        items = [{"name": "Apple Music (Monthly)", "price": 999}]  # $9.99 in cents

        splits = calculate_apple_splits(transaction_amount, items)

        assert len(splits) == 1
        assert "subscription" in splits[0]["memo"].lower() or "monthly" in splits[0]["memo"].lower()


class TestAppleSplitCalculationDomainModels:
    """Test Apple split calculation with domain models (new signatures)."""

    @pytest.mark.ynab
    def test_apple_splits_with_domain_models(self):
        """Test calculate_apple_splits accepts ParsedReceipt and returns YnabSplit list."""
        # Create transaction
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -599960,  # $599.96 total in milliunits
        })

        # Create ParsedReceipt with multiple items
        receipt = ParsedReceipt(
            format_detected="modern",
            apple_id="test@example.com",
            receipt_date=FinancialDate.from_string("2024-10-15"),
            order_id="ORDER123",
            document_number="DOC123",
            subtotal=Money.from_cents(56407),  # Subtotal before tax
            tax=Money.from_cents(3589),  # Tax amount
            total=Money.from_cents(59996),  # Total
            currency="USD",
            payment_method=None,
            billed_to=None,
            items=[
                ParsedItem(
                    title="Final Cut Pro",
                    cost=Money.from_cents(29999),
                    quantity=1,
                    subscription=False,
                ),
                ParsedItem(
                    title="Logic Pro",
                    cost=Money.from_cents(19999),
                    quantity=1,
                    subscription=False,
                ),
                ParsedItem(
                    title="Compressor",
                    cost=Money.from_cents(4999),
                    quantity=1,
                    subscription=False,
                ),
                ParsedItem(
                    title="Motion",
                    cost=Money.from_cents(1410),
                    quantity=1,
                    subscription=False,
                ),
            ],
            parsing_metadata={},
            base_name="test_receipt",
        )

        # Call with new signature
        splits = calculate_apple_splits(transaction, receipt)

        # Should return list of YnabSplit
        assert isinstance(splits, list)
        assert len(splits) == 4
        assert all(isinstance(s, YnabSplit) for s in splits)

        # Check that splits have proper memos
        assert splits[0].memo == "Final Cut Pro"
        assert splits[1].memo == "Logic Pro"
        assert splits[2].memo == "Compressor"
        assert splits[3].memo == "Motion"

        # Verify total matches transaction
        total_milliunits = sum(s.amount.to_milliunits() for s in splits)
        assert total_milliunits == transaction.amount.to_milliunits()

    @pytest.mark.ynab
    def test_apple_splits_domain_models_with_tax(self):
        """Test Apple splits with tax allocation."""
        # Create transaction
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -108000,  # $108.00 total with tax in milliunits
        })

        # Receipt with subtotal and tax
        receipt = ParsedReceipt(
            format_detected="modern",
            apple_id="test@example.com",
            receipt_date=FinancialDate.from_string("2024-10-15"),
            order_id="ORDER123",
            document_number="DOC123",
            subtotal=Money.from_cents(10000),  # $100.00 subtotal
            tax=Money.from_cents(800),  # $8.00 tax (8%)
            total=Money.from_cents(10800),  # $108.00 total
            currency="USD",
            payment_method=None,
            billed_to=None,
            items=[
                ParsedItem(
                    title="App 1",
                    cost=Money.from_cents(5000),
                    quantity=1,
                    subscription=False,
                ),
                ParsedItem(
                    title="App 2",
                    cost=Money.from_cents(5000),
                    quantity=1,
                    subscription=False,
                ),
            ],
            parsing_metadata={},
            base_name="test_receipt",
        )

        # Call with new signature
        splits = calculate_apple_splits(transaction, receipt)

        # Tax should be allocated proportionally
        assert len(splits) == 2
        # Each app should get half the tax: $50.00 + $4.00 = $54.00
        assert splits[0].amount.to_cents() == -5400
        assert splits[1].amount.to_cents() == -5400

        # Verify total
        total_milliunits = sum(s.amount.to_milliunits() for s in splits)
        assert total_milliunits == transaction.amount.to_milliunits()


class TestGenericSplitCalculation:
    """Test generic split calculation for other vendors."""

    @pytest.mark.ynab
    def test_even_split(self):
        """Test even split across categories."""
        transaction_amount = -60000  # $60.00 in milliunits
        items = [
            {"name": "Groceries", "amount": 2000},  # $20.00 in cents
            {"name": "Household", "amount": 2000},  # $20.00 in cents
            {"name": "Personal Care", "amount": 2000},  # $20.00 in cents
        ]

        splits = calculate_generic_splits(transaction_amount, items)

        assert len(splits) == 3
        # Should split evenly: $20.00 each in milliunits
        for split in splits:
            assert split["amount"] == -20000

        total = sum(split["amount"] for split in splits)
        assert total == transaction_amount

    @pytest.mark.ynab
    def test_weighted_split(self):
        """Test weighted split with custom amounts."""
        transaction_amount = -100000  # $100.00 in milliunits
        items = [
            {"name": "Groceries", "amount": 6000},  # $60.00 in cents
            {"name": "Household", "amount": 2500},  # $25.00 in cents
            {"name": "Personal Care", "amount": 1500},  # $15.00 in cents
        ]

        splits = calculate_generic_splits(transaction_amount, items)

        assert len(splits) == 3
        assert splits[0]["amount"] == -60000  # $60.00 in milliunits
        assert splits[1]["amount"] == -25000  # $25.00 in milliunits
        assert splits[2]["amount"] == -15000  # $15.00 in milliunits

        total = sum(split["amount"] for split in splits)
        assert total == transaction_amount


class TestSplitValidation:
    """Test split calculation validation."""

    @pytest.mark.ynab
    def test_validate_split_calculation(self):
        """Test split validation function."""
        splits = [
            {"amount": -20000, "memo": "Item 1"},  # $20.00 in milliunits
            {"amount": -30000, "memo": "Item 2"},  # $30.00 in milliunits
        ]

        # Valid split
        is_valid, _ = validate_split_calculation(splits, -50000)
        assert is_valid is True

        # Invalid split (doesn't sum to total)
        is_valid, _ = validate_split_calculation(splits, -60000)
        assert is_valid is False

        # With tolerance
        is_valid, _ = validate_split_calculation(splits, -50050, tolerance=100)
        assert is_valid is True

    @pytest.mark.ynab
    def test_split_sorting(self):
        """Test split sorting for consistent order."""
        splits = [
            {"amount": -10000, "memo": "B Item"},  # $10.00 in milliunits
            {"amount": -30000, "memo": "A Item"},  # $30.00 in milliunits
            {"amount": -20000, "memo": "C Item"},  # $20.00 in milliunits
        ]

        sorted_splits = sort_splits_for_stability(splits)

        # Should be sorted by amount (descending absolute value)
        amounts = [split["amount"] for split in sorted_splits]
        assert amounts == [-30000, -20000, -10000]

    @pytest.mark.ynab
    def test_split_summary(self):
        """Test split summary generation."""
        splits = [
            {"amount": -20000, "memo": "Item 1", "category": "Shopping"},  # $20.00 in milliunits
            {"amount": -30000, "memo": "Item 2", "category": "Electronics"},  # $30.00 in milliunits
        ]

        summary = create_split_summary(splits)

        assert summary["total_amount"] == -50000
        assert summary["split_count"] == 2
