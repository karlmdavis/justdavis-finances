#!/usr/bin/env python3
"""Tests for core data models with Money and FinancialDate."""

from datetime import date

from finances.core import FinancialDate, Money, Receipt, Transaction


class TestTransaction:
    """Test Transaction model."""

    def test_transaction_construction(self):
        """Test Transaction with Money and FinancialDate."""
        tx = Transaction(
            id="test-1",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            amount_money=Money.from_cents(1234),
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.amount_money.to_cents() == 1234
        assert tx.date_obj.date == date(2024, 1, 15)

    def test_transaction_with_negative_amount(self):
        """Test Transaction with negative Money (expense)."""
        tx = Transaction(
            id="test-2",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            amount_money=Money.from_cents(-1234),
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.amount_money.to_cents() == -1234
        assert tx.date_obj.date == date(2024, 1, 15)

    def test_transaction_properties(self):
        """Test Transaction computed properties."""
        tx = Transaction(
            id="test-3",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            amount_money=Money.from_cents(1234),
            description="Test transaction",
            account_name="Checking",
        )
        assert tx.amount_cents == 1234
        assert tx.amount_dollars == "$12.34"
        assert tx.transaction_type.value == "income"


class TestReceipt:
    """Test Receipt model."""

    def test_receipt_construction(self):
        """Test Receipt with Money and FinancialDate."""
        receipt = Receipt(
            id="receipt-1",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            vendor="Test Vendor",
            total_money=Money.from_cents(1234),
            subtotal_money=Money.from_cents(1000),
            tax_money=Money.from_cents(234),
        )
        assert receipt.total_money.to_cents() == 1234
        assert receipt.subtotal_money.to_cents() == 1000
        assert receipt.tax_money.to_cents() == 234
        assert receipt.date_obj.date == date(2024, 1, 15)

    def test_receipt_without_optional_fields(self):
        """Test Receipt without subtotal/tax."""
        receipt = Receipt(
            id="receipt-2",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            vendor="Test Vendor",
            total_money=Money.from_cents(1234),
        )
        assert receipt.total_money.to_cents() == 1234
        assert receipt.subtotal_money is None
        assert receipt.tax_money is None
        assert receipt.date_obj.date == date(2024, 1, 15)

    def test_receipt_properties(self):
        """Test Receipt computed properties."""
        receipt = Receipt(
            id="receipt-3",
            date_obj=FinancialDate(date=date(2024, 1, 15)),
            vendor="Test Vendor",
            total_money=Money.from_cents(1234),
            subtotal_money=Money.from_cents(1000),
            tax_money=Money.from_cents(234),
        )
        assert receipt.item_count == 0  # No items
        assert receipt.total_dollars == "$12.34"
